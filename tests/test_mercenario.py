# tests/test_mercenario.py
# Step 2c, commit 2: Golpe Oportunista (skill) e Desespero (passiva) do
# Mercenário. Ver decisoes.md § Step 2c.
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

def test_nao_ascendido_nao_conhece_golpe_oportunista():
    j = _combatente(1, classe="guerreiro", forca=20).jogador
    assert "golpe_oportunista" not in hab.conhecidas(j)


def test_mercenario_conhece_golpe_oportunista():
    j = _combatente(1, classe="guerreiro", forca=20, ascensao="mercenario").jogador
    assert "golpe_oportunista" in hab.conhecidas(j)


def test_golpe_oportunista_nao_tem_requisito_de_atributo():
    """A ascensão É o requisito -- ver decisoes.md § Step 2a."""
    assert "requisito" not in game_data.HABILIDADES["golpe_oportunista"]


# ==================================================================
# Dano -- passa por at.aplicar_defesa e escala com o HP QUE O PRÓPRIO
# GUERREIRO já perdeu (nunca o HP do chefe -- é o espelho do Golpe Fatal)
# ==================================================================

def test_golpe_oportunista_aplica_a_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="mercenario")
    dados = game_data.HABILIDADES["golpe_oportunista"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    combate._efeito_golpe_oportunista(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    c2 = _combatente(2, classe="guerreiro", forca=20, ascensao="mercenario")
    luta_com_def = combate.Luta([c2], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_golpe_oportunista(luta_com_def, c2, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def < dano_sem_def


def test_golpe_oportunista_causa_mais_dano_quanto_mais_baixo_o_hp_do_proprio_guerreiro(monkeypatch):
    _sem_variancia(monkeypatch)
    dados = game_data.HABILIDADES["golpe_oportunista"]
    chefe_sem_def = {**CHEFE_TESTE, "def": 0}

    c_cheio = _combatente(1, classe="guerreiro", forca=20, ascensao="mercenario")
    luta_cheio = combate.Luta([c_cheio], chefe_sem_def, andar_num=1)
    combate._efeito_golpe_oportunista(luta_cheio, c_cheio, dados)
    dano_cheio = luta_cheio.hp_chefe_max - luta_cheio.hp_chefe

    c_baixo = _combatente(2, classe="guerreiro", forca=20, ascensao="mercenario")
    c_baixo.hp = 1   # o próprio guerreiro perto da morte
    luta_baixo = combate.Luta([c_baixo], chefe_sem_def, andar_num=1)
    combate._efeito_golpe_oportunista(luta_baixo, c_baixo, dados)
    dano_baixo = luta_baixo.hp_chefe_max - luta_baixo.hp_chefe

    assert dano_baixo > dano_cheio


def test_golpe_oportunista_usa_o_hp_do_guerreiro_nao_o_hp_do_chefe(monkeypatch):
    """O chefe pode estar baixo de HP também -- não pode confundir com
    Golpe Fatal (Step 2a) e olhar pro hp_chefe por engano."""
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="mercenario")
    dados = game_data.HABILIDADES["golpe_oportunista"]
    luta = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    luta.hp_chefe = 1   # chefe agonizando -- não deveria mudar o multiplicador desta skill
    hp_chefe_antes = luta.hp_chefe

    combate._efeito_golpe_oportunista(luta, c, dados)

    dano = hp_chefe_antes - luta.hp_chefe

    base = hab.poder_base(c.jogador, combate._bonus_arma_de(c)) * combate._multiplicador_afinidade(c)
    esperado = max(1, int(base * combate.MULTIPLICADOR_GOLPE_OPORTUNISTA))   # HP CHEIO do guerreiro -> 2.0x
    assert dano == esperado


# ==================================================================
# Desespero -- abaixo de metade do HP, Fúria sobe mais rápido, nas DUAS
# portas (ganhar_furia e ganhar_furia_defesa)
# ==================================================================

def test_desespero_acelera_ganhar_furia_abaixo_de_metade_do_hp():
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="mercenario")
    c.hp = int(c.s["hp_max"] * 0.4)   # abaixo de 50%
    c.furia = 0

    combate.ganhar_furia(c)

    ganho_base = combate.FURIA_POR_GOLPE + int(c.jogador["forca"] or 0) / 5
    assert c.furia == ganho_base * game_data.PASSIVAS["desespero"]["valor"]


def test_desespero_acelera_ganhar_furia_defesa_abaixo_de_metade_do_hp():
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="mercenario")
    c.hp = int(c.s["hp_max"] * 0.4)
    c.furia = 0

    combate.ganhar_furia_defesa(c)

    ganho_base = 0.5 * (combate.FURIA_POR_GOLPE + int(c.jogador["forca"] or 0) / 5)
    assert c.furia == ganho_base * game_data.PASSIVAS["desespero"]["valor"]


def test_desespero_nao_acelera_acima_de_metade_do_hp():
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="mercenario")
    c.hp = c.s["hp_max"]   # HP cheio
    c.furia = 0

    combate.ganhar_furia(c)

    ganho_base = combate.FURIA_POR_GOLPE + int(c.jogador["forca"] or 0) / 5
    assert c.furia == ganho_base   # sem o bônus -- acima da metade


def test_sem_desespero_ganho_de_furia_nao_muda_mesmo_com_hp_baixo():
    c = _combatente(1, classe="guerreiro", forca=20)   # sem ascensão
    c.hp = int(c.s["hp_max"] * 0.1)   # bem abaixo de metade
    c.furia = 0

    combate.ganhar_furia(c)

    ganho_base = combate.FURIA_POR_GOLPE + int(c.jogador["forca"] or 0) / 5
    assert c.furia == ganho_base
