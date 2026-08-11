# tests/test_comercio.py
# Comércio/serviço dentro do diálogo (mercador/ferreiro/taverneiro/
# carroceiro): as funções puras de montagem de select, e os fluxos
# ponta-a-ponta dos painéis via interações fake (mesma estratégia de
# tests/test_dialogo.py e do smoke test manual usado antes de fechar o
# cartão — discord.py não conecta de verdade sem subir o bot, então não dá
# pra testar clique de botão real). Ver decisoes.md § Comércio dentro do
# diálogo e § Ações de diálogo de todos os NPCs.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula comercio.H (comercio.instalar), sem conectar em nada
import comercio
import database as db
import game_data
import npcs

MERCADOR = next(n for n in npcs.NPCS[1] if n["tipo"] == "mercador")     # Elna, 1 pergunta
FERREIRO = next(n for n in npcs.NPCS[1] if n["tipo"] == "ferreiro")     # Torv, 1 pergunta
TAVERNEIRO = next(n for n in npcs.NPCS[1] if n["tipo"] == "taverneiro")  # Sera, 2 perguntas
CARROCEIRO = next(n for n in npcs.NPCS[3] if n["tipo"] == "carroceiro")  # Bramm, 0 perguntas


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


def _jogador(moedas=10000, andar=1, andar_max=1, pronome="elu", **campos):
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, moedas=moedas, andar=andar, andar_max=andar_max, pronome=pronome, **campos)
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


def test_opcoes_destino_exclui_o_andar_atual_e_mostra_preco():
    j = _jogador(andar=1, andar_max=3)
    opcoes = comercio._opcoes_destino(j)
    valores = [o.value for o in opcoes]
    assert "1" not in valores          # andar atual não é destino de si mesmo
    assert set(valores) == {"2", "3"}


def test_opcoes_destino_mostra_gratis_com_carroca_ativa(monkeypatch):
    j = _jogador(andar=1, andar_max=3)
    monkeypatch.setitem(comercio.H, "carroca_ativa", lambda: (True, None))
    monkeypatch.setitem(comercio.H, "conheceu_bramm", lambda j: True)
    opcoes = comercio._opcoes_destino(j)
    assert all(o.description == "grátis" for o in opcoes)


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


# ---------------- fluxos ponta-a-ponta: compra/venda ----------------
def test_mercador_comprar_pede_quantidade_antes_de_debitar():
    _jogador(moedas=10000)
    view = comercio.MercadorView(1, MERCADOR, 1, "elu")
    it = _interacao(1)

    async def cenario():
        await _botao(view, "Comprar").callback(it)
        sel_item = it.response.edit_message.call_args.kwargs["view"].children[0]
        chave = sel_item.options[0].value

        it2 = _interacao(1, mensagem=it.message)
        await sel_item._ao_escolher(it2, chave)
        return chave, it2

    chave, it2 = asyncio.run(cenario())
    assert db.get_jogador(1)["moedas"] == 10000
    sel_qtd = it2.response.edit_message.call_args.kwargs["view"].children[0]
    valores = [o.value for o in sel_qtd.options]
    assert valores == ["1", "5", "10", "25"]
    preco = game_data.ITENS[chave]["preco"]
    assert f"{preco * 5} 🪙 no total" == sel_qtd.options[1].description


def test_mercador_comprar_5_em_uma_interacao_so():
    _jogador(moedas=10000)
    view = comercio.MercadorView(1, MERCADOR, 1, "elu")
    it = _interacao(1)

    async def cenario():
        await _botao(view, "Comprar").callback(it)
        sel_item = it.response.edit_message.call_args.kwargs["view"].children[0]
        chave = sel_item.options[0].value

        it2 = _interacao(1, mensagem=it.message)
        await sel_item._ao_escolher(it2, chave)
        sel_qtd = it2.response.edit_message.call_args.kwargs["view"].children[0]

        it3 = _interacao(1, mensagem=it2.message)
        await sel_qtd._ao_escolher(it3, "5")
        return chave, it3

    chave, it3 = asyncio.run(cenario())
    preco = game_data.ITENS[chave]["preco"]
    j = db.get_jogador(1)
    assert j["moedas"] == 10000 - preco * 5
    assert db.tem_item(1, chave, 5)
    it3.message.edit.assert_called_once()   # painel principal restaurado


