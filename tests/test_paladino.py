# tests/test_paladino.py
# Step 2d, commit 4: Represália (dano + reflexão) e Juramento (transferência
# de dano de aliado pro paladino). Fecha o pacote de ascensões (Step 2). Ver
# decisoes.md § Step 2d.
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
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita, nunca proca a arma, nunca esquiva


def _sobrevive_n_ticks_e_expira_no_seguinte(luta, nome, n):
    """Mesma técnica de tests/test_condicoes.py (bloco 4, contrato N+1) e
    tests/test_monge.py."""
    for i in range(n):
        condicoes.tick(luta)
        assert any(c["nome"] == nome for c in luta.condicoes), f"'{nome}' sumiu cedo demais, tick {i + 1}/{n}"
    condicoes.tick(luta)
    assert not any(c["nome"] == nome for c in luta.condicoes), f"'{nome}' deveria ter expirado no tick {n + 1}"


# ==================================================================
# Gate de ascensão
# ==================================================================

def test_nao_ascendido_nao_conhece_represalia():
    j = _combatente(1, classe="orador", inteligencia=20).jogador
    assert "represalia" not in hab.conhecidas(j)


def test_paladino_conhece_represalia():
    j = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino").jogador
    assert "represalia" in hab.conhecidas(j)


def test_represalia_nao_tem_requisito_de_atributo():
    """A ascensão É o requisito -- ver decisoes.md § Step 2a."""
    assert "requisito" not in game_data.HABILIDADES["represalia"]


# ==================================================================
# Represália -- dano aplica defesa + aplica reflete_dano no próprio
# paladino por 3 rodadas (regra N+1)
# ==================================================================

