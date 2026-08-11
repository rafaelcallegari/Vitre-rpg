# tests/test_comercio.py
# Comércio dentro do diálogo (mercador/ferreiro): as funções puras de
# montagem de select, e os fluxos ponta-a-ponta dos painéis via interações
# fake (mesma estratégia de tests/test_dialogo.py e do smoke test manual
# usado antes de fechar o cartão — discord.py não conecta de verdade sem
# subir o bot, então não dá pra testar clique de botão real). Ver
# decisoes.md § Comércio dentro do diálogo.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula comercio.H (comercio.instalar), sem conectar em nada
import comercio
import database as db
import game_data
import npcs

MERCADOR = next(n for n in npcs.NPCS[1] if n["tipo"] == "mercador")
FERREIRO = next(n for n in npcs.NPCS[1] if n["tipo"] == "ferreiro")


def _interacao(user_id, mensagem=None):
    it = MagicMock()
    it.user.id = user_id
    it.response = MagicMock()
    it.response.is_done.return_value = False
    it.response.send_message = AsyncMock()
    it.response.edit_message = AsyncMock()
    it.followup.send = AsyncMock()
    it.message = mensagem or MagicMock()
    it.message.embeds = [MagicMock()]
    it.message.edit = AsyncMock()
    return it


def _botao(view, label):
    return next(c for c in view.children if getattr(c, "label", None) == label)


def _jogador(moedas=10000, andar=1, andar_max=1, **campos):
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, moedas=moedas, andar=andar, andar_max=andar_max, **campos)
    return db.get_jogador(1)


# ---------------- funções puras de montagem de select ----------------
def test_opcoes_compra_mostra_nome_e_preco():
    disponiveis = {"pocao_p": game_data.ITENS["pocao_p"]}
    opcoes = comercio._opcoes_compra(disponiveis)
    assert len(opcoes) == 1
    assert opcoes[0].value == "pocao_p"
    assert str(game_data.ITENS["pocao_p"]["preco"]) in opcoes[0].description


def test_opcoes_compra_capa_em_25():
    disponiveis = {f"item_{i}": {"nome": f"Item {i}", "preco": 10, "emoji": None} for i in range(40)}
    assert len(comercio._opcoes_compra(disponiveis)) == 25


def test_opcoes_venda_so_lista_o_que_o_jogador_tem_do_tipo_certo():
    _jogador()
    db.add_item(1, "pocao_p", 3)
    db.add_item(1, "presa_javali", 5)   # material -- não é consumível
    opcoes = comercio._opcoes_venda(1, ("consumivel",))
    assert [o.value for o in opcoes] == ["pocao_p"]


def test_opcoes_venda_respeita_vendavel_false():
    _jogador()
    db.add_item(1, "fragmento_selo", 1)   # não se vende (ver game_data)
    opcoes = comercio._opcoes_venda(1, ("material",))
    assert opcoes == []


def test_opcoes_equipamento_inventario_ignora_vendavel():
    """Desmanchar não olha `vendavel` -- só olha tipo arma/armadura."""
    _jogador()
    db.add_item(1, "espada_ferro", 1)
    opcoes = comercio._opcoes_equipamento_inventario(1)
    assert [o.value for o in opcoes] == ["espada_ferro"]


# ---------------- ShimCtx ----------------
def test_shimctx_manda_pela_response_na_primeira_chamada():
    it = _interacao(1)
    ctx = comercio.ShimCtx(it)
    asyncio.run(ctx.send("oi"))
    it.response.send_message.assert_called_once_with(content="oi")
    it.followup.send.assert_not_called()


def test_shimctx_usa_followup_se_a_response_ja_foi_usada():
    it = _interacao(1)
    it.response.is_done.return_value = True
    ctx = comercio.ShimCtx(it)
    asyncio.run(ctx.send(embed="e"))
    it.followup.send.assert_called_once_with(embed="e")
    it.response.send_message.assert_not_called()


# ---------------- fluxos ponta-a-ponta ----------------
def test_mercador_comprar_debita_moedas_e_entrega_o_item():
    _jogador(moedas=10000)
    view = comercio.MercadorView(1, MERCADOR, 1)
    it = _interacao(1)

    async def cenario():
        await _botao(view, "Comprar").callback(it)
        sel = it.response.edit_message.call_args.kwargs["view"].children[0]
        chave = sel.options[0].value
        it2 = _interacao(1, mensagem=it.message)
        await sel._ao_escolher(it2, chave)
        return chave, it2

    chave, it2 = asyncio.run(cenario())
    j = db.get_jogador(1)
    assert j["moedas"] < 10000
    assert db.tem_item(1, chave, 1)
    it2.message.edit.assert_called_once()   # painel principal restaurado


def test_mercador_vender_so_lista_consumivel_mesmo_com_equipamento_na_mochila():
    _jogador()
    db.add_item(1, "pocao_p", 2)
    db.add_item(1, "espada_ferro", 1)
    view = comercio.MercadorView(1, MERCADOR, 1)
    it = _interacao(1)

    asyncio.run(_botao(view, "Vender").callback(it))

    sel = it.response.edit_message.call_args.kwargs["view"].children[0]
    assert [o.value for o in sel.options] == ["pocao_p"]