def test_mercador_comprar_mais_do_que_as_moedas_permitem_recusa_igual_ao_comando():
    _jogador(moedas=1)   # não cobre nem 1 unidade da poção mais barata
    view = comercio.MercadorView(1, MERCADOR, 1, "elu")
    it = _interacao(1)

    async def cenario():
        await _botao(view, "Comprar").callback(it)
        sel_item = it.response.edit_message.call_args.kwargs["view"].children[0]
        chave = sel_item.options[0].value

        it2 = _interacao(1, mensagem=it.message)
        await sel_item._ao_escolher(it2, chave)
        sel_qtd = it2.response.edit_message.call_args.kwargs["view"].children[0]

        it3 = _interacao(1, mensagem=it2.message)
        await sel_qtd._ao_escolher(it3, "1")
        return chave, it3

    chave, it3 = asyncio.run(cenario())
    assert db.get_jogador(1)["moedas"] == 1          # nada foi debitado
    assert not db.tem_item(1, chave, 1)               # nada foi entregue
    it3.response.send_message.assert_called_once()    # recusa do comprar() de verdade, via ShimCtx
    assert "faltam" in it3.response.send_message.call_args.kwargs["content"].lower()


def test_mercador_vender_so_lista_consumivel_mesmo_com_equipamento_na_mochila():
    _jogador()
    db.add_item(1, "pocao_p", 2)
    db.add_item(1, "espada_ferro", 1)
    view = comercio.MercadorView(1, MERCADOR, 1, "elu")
    it = _interacao(1)

    asyncio.run(_botao(view, "Vender").callback(it))

    sel = it.response.edit_message.call_args.kwargs["view"].children[0]
    assert [o.value for o in sel.options] == ["pocao_p"]


def test_ferreiro_vender_so_lista_equipamento_mesmo_com_pocao_na_mochila():
    _jogador()
    db.add_item(1, "pocao_p", 2)
    db.add_item(1, "espada_ferro", 1)
    view = comercio.FerreiroView(1, FERREIRO, 1, "elu")
    it = _interacao(1)

    asyncio.run(_botao(view, "Vender").callback(it))

    sel = it.response.edit_message.call_args.kwargs["view"].children[0]
    assert [o.value for o in sel.options] == ["espada_ferro"]


# ---------------- fluxos ponta-a-ponta: oficina ----------------
def test_forjar_sem_ser_forjador_recusa_ephemeral_sem_abrir_select():
    _jogador(profissao="alquimia")
    view = comercio.FerreiroView(1, FERREIRO, 1, "elu")
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
    view = comercio.FerreiroView(1, FERREIRO, 1, "elu")
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
    view = comercio.FerreiroView(1, FERREIRO, 1, "elu")
    it = _interacao(1)

    asyncio.run(_botao(view, "Melhorar").callback(it))

    sel = it.response.edit_message.call_args.kwargs["view"].children[0]
    assert [o.value for o in sel.options] == ["arma"]


def test_melhorar_sem_nada_equipado_recusa_ephemeral():
    _jogador()
    view = comercio.FerreiroView(1, FERREIRO, 1, "elu")
    it = _interacao(1)

    asyncio.run(_botao(view, "Melhorar").callback(it))

    it.response.send_message.assert_called_once()
    assert it.response.send_message.call_args.kwargs.get("ephemeral") is True


