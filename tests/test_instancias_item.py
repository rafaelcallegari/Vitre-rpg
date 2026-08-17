# tests/test_instancias_item.py
# Três lacunas na mesma área (tabela `instancias`): desencantar reembolsava
# em vez de cobrar, `rpg vender` ignorava o bônus da joia/encantamento, e
# duas instâncias da mesma chave (ex.: dois anéis do Joalheiro) deixavam uma
# delas presa -- inalcançável por `rpg equipar`/`rpg vender`. Ver
# decisoes.md § Instâncias de item.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot
import database as db


def _jogador(**campos):
    db.criar_jogador(1, "Alice")
    if campos:
        db.atualizar_jogador(1, **campos)
    return db.get_jogador(1)


def _ctx():
    ctx = MagicMock()
    ctx.author.id = 1
    ctx.send = AsyncMock()
    return ctx


# ---------------------------------------------------- 1. desencantar cobra
def test_desencantar_cobra_metade_do_custo_do_bonus_por_valor():
    esperado = {1: 200, 2: 450, 3: 800, 4: 1300, 5: 1900, 6: 2600, 7: 3400}
    for bonus, custo in esperado.items():
        _jogador(moedas=custo, andar=1, arma="espada_ferro")
        instancia_id = db.criar_instancia(1, "espada_ferro")
        db.definir_encantamento(instancia_id, "forca", bonus)
        db.atualizar_jogador(1, arma_instancia_id=instancia_id)

        asyncio.run(bot.bot.get_command("desencantar").callback(_ctx(), argumento="arma"))

        assert db.get_jogador(1)["moedas"] == 0, f"bonus {bonus} devia cobrar {custo}"
        assert db.get_instancia(instancia_id)["encantamento_atributo"] is None


def test_desencantar_recusa_sem_saldo_e_nao_mexe_no_encantamento():
    _jogador(moedas=100, andar=1, arma="espada_ferro")
    instancia_id = db.criar_instancia(1, "espada_ferro")
    db.definir_encantamento(instancia_id, "forca", 7)   # custa 3400
    db.atualizar_jogador(1, arma_instancia_id=instancia_id)

    ctx = _ctx()
    asyncio.run(bot.bot.get_command("desencantar").callback(ctx, argumento="arma"))

    assert db.get_jogador(1)["moedas"] == 100   # não cobrou nada
    instancia = db.get_instancia(instancia_id)
    assert instancia["encantamento_atributo"] == "forca"   # continua encantada
    texto = ctx.send.call_args.args[0]
    assert "3300" in texto   # faltam 3400 - 100


# ---------------------------------------------------- 2. venda por camada
def test_preco_de_venda_da_joia_escala_com_o_bonus():
    _jogador(moedas=0, andar=2)
    db.criar_instancia(1, "anel_joia", joia_atributo="inteligencia", joia_valor=1)
    asyncio.run(bot.vender.callback(_ctx(), argumento="anel lapidado"))
    preco_bonus_1 = db.get_jogador(1)["moedas"]

    db.atualizar_jogador(1, moedas=0)
    db.criar_instancia(1, "anel_joia", joia_atributo="inteligencia", joia_valor=7)
    asyncio.run(bot.vender.callback(_ctx(), argumento="anel lapidado"))
    preco_bonus_7 = db.get_jogador(1)["moedas"]

    assert preco_bonus_1 == 200    # metade de CUSTO_MOEDAS_POR_BONUS[1] = 400
    assert preco_bonus_7 == 3400   # metade de CUSTO_MOEDAS_POR_BONUS[7] = 6800
    assert preco_bonus_7 > preco_bonus_1


def test_encantamento_soma_no_preco_de_venda_em_vez_de_sumir():
    _jogador(moedas=0, andar=1)
    db.criar_instancia(1, "espada_ferro")
    asyncio.run(bot.vender.callback(_ctx(), argumento="espada de ferro"))
    preco_sem_encanto = db.get_jogador(1)["moedas"]

    db.atualizar_jogador(1, moedas=0)
    instancia_id = db.criar_instancia(1, "espada_ferro")
    db.definir_encantamento(instancia_id, "forca", 3)   # metade de 1600 = 800
    asyncio.run(bot.vender.callback(_ctx(), argumento="espada de ferro"))
    preco_com_encanto = db.get_jogador(1)["moedas"]

    assert preco_com_encanto == preco_sem_encanto + 800


