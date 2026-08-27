# tests/test_guia_manto.py
# A Guia (andares 11-15): menu de diálogo (Pedir para voltar / O que me
# espera / Sobre você / Sair + Entregar condicional), a corrente de pedidos
# que entrega as peças do manto, e a flor do andar 1. A maior parte da
# lógica vive em funções puras de andares_altos.py (sem Discord); as duas
# últimas classes de teste cobrem a fiação em bot.py com interações fake —
# mesma estratégia de tests/test_comercio.py.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import andares_altos
import bot  # noqa: F401 -- import direto e seguro, ver test_bot_seguro.py
import database as db
import npcs
from game_data import ITENS


def _jogador(user_id=1, andar=11, andar_max=11, mortes=0, **campos):
    db.criar_jogador(user_id, "Alice")
    db.atualizar_jogador(user_id, andar=andar, andar_max=andar_max, mortes=mortes, **campos)
    return db.get_jogador(user_id)


def _interacao(user_id):
    it = MagicMock()
    it.user.id = user_id
    it.response = MagicMock()
    it.response.send_message = AsyncMock()
    it.response.edit_message = AsyncMock()
    it.message = MagicMock()
    it.message.embeds = [MagicMock()]
    return it


def _botao(view, label):
    return next(c for c in view.children if getattr(c, "label", None) == label)


# ---------------------------------------------------------------- falas
def test_o_que_espera_tem_uma_fala_por_andar_11_a_15():
    trechos = {
        11: "Vento, e mais vento",
        12: "O trovão daqui não vem de nuvem nenhuma",
        13: "Branco em toda direção",
        14: "A luz aqui não aquece",
        15: "Não vou te pedir de novo",
    }
    for andar, trecho in trechos.items():
        assert andares_altos.o_que_espera(andar).startswith(trecho)


def test_o_que_espera_none_fora_do_andar_11_a_15():
    assert andares_altos.o_que_espera(10) is None
    assert andares_altos.o_que_espera(16) is None


def test_sobre_voce_muda_nas_tres_faixas_de_mortes():
    fala_0 = andares_altos.sobre_voce(0)
    fala_2 = andares_altos.sobre_voce(2)
    fala_3 = andares_altos.sobre_voce(3)
    fala_6 = andares_altos.sobre_voce(6)
    fala_7 = andares_altos.sobre_voce(7)
    fala_10 = andares_altos.sobre_voce(10)

    assert fala_0 == fala_2          # faixa 0-2 é a mesma
    assert fala_3 == fala_6          # faixa 3-6 é a mesma
    assert fala_7 == fala_10         # faixa 7+ é a mesma
    assert len({fala_0, fala_3, fala_7}) == 3


def test_revelacao_de_escudeira_so_sai_na_faixa_7_mais():
    assert "escudeira" not in andares_altos.sobre_voce(0)
    assert "escudeira" not in andares_altos.sobre_voce(3)
    assert "escudeira" not in andares_altos.sobre_voce(6)
    assert "escudeira" in andares_altos.sobre_voce(7)


# ---------------------------------------------------------------- corrente de pedidos
def test_pedido_pendente_comeca_na_flor_do_andar_11():
    j = _jogador()
    pedido, estado = andares_altos.pedido_pendente(j["user_id"])
    assert pedido["andar"] == 11
    assert pedido["pede"] == "flor_do_andar_1"
    assert estado == "antes"


def test_conceder_pedido_pendente_da_uma_vez_so():
    j = _jogador()
    primeiro = andares_altos.conceder_pedido_pendente(j["user_id"])
    assert primeiro["quest_id"] == "guia_flor"

    segundo = andares_altos.conceder_pedido_pendente(j["user_id"])
    assert segundo is None   # já estava 'ativa' -- não dá de novo

    _, estado = andares_altos.pedido_pendente(j["user_id"])
    assert estado == "durante"


def test_flor_nao_nasce_pra_quem_ainda_nao_recebeu_o_pedido():
    j = _jogador()
    assert andares_altos.pode_colher_flor(j["user_id"]) is False   # ainda 'antes'


def test_flor_disponivel_depois_do_pedido_concedido():
    j = _jogador()
    andares_altos.conceder_pedido_pendente(j["user_id"])
    assert andares_altos.pode_colher_flor(j["user_id"]) is True


