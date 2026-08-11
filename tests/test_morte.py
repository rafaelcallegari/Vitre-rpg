# tests/test_morte.py
# processar_morte trava a penalidade de morte: 20% das moedas, HP de volta
# a 30% do máximo, contador de mortes, e a reconquista do andar acima do
# Selo (ver decisoes.md § Morte e reconquista / Roguelike acima do Selo).
import asyncio

import andares_altos
import database as db

# import direto e seguro -- bot.run(TOKEN) mora atrás de `if __name__ ==
# "__main__"` desde o cartão da guarda de main (ver
# tests/test_bot_seguro.py e decisoes.md § Guarda de main).
import bot


def _jogador_e_stats(andar=5, andar_max=5, moedas=1000, mortes=0):
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, andar=andar, andar_max=andar_max, moedas=moedas, mortes=mortes)
    j = db.get_jogador(1)
    s = {"hp_max": 200}
    return j, s


def test_penalidade_normal_tira_20_por_cento_das_moedas_e_soma_uma_morte():
    j, s = _jogador_e_stats(moedas=1000, mortes=2)
    perda = bot.processar_morte(j, s)
    assert perda == 200

    atualizado = db.get_jogador(1)
    assert atualizado["moedas"] == 800
    assert atualizado["mortes"] == 3


def test_penalidade_normal_devolve_hp_a_30_por_cento_do_maximo():
    j, s = _jogador_e_stats()
    bot.processar_morte(j, s)
    assert db.get_jogador(1)["hp"] == int(s["hp_max"] * 0.3)


def test_morte_no_ou_abaixo_do_selo_nao_mexe_no_andar():
    j, s = _jogador_e_stats(andar=andares_altos.ANDAR_ACIMA_DO_SELO, andar_max=andares_altos.ANDAR_ACIMA_DO_SELO)
    bot.processar_morte(j, s)
    atualizado = db.get_jogador(1)
    assert atualizado["andar"] == andares_altos.ANDAR_ACIMA_DO_SELO
    assert atualizado["andar_max"] == andares_altos.ANDAR_ACIMA_DO_SELO


def test_morte_acima_do_selo_derruba_andar_e_andar_max_pro_10_sem_zerar_chefes():
    andar_alto = andares_altos.ANDAR_ACIMA_DO_SELO + 3
    j, s = _jogador_e_stats(andar=andar_alto, andar_max=andares_altos.ANDAR_ACIMA_DO_SELO + 5)
    for _ in range(7):
        db.registrar_vitoria_chefe(1, andar_alto)

    bot.processar_morte(j, s)

    atualizado = db.get_jogador(1)
    assert atualizado["andar"] == andares_altos.ANDAR_ACIMA_DO_SELO
    assert atualizado["andar_max"] == andares_altos.ANDAR_ACIMA_DO_SELO
    # a torre esquece onde o jogador estava, nunca quem ele matou
    assert db.vezes_derrotado_chefe(1, andar_alto) == 7


def test_a_processar_morte_delega_pra_versao_sincrona_e_devolve_a_mesma_perda():
    """Sem pytest-asyncio na suíte -- roda a corrotina até o fim com
    asyncio.run() em vez de declarar o teste como `async def`."""
    j, s = _jogador_e_stats(moedas=500)
    perda = asyncio.run(bot.a_processar_morte(j, s))
    assert perda == 100
    assert db.get_jogador(1)["moedas"] == 400
