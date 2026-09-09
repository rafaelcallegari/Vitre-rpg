# tests/test_mestres.py
# Os quatro mestres do andar 7 (Step 4): o roubo/devolução do Arvin e o
# `rpg ascencao` jogável (escolha de ramo + confirmação, via conversa com o
# mestre certo). Funções puras de mestres.py primeiro, depois a fiação em
# bot.py (`falar`) com interações fake -- mesma estratégia de
# tests/test_guia_manto.py.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- import direto e seguro, ver test_bot_seguro.py
import database as db
import game_data
import mestres
import npcs


def _jogador(user_id=1, classe="guerreiro", nivel=15, andar=7, moedas=1000, ascensao=None, **campos):
    db.criar_jogador(user_id, "Alice")
    db.atualizar_jogador(
        user_id, classe=classe, nivel=nivel, andar=andar, andar_max=andar,
        moedas=moedas, ascensao=ascensao, **campos,
    )
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


def _falar(user_id, quem):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    asyncio.run(bot.falar.callback(ctx, quem=quem))
    return ctx


# ---------------------------------------------------------------- npcs.py
def test_mestre_do_andar_acha_o_npc_certo_por_classe():
    assert npcs.mestre_do_andar(7, "guerreiro")["dialogo"] == "cavaleiro"
    assert npcs.mestre_do_andar(7, "orador")["dialogo"] == "augustiel"
    assert npcs.mestre_do_andar(7, "mago")["dialogo"] == "merlin"
    assert npcs.mestre_do_andar(7, "ladino")["dialogo"] == "arvin"


def test_mestre_do_andar_none_fora_do_andar_7():
    assert npcs.mestre_do_andar(1, "guerreiro") is None


# ------------------------------------------------------------- Arvin (commit 2)
def test_arvin_rouba_20_por_cento_na_primeira_conversa():
    j = _jogador(moedas=1000)
    resultado, valor = mestres.arvin_interagir(j["user_id"])
    assert resultado == "roubou"
    assert valor == 200
    depois = db.get_jogador(j["user_id"])
    assert depois["moedas"] == 800
    assert depois["arvin_divida"] == 200


def test_arvin_devolve_o_valor_exato_mesmo_que_o_saldo_tenha_mudado_no_meio():
    j = _jogador(moedas=1000)
    mestres.arvin_interagir(j["user_id"])   # rouba 200
    db.atualizar_jogador(j["user_id"], moedas=50)   # saldo mudou (gastou/ganhou) entre as conversas

    resultado, valor = mestres.arvin_interagir(j["user_id"])

    assert resultado == "devolveu"
    assert valor == 200   # não é 20% de 50 -- é o valor guardado
    depois = db.get_jogador(j["user_id"])
    assert depois["moedas"] == 250
    assert depois["arvin_divida"] == 0


def test_arvin_rouba_de_novo_depois_de_devolver_ciclo_completo():
    j = _jogador(moedas=1000)
    mestres.arvin_interagir(j["user_id"])                 # rouba 200 -> 800
    mestres.arvin_interagir(j["user_id"])                 # devolve 200 -> 1000
    resultado, valor = mestres.arvin_interagir(j["user_id"])   # rouba de novo
    assert resultado == "roubou"
    assert valor == 200


def test_arvin_sem_moedas_rouba_zero_sem_quebrar():
    j = _jogador(moedas=0)
    resultado, valor = mestres.arvin_interagir(j["user_id"])
    assert resultado == "roubou"
    assert valor == 0
    assert db.get_jogador(j["user_id"])["moedas"] == 0


def test_falar_com_arvin_mostra_o_roubo_e_avisa_que_devolve():
    j = _jogador(classe="guerreiro", moedas=1000)
    ctx = _falar(j["user_id"], "arvin")
    e = ctx.send.call_args.kwargs["embed"]
    campo = next(f for f in e.fields if f.name == "🖐️ Mãos Rápidas")
    assert "200" in campo.value
    assert "devolvo" in campo.value.lower()   # deixa claro que vai voltar


def test_falar_com_arvin_texto_diferente_quando_quem_fala_e_ladino():
    j_guerreiro = _jogador(user_id=1, classe="guerreiro", moedas=1000)
    j_ladino = _jogador(user_id=2, classe="ladino", moedas=1000)

    texto_guerreiro = _falar(j_guerreiro["user_id"], "arvin").send.call_args.kwargs["embed"] \
        .fields[0].value
    texto_ladino = _falar(j_ladino["user_id"], "arvin").send.call_args.kwargs["embed"] \
        .fields[0].value

    assert texto_guerreiro != texto_ladino


# ---------------------------------------------------- pode_ascender (commit 3)
def test_pode_ascender_recusa_sem_orbe():
    j = _jogador(classe="guerreiro", nivel=15, andar=7)
    ok, motivo = mestres.pode_ascender(j)
    assert (ok, motivo) == (False, "sem_orbe")


