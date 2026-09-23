# tests/test_principades.py
# Step F, commit 3: Principades. Cidade grande -- compra espólio ACIMA do
# valor de face (`principades.BONUS_COMPRA_ESPOLIO`) e vende material de
# profissão a preço calibrado (`principades.MULTIPLICADOR_COMPRA_MATERIAL`).
# Nunca vende arma, armadura nem encantamento -- isso continua sendo só da
# torre (Selen, as 24 elementais, o ferreiro, o encantador). Ver decisoes.md
# § Step F.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import database as db
import game_data
import mundo
import principades

ITENS = game_data.ITENS


def _jogador(user_id=1, mundo_atual=None, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if mundo_atual is not None:
        campos["mundo"] = mundo_atual
    if campos:
        db.atualizar_jogador(user_id, **campos)
    return db.get_jogador(user_id)


def _ctx(user_id=1):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    return ctx


def _msg(ctx):
    return ctx.send.call_args.args[0]


# ==================================================================
# materiais de profissão -- catálogo e preço
# ==================================================================

def test_materiais_a_venda_e_so_tipo_material_compravel():
    catalogo = principades.materiais_a_venda()
    for k in catalogo:
        assert ITENS[k]["tipo"] == "material"
        assert ITENS[k].get("loja", True)
        assert ITENS[k].get("vendavel", True)


def test_materiais_de_quest_ou_fabricacao_ficam_de_fora():
    catalogo = principades.materiais_a_venda()
    assert "flor_do_andar_1" not in catalogo   # loja: False
    assert "molde_do_manto" not in catalogo    # loja: False
    assert "fragmento_selo" not in catalogo    # vendavel: False


def test_preco_de_venda_e_o_base_vezes_o_multiplicador():
    catalogo = principades.materiais_a_venda()
    assert catalogo["presa_javali"]["preco"] == ITENS["presa_javali"]["preco"] * principades.MULTIPLICADOR_COMPRA_MATERIAL


def test_nenhum_material_a_venda_e_arma_armadura_ou_encantamento():
    catalogo = principades.materiais_a_venda()
    tipos_proibidos = {"arma", "armadura"}
    for k in catalogo:
        assert ITENS[k]["tipo"] not in tipos_proibidos


# ==================================================================
# comprar material em Principades
# ==================================================================

def test_comprar_material_em_principades_funciona():
    _jogador(1, mundo_atual=mundo.PRINCIPADES, andar=15, andar_max=15, moedas=100000)
    ctx = _ctx(1)
    asyncio.run(bot.comprar.callback(ctx, argumento="presa de javali 1"))
    assert db.tem_item(1, "presa_javali", 1)
    custo_esperado = ITENS["presa_javali"]["preco"] * principades.MULTIPLICADOR_COMPRA_MATERIAL
    assert db.get_jogador(1)["moedas"] == 100000 - custo_esperado


def test_comprar_material_fora_de_principades_e_recusado():
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15, moedas=100000)
    ctx = _ctx(1)
    asyncio.run(bot.comprar.callback(ctx, argumento="presa de javali 1"))
    assert not db.tem_item(1, "presa_javali", 1)


def test_comprar_material_dentro_da_torre_e_recusado_com_dica():
    _jogador(1, andar=1, andar_max=5, moedas=100000)
    ctx = _ctx(1)
    asyncio.run(bot.comprar.callback(ctx, argumento="presa de javali 1"))
    assert not db.tem_item(1, "presa_javali", 1)
    assert "principades" in _msg(ctx).lower()


def test_principades_recusa_comprar_arma():
    _jogador(1, mundo_atual=mundo.PRINCIPADES, andar=15, andar_max=15, moedas=100000)
    ctx = _ctx(1)
    asyncio.run(bot.comprar.callback(ctx, argumento="lamina do selo 1"))
    assert not db.tem_item(1, "lamina_selo", 1)


# ==================================================================
# comprar espólio (compra não existe -- só cai de dungeon)
# ==================================================================

def test_principades_nao_vende_espolio_so_compra():
    catalogo = principades.materiais_a_venda()
    espolios = [k for k in ITENS if ITENS[k]["tipo"] == "espolio"]
    for k in espolios:
        assert k not in catalogo


# ==================================================================
# vender espólio em Principades -- acima do valor de face
# ==================================================================

def _primeiro_espolio():
    return next(k for k, v in ITENS.items() if v["tipo"] == "espolio")


def test_vender_espolio_em_principades_paga_bonus():
    espolio = _primeiro_espolio()
    _jogador(1, mundo_atual=mundo.PRINCIPADES, andar=15, andar_max=15)
    db.add_item(1, espolio, 1)
    ctx = _ctx(1)
    asyncio.run(bot.vender.callback(ctx, argumento=f"{ITENS[espolio]['nome']} 1"))
    esperado = principades.preco_compra_espolio(ITENS[espolio]["preco"])
    assert db.get_jogador(1)["moedas"] == esperado
    assert esperado > ITENS[espolio]["preco"]


def test_vender_espolio_fora_de_principades_paga_preco_cheio_regressao():
    espolio = _primeiro_espolio()
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15)
    db.add_item(1, espolio, 1)
    ctx = _ctx(1)
    asyncio.run(bot.vender.callback(ctx, argumento=f"{ITENS[espolio]['nome']} 1"))
    assert db.get_jogador(1)["moedas"] == ITENS[espolio]["preco"]


def test_vender_material_em_principades_nao_ganha_bonus():
    """O bônus é só pra espólio -- material sempre vendeu a preço cheio
    em qualquer lugar (ver bot.vender), Principades não muda isso."""
    _jogador(1, mundo_atual=mundo.PRINCIPADES, andar=15, andar_max=15)
    db.add_item(1, "presa_javali", 1)
    ctx = _ctx(1)
    asyncio.run(bot.vender.callback(ctx, argumento="presa de javali 1"))
    assert db.get_jogador(1)["moedas"] == ITENS["presa_javali"]["preco"]


# ==================================================================
# regressão -- torre e Mirante não mudam
# ==================================================================

def test_comprar_na_torre_continua_igual_regressao():
    _jogador(1, andar=1, andar_max=5, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.comprar.callback(ctx, argumento="pocao pequena 1"))
    assert db.tem_item(1, "pocao_p", 1)


def test_comprar_no_mirante_continua_recusado_regressao():
    _jogador(1, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.comprar.callback(ctx, argumento="presa de javali 1"))
    assert not db.tem_item(1, "presa_javali", 1)
