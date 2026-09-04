# tests/test_mago_raio.py
# Step 2b, commit 3: Interrupção (skill) e Reflexos (passiva) do Mago de
# Raio. Ver decisoes.md § Step 2b.
import bot
import combate
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
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita, nunca proca a arma


# ==================================================================
# Gate de ascensão
# ==================================================================

def test_nao_ascendido_nao_conhece_interrupcao():
    j = _combatente(1, classe="mago", inteligencia=20).jogador
    assert "interrupcao" not in hab.conhecidas(j)


def test_mago_raio_conhece_interrupcao():
    j = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio").jogador
    assert "interrupcao" in hab.conhecidas(j)


def test_interrupcao_nao_tem_requisito_de_atributo():
    """A ascensão É o requisito -- ver decisoes.md § Step 2a."""
    assert "requisito" not in game_data.HABILIDADES["interrupcao"]


# ==================================================================
# Dano -- passa por at.aplicar_defesa (ver decisoes.md § Step 2b)
# ==================================================================

def test_interrupcao_aplica_a_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    dados = game_data.HABILIDADES["interrupcao"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    combate._efeito_interrupcao(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    c2 = _combatente(2, classe="mago", inteligencia=20, ascensao="mago_raio")
    luta_com_def = combate.Luta([c2], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_interrupcao(luta_com_def, c2, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def < dano_sem_def


# ==================================================================
# Interrupção -- cancela o golpe carregado, e SÓ isso
# ==================================================================

def test_interrupcao_cancela_a_carga_e_o_golpe_seguinte_do_chefe_nao_e_carregado(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    dados = game_data.HABILIDADES["interrupcao"]
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    luta.carregando = True

    combate._efeito_interrupcao(luta, c, dados)

    assert luta.carregando is False

    # rodada seguinte: turno_do_chefe não pode soltar o golpe carregado --
    # espiona dano_do_chefe pra confirmar carregado=False (nunca o 3x)
    chamadas = []
    original = combate.dano_do_chefe

    def _espiao(chefe, s, andar_num, defendendo=False, carregado=False):
        chamadas.append(carregado)
        return original(chefe, s, andar_num, defendendo=defendendo, carregado=carregado)

    monkeypatch.setattr(combate, "dano_do_chefe", _espiao)
    luta.rodada = 2   # RODADA_1_SEM_CHEFE só trava a rodada 1
    luta.turno_do_chefe()

    assert chamadas == [False]


def test_interrupcao_contra_chefe_nao_carregando_e_so_dano(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    dados = game_data.HABILIDADES["interrupcao"]
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    assert luta.carregando is False

    combate._efeito_interrupcao(luta, c, dados)

    assert luta.carregando is False   # continua False -- não tinha nada pra cancelar
    assert luta.hp_chefe < luta.hp_chefe_max   # mas o dano aconteceu normalmente


def test_interrupcao_nao_cancela_nada_alem_da_carga(monkeypatch):
    """Fronteira dura: preparando_condicao é OUTRO estado de ação do chefe
    (telegraph elemental, andares 11+, roda independente do golpe
    carregado -- ver Luta._talvez_telegrafar_condicao) que também pode
    estar pendente na mesma rodada. Interrupção cancela `carregando` e
    NADA mais -- se alguém um dia generalizar isto pra "cancela qualquer
    ação pendente do chefe", este teste cai."""
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    dados = game_data.HABILIDADES["interrupcao"]
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    luta.carregando = True
    luta.preparando_condicao = {"tipo": "vulneravel", "nome": "Marca", "emoji": "✨", "alvo_id": c.id}

    combate._efeito_interrupcao(luta, c, dados)

    assert luta.carregando is False                    # isto, cancela
    assert luta.preparando_condicao is not None         # isto, NUNCA -- não é carga


# ==================================================================
# Reflexos -- garante a iniciativa na rodada 1 (código hoje dormente sob
# RODADA_1_SEM_CHEFE=True, ver decisoes.md § Step 2b)
# ==================================================================

def test_reflexos_garante_a_iniciativa_quando_rodada_1_sem_chefe_esta_desligado(monkeypatch):
    monkeypatch.setattr(combate, "RODADA_1_SEM_CHEFE", False)
    monkeypatch.setattr(combate.at, "chance_iniciativa", lambda *a, **k: -1.0)   # perderia sempre sem a passiva
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio", destreza=1)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    hp_antes = c.hp

    combate._resolver_abertura_do_chefe(luta, [c], andar_num=1)

    assert c.hp == hp_antes   # o chefe não abriu batendo em ninguém
    assert not c.caiu


def test_sem_reflexos_o_chefe_pode_abrir_batendo_quando_rodada_1_sem_chefe_esta_desligado(monkeypatch):
    monkeypatch.setattr(combate, "RODADA_1_SEM_CHEFE", False)
    monkeypatch.setattr(combate.at, "chance_iniciativa", lambda *a, **k: -1.0)   # perde sempre
    c = _combatente(1, classe="mago", inteligencia=20, destreza=1)   # sem ascensão -- sem Reflexos
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    hp_antes = c.hp

    combate._resolver_abertura_do_chefe(luta, [c], andar_num=1)

    assert c.hp < hp_antes   # o chefe abriu batendo -- comportamento de sempre, sem a passiva


def test_resolver_abertura_do_chefe_e_no_op_com_rodada_1_sem_chefe_ligado():
    """Estado padrão do jogo hoje -- Reflexos fica dormente até o toggle
    mudar, mas não pode quebrar nem interferir enquanto isso."""
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    hp_antes = c.hp

    combate._resolver_abertura_do_chefe(luta, [c], andar_num=1)

    assert c.hp == hp_antes