def test_entregar_sem_ter_o_pedido_concedido_nao_faz_nada():
    j = _jogador()
    db.add_item(j["user_id"], "flor_do_andar_1", 1)   # tem o item, mas nunca pediram
    assert andares_altos.entregar_pedido(j["user_id"]) is None
    assert db.tem_item(j["user_id"], "flor_do_andar_1", 1)   # não consumiu


def test_entregar_sem_quantidade_completa_nao_consome_nada():
    j = _jogador(andar=12, andar_max=12)
    andares_altos.conceder_pedido_pendente(j["user_id"])   # guia_flor -> ativa
    andares_altos.entregar_pedido(j["user_id"])            # sem flor -- falha, nada consumido
    db.add_item(j["user_id"], "flor_do_andar_1", 1)
    andares_altos.entregar_pedido(j["user_id"])             # agora entrega -- avança pro andar 12
    andares_altos.conceder_pedido_pendente(j["user_id"])    # concede o pedido do 12 (farpas)

    db.add_item(j["user_id"], "farpa_eletrica", 5)          # pede 6, só tem 5
    resultado = andares_altos.entregar_pedido(j["user_id"])
    assert resultado is None
    inv = {i["item"]: i["qtd"] for i in db.get_inventario(j["user_id"])}
    assert inv.get("farpa_eletrica") == 5                    # nada foi consumido
    assert "fio_do_manto" not in inv


def test_entregar_consome_exatamente_a_quantidade_e_da_uma_peca():
    j = _jogador(andar=12, andar_max=12)
    andares_altos.conceder_pedido_pendente(j["user_id"])
    db.add_item(j["user_id"], "flor_do_andar_1", 1)
    andares_altos.entregar_pedido(j["user_id"])   # conclui a flor -- frente vira o 12
    andares_altos.conceder_pedido_pendente(j["user_id"])

    db.add_item(j["user_id"], "farpa_eletrica", 9)   # sobra depois de entregar 6
    pedido = andares_altos.entregar_pedido(j["user_id"])
    assert pedido["da"] == "fio_do_manto"

    inv = {i["item"]: i["qtd"] for i in db.get_inventario(j["user_id"])}
    assert inv.get("farpa_eletrica") == 3     # 9 - 6
    assert inv.get("fio_do_manto") == 1
    assert db.estado_sidequest(j["user_id"], "guia_farpas") == "depois"


def test_entrega_fora_de_ordem_nao_funciona_ela_cobra_a_anterior():
    """Ter o material do andar 12 não adianta nada se a corrente ainda
    está travada no pedido do andar 11 (a flor) — mesmo chegando direto no
    13 sem nunca ter passado pelo 12, o pedido em jogo continua sendo o
    mais antigo em aberto."""
    j = _jogador(andar=13, andar_max=13)
    andares_altos.conceder_pedido_pendente(j["user_id"])   # concede a flor (11), não o 13
    db.add_item(j["user_id"], "estilhaco_gelido", 8)        # material do 13, na mão
    db.add_item(j["user_id"], "farpa_eletrica", 6)          # material do 12, na mão

    resultado = andares_altos.entregar_pedido(j["user_id"])
    assert resultado is None   # nada entrega -- falta é a flor, não isso

    inv = {i["item"]: i["qtd"] for i in db.get_inventario(j["user_id"])}
    assert inv["estilhaco_gelido"] == 8
    assert inv["farpa_eletrica"] == 6
    pedido, estado = andares_altos.pedido_pendente(j["user_id"])
    assert pedido["andar"] == 11 and estado == "durante"


def test_corrente_completa_11_a_14_entrega_as_quatro_pecas_em_ordem():
    j = _jogador(andar=14, andar_max=14)
    pecas_recebidas = []
    for material, qtd in (
        ("flor_do_andar_1", 1), ("farpa_eletrica", 6),
        ("estilhaco_gelido", 8), ("cinza_quente", 10),
    ):
        novo = andares_altos.conceder_pedido_pendente(j["user_id"])
        assert novo is not None
        db.add_item(j["user_id"], material, qtd)
        pedido = andares_altos.entregar_pedido(j["user_id"])
        assert pedido is not None
        pecas_recebidas.append(pedido["da"])

    assert pecas_recebidas == ["molde_do_manto", "fio_do_manto", "forro_do_manto", "fecho_do_manto"]
    assert andares_altos.conceder_pedido_pendente(j["user_id"]) is None   # nada mais pra conceder
    assert andares_altos.pedido_pendente(j["user_id"]) == (None, None)
    inv = {i["item"]: i["qtd"] for i in db.get_inventario(j["user_id"])}
    for peca in pecas_recebidas:
        assert inv[peca] == 1