# ------------------------------------------ 3. duplicata da mesma chave
def test_duas_instancias_da_mesma_chave_sao_ambas_alcancaveis_por_equipar():
    _jogador(moedas=0, andar=2)
    id1 = db.criar_instancia(1, "anel_joia", joia_atributo="forca", joia_valor=3)
    id2 = db.criar_instancia(1, "anel_joia", joia_atributo="inteligencia", joia_valor=5)

    asyncio.run(bot.equipar.callback(_ctx(), texto="anel lapidado 1"))
    assert db.get_jogador(1)["anel_instancia_id"] == id1

    db.atualizar_jogador(1, anel=None, anel_instancia_id=None)   # desequipa sem tocar nas instâncias

    asyncio.run(bot.equipar.callback(_ctx(), texto="anel lapidado 2"))
    assert db.get_jogador(1)["anel_instancia_id"] == id2


def test_duas_instancias_da_mesma_chave_sao_ambas_alcancaveis_por_vender():
    _jogador(moedas=0, andar=2)
    id1 = db.criar_instancia(1, "anel_joia", joia_atributo="forca", joia_valor=1)        # venda 200
    id2 = db.criar_instancia(1, "anel_joia", joia_atributo="inteligencia", joia_valor=7)  # venda 3400

    # vende o MAIS ANTIGO primeiro -- era o que ficava preso atrás do mais
    # recente antes da correção (dict colapsava pra só o último id).
    asyncio.run(bot.vender.callback(_ctx(), argumento="anel lapidado 1"))
    assert db.get_jogador(1)["moedas"] == 200
    assert db.get_instancia(id1) is None
    assert db.get_instancia(id2) is not None

    asyncio.run(bot.vender.callback(_ctx(), argumento="anel lapidado"))   # só sobrou 1, índice default
    assert db.get_jogador(1)["moedas"] == 200 + 3400
    assert db.get_instancia(id2) is None


def test_equipar_alem_da_quantidade_de_instancias_recusa_com_mensagem_clara():
    _jogador(moedas=0, andar=2)
    db.criar_instancia(1, "anel_joia", joia_atributo="forca", joia_valor=1)

    ctx = _ctx()
    asyncio.run(bot.equipar.callback(ctx, texto="anel lapidado 2"))
    assert db.get_jogador(1)["anel"] is None   # não equipou nada
    texto = ctx.send.call_args.args[0]
    assert "1" in texto and "inventario" in texto


# ---------------------------------------------------- 4. inventário mostra
def test_inventario_mostra_atributo_e_valor_da_joia():
    _jogador(moedas=0, andar=2)
    db.criar_instancia(1, "anel_joia", joia_atributo="inteligencia", joia_valor=7)

    ctx = _ctx()
    asyncio.run(bot.inventario.callback(ctx))

    e = ctx.send.call_args.kwargs["embed"]
    campo = next(f for f in e.fields if "Anel Lapidado" in f.name)
    assert "INT" in campo.name and "+7" in campo.name


def test_inventario_numera_instancias_duplicadas_da_mesma_chave():
    _jogador(moedas=0, andar=2)
    db.criar_instancia(1, "anel_joia", joia_atributo="forca", joia_valor=1)
    db.criar_instancia(1, "anel_joia", joia_atributo="inteligencia", joia_valor=5)

    ctx = _ctx()
    asyncio.run(bot.inventario.callback(ctx))

    e = ctx.send.call_args.kwargs["embed"]
    nomes = [f.name for f in e.fields if "Anel Lapidado" in f.name]
    assert len(nomes) == 2
    assert any("#1" in n for n in nomes)
    assert any("#2" in n for n in nomes)


def test_inventario_nao_numera_quando_so_tem_uma_instancia_da_chave():
    _jogador(moedas=0, andar=1)
    db.criar_instancia(1, "espada_ferro", nivel_melhoria=2)

    ctx = _ctx()
    asyncio.run(bot.inventario.callback(ctx))

    e = ctx.send.call_args.kwargs["embed"]
    campo = next(f for f in e.fields if "Espada de Ferro" in f.name)
    assert "#" not in campo.name
    assert "+2" in campo.name
