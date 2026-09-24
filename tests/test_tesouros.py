# tests/test_tesouros.py
# Os dez tesouros de chefe depois do corte do Salão (ver decisoes.md §
# Corte do Salão da Guilda): continuam caindo a 100% nos chefes 1-10,
# continuam sem venda, craft ou equipamento, e agora são chave de
# sidequest do próprio andar -- por isso também não entram no baú.
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import bot  # noqa: F401 -- side effect: liga H de guildas.py via instalar()
import database as db
import guildas
import profissoes
from game_data import ANDARES, ITENS, andar_do_tesouro


def _catalogo():
    return [k for k, v in ITENS.items() if v.get("tipo") == "tesouro"]


# ------------------------------------------------------- drop dos chefes
def test_cada_chefe_de_1_a_10_solta_um_tesouro_distinto_100_por_cento():
    catalogo = set(_catalogo())
    assert len(catalogo) == 10

    usados = set()
    for andar in range(1, 11):
        drops = dict(ANDARES[andar]["boss"]["drops"])
        assert "fragmento_selo" in drops and drops["fragmento_selo"] == 1.0

        tesouros_do_andar = [item for item in drops if item in catalogo]
        assert len(tesouros_do_andar) == 1, f"andar {andar} deveria soltar exatamente 1 tesouro"
        item = tesouros_do_andar[0]
        assert drops[item] == 1.0
        assert item not in usados, "cada tesouro só pode pertencer a um andar"
        usados.add(item)
        assert andar_do_tesouro(item) == andar

    assert usados == catalogo, "todo tesouro do catálogo precisa vir de algum andar 1-10"


def test_andares_11_a_15_nao_ganham_tesouro():
    catalogo = set(_catalogo())
    for andar in range(11, 16):
        drops = dict(ANDARES[andar]["boss"]["drops"])
        assert not (catalogo & set(drops))


def test_andar_do_tesouro_de_item_que_nao_e_tesouro_e_none():
    assert andar_do_tesouro("pocao_p") is None


# ------------------------------------------- tesouro não é X, Y, Z
def test_tesouro_nao_e_vendavel_nem_de_loja():
    for chave in _catalogo():
        dado = ITENS[chave]
        assert dado.get("vendavel", True) is False
        assert dado.get("loja", True) is False


def test_tesouro_nao_e_equipavel():
    tipos_equipaveis = ("arma", "armadura", "anel", "colar")
    for chave in _catalogo():
        assert ITENS[chave]["tipo"] not in tipos_equipaveis


def test_tesouro_nao_entra_em_receita_de_profissao():
    catalogo = set(_catalogo())
    assert not (catalogo & set(profissoes.RECEITAS))
    for receita in profissoes.RECEITAS.values():
        assert not (catalogo & set(receita["materiais"]))


# ------------------------------------------------------ nem vai pro baú
def test_tesouro_nao_entra_no_bau_e_fica_na_mochila():
    """Tesouro já não troca (`rpg trade` recusa não vendável); o baú seria o
    jeito de passar a chave de sidequest pra outro membro."""
    db.criar_jogador(1, "Jogadora")
    guilda_id = db.criar_guilda("Ordem", 1, 1, cargo_id=10, canal_id=20)
    db.add_item(1, "coroa_velha", 1)
    ctx = SimpleNamespace(author=SimpleNamespace(id=1), send=AsyncMock(), guild=None)

    asyncio.run(guildas.acao_depositar(ctx, db.get_jogador(1), "coroa velha"))

    assert db.get_bau(guilda_id) == []
    assert db.tem_item(1, "coroa_velha", 1)
    texto = ctx.send.await_args.args[0]
    assert "andar 1" in texto


def test_item_comum_continua_entrando_no_bau():
    db.criar_jogador(1, "Jogadora")
    guilda_id = db.criar_guilda("Ordem", 1, 1, cargo_id=10, canal_id=20)
    db.add_item(1, "pocao_p", 2)
    ctx = SimpleNamespace(author=SimpleNamespace(id=1), send=AsyncMock(), guild=None)

    asyncio.run(guildas.acao_depositar(ctx, db.get_jogador(1), "pocao pequena 2"))

    assert [(i["item"], i["qtd"]) for i in db.get_bau(guilda_id)] == [("pocao_p", 2)]