def test_quest_concluida_flor_nunca_mais_nasce():
    j = _jogador()
    andares_altos.conceder_pedido_pendente(j["user_id"])
    db.add_item(j["user_id"], "flor_do_andar_1", 1)
    andares_altos.entregar_pedido(j["user_id"])
    assert andares_altos.pode_colher_flor(j["user_id"]) is False


# ---------------------------------------------------------------- morte acima do Selo
def test_morte_acima_do_selo_preserva_pecas_e_progresso_da_quest():
    j = _jogador(andar=13, andar_max=13, moedas=1000)
    andares_altos.conceder_pedido_pendente(j["user_id"])
    db.add_item(j["user_id"], "flor_do_andar_1", 1)
    andares_altos.entregar_pedido(j["user_id"])           # molde_do_manto na mochila
    andares_altos.conceder_pedido_pendente(j["user_id"])  # pedido do 12 concedido, ainda não entregue

    s = {"hp_max": 300}
    bot.processar_morte(db.get_jogador(j["user_id"]), s)

    depois = db.get_jogador(j["user_id"])
    assert depois["andar"] == andares_altos.ANDAR_ACIMA_DO_SELO
    assert depois["andar_max"] == andares_altos.ANDAR_ACIMA_DO_SELO
    assert db.tem_item(j["user_id"], "molde_do_manto", 1)             # peça recebida sobrevive
    assert db.estado_sidequest(j["user_id"], "guia_flor") == "depois"  # progresso da quest sobrevive
    assert db.estado_sidequest(j["user_id"], "guia_farpas") == "durante"


# ---------------------------------------------------------------- fiação em bot.py (falar/colher)
def test_falar_guia_abre_menu_com_quatro_botoes_fixos_mais_sobre_o_pedido():
    j = _jogador(andar=11, andar_max=11)
    ctx = MagicMock()
    ctx.author.id = j["user_id"]
    ctx.send = AsyncMock()

    asyncio.run(bot.falar.callback(ctx, quem="guia"))

    view = ctx.send.call_args.kwargs["view"]
    labels = sorted(c.label for c in view.children)
    # 4 fixos + "Sobre o pedido" (há pedido em aberto assim que ela concede
    # a flor) -- sem "Entregar", que exige ter o material na mochila.
    assert labels == ["O que me espera", "Pedir para voltar", "Sair", "Sobre o pedido", "Sobre você"]
    assert db.estado_sidequest(j["user_id"], "guia_flor") == "durante"   # pedido concedido ao abrir


def test_falar_guia_mostra_botao_entregar_quando_tem_o_material():
    j = _jogador(andar=11, andar_max=11)
    andares_altos.conceder_pedido_pendente(j["user_id"])
    db.add_item(j["user_id"], "flor_do_andar_1", 1)
    ctx = MagicMock()
    ctx.author.id = j["user_id"]
    ctx.send = AsyncMock()

    asyncio.run(bot.falar.callback(ctx, quem="guia"))

    view = ctx.send.call_args.kwargs["view"]
    labels = {c.label for c in view.children}
    assert any(label.startswith("Entregar") for label in labels)


def test_botao_pedir_para_voltar_teleporta_pro_10_e_trava_o_painel():
    j = _jogador(andar=13, andar_max=13)
    view = bot.GuiaDialogoView(j["user_id"], "elu", "espera", "sobre", None, None)
    it = _interacao(j["user_id"])

    asyncio.run(_botao(view, "Pedir para voltar").callback(it))

    assert db.get_jogador(j["user_id"])["andar"] == andares_altos.ANDAR_ACIMA_DO_SELO
    assert all(c.disabled for c in view.children)