def test_pode_ascender_recusa_nivel_baixo():
    j = _jogador(classe="guerreiro", nivel=10, andar=7)
    db.add_item(j["user_id"], "orbe_de_ascensao")
    ok, motivo = mestres.pode_ascender(db.get_jogador(j["user_id"]))
    assert (ok, motivo) == (False, "nivel_baixo")


def test_pode_ascender_recusa_andar_errado():
    j = _jogador(classe="guerreiro", nivel=15, andar=1)
    db.add_item(j["user_id"], "orbe_de_ascensao")
    ok, motivo = mestres.pode_ascender(db.get_jogador(j["user_id"]))
    assert (ok, motivo) == (False, "andar_errado")


def test_pode_ascender_recusa_ja_ascendido():
    j = _jogador(classe="guerreiro", nivel=15, andar=7, ascensao="espadachim")
    db.add_item(j["user_id"], "orbe_de_ascensao")
    ok, motivo = mestres.pode_ascender(db.get_jogador(j["user_id"]))
    assert (ok, motivo) == (False, "ja_ascendeu")


def test_pode_ascender_ok_com_tudo():
    j = _jogador(classe="guerreiro", nivel=15, andar=7)
    db.add_item(j["user_id"], "orbe_de_ascensao")
    ok, motivo = mestres.pode_ascender(db.get_jogador(j["user_id"]))
    assert (ok, motivo) == (True, None)


def test_ramos_da_base_guerreiro_tem_tres_ladino_tem_dois():
    assert len(mestres.ramos_da_base("guerreiro")) == 3
    assert len(mestres.ramos_da_base("mago")) == 3
    assert len(mestres.ramos_da_base("orador")) == 3
    assert len(mestres.ramos_da_base("ladino")) == 2   # Batedor de Carteira foi cortado


def test_descricao_ramo_traz_texto_real_nao_so_o_nome():
    dados, skill, passivas_do_ramo = mestres.descricao_ramo("espadachim")
    assert dados["nome"] == "Espadachim"
    assert len(skill["desc"]) > 10   # texto de verdade, não vazio/placeholder
    assert all(len(p["desc"]) > 10 for p in passivas_do_ramo)


# --------------------------------------------------- fluxo de conversa (commit 3)
def test_falar_com_mestre_de_outra_classe_recusa_em_personagem():
    j = _jogador(classe="guerreiro", nivel=15, andar=7)
    db.add_item(j["user_id"], "orbe_de_ascensao")

    ctx = _falar(j["user_id"], "merlin")   # mestre do mago, jogador é guerreiro

    e = ctx.send.call_args.kwargs["embed"]
    assert any(f.name == "Não é o seu mestre" for f in e.fields)
    view = ctx.send.call_args.kwargs["view"]
    assert not any(getattr(c, "label", None) == "Ver os caminhos" for c in view.children)
    assert db.get_jogador(j["user_id"])["ascensao"] is None


def test_falar_com_o_proprio_mestre_sem_orbe_nao_oferece_ascensao():
    j = _jogador(classe="guerreiro", nivel=15, andar=7)   # sem Orbe

    ctx = _falar(j["user_id"], "cavaleiro")

    view = ctx.send.call_args.kwargs["view"]
    assert not any(getattr(c, "label", None) == "Ver os caminhos" for c in view.children)
    e = ctx.send.call_args.kwargs["embed"]
    assert any(f.name == "Ainda não" for f in e.fields)


def test_falar_com_o_proprio_mestre_nivel_baixo_nao_oferece_ascensao():
    j = _jogador(classe="guerreiro", nivel=10, andar=7)
    db.add_item(j["user_id"], "orbe_de_ascensao")

    ctx = _falar(j["user_id"], "cavaleiro")

    view = ctx.send.call_args.kwargs["view"]
    assert not any(getattr(c, "label", None) == "Ver os caminhos" for c in view.children)


def test_falar_com_o_proprio_mestre_ja_ascendido_nao_oferece_de_novo():
    j = _jogador(classe="guerreiro", nivel=15, andar=7, ascensao="espadachim")
    db.add_item(j["user_id"], "orbe_de_ascensao")

    ctx = _falar(j["user_id"], "cavaleiro")

    view = ctx.send.call_args.kwargs["view"]
    assert not any(getattr(c, "label", None) == "Ver os caminhos" for c in view.children)
    e = ctx.send.call_args.kwargs["embed"]
    assert any(f.name == "Já ascendeu" for f in e.fields)


def test_falar_com_o_proprio_mestre_com_tudo_oferece_ver_os_caminhos():
    j = _jogador(classe="guerreiro", nivel=15, andar=7)
    db.add_item(j["user_id"], "orbe_de_ascensao")

    ctx = _falar(j["user_id"], "cavaleiro")

    view = ctx.send.call_args.kwargs["view"]
    assert any(getattr(c, "label", None) == "Ver os caminhos" for c in view.children)


