# tests/test_chefe_ia.py
# Cartão "Step 3 — os 4 espelhos e o motor de decisão de chefe", commit 1:
# o motor GERAL de decisão. Só lê o que aconteceu NAQUELA luta -- estado
# montado à mão em cada teste, nada de RNG (regras legíveis, não peso
# aleatório). Ver decisoes.md § Step 3.
import inspect

import bot
import chefe_ia
import combate
import condicoes
import database as db

CHEFE_TESTE = {"nome": "Testinho", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0}


def _combatente(user_id, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


def _luta(*combatentes):
    return combate.Luta(list(combatentes), CHEFE_TESTE, andar_num=1)


# ==================================================================
# Registro -- cada luta começa vazia, nunca herda de outra
# ==================================================================

def test_historico_comeca_vazio_numa_luta_nova():
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta(c)

    assert luta.historico_ia == {}
    assert chefe_ia.vezes_curou(luta, c.id) == 0
    assert chefe_ia.vezes_usou_habilidade(luta, c.id, "qualquer") == 0
    assert chefe_ia.segurando_recurso(luta, c.id) is True   # fração 1.0 por padrão -- ainda não gastou nada


def test_duas_lutas_diferentes_nunca_compartilham_historico():
    c = _combatente(1, classe="guerreiro", forca=20)
    luta1 = _luta(c)
    chefe_ia.registrar_cura(luta1, c.id)
    chefe_ia.registrar_cura(luta1, c.id)

    luta2 = _luta(c)

    assert chefe_ia.vezes_curou(luta2, c.id) == 0   # a luta nova não herdou nada da anterior


# ==================================================================
# vezes_curou / curou_demais
# ==================================================================

def test_registrar_cura_soma_e_curou_demais_bate_no_limiar():
    c = _combatente(1, classe="orador", inteligencia=20)
    luta = _luta(c)

    assert chefe_ia.curou_demais(luta, c.id) is False
    chefe_ia.registrar_cura(luta, c.id)
    assert chefe_ia.vezes_curou(luta, c.id) == 1
    assert chefe_ia.curou_demais(luta, c.id) is False   # ainda não bateu o limiar (2)

    chefe_ia.registrar_cura(luta, c.id)
    assert chefe_ia.vezes_curou(luta, c.id) == 2
    assert chefe_ia.curou_demais(luta, c.id) is True


def test_curas_de_jogadores_diferentes_nao_se_misturam():
    a = _combatente(1, classe="orador", inteligencia=20)
    b = _combatente(2, classe="orador", inteligencia=20)
    luta = _luta(a, b)
    chefe_ia.registrar_cura(luta, a.id)
    chefe_ia.registrar_cura(luta, a.id)

    assert chefe_ia.curou_demais(luta, a.id) is True
    assert chefe_ia.curou_demais(luta, b.id) is False


# ==================================================================
# habilidades usadas
# ==================================================================

def test_registrar_habilidade_conta_por_chave():
    c = _combatente(1, classe="mago", inteligencia=20)
    luta = _luta(c)
    chefe_ia.registrar_habilidade(luta, c.id, "dardo_arcano")
    chefe_ia.registrar_habilidade(luta, c.id, "dardo_arcano")
    chefe_ia.registrar_habilidade(luta, c.id, "ruptura")

    assert chefe_ia.vezes_usou_habilidade(luta, c.id, "dardo_arcano") == 2
    assert chefe_ia.vezes_usou_habilidade(luta, c.id, "ruptura") == 1
    assert chefe_ia.vezes_usou_habilidade(luta, c.id, "nunca_usada") == 0


# ==================================================================
# segurando_recurso
# ==================================================================

def test_segurando_recurso_e_true_acima_do_limiar_false_abaixo():
    c = _combatente(1, classe="mago", inteligencia=20)
    luta = _luta(c)

    chefe_ia.registrar_fracao_recurso(luta, c.id, 0.9)
    assert chefe_ia.segurando_recurso(luta, c.id) is True

    chefe_ia.registrar_fracao_recurso(luta, c.id, chefe_ia.LIMIAR_FRACAO_RECURSO_SEGURANDO)
    assert chefe_ia.segurando_recurso(luta, c.id) is True   # exatamente no limiar -- ainda conta

    chefe_ia.registrar_fracao_recurso(luta, c.id, 0.3)
    assert chefe_ia.segurando_recurso(luta, c.id) is False


def test_registrar_fracao_recurso_sobrescreve_nao_soma():
    c = _combatente(1, classe="mago", inteligencia=20)
    luta = _luta(c)
    chefe_ia.registrar_fracao_recurso(luta, c.id, 0.9)
    chefe_ia.registrar_fracao_recurso(luta, c.id, 0.2)

    assert luta.historico_ia[c.id]["fracao_recurso"] == 0.2   # não 1.1 nem acumulado


# ==================================================================
# fracao_hp / com_pouco_hp -- estado AGORA, não histórico acumulado
# ==================================================================

def test_com_pouco_hp_reflete_o_hp_atual_do_combatente():
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta(c)
    c.hp = c.s["hp_max"]
    assert chefe_ia.com_pouco_hp(luta, c.id) is False

    c.hp = int(c.s["hp_max"] * chefe_ia.LIMIAR_FRACAO_HP_BAIXO)
    assert chefe_ia.com_pouco_hp(luta, c.id) is True


def test_com_pouco_hp_de_combatente_caido_e_sempre_true():
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta(c)
    c.hp = 0
    c.caiu = True

    assert chefe_ia.fracao_hp(luta, c.id) == 0.0
    assert chefe_ia.com_pouco_hp(luta, c.id) is True


# ==================================================================
# condições ativas dos dois lados
# ==================================================================

def test_condicoes_no_chefe_filtra_por_alvo_e_duracao():
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta(c)
    condicoes.aplicar(luta, "chefe", "reduz_dano", "Muralha", "🛡️", duracao=3, valor=0.2)
    condicoes.aplicar(luta, c.id, "reduz_dano", "Voto de Ferro", "⚔️", duracao=3, valor=0.1)

    ativas = chefe_ia.condicoes_no_chefe(luta)

    assert len(ativas) == 1
    assert ativas[0]["nome"] == "Muralha"


def test_condicoes_no_jogador_ignora_as_ja_expiradas():
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta(c)
    condicoes.aplicar(luta, c.id, "vulneravel", "Marca", "✨", duracao=3, valor=0.2)
    luta.condicoes[0]["duracao"] = 0   # já expirou, só não foi limpa pelo tick ainda

    assert chefe_ia.condicoes_no_jogador(luta, c.id) == []


# ==================================================================
# decidir_acao -- regras legíveis, ordem de prioridade fixa, sempre
# com motivo quando não é "padrao"
# ==================================================================

def test_decidir_acao_padrao_sem_nenhuma_leitura_disparando():
    """HP cheio, sem curar demais, e recurso já gasto (abaixo do
    limiar) -- "nunca registrou fração de recurso" NÃO é o cenário
    neutro aqui: por padrão o registro nasce em 1.0 (ninguém gastou
    nada ainda), o que dispara "pressionar" de propósito -- ver
    test_historico_comeca_vazio_numa_luta_nova. O cenário neutro de
    verdade precisa registrar recurso já gasto."""
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta(c)
    c.hp = c.s["hp_max"]
    chefe_ia.registrar_fracao_recurso(luta, c.id, 0.3)

    decisao = chefe_ia.decidir_acao(luta, c.id)

    assert decisao == {"acao": "padrao", "motivo": None}


def test_decidir_acao_prioriza_carregado_com_pouco_hp():
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta(c)
    c.hp = 1   # bem abaixo do limiar

    decisao = chefe_ia.decidir_acao(luta, c.id)

    assert decisao["acao"] == "priorizar_carregado"
    assert decisao["motivo"]   # telegrafar é requisito -- nunca vazio numa decisão de verdade


def test_decidir_acao_reduz_cura_quando_curou_demais_e_hp_esta_bem():
    c = _combatente(1, classe="orador", inteligencia=20)
    luta = _luta(c)
    c.hp = c.s["hp_max"]
    chefe_ia.registrar_cura(luta, c.id)
    chefe_ia.registrar_cura(luta, c.id)

    decisao = chefe_ia.decidir_acao(luta, c.id)

    assert decisao["acao"] == "reduzir_cura"
    assert decisao["motivo"]


def test_decidir_acao_pressiona_quando_so_segurando_recurso():
    c = _combatente(1, classe="mago", inteligencia=20)
    luta = _luta(c)
    c.hp = c.s["hp_max"]
    chefe_ia.registrar_fracao_recurso(luta, c.id, 1.0)

    decisao = chefe_ia.decidir_acao(luta, c.id)

    assert decisao["acao"] == "pressionar"
    assert decisao["motivo"]


def test_decidir_acao_hp_baixo_vence_mesmo_curando_demais_e_segurando_recurso():
    """Ordem de prioridade fixa -- pouco HP sempre vence as outras duas,
    nunca sorteado entre as regras que bateram."""
    c = _combatente(1, classe="orador", inteligencia=20)
    luta = _luta(c)
    c.hp = 1
    chefe_ia.registrar_cura(luta, c.id)
    chefe_ia.registrar_cura(luta, c.id)
    chefe_ia.registrar_fracao_recurso(luta, c.id, 1.0)

    decisao = chefe_ia.decidir_acao(luta, c.id)

    assert decisao["acao"] == "priorizar_carregado"


def test_decidir_acao_reduzir_cura_vence_pressionar_quando_os_dois_batem():
    c = _combatente(1, classe="orador", inteligencia=20)
    luta = _luta(c)
    c.hp = c.s["hp_max"]
    chefe_ia.registrar_cura(luta, c.id)
    chefe_ia.registrar_cura(luta, c.id)
    chefe_ia.registrar_fracao_recurso(luta, c.id, 1.0)

    decisao = chefe_ia.decidir_acao(luta, c.id)

    assert decisao["acao"] == "reduzir_cura"


# ==================================================================
# Fronteira que não se mexe: os chefes da torre NÃO usam este motor
# nesta passada
# ==================================================================

def test_turno_do_chefe_nao_conhece_chefe_ia():
    """Este motor nasce GERAL -- os chefes da torre (1-10) herdam ele
    num cartão próprio, não nesta passada (só os espelhos, Step 3
    commit 3, são os primeiros a consultar de verdade). Se algum dia
    alguém plugar `chefe_ia` direto em `turno_do_chefe` sem passar por
    esse cartão, isto cai."""
    codigo = inspect.getsource(combate.Luta.turno_do_chefe)
    assert "chefe_ia" not in codigo


def test_historico_ia_nunca_e_populado_por_um_ataque_normal_do_chefe():
    """`turno_do_chefe` continua exatamente como era -- ataque normal,
    golpe carregado, tudo por random.random() puro, sem tocar em
    `historico_ia`. Prova indireta de que a fiação (commit 3) ainda não
    aconteceu: o registro so aparece se alguem chamar chefe_ia.registrar_*
    explicitamente."""
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta(c)
    luta.rodada = 2   # RODADA_1_SEM_CHEFE -- precisa avançar a rodada (armadilha do e687f27)

    luta.turno_do_chefe()

    assert luta.historico_ia == {}