def test_botao_entregar_falha_sem_quebrar_se_material_sumiu_entre_abrir_e_clicar():
    j = _jogador(andar=11, andar_max=11)
    pedido = andares_altos.conceder_pedido_pendente(j["user_id"])
    view = bot.GuiaDialogoView(j["user_id"], "elu", "espera", "sobre", pedido, pedido)
    it = _interacao(j["user_id"])

    asyncio.run(_botao(view, f"Entregar {pedido['qtd']}x {ITENS[pedido['pede']]['nome']}").callback(it))

    it.response.send_message.assert_awaited_once()
    assert "não tem mais o suficiente" in it.response.send_message.call_args.args[0].lower()
    assert db.estado_sidequest(j["user_id"], "guia_flor") == "durante"   # continua pendente


def test_colher_funciona_na_janela_com_pedido_e_falha_fora_dela(monkeypatch):
    j = _jogador(andar=1, andar_max=13)
    andares_altos.conceder_pedido_pendente(db.get_jogador(j["user_id"])["user_id"])
    # o pedido é concedido a partir do andar 11 -- aqui simulamos que ele já
    # foi concedido antes (o jogador desceu pra colher), então o `andar`
    # atual (1) não importa pra elegibilidade, só a janela e o estado da quest.

    ctx = MagicMock()
    ctx.author.id = j["user_id"]
    ctx.send = AsyncMock()

    monkeypatch.setattr(bot, "flor_ativa", lambda: (False, None))
    asyncio.run(bot.colher.callback(ctx))
    assert not db.tem_item(j["user_id"], "flor_do_andar_1", 1)
    assert "mais tarde" in ctx.send.call_args.args[0].lower()

    monkeypatch.setattr(bot, "flor_ativa", lambda: (True, None))
    asyncio.run(bot.colher.callback(ctx))
    assert db.tem_item(j["user_id"], "flor_do_andar_1", 1)


def test_colher_nao_faz_nada_fora_do_andar_1():
    j = _jogador(andar=11, andar_max=11)
    andares_altos.conceder_pedido_pendente(j["user_id"])
    ctx = MagicMock()
    ctx.author.id = j["user_id"]
    ctx.send = AsyncMock()

    asyncio.run(bot.colher.callback(ctx))

    assert not db.tem_item(j["user_id"], "flor_do_andar_1", 1)
    assert "andar 1" in ctx.send.call_args.args[0]


# ---------------------------------------------------------------- aviso da flor em cacar/explorar
def _embed_enviado(ctx):
    return ctx.send.call_args.kwargs.get("embed") or ctx.send.call_args.args[0]


def _tem_aviso_flor(embed):
    return any(f.name == "🌸 Na grama" for f in embed.fields)


def _ctx_jogador(user_id):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    return ctx


def test_cacar_avisa_a_flor_parado_no_andar_1_com_a_janela_aberta(monkeypatch):
    j = _jogador(andar=1, andar_max=13)
    andares_altos.conceder_pedido_pendente(j["user_id"])   # pedido do 11 concedido, jogador desceu
    monkeypatch.setattr(bot, "flor_ativa", lambda: (True, None))
    ctx = _ctx_jogador(j["user_id"])

    asyncio.run(bot.cacar.callback(ctx))

    assert _tem_aviso_flor(_embed_enviado(ctx))


def test_explorar_avisa_a_flor_parado_no_andar_1_com_a_janela_aberta(monkeypatch):
    j = _jogador(andar=1, andar_max=13)
    andares_altos.conceder_pedido_pendente(j["user_id"])
    monkeypatch.setattr(bot, "flor_ativa", lambda: (True, None))
    ctx = _ctx_jogador(j["user_id"])

    asyncio.run(bot.explorar.callback(ctx))

    assert _tem_aviso_flor(_embed_enviado(ctx))


def test_cacar_nao_avisa_sem_a_janela_aberta(monkeypatch):
    j = _jogador(andar=1, andar_max=13)
    andares_altos.conceder_pedido_pendente(j["user_id"])
    monkeypatch.setattr(bot, "flor_ativa", lambda: (False, None))
    ctx = _ctx_jogador(j["user_id"])

    asyncio.run(bot.cacar.callback(ctx))

    assert not _tem_aviso_flor(_embed_enviado(ctx))


