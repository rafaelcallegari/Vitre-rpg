# tests/test_multi_inimigo.py
# Step A: multi-inimigo no motor de combate -- refatoração pura, nada muda
# pra quem já joga hoje (nenhum chefe existente ganha companhia, nenhum
# conteúdo novo). A suíte existente inteira é a rede de segurança principal
# (roda sem alteração nenhuma -- ver decisoes.md § Step A); este arquivo só
# cobre o mínimo novo que o cartão pede: dois inimigos de verdade dentro de
# uma `Luta`, com estado independente.
import asyncio

import bot  # noqa: F401 -- popula combate.H
import combate
import condicoes
import database as db
import game_data


CHEFE_A = {"nome": "Inimigo A", "hp": 100, "atk": 10, "def": 0, "xp": 0, "moedas": 0}
CHEFE_B = {"nome": "Inimigo B", "hp": 80, "atk": 5, "def": 0, "xp": 0, "moedas": 0}


def _combatente(user_id, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


# ==================================================================
# Commit 1 -- a Luta aceita uma lista
# ==================================================================

def test_luta_aceita_lista_de_inimigos_um_objeto_por_dict():
    c = _combatente(1)
    luta = combate.Luta([c], [CHEFE_A, CHEFE_B], andar_num=1)

    assert len(luta.inimigos) == 2
    assert luta.inimigos[0].id == "chefe"
    assert luta.inimigos[1].id == "chefe_1"
    assert luta.inimigos[0].nome == "Inimigo A"
    assert luta.inimigos[1].nome == "Inimigo B"
    assert luta.inimigos[0].hp == luta.inimigos[0].hp_max == 100
    assert luta.inimigos[1].hp == luta.inimigos[1].hp_max == 80


def test_chefe_unico_dict_continua_virando_lista_de_um_ponte_intacta():
    """Todo chamador de hoje (raide.py, dungeon.py, iniciar_luta) passa um
    dict sozinho -- "chefe sozinho vira lista de um" precisa ser 100%
    transparente: luta.chefe/hp_chefe/hp_chefe_max continuam funcionando
    exatamente como sempre, porque são a mesma memória de inimigos[0]."""
    c = _combatente(1)
    luta = combate.Luta([c], CHEFE_A, andar_num=1)

    assert len(luta.inimigos) == 1
    assert luta.inimigos[0].id == "chefe"
    assert luta.chefe is luta.inimigos[0].dados
    assert luta.hp_chefe == luta.inimigos[0].hp == 100

    luta.hp_chefe -= 30   # escreve pela ponte antiga
    assert luta.inimigos[0].hp == 70   # aparece no objeto novo


def test_matar_um_inimigo_nao_encerra_a_luta_matar_todos_encerra():
    c = _combatente(1)
    luta = combate.Luta([c], [CHEFE_A, CHEFE_B], andar_num=1)
    assert len(luta.inimigos_ativos) == 2

    luta.inimigos[0].hp = 0
    assert len(luta.inimigos_ativos) == 1
    assert luta.inimigos_ativos == [luta.inimigos[1]]

    luta.inimigos[1].hp = 0
    assert luta.inimigos_ativos == []


def test_fim_da_luta_so_dispara_quando_todos_os_inimigos_morrem():
    c = _combatente(1)
    luta = combate.Luta([c], [CHEFE_A, CHEFE_B], andar_num=1)
    painel = combate.PainelLuta(luta)

    luta.inimigos[0].hp = 0
    assert asyncio.run(painel.fim_da_luta()) is None   # um morreu, o outro segue

    luta.inimigos[1].hp = 0
    resultado = asyncio.run(painel.fim_da_luta())
    assert resultado is not None   # os dois mortos -- luta termina


def test_hp_escala_por_inimigo_independente_com_dois_donos():
    """Decisão do Step A (ver decisoes.md): cada inimigo escala o próprio
    HP por dono, igual sempre escalou pro chefe único -- não só o
    principal, não fixo pro grupo."""
    c1 = _combatente(1)
    c2 = _combatente(2)
    luta = combate.Luta([c1, c2], [CHEFE_A, CHEFE_B], andar_num=1)

    assert luta.inimigos[0].hp == 100 * 2
    assert luta.inimigos[1].hp == 80 * 2


def test_hp_fixo_acima_do_selo_vale_pra_cada_inimigo():
    c1 = _combatente(1)
    c2 = _combatente(2)
    luta = combate.Luta([c1, c2], [CHEFE_A, CHEFE_B], andar_num=11)

    assert luta.inimigos[0].hp == 100
    assert luta.inimigos[1].hp == 80