def test_ferreiro_vender_so_lista_equipamento_mesmo_com_pocao_na_mochila():
    _jogador()
    db.add_item(1, "pocao_p", 2)
    db.add_item(1, "espada_ferro", 1)
    view = comercio.FerreiroView(1, FERREIRO, 1)
    it = _interacao(1)

    asyncio.run(_botao(view, "Vender").callback(it))

    sel = it.response.edit_message.call_args.kwargs["view"].children[0]
    assert [o.value for o in sel.options] == ["espada_ferro"]


def test_forjar_sem_ser_forjador_recusa_ephemeral_sem_abrir_select():
    _jogador(profissao="alquimia")
    view = comercio.FerreiroView(1, FERREIRO, 1)
    it = _interacao(1)

    asyncio.run(_botao(view, "Forjar").callback(it))

    assert it.response.edit_message.called is False
    it.response.send_message.assert_called_once()
    assert it.response.send_message.call_args.kwargs.get("ephemeral") is True
    assert "alquimia" in it.response.send_message.call_args.args[0].lower() or \
        "Alquimia" in it.response.send_message.call_args.args[0]


def test_forjar_como_forjador_com_material_crafta_de_verdade():
    _jogador(profissao="forja", prof_nivel=5, prof_xp=0)
    db.add_item(1, "presa_javali", 10)
    view = comercio.FerreiroView(1, FERREIRO, 1)
    it = _interacao(1)

    async def cenario():
        await _botao(view, "Forjar").callback(it)
        sel = it.response.edit_message.call_args.kwargs["view"].children[0]
        chave = sel.options[0].value
        it2 = _interacao(1, mensagem=it.message)
        await sel._ao_escolher(it2, chave)
        return chave

    chave = asyncio.run(cenario())
    assert db.tem_item(1, chave, 1)


def test_melhorar_so_lista_slots_equipados():
    _jogador(arma="espada_ferro", armadura=None)
    view = comercio.FerreiroView(1, FERREIRO, 1)
    it = _interacao(1)

    asyncio.run(_botao(view, "Melhorar").callback(it))

    sel = it.response.edit_message.call_args.kwargs["view"].children[0]
    assert [o.value for o in sel.options] == ["arma"]


def test_melhorar_sem_nada_equipado_recusa_ephemeral():
    _jogador()
    view = comercio.FerreiroView(1, FERREIRO, 1)
    it = _interacao(1)

    asyncio.run(_botao(view, "Melhorar").callback(it))

    it.response.send_message.assert_called_once()
    assert it.response.send_message.call_args.kwargs.get("ephemeral") is True


def test_desmanchar_lista_equipamento_da_mochila_e_executa():
    _jogador()
    db.add_item(1, "espada_ferro", 2)
    view = comercio.FerreiroView(1, FERREIRO, 1)
    it = _interacao(1)

    async def cenario():
        await _botao(view, "Desmanchar").callback(it)
        sel = it.response.edit_message.call_args.kwargs["view"].children[0]
        it2 = _interacao(1, mensagem=it.message)
        await sel._ao_escolher(it2, "espada_ferro")

    asyncio.run(cenario())
    assert db.tem_item(1, "espada_ferro", 1)   # tinha 2, desmanchou 1


def test_outro_jogador_e_negado_com_ephemeral_e_painel_nao_muda():
    _jogador()
    view = comercio.MercadorView(1, MERCADOR, 1)
    it_outro = _interacao(999)

    permitido = asyncio.run(view.interaction_check(it_outro))

    assert permitido is False
    it_outro.response.send_message.assert_called_once()
    assert it_outro.response.send_message.call_args.kwargs.get("ephemeral") is True


def test_sair_desabilita_todos_os_botoes():
    # `view.is_finished()` não dá pra checar aqui: discord.py só inicializa
    # o Future interno de stop() quando a view passa pelo dispatch de
    # verdade (real conexão) -- fora disso `stop()` é um no-op silencioso.
    # `disabled=True` em todos os filhos é o efeito que interessa e que dá
    # pra observar sem subir o bot.
    _jogador()
    view = comercio.MercadorView(1, MERCADOR, 1)
    it = _interacao(1)

    asyncio.run(_botao(view, "Sair").callback(it))

    assert all(c.disabled for c in view.children)


def test_ferreiro_tem_seis_botoes_em_tres_fileiras():
    view = comercio.FerreiroView(1, FERREIRO, 1)
    por_fileira = {}
    for c in view.children:
        por_fileira.setdefault(c.row, []).append(c.label)
    assert sorted(por_fileira[0]) == ["Comprar", "Vender"]
    assert sorted(por_fileira[1]) == ["Desmanchar", "Forjar", "Melhorar"]
    assert por_fileira[2] == ["Sair"]


def test_mercador_tem_tres_botoes_em_duas_fileiras():
    view = comercio.MercadorView(1, MERCADOR, 1)
    por_fileira = {}
    for c in view.children:
        por_fileira.setdefault(c.row, []).append(c.label)
    assert sorted(por_fileira[0]) == ["Comprar", "Vender"]
    assert por_fileira[1] == ["Sair"]


def test_rpg_loja_redireciona_em_vez_de_listar_itens():
    ctx = MagicMock()
    ctx.send = AsyncMock()
    asyncio.run(bot.loja.callback(ctx))
    texto = ctx.send.call_args.args[0]
    assert "não existe mais" in texto
    assert "rpg falar" in texto