def test_desmanchar_lista_equipamento_da_mochila_e_executa():
    _jogador()
    db.add_item(1, "espada_ferro", 2)
    view = comercio.FerreiroView(1, FERREIRO, 1, "elu")
    it = _interacao(1)

    async def cenario():
        await _botao(view, "Desmanchar").callback(it)
        sel = it.response.edit_message.call_args.kwargs["view"].children[0]
        it2 = _interacao(1, mensagem=it.message)
        await sel._ao_escolher(it2, "espada_ferro")

    asyncio.run(cenario())
    assert db.tem_item(1, "espada_ferro", 1)   # tinha 2, desmanchou 1


# ---------------- fluxos ponta-a-ponta: taverneiro/carroceiro ----------------
def test_taverneiro_descansar_chama_o_comando_de_verdade():
    j = _jogador(hp=1, mana=0)
    db.atualizar_jogador(1, moedas=j["moedas"])
    view = comercio.TaverneiroView(1, TAVERNEIRO, 1, "elu")
    it = _interacao(1)

    asyncio.run(_botao(view, "Descansar").callback(it))

    j_depois = db.get_jogador(1)
    assert j_depois["hp"] > 1   # rpg descansar de verdade curou, via ShimCtx


def test_carroceiro_embed_mostra_estado_ativo(monkeypatch):
    j = _jogador(andar=3, andar_max=3)
    agora = npcs.agora()
    monkeypatch.setitem(comercio.H, "agora", lambda: agora)
    monkeypatch.setitem(comercio.H, "carroca_ativa", lambda: (True, agora + __import__("datetime").timedelta(minutes=10)))
    view = comercio.CarroceiroView(1, CARROCEIRO, 3, "elu")
    e = view.embed(j)
    campo = next(f for f in e.fields if "carroça" in f.name.lower())
    assert "Parada agora" in campo.value


def test_carroceiro_embed_mostra_proximo_horario_quando_inativa(monkeypatch):
    j = _jogador(andar=3, andar_max=3)
    agora = npcs.agora()
    monkeypatch.setitem(comercio.H, "agora", lambda: agora)
    monkeypatch.setitem(comercio.H, "carroca_ativa", lambda: (False, None))
    monkeypatch.setitem(
        comercio.H, "proxima_carroca",
        lambda: agora.replace(hour=15, minute=0, second=0, microsecond=0) + __import__("datetime").timedelta(days=1),
    )
    view = comercio.CarroceiroView(1, CARROCEIRO, 3, "elu")
    e = view.embed(j)
    campo = next(f for f in e.fields if "carroça" in f.name.lower())
    assert "Não está aqui agora" in campo.value
    assert "15:00" in campo.value


def test_carroceiro_viajar_chama_o_comando_de_verdade():
    _jogador(andar=3, andar_max=3, moedas=10000)
    view = comercio.CarroceiroView(1, CARROCEIRO, 3, "elu")
    it = _interacao(1)

    async def cenario():
        await _botao(view, "Viajar").callback(it)
        sel = it.response.edit_message.call_args.kwargs["view"].children[0]
        destino = sel.options[0].value
        it2 = _interacao(1, mensagem=it.message)
        await sel._ao_escolher(it2, destino)
        return destino

    destino = asyncio.run(cenario())
    assert db.get_jogador(1)["andar"] == int(destino)


def test_bramm_nao_tem_botao_de_pergunta_so_viajar_e_sair():
    view = comercio.CarroceiroView(1, CARROCEIRO, 3, "elu")
    labels = sorted(c.label for c in view.children)
    assert labels == ["Sair", "Viajar"]


def test_selen_comprar_nao_precisa_de_caso_especial():
    """Selen (andar 9) não vende nada -- a Lore avisa que o botão Comprar
    'não se aplica a ela'. Não precisou de nenhum código novo: sem receita
    de loja com andar_min=9, `equipamentos_do_andar(9)` já vem vazio, e o
    Comprar cai sozinho no fallback de sempre."""
    selen = next(n for n in npcs.NPCS[9] if n["nome"] == "Selen")
    _jogador(andar=9, andar_max=9)
    view = comercio.FerreiroView(1, selen, 9, "elu")
    it = _interacao(1)

    asyncio.run(_botao(view, "Comprar").callback(it))

    assert it.response.edit_message.called is False
    it.response.send_message.assert_called_once_with("Nada à venda aqui agora.", ephemeral=True)