def test_represalia_aplica_a_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    dados = game_data.HABILIDADES["represalia"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    combate._efeito_represalia(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    c2 = _combatente(2, classe="orador", inteligencia=20, ascensao="paladino")
    luta_com_def = combate.Luta([c2], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_represalia(luta_com_def, c2, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def < dano_sem_def


def test_represalia_aplica_reflete_dano_no_proprio_paladino_por_3_rodadas():
    c = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    dados = game_data.HABILIDADES["represalia"]
    combate._efeito_represalia(luta, c, dados)

    cond = next(x for x in luta.condicoes if x["tipo"] == "reflete_dano")
    assert cond["alvo"] == c.id
    assert cond["valor"] == combate.FRACAO_REFLEXAO_REPRESALIA
    _sobrevive_n_ticks_e_expira_no_seguinte(luta, dados["nome"], combate.DURACAO_REFLEXAO_REPRESALIA_RODADAS)


# ==================================================================
# Represália em ação -- o chefe toma de volta parte do dano que causa
# no paladino (ataque normal e golpe carregado, os dois pontos que
# _aplicar_dano_do_chefe cobre)
# ==================================================================

def test_ataque_normal_do_chefe_no_paladino_reflete_dano_de_volta():
    paladino = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    luta = combate.Luta([paladino], CHEFE_TESTE, andar_num=1)
    condicoes.aplicar(
        luta, paladino.id, "reflete_dano", "Represália", "🔥",
        duracao=4, valor=combate.FRACAO_REFLEXAO_REPRESALIA, origem=paladino.id,
    )
    hp_chefe_antes = luta.hp_chefe

    dano_no_alvo = combate._aplicar_dano_do_chefe(luta, paladino, 100)

    assert dano_no_alvo == 100
    assert paladino.hp == paladino.s["hp_max"] - 100
    refletido = hp_chefe_antes - luta.hp_chefe
    assert refletido == int(100 * combate.FRACAO_REFLEXAO_REPRESALIA)
    assert refletido > 0


def test_sem_represalia_ativa_o_chefe_nao_toma_nada_de_volta():
    paladino = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    luta = combate.Luta([paladino], CHEFE_TESTE, andar_num=1)
    hp_chefe_antes = luta.hp_chefe

    combate._aplicar_dano_do_chefe(luta, paladino, 100)

    assert luta.hp_chefe == hp_chefe_antes


def test_dano_refletido_nunca_dispara_reflexao_de_novo():
    """A rede de segurança do cartão: o dano que o CHEFE toma de volta
    sai de `luta.hp_chefe` direto -- não existe caminho pelo qual esse
    dano volte a passar por `_aplicar_dano_do_chefe`/`_refletir_se_
    paladino`, então não tem como um reflexo disparar outro reflexo."""
    paladino = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    luta = combate.Luta([paladino], CHEFE_TESTE, andar_num=1)
    condicoes.aplicar(
        luta, paladino.id, "reflete_dano", "Represália", "🔥",
        duracao=4, valor=1.0, origem=paladino.id,   # 100% de propósito, pra maximizar a chance de um loop aparecer
    )
    hp_chefe_antes = luta.hp_chefe

    combate._aplicar_dano_do_chefe(luta, paladino, 100)

    # se refletir disparasse outro reflexo, o chefe teria perdido muito
    # mais que os 100 refletidos (loop) -- aqui perde exatamente 100.
    assert hp_chefe_antes - luta.hp_chefe == 100


def test_golpe_carregado_no_paladino_tambem_reflete(monkeypatch):
    _sem_variancia(monkeypatch)
    paladino = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    luta = combate.Luta([paladino], {**CHEFE_TESTE, "atk": 20}, andar_num=1)
    luta.rodada = 2   # RODADA_1_SEM_CHEFE
    luta.carregando = True
    condicoes.aplicar(
        luta, paladino.id, "reflete_dano", "Represália", "🔥",
        duracao=4, valor=combate.FRACAO_REFLEXAO_REPRESALIA, origem=paladino.id,
    )
    hp_chefe_antes = luta.hp_chefe

    luta.turno_do_chefe()

    assert luta.hp_chefe < hp_chefe_antes   # refletiu alguma coisa


# ==================================================================
# Juramento -- transferência de dano de aliado pro paladino (não é
# redução, não é a Muralha)
# ==================================================================

def test_juramento_transfere_parte_do_dano_de_aliado_pro_paladino():
    paladino = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    aliado = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([paladino, aliado], CHEFE_TESTE, andar_num=1)
    hp_paladino_antes = paladino.hp

    dano_no_aliado = combate._aplicar_dano_do_chefe(luta, aliado, 100)

    esperado_absorvido = int(100 * combate.FRACAO_ABSORCAO_JURAMENTO)
    assert dano_no_aliado == 100 - esperado_absorvido
    assert aliado.hp == aliado.s["hp_max"] - dano_no_aliado
    assert paladino.hp == hp_paladino_antes - esperado_absorvido


def test_juramento_nao_transfere_dano_que_o_proprio_paladino_recebe():
    paladino = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    aliado = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([paladino, aliado], CHEFE_TESTE, andar_num=1)

    dano_no_paladino = combate._aplicar_dano_do_chefe(luta, paladino, 100)

    assert dano_no_paladino == 100   # sem "autotransferência" -- ele já é o alvo


def test_sem_paladino_na_party_ninguem_absorve_nada():
    a = _combatente(1, classe="guerreiro", forca=20)
    b = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([a, b], CHEFE_TESTE, andar_num=1)

    dano_em_a = combate._aplicar_dano_do_chefe(luta, a, 100)

    assert dano_em_a == 100
    assert b.hp == b.s["hp_max"]   # b não pagou nada -- não é paladino


def test_paladino_caido_nao_absorve_dano_de_aliado():
    paladino = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    aliado = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([paladino, aliado], CHEFE_TESTE, andar_num=1)
    paladino.caiu = True
    paladino.hp = 0

    dano_no_aliado = combate._aplicar_dano_do_chefe(luta, aliado, 100)

    assert dano_no_aliado == 100   # paladino caído não conta como "ativo"


def test_juramento_nao_e_reducao_de_dano_nao_mexe_na_reducao_dano_total():
    """NÃO é reducao_dano_recebido -- não divide teto de 0.5 com
    Disciplina/Voto de Ferro/Muralha de Escudos, é transferência pura."""
    paladino = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    aliado = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([paladino, aliado], CHEFE_TESTE, andar_num=1)

    assert condicoes.reducao_dano_recebido(luta, aliado.id) == 0.0
    dano_no_aliado = combate._aplicar_dano_do_chefe(luta, aliado, 100)
    assert dano_no_aliado == 100 - int(100 * combate.FRACAO_ABSORCAO_JURAMENTO)   # não os 100 inteiros


def test_juramento_nao_e_a_muralha_o_chefe_continua_escolhendo_o_alvo():
    """Diferença explícita do cartão: a Muralha redireciona quem o chefe
    ATACA (condicoes.alvo_forcado); Juramento não mexe nisso -- o chefe
    escolhe o alvo normalmente, só quem PAGA parte da conta muda."""
    paladino = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    aliado = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([paladino, aliado], CHEFE_TESTE, andar_num=1)

    assert condicoes.alvo_forcado(luta) is None   # ninguém redirecionou o chefe


# ==================================================================
# O paladino pode cair pelo próprio Juramento (intencional) -- mas a
# transferência não pode explodir em dano imprevisível
# ==================================================================

def test_paladino_pode_cair_absorvendo_dano_de_aliado():
    paladino = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    aliado = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([paladino, aliado], CHEFE_TESTE, andar_num=1)
    paladino.hp = 1   # HP baixíssimo

    dano_grande = int(paladino.s["hp_max"] * 2)   # golpe carregado grosso o bastante pra derrubar
    combate._aplicar_dano_do_chefe(luta, aliado, dano_grande)

    assert paladino.caiu is True
    esperado_absorvido = int(dano_grande * combate.FRACAO_ABSORCAO_JURAMENTO)
    assert paladino.hp == 1 - esperado_absorvido   # dano PREVISÍVEL -- exatamente a fração, nada a mais


def test_transferencia_de_ataque_normal_no_paladino_em_hp_baixo_e_previsivel(monkeypatch):
    """Caso específico do cartão: paladino em HP baixo absorvendo dano de
    Juramento -- ponta a ponta, direto de `Luta.turno_do_chefe` (não a
    chamada isolada de `_aplicar_dano_do_chefe`). Usa o ATAQUE NORMAL com
    o chefe forçado (`condicoes.alvo_forcado`, mesmo mecanismo da
    Muralha) a bater no ALIADO -- assim o paladino não toma nenhum golpe
    PRÓPRIO nesta rodada (o golpe carregado bateria nos dois ao mesmo
    tempo, o que confundiria "dano próprio" com "dano transferido"), e o
    teste prova que o que ele perde é EXATAMENTE a fração de Juramento
    do dano original -- nunca o golpe inteiro, nunca mais que isso."""
    _sem_variancia(monkeypatch)
    paladino = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    aliado = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([paladino, aliado], {**CHEFE_TESTE, "atk": 20}, andar_num=1)
    luta.rodada = 2
    paladino.hp = 1
    condicoes.aplicar(luta, "chefe", "redireciona", "Provocado", "🎯", duracao=2, valor=aliado.id)

    luta.turno_do_chefe()

    dano_no_aliado = aliado.s["hp_max"] - aliado.hp   # o que ele efetivamente pagou, já sem a parte transferida
    perda_paladino = 1 - paladino.hp
    dano_original = dano_no_aliado + perda_paladino    # dano_alvo + dano_paladino = o dano antes da transferência
    assert dano_original > 0   # sanity -- o golpe aconteceu de verdade
    assert perda_paladino == int(dano_original * combate.FRACAO_ABSORCAO_JURAMENTO)


# ==================================================================
# Represália + Juramento juntos -- dano absorvido pelo paladino também
# reflete, mas sem loop
# ==================================================================

def test_dano_absorvido_por_juramento_tambem_reflete_com_represalia_ativa():
    paladino = _combatente(1, classe="orador", inteligencia=20, ascensao="paladino")
    aliado = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([paladino, aliado], CHEFE_TESTE, andar_num=1)
    condicoes.aplicar(
        luta, paladino.id, "reflete_dano", "Represália", "🔥",
        duracao=4, valor=combate.FRACAO_REFLEXAO_REPRESALIA, origem=paladino.id,
    )
    hp_chefe_antes = luta.hp_chefe

    combate._aplicar_dano_do_chefe(luta, aliado, 100)

    dano_absorvido = int(100 * combate.FRACAO_ABSORCAO_JURAMENTO)
    refletido_esperado = int(dano_absorvido * combate.FRACAO_REFLEXAO_REPRESALIA)
    assert hp_chefe_antes - luta.hp_chefe == refletido_esperado
    assert refletido_esperado > 0
