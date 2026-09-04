# tests/test_solo_vs_party.py
# Step 2d, commit 1: o motor de solo vs party. `Luta.em_party` era uma
# @property recalculada de `len(self.participantes)` -- valor já era fixo
# na prática (participantes nunca muda depois do __init__), virou atributo
# congelado no momento da criação pra ficar fixo por CONSTRUÇÃO, não por
# coincidência. O Clérigo (commit 3) depende disso: uma party que perde
# todo mundo menos ele continua sendo party, nunca vira solo no meio da
# luta. Ver decisoes.md § Step 2d.
import bot
import combate
import database as db

CHEFE_TESTE = {"nome": "Testinho", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0}


def _combatente(user_id, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


def test_luta_solo_e_em_party_false():
    c = _combatente(1, classe="orador", inteligencia=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    assert luta.em_party is False


def test_luta_com_dois_ou_mais_e_em_party_true():
    c1 = _combatente(1, classe="orador", inteligencia=20)
    c2 = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([c1, c2], CHEFE_TESTE, andar_num=1)

    assert luta.em_party is True


def test_party_que_cai_pra_um_sobrevivente_continua_em_party():
    """O caso que o cartão pediu explicitamente -- uma party de 3 onde só o
    clérigo fica de pé continua sendo party pra ele, nunca vira solo."""
    c1 = _combatente(1, classe="orador", inteligencia=20)
    c2 = _combatente(2, classe="guerreiro", forca=20)
    c3 = _combatente(3, classe="mago", inteligencia=20)
    luta = combate.Luta([c1, c2, c3], CHEFE_TESTE, andar_num=1)

    c2.caiu = True
    c3.caiu = True

    assert [c.id for c in luta.ativos] == [c1.id]   # só o orador continua ativo
    assert luta.em_party is True                     # mas a luta continua sendo party


def test_em_party_nao_reconsulta_participantes_durante_o_combate():
    """Trava o comportamento explicitamente: mesmo se `luta.participantes`
    fosse mutado depois da criação (não deveria, mas se alguém um dia
    fizer isso por engano), `em_party` já está congelado e não muda."""
    c1 = _combatente(1, classe="orador", inteligencia=20)
    c2 = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([c1, c2], CHEFE_TESTE, andar_num=1)

    assert luta.em_party is True
    luta.participantes = [c1]   # simula uma mutação indevida
    assert luta.em_party is True   # continua True -- não é mais recalculado
