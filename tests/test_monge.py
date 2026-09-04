# tests/test_monge.py
# Step 2d, commit 2: Punho do Silêncio (skill) e Corpo Desperto (passiva)
# do Monge. Ver decisoes.md § Step 2d.
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
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita, nunca proca a arma


def _sobrevive_n_ticks_e_expira_no_seguinte(luta, nome, n):
    """Mesma técnica de tests/test_condicoes.py (bloco 4, contrato N+1)."""
    for i in range(n):
        condicoes.tick(luta)
        assert any(c["nome"] == nome for c in luta.condicoes), f"'{nome}' sumiu cedo demais, tick {i + 1}/{n}"
    condicoes.tick(luta)
    assert not any(c["nome"] == nome for c in luta.condicoes), f"'{nome}' deveria ter expirado no tick {n + 1}"


# ==================================================================
# Gate de ascensão
# ==================================================================

def test_nao_ascendido_nao_conhece_punho_do_silencio():
    j = _combatente(1, classe="orador", inteligencia=20).jogador
    assert "punho_do_silencio" not in hab.conhecidas(j)


def test_monge_conhece_punho_do_silencio():
    j = _combatente(1, classe="orador", inteligencia=20, ascensao="monge").jogador
    assert "punho_do_silencio" in hab.conhecidas(j)


def test_punho_do_silencio_nao_tem_requisito_de_atributo():
    """A ascensão É o requisito -- ver decisoes.md § Step 2a."""
    assert "requisito" not in game_data.HABILIDADES["punho_do_silencio"]


# ==================================================================
# Dano -- aplica defesa e escala em DES, NÃO em INT (única skill do jogo
# que troca o atributo da própria classe)
# ==================================================================

def test_punho_do_silencio_aplica_a_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="orador", inteligencia=20, destreza=20, ascensao="monge")
    dados = game_data.HABILIDADES["punho_do_silencio"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    combate._efeito_punho_do_silencio(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    c2 = _combatente(2, classe="orador", inteligencia=20, destreza=20, ascensao="monge")
    luta_com_def = combate.Luta([c2], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_punho_do_silencio(luta_com_def, c2, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def < dano_sem_def


def test_punho_do_silencio_escala_com_destreza_nao_com_inteligencia(monkeypatch):
    """O teste que mais importa desta skill: subir INT (o atributo_
    habilidade normal do Orador) não muda nada; subir DES muda tudo."""
    _sem_variancia(monkeypatch)
    dados = game_data.HABILIDADES["punho_do_silencio"]
    chefe_sem_def = {**CHEFE_TESTE, "def": 0}

    des_baixa = _combatente(1, classe="orador", inteligencia=100, destreza=5, ascensao="monge")
    luta_des_baixa = combate.Luta([des_baixa], chefe_sem_def, andar_num=1)
    combate._efeito_punho_do_silencio(luta_des_baixa, des_baixa, dados)
    dano_des_baixa = luta_des_baixa.hp_chefe_max - luta_des_baixa.hp_chefe

    des_alta = _combatente(2, classe="orador", inteligencia=5, destreza=100, ascensao="monge")
    luta_des_alta = combate.Luta([des_alta], chefe_sem_def, andar_num=1)
    combate._efeito_punho_do_silencio(luta_des_alta, des_alta, dados)
    dano_des_alta = luta_des_alta.hp_chefe_max - luta_des_alta.hp_chefe

    assert dano_des_alta > dano_des_baixa   # INT alta não ajudou; DES alta ajudou


def test_punho_do_silencio_com_mesma_destreza_independe_da_inteligencia(monkeypatch):
    _sem_variancia(monkeypatch)
    dados = game_data.HABILIDADES["punho_do_silencio"]
    chefe_sem_def = {**CHEFE_TESTE, "def": 0}

    int_baixa = _combatente(1, classe="orador", inteligencia=5, destreza=20, ascensao="monge")
    luta_1 = combate.Luta([int_baixa], chefe_sem_def, andar_num=1)
    combate._efeito_punho_do_silencio(luta_1, int_baixa, dados)
    dano_1 = luta_1.hp_chefe_max - luta_1.hp_chefe

    int_alta = _combatente(2, classe="orador", inteligencia=100, destreza=20, ascensao="monge")
    luta_2 = combate.Luta([int_alta], chefe_sem_def, andar_num=1)
    combate._efeito_punho_do_silencio(luta_2, int_alta, dados)
    dano_2 = luta_2.hp_chefe_max - luta_2.hp_chefe

    assert dano_1 == dano_2


# ==================================================================
# bloqueia_skill no chefe -- 2 rodadas (regra N+1: duracao guardada = 3).
# Hoje quase não faz efeito (chefe não tem skill própria) -- INTENCIONAL,
# ver decisoes.md § Step 2d (não é o erro do Reflexos, Step 2b correção).
# ==================================================================

def test_punho_do_silencio_aplica_bloqueia_skill_por_2_rodadas(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="orador", inteligencia=20, destreza=20, ascensao="monge")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    combate._efeito_punho_do_silencio(luta, c, game_data.HABILIDADES["punho_do_silencio"])

    assert any(cc["tipo"] == "bloqueia_skill" for cc in luta.condicoes)
    _sobrevive_n_ticks_e_expira_no_seguinte(luta, "Punho do Silêncio", 2)


def test_bloqueia_skill_do_punho_ja_e_consultado_de_verdade_hoje(monkeypatch):
    """O mecanismo (condicoes.pode_lancar_habilidade) já existe e já
    funciona -- só o chefe não tem NENHUMA skill própria pra bloquear
    ainda (entra no step 3). Prova que não é código morto por acidente:
    a consulta responde certo, falta só o chefe ter o que bloquear."""
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="orador", inteligencia=20, destreza=20, ascensao="monge")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    assert condicoes.pode_lancar_habilidade(luta, "chefe") is True
    combate._efeito_punho_do_silencio(luta, c, game_data.HABILIDADES["punho_do_silencio"])
    assert condicoes.pode_lancar_habilidade(luta, "chefe") is False


# ==================================================================
# Corpo Desperto -- recupera mana no ataque normal e na skill
# ==================================================================

def test_corpo_desperto_recupera_mana_no_ataque_normal(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="orador", inteligencia=20, ascensao="monge", mana=0)
    luta = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)

    combate._rolar_ataque_normal(luta, c, c.s["atk"], 0, c.s["critico"])
    combate._recuperar_mana_por_golpe(c)   # mesmo par que registrar_acao/on_timeout chamam

    assert c.mana == game_data.PASSIVAS["corpo_desperto"]["valor"]


def test_corpo_desperto_recupera_mana_no_punho_do_silencio(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="orador", inteligencia=20, destreza=20, ascensao="monge", mana=0)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    combate._efeito_punho_do_silencio(luta, c, game_data.HABILIDADES["punho_do_silencio"])

    assert c.mana == game_data.PASSIVAS["corpo_desperto"]["valor"]


def test_corpo_desperto_nao_estoura_o_teto_de_mana():
    c = _combatente(1, classe="orador", inteligencia=20, ascensao="monge")
    c.mana = c.s["mana_max"]   # já no teto

    combate._recuperar_mana_por_golpe(c)

    assert c.mana == c.s["mana_max"]


def test_sem_corpo_desperto_ataque_normal_nao_recupera_mana(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="orador", inteligencia=20, mana=0)   # sem ascensão
    luta = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)

    combate._rolar_ataque_normal(luta, c, c.s["atk"], 0, c.s["critico"])
    combate._recuperar_mana_por_golpe(c)

    assert c.mana == 0