# ---------------- opções de diálogo dentro do painel ----------------
def test_clicar_numa_pergunta_do_mercador_edita_a_descricao_sem_fechar_o_painel():
    view = comercio.MercadorView(1, MERCADOR, 1, "elu")
    botao_pergunta = _botao(view, "Perguntar sobre a barraca torta")
    it = _interacao(1)

    asyncio.run(botao_pergunta.callback(it))

    embed_editado = it.response.edit_message.call_args.kwargs["embed"]
    assert "torta" in embed_editado.description.lower()
    view_editada = it.response.edit_message.call_args.kwargs["view"]
    assert not any(c.disabled for c in view_editada.children)   # painel continua ativo


def test_outro_jogador_e_negado_com_ephemeral_e_painel_nao_muda():
    _jogador()
    view = comercio.MercadorView(1, MERCADOR, 1, "elu")
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
    view = comercio.MercadorView(1, MERCADOR, 1, "elu")
    it = _interacao(1)

    asyncio.run(_botao(view, "Sair").callback(it))

    assert all(c.disabled for c in view.children)


def test_ferreiro_tem_sete_botoes_com_a_pergunta_do_torv():
    view = comercio.FerreiroView(1, FERREIRO, 1, "elu")
    por_fileira = {}
    for c in view.children:
        por_fileira.setdefault(c.row, []).append(c.label)
    assert sorted(por_fileira[0]) == ["Comprar", "Vender"]
    assert sorted(por_fileira[1]) == ["Desmanchar", "Forjar", "Melhorar"]
    assert por_fileira[2] == ["Perguntar por que está aposentado"]
    assert por_fileira[3] == ["Sair"]


def test_mercador_tem_quatro_botoes_com_a_pergunta_da_barraca():
    view = comercio.MercadorView(1, MERCADOR, 1, "elu")
    por_fileira = {}
    for c in view.children:
        por_fileira.setdefault(c.row, []).append(c.label)
    assert sorted(por_fileira[0]) == ["Comprar", "Vender"]
    assert por_fileira[1] == ["Perguntar sobre a barraca torta"]
    assert por_fileira[2] == ["Sair"]


def test_rpg_loja_redireciona_em_vez_de_listar_itens():
    ctx = MagicMock()
    ctx.send = AsyncMock()
    asyncio.run(bot.loja.callback(ctx))
    texto = ctx.send.call_args.args[0]
    assert "não existe mais" in texto
    assert "rpg falar" in texto


def test_rpg_descansar_continua_funcionando_direto_sem_taverneiro_por_perto():
    """Diferente do rpg loja: descansar já funcionava sem NPC físico por
    perto (comprar/vender também), então ficou de pé -- só ganhou a porta
    extra do menu. Andar 5 não tem taverneiro nenhum."""
    j = _jogador(andar=5, andar_max=5, hp=1, mana=0)
    ctx = MagicMock()
    ctx.author.id = 1
    ctx.send = AsyncMock()

    asyncio.run(bot.descansar.callback(ctx))

    j_depois = db.get_jogador(1)
    assert j_depois["hp"] > 1   # curou de verdade, não é stub de redirecionamento


def test_rpg_carroca_continua_mostrando_o_horario_direto():
    _jogador(andar=5, andar_max=5)   # longe do andar do Bramm
    ctx = MagicMock()
    ctx.author.id = 1
    ctx.send = AsyncMock()

    asyncio.run(bot.carroca.callback(ctx))

    embed_enviado = ctx.send.call_args.kwargs.get("embed") or ctx.send.call_args.args[0]
    texto = (embed_enviado.description or "") if hasattr(embed_enviado, "description") else str(embed_enviado)
    assert "não existe mais" not in texto.lower()   # não é stub de redirecionamento