def test_ver_os_caminhos_mostra_os_tres_ramos_com_skill_e_passiva_de_verdade():
    j = _jogador(classe="guerreiro", nivel=15, andar=7)
    db.add_item(j["user_id"], "orbe_de_ascensao")
    ctx = _falar(j["user_id"], "cavaleiro")
    view = ctx.send.call_args.kwargs["view"]
    it = _interacao(j["user_id"])

    asyncio.run(_botao(view, "Ver os caminhos").callback(it))

    e = it.response.edit_message.call_args.kwargs["embed"]
    nomes_ramo = {a["nome"] for a in mestres.ramos_da_base("guerreiro").values()}
    assert {f.name for f in e.fields} == nomes_ramo
    for f in e.fields:
        assert len(f.value) > 20   # skill+passiva de verdade, não só o nome


def test_escolher_um_ramo_pede_confirmacao_e_avisa_que_nao_tem_volta():
    j = _jogador(classe="guerreiro", nivel=15, andar=7)
    db.add_item(j["user_id"], "orbe_de_ascensao")
    ctx = _falar(j["user_id"], "cavaleiro")
    view = ctx.send.call_args.kwargs["view"]
    it1 = _interacao(j["user_id"])
    asyncio.run(_botao(view, "Ver os caminhos").callback(it1))
    view_escolha = it1.response.edit_message.call_args.kwargs["view"]

    it2 = _interacao(j["user_id"])
    asyncio.run(_botao(view_escolha, "Espadachim").callback(it2))

    e = it2.response.edit_message.call_args.kwargs["embed"]
    assert "não tem volta" in e.description.lower()
    # nada gravado ainda -- só a tela de confirmação abriu
    assert db.get_jogador(j["user_id"])["ascensao"] is None
    assert db.tem_item(j["user_id"], "orbe_de_ascensao")


def test_voltar_na_confirmacao_nao_grava_nem_consome_o_orbe():
    j = _jogador(classe="guerreiro", nivel=15, andar=7)
    db.add_item(j["user_id"], "orbe_de_ascensao")
    ctx = _falar(j["user_id"], "cavaleiro")
    view = ctx.send.call_args.kwargs["view"]
    it1 = _interacao(j["user_id"])
    asyncio.run(_botao(view, "Ver os caminhos").callback(it1))
    view_escolha = it1.response.edit_message.call_args.kwargs["view"]
    it2 = _interacao(j["user_id"])
    asyncio.run(_botao(view_escolha, "Espadachim").callback(it2))
    view_confirma = it2.response.edit_message.call_args.kwargs["view"]

    it3 = _interacao(j["user_id"])
    asyncio.run(_botao(view_confirma, "Voltar").callback(it3))

    depois = db.get_jogador(j["user_id"])
    assert depois["ascensao"] is None
    assert db.tem_item(j["user_id"], "orbe_de_ascensao")


def test_confirmar_grava_a_ascensao_e_consome_o_orbe_na_mesma_acao():
    j = _jogador(classe="guerreiro", nivel=15, andar=7)
    db.add_item(j["user_id"], "orbe_de_ascensao")
    ctx = _falar(j["user_id"], "cavaleiro")
    view = ctx.send.call_args.kwargs["view"]
    it1 = _interacao(j["user_id"])
    asyncio.run(_botao(view, "Ver os caminhos").callback(it1))
    view_escolha = it1.response.edit_message.call_args.kwargs["view"]
    it2 = _interacao(j["user_id"])
    asyncio.run(_botao(view_escolha, "Espadachim").callback(it2))
    view_confirma = it2.response.edit_message.call_args.kwargs["view"]

    it3 = _interacao(j["user_id"])
    asyncio.run(_botao(view_confirma, "Confirmar — sem volta").callback(it3))

    depois = db.get_jogador(j["user_id"])
    assert depois["ascensao"] == "espadachim"
    assert not db.tem_item(j["user_id"], "orbe_de_ascensao")
    assert all(c.disabled for c in view_confirma.children)


def test_ascensao_destrava_a_skill_nova_na_hora():
    """Só gravar a coluna já basta -- habilidades.conhecidas já lê
    jogador["ascensao"] (Step 2a), não precisa de nada extra aqui."""
    j = _jogador(classe="guerreiro", nivel=15, andar=7)
    db.add_item(j["user_id"], "orbe_de_ascensao")
    mestres.executar_ascensao(j["user_id"], "espadachim")

    import habilidades as hab
    depois = db.get_jogador(j["user_id"])
    assert "sequencia" in hab.conhecidas(depois)   # skill do Espadachim


def test_ladino_com_orbe_na_primeira_conversa_com_arvin_e_roubado_e_ascende():
    """"O roubo não pode atrapalhar a ascensão: um ladino que chegue com o
    Orbe na primeira conversa precisa conseguir as duas coisas." (card)"""
    j = _jogador(classe="ladino", nivel=15, andar=7, moedas=1000)
    db.add_item(j["user_id"], "orbe_de_ascensao")

    ctx = _falar(j["user_id"], "arvin")

    e = ctx.send.call_args.kwargs["embed"]
    assert any(f.name == "🖐️ Mãos Rápidas" for f in e.fields)   # foi roubado
    assert db.get_jogador(j["user_id"])["moedas"] == 800
    view = ctx.send.call_args.kwargs["view"]
    assert any(getattr(c, "label", None) == "Ver os caminhos" for c in view.children)   # E pode ascender
