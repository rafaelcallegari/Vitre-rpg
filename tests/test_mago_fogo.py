# tests/test_mago_fogo.py
# Step 2b, commit 2: Conflagração (skill) e Combustão (passiva) do Mago de
# Fogo. Combustão faz a Brasa empilhar -- mesma lógica de Sangramento em
# combate._efeito_golpe_aberto, já testada em tests/test_condicoes.py (não
# reimplementada aqui, só referenciada); os testes abaixo provam a parte
# NOVA: que Brasa participa dessa lógica só com a passiva, e continua
# refrescando (comportamento de sempre) sem ela. Ver decisoes.md § Step 2b.
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
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita, nunca proca a arma sozinho


def _stacks_brasa(luta):
    return [cc for cc in luta.condicoes if cc["nome"] == "Brasa" and cc["alvo"] == "chefe"]


def _semear_brasa(luta, n):
    for _ in range(n):
        condicoes.aplicar(luta, "chefe", "dano_por_rodada", "Brasa", "🔥", duracao=3, valor=0.03)


# ==================================================================
# Gate de ascensão
# ==================================================================

def test_nao_ascendido_nao_conhece_conflagracao():
    j = _combatente(1, classe="mago", inteligencia=20).jogador
    assert "conflagracao" not in hab.conhecidas(j)


def test_mago_fogo_conhece_conflagracao():
    j = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_fogo").jogador
    assert "conflagracao" in hab.conhecidas(j)


def test_conflagracao_nao_tem_requisito_de_atributo():
    """A ascensão É o requisito -- ver decisoes.md § Step 2a."""
    assert "requisito" not in game_data.HABILIDADES["conflagracao"]


# ==================================================================
# Dano -- passa por at.aplicar_defesa (ver decisoes.md § Step 2b) e cresce
# com a Brasa já acumulada no alvo
# ==================================================================

def test_conflagracao_aplica_a_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_fogo")
    dados = game_data.HABILIDADES["conflagracao"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    combate._efeito_conflagracao(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    c2 = _combatente(2, classe="mago", inteligencia=20, ascensao="mago_fogo")
    luta_com_def = combate.Luta([c2], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_conflagracao(luta_com_def, c2, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def < dano_sem_def


def test_conflagracao_com_3_stacks_de_brasa_vale_2_75x_a_base(monkeypatch):
    """MULTIPLICADOR_CONFLAGRACAO (2.0) + BONUS_CONFLAGRACAO_POR_STACK
    (0.25) * 3 stacks já acumulados = 2.75 -- conta as pilhas ANTES de
    aplicar a própria."""
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_fogo")
    dados = game_data.HABILIDADES["conflagracao"]
    chefe_sem_def = {**CHEFE_TESTE, "def": 0}

    luta_0_stacks = combate.Luta([c], chefe_sem_def, andar_num=1)
    combate._efeito_conflagracao(luta_0_stacks, c, dados)
    dano_0_stacks = luta_0_stacks.hp_chefe_max - luta_0_stacks.hp_chefe

    c2 = _combatente(2, classe="mago", inteligencia=20, ascensao="mago_fogo")
    luta_3_stacks = combate.Luta([c2], chefe_sem_def, andar_num=1)
    _semear_brasa(luta_3_stacks, 3)
    combate._efeito_conflagracao(luta_3_stacks, c2, dados)
    dano_3_stacks = luta_3_stacks.hp_chefe_max - luta_3_stacks.hp_chefe

    base = hab.poder_base(c.jogador, combate._bonus_arma_de(c)) * combate._multiplicador_afinidade(c)
    assert dano_0_stacks == max(1, int(base * 2.0))
    assert dano_3_stacks == max(1, int(base * 2.75))


# ==================================================================
# Combustão -- Brasa empilha até MAX_STACKS_BRASA (3) só com a passiva;
# sem ela, continua refrescando (comportamento de sempre)
# ==================================================================

def test_combustao_empilha_brasa_ate_3_e_renova_a_mais_antiga_no_4o_uso(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_fogo")
    dados = game_data.HABILIDADES["conflagracao"]
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    for _ in range(3):
        combate._efeito_conflagracao(luta, c, dados)
    assert len(_stacks_brasa(luta)) == 3

    _stacks_brasa(luta)[0]["duracao"] = 1   # simula a primeira pilha quase expirando

    combate._efeito_conflagracao(luta, c, dados)   # 4º uso

    stacks_depois = _stacks_brasa(luta)
    assert len(stacks_depois) == 3             # não virou 4
    assert stacks_depois[0]["duracao"] == 3     # a primeira pilha foi renovada, não criada de novo


def test_mago_fogo_sem_combustao_continua_so_refrescando_brasa(monkeypatch):
    """Sem a passiva, aplicar Brasa de novo (skill ou arma) tem que
    continuar se comportando como hoje -- refresh, nunca uma segunda
    condição."""
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20)   # sem ascensão -- sem Combustão
    dados = game_data.HABILIDADES["conflagracao"]
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    for _ in range(3):
        combate._efeito_conflagracao(luta, c, dados)

    assert len(_stacks_brasa(luta)) == 1   # nunca empilhou


def test_mago_gelo_com_cajado_de_fogo_nao_empilha_brasa(monkeypatch):
    """Caso explícito pedido no cartão: outro ramo (mago_gelo) empunhando
    arma de fogo não ganha o empilhamento -- Combustão é do mago_fogo."""
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_gelo", arma="cajado_solario")
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)   # garante o proc da arma
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    combate._talvez_condicionar_chefe(luta, c)
    luta.elementos_aplicados_rodada.discard("fogo")   # simula outro golpe na mesma rodada
    combate._talvez_condicionar_chefe(luta, c)

    assert len(_stacks_brasa(luta)) == 1   # refrescou, não empilhou
