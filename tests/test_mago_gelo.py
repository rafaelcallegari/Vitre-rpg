# tests/test_mago_gelo.py
# Step 2b, commit 1: Prisão de Cristal (skill) e Inverno Constante (passiva)
# do Mago de Gelo. Ver decisoes.md § Step 2b.
import bot
import combate
import condicoes
import database as db
import game_data
import habilidades as hab

CHEFE_TESTE = {"nome": "Testinho", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0}


def _combatente(user_id, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


def _sem_variancia(monkeypatch):
    monkeypatch.setattr(combate.random, "uniform", lambda a, b: 1.0)
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita, nunca condiciona a arma


def _sobrevive_n_ticks_e_expira_no_seguinte(luta, nome, n):
    """Mesma técnica de tests/test_condicoes.py (bloco 4, contrato N+1) --
    confirma a duração CONTANDO TICKS, não lendo cond['duracao']."""
    for i in range(n):
        condicoes.tick(luta)
        assert any(c["nome"] == nome for c in luta.condicoes), f"'{nome}' sumiu cedo demais, tick {i + 1}/{n}"
    condicoes.tick(luta)
    assert not any(c["nome"] == nome for c in luta.condicoes), f"'{nome}' deveria ter expirado no tick {n + 1}"


# ==================================================================
# Gate de ascensão
# ==================================================================

def test_nao_ascendido_nao_conhece_prisao_de_cristal():
    j = _combatente(1, classe="mago", inteligencia=20).jogador
    assert "prisao_de_cristal" not in hab.conhecidas(j)


def test_mago_gelo_conhece_prisao_de_cristal():
    j = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_gelo").jogador
    assert "prisao_de_cristal" in hab.conhecidas(j)


def test_prisao_de_cristal_nao_tem_requisito_de_atributo():
    """A ascensão É o requisito -- ver decisoes.md § Step 2a."""
    assert "requisito" not in game_data.HABILIDADES["prisao_de_cristal"]


# ==================================================================
# Dano -- passa por at.aplicar_defesa (ao contrário do Dardo Arcano)
# ==================================================================

def test_prisao_de_cristal_aplica_a_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_gelo")
    dados = game_data.HABILIDADES["prisao_de_cristal"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    combate._efeito_prisao_de_cristal(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    luta_com_def = combate.Luta([c], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_prisao_de_cristal(luta_com_def, c, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def < dano_sem_def


# ==================================================================
# Travamento -- duração contada em ticks (regra N+1), Inverno Constante
# soma 1 rodada extra pra quem aplica
# ==================================================================

def test_prisao_de_cristal_trava_o_chefe_por_2_rodadas_com_inverno_constante(monkeypatch):
    """mago_gelo tem uma passiva só (Inverno Constante) e ela é automática
    -- não existe estado "mago_gelo sem a passiva" pra testar à parte. O
    "sem a passiva" dos dois testes abaixo (outro ramo / sem ascensão)."""
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_gelo")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    combate._efeito_prisao_de_cristal(luta, c, game_data.HABILIDADES["prisao_de_cristal"])

    assert any(cc["tipo"] == "pula_turno" and cc["nome"] == "Travamento" for cc in luta.condicoes)
    _sobrevive_n_ticks_e_expira_no_seguinte(luta, "Travamento", 2)


def test_mago_nao_gelo_ficaria_travado_por_1_rodada_se_pudesse_lancar():
    """Prisão de Cristal é exclusiva do mago_gelo (gate testado acima) --
    este teste só confirma que a MECÂNICA em si (sem a passiva de outro
    ramo) não estica a duração sozinha. Chamar o efeito direto (sem passar
    pelo gate) é o mesmo padrão dos outros testes de _efeito_* já na
    suíte."""
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_fogo")   # outro ramo, sem Inverno Constante
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    combate._efeito_prisao_de_cristal(luta, c, game_data.HABILIDADES["prisao_de_cristal"])

    _sobrevive_n_ticks_e_expira_no_seguinte(luta, "Travamento", 1)


def test_jogador_sem_ascensao_travamento_da_skill_dura_1_rodada():
    c = _combatente(1, classe="mago", inteligencia=20)   # sem ascensão
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    combate._efeito_prisao_de_cristal(luta, c, game_data.HABILIDADES["prisao_de_cristal"])

    _sobrevive_n_ticks_e_expira_no_seguinte(luta, "Travamento", 1)


# ==================================================================
# Inverno Constante também vale pro Travamento da ARMA elemental (gelo) --
# "um mago de gelo com cajado de gelo é o caso que mais importa acertar"
# ==================================================================

def test_travamento_da_arma_elemental_dura_1_rodada_sem_a_passiva(monkeypatch):
    """Timing diferente da skill: a arma elemental aplica DEPOIS do tick()
    da própria rodada (dentro do loop de ataques, ver _talvez_condicionar_
    chefe), então o Travamento já está pronto pro turno_do_chefe desta
    MESMA rodada sem precisar de nenhum tick antes -- só o tick da rodada
    SEGUINTE o consome. `_sobrevive_n_ticks_e_expira_no_seguinte` (regra
    N+1) não serve aqui, é pro timing de skill (aplicada ANTES do tick)."""
    c = _combatente(1, classe="mago", inteligencia=20, arma="cajado_gelo")   # sem ascensão
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)   # garante o proc da arma
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    combate._talvez_condicionar_chefe(luta, c)

    assert any(cc["nome"] == "Travamento" for cc in luta.condicoes)   # travado nesta rodada
    condicoes.tick(luta)   # rodada seguinte
    assert not any(cc["nome"] == "Travamento" for cc in luta.condicoes)   # já destravou


def test_travamento_da_arma_elemental_com_inverno_constante_dura_2_rodadas(monkeypatch):
    c = _combatente(1, classe="mago", inteligencia=20, arma="cajado_gelo", ascensao="mago_gelo")
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)   # garante o proc da arma
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    combate._talvez_condicionar_chefe(luta, c)

    assert any(cc["nome"] == "Travamento" for cc in luta.condicoes)   # rodada em que aplicou
    condicoes.tick(luta)
    assert any(cc["nome"] == "Travamento" for cc in luta.condicoes)   # rodada seguinte -- ainda travado (bônus)
    condicoes.tick(luta)
    assert not any(cc["nome"] == "Travamento" for cc in luta.condicoes)   # aí sim destrava


def test_refresh_da_arma_elemental_nunca_encolhe_um_travamento_mais_longo(monkeypatch):
    """A skill (Prisão de Cristal, com Inverno Constante) trava por 2
    rodadas (duracao guardada = 3, regra N+1). Se o MESMO golpe também
    rolar o proc da arma elemental (cajado de gelo), o refresh não pode
    sobrescrever com o valor cru da arma (1 rodada, duracao guardada = 1)
    -- ver o max() em _talvez_condicionar_chefe."""
    _sem_variancia(monkeypatch)   # random()=1.0 nunca crita, mas TAMBÉM nunca proca a arma sozinho
    c = _combatente(1, classe="mago", inteligencia=20, arma="cajado_gelo", ascensao="mago_gelo")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    combate._efeito_prisao_de_cristal(luta, c, game_data.HABILIDADES["prisao_de_cristal"])
    travamento = next(cc for cc in luta.condicoes if cc["nome"] == "Travamento")
    assert travamento["duracao"] == 3   # 1 (N) + 1 (regra) + 1 (Inverno Constante)

    # agora força o refresh da arma como se tivesse procado -- não pode encolher
    luta.elementos_aplicados_rodada.discard("gelo")   # simula um novo golpe na mesma rodada
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)   # garante o proc desta vez
    combate._talvez_condicionar_chefe(luta, c)

    travamento_depois = next(cc for cc in luta.condicoes if cc["nome"] == "Travamento")
    assert travamento_depois["duracao"] == 3   # não encolheu pra 2 (1 base + 1 da passiva)