def test_cacar_nao_avisa_sem_o_pedido_da_flor_em_aberto(monkeypatch):
    j = _jogador(andar=1, andar_max=13)   # nunca falou com a Guia -- pedido ainda 'antes'
    monkeypatch.setattr(bot, "flor_ativa", lambda: (True, None))
    ctx = _ctx_jogador(j["user_id"])

    asyncio.run(bot.cacar.callback(ctx))

    assert not _tem_aviso_flor(_embed_enviado(ctx))


def test_explorar_nao_avisa_fora_do_andar_1_mesmo_com_a_janela_aberta(monkeypatch):
    j = _jogador(andar=12, andar_max=13)
    andares_altos.conceder_pedido_pendente(j["user_id"])
    monkeypatch.setattr(bot, "flor_ativa", lambda: (True, None))
    ctx = _ctx_jogador(j["user_id"])

    asyncio.run(bot.explorar.callback(ctx))

    assert not _tem_aviso_flor(_embed_enviado(ctx))


# ---------------------------------------------------------------- botão "Sobre o pedido"
def test_fala_do_pedido_bate_com_os_quatro_textos_aprovados():
    trechos = {
        "guia_flor": "nasce uma flor",
        "guia_farpas": "Seis farpas",
        "guia_estilhacos": "Oito estilhaços",
        "guia_cinzas": "Dez punhados de cinza",
    }
    for quest_id, trecho in trechos.items():
        assert trecho in andares_altos.fala_do_pedido(quest_id)


def test_sobre_o_pedido_nao_aparece_sem_pedido_em_aberto():
    j = _jogador(andar=15, andar_max=15)
    # esgota a corrente inteira sem nunca deixar nada pendente
    for material, qtd in (
        ("flor_do_andar_1", 1), ("farpa_eletrica", 6),
        ("estilhaco_gelido", 8), ("cinza_quente", 10),
    ):
        andares_altos.conceder_pedido_pendente(j["user_id"])
        db.add_item(j["user_id"], material, qtd)
        andares_altos.entregar_pedido(j["user_id"])
    ctx = _ctx_jogador(j["user_id"])

    asyncio.run(bot.falar.callback(ctx, quem="guia"))

    view = ctx.send.call_args.kwargs["view"]
    labels = {c.label for c in view.children}
    assert "Sobre o pedido" not in labels
    assert not any(label.startswith("Entregar") for label in labels)


def test_botao_sobre_o_pedido_mostra_fala_e_progresso_tem_precisa():
    j = _jogador(andar=12, andar_max=12)
    pedido = andares_altos.conceder_pedido_pendente(j["user_id"])   # guia_flor
    db.add_item(j["user_id"], "flor_do_andar_1", 1)
    andares_altos.entregar_pedido(j["user_id"])
    pedido = andares_altos.conceder_pedido_pendente(j["user_id"])   # guia_farpas, pede 6
    db.add_item(j["user_id"], "farpa_eletrica", 4)                  # só juntou 4 até agora

    view = bot.GuiaDialogoView(j["user_id"], "elu", "espera", "sobre", pedido, None)
    it = _interacao(j["user_id"])

    asyncio.run(_botao(view, "Sobre o pedido").callback(it))

    e = it.message.embeds[0]
    assert "Seis farpas" in e.description
    e.set_footer.assert_called_once()
    assert e.set_footer.call_args.kwargs["text"] == "Farpa Elétrica: 4/6"


def test_botao_sobre_o_pedido_le_a_mochila_na_hora_do_clique_nao_na_abertura():
    """O progresso não pode ficar congelado no que a mochila tinha quando o
    menu foi montado -- o jogador pode ter farmado mais material enquanto a
    conversa estava aberta na tela."""
    j = _jogador(andar=12, andar_max=12)
    andares_altos.conceder_pedido_pendente(j["user_id"])
    db.add_item(j["user_id"], "flor_do_andar_1", 1)
    andares_altos.entregar_pedido(j["user_id"])
    pedido = andares_altos.conceder_pedido_pendente(j["user_id"])   # guia_farpas

    view = bot.GuiaDialogoView(j["user_id"], "elu", "espera", "sobre", pedido, None)
    db.add_item(j["user_id"], "farpa_eletrica", 3)   # chega DEPOIS do menu já montado
    it = _interacao(j["user_id"])

    asyncio.run(_botao(view, "Sobre o pedido").callback(it))

    assert it.message.embeds[0].set_footer.call_args.kwargs["text"] == "Farpa Elétrica: 3/6"
