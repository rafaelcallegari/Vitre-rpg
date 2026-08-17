# tests/test_despertar.py
# Sequência de início (patch 0.3): classe -> ofício -> pronome -> Elna. Segue
# a mesma estratégia de tests/test_comercio.py -- interações fake, discord.py
# não conecta de verdade sem subir o bot. Views/botões da Elna em si (feitas
# de DialogoView, já testada indiretamente por bot.py) não são recobertas
# aqui -- só a plumbing própria do despertar. Ver decisoes.md § despertar.
#
# A sala privada agora nasce em `rpg comecar` (bot.py), ANTES da sequência de
# despertar começar -- iniciar_despertar() recebe o canal já pronto e manda
# tudo pra lá, nunca mais pro ctx original. Ver decisoes.md § despertar.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot
import database as db
import despertar
import dialogos


def _interacao(user_id, mensagem=None, display_name="Alice"):
    it = MagicMock()
    it.user.id = user_id
    it.user.display_name = display_name
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


def _ctx(user_id, display_name="Alice"):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.author.display_name = display_name
    ctx.send = AsyncMock()
    return ctx


def _canal_fake(nome="torre-alice"):
    canal = MagicMock()
    canal.mention = f"#{nome}"
    canal.send = AsyncMock()
    return canal


class _DialogoViewFake:
    """Não é discord.ui.View de verdade -- só grava com que foi chamada, pra
    provar que iniciar_despertar entrega os dados certos pra Elna sem
    precisar da DialogoView real (essa já é testada via bot.py)."""

    def __init__(self, autor_id, pronome, opcoes, saida):
        self.autor_id = autor_id
        self.pronome = pronome
        self.opcoes = opcoes
        self.saida = saida
        self.mensagem = None


def _deps():
    return {"dialogo_view_cls": _DialogoViewFake}


async def _avancar_ate_pronome(user_id=1, classe_label="Guerreiro", oficio_label="Joalheiro"):
    """Roda os 2 primeiros passos (classe, ofício) e devolve a
    EscolhaPronomeView pronta pro terceiro clique -- repetido em vários
    testes, então vira helper."""
    ctx = _ctx(user_id)
    canal = _canal_fake()
    view1 = despertar.EscolhaClasseView(user_id, ctx, canal, _deps())
    it1 = _interacao(user_id)
    await _botao(view1, classe_label).callback(it1)
    view2 = it1.response.edit_message.call_args.kwargs["view"]

    it2 = _interacao(user_id, mensagem=it1.message)
    await _botao(view2, oficio_label).callback(it2)
    view3 = it2.response.edit_message.call_args.kwargs["view"]
    return ctx, canal, it2, view3


# ---------------- nada grava até o pronome ----------------
def test_nada_grava_no_banco_antes_do_pronome():
    async def cenario():
        await _avancar_ate_pronome()
    asyncio.run(cenario())
    assert db.get_jogador(1) is None


def test_classe_e_oficio_ficam_so_na_view_ate_o_pronome():
    async def cenario():
        _, _, _, view3 = await _avancar_ate_pronome(classe_label="Mago", oficio_label="Encantador")
        return view3
    view3 = asyncio.run(cenario())
    assert view3.classe == "mago"
    assert view3.oficio == "encantador"


# ---------------- o pronome grava tudo de uma vez ----------------
def test_pronome_grava_classe_oficio_pronome_e_as_pocoes_juntos():
    async def cenario():
        ctx, canal, it2, view3 = await _avancar_ate_pronome(classe_label="Guerreiro", oficio_label="Joalheiro")
        it3 = _interacao(1, mensagem=it2.message)
        await _botao(view3, "ela / dela").callback(it3)
    asyncio.run(cenario())

    j = db.get_jogador(1)
    assert j is not None
    assert j["classe"] == "guerreiro"
    assert j["profissao"] == "joalheiro"
    assert j["prof_nivel"] == 1
    assert j["pronome"] == "ela"
    assert db.tem_item(1, "pocao_p", 3)


def test_pronome_manda_a_fala_da_elna_com_a_concordancia_certa():
    async def cenario():
        ctx, canal, it2, view3 = await _avancar_ate_pronome()
        it3 = _interacao(1, mensagem=it2.message)
        await _botao(view3, "ela / dela").callback(it3)
        return ctx, canal
    ctx, canal = asyncio.run(cenario())

    # a sequência inteira roda na sala, não no canal onde `rpg comecar` foi
    # digitado -- as mensagens do fim do despertar vão pro canal, não pro ctx
    ctx.send.assert_not_called()

    # duas mensagens novas no canal depois do pronome: fala da Elna + fechamento
    embeds_enviados = [c.kwargs.get("embed") for c in canal.send.call_args_list if c.kwargs.get("embed")]
    assert len(embeds_enviados) == 2
    elna_embed = embeds_enviados[0]
    assert "suja" in elna_embed.description   # "Esta tod{o|a} suj{o|a}" -> forma 'ela'

    view_elna = None
    for c in canal.send.call_args_list:
        if isinstance(c.kwargs.get("view"), _DialogoViewFake):
            view_elna = c.kwargs["view"]
    assert view_elna is not None
    assert view_elna.pronome == "ela"
    labels = {o["label"] for o in view_elna.opcoes}
    assert labels == {"Agradecer", "Perguntar onde está", "Olhar em volta"}


def test_confirmacao_de_classe_usa_o_nome_certo_e_pronome_ainda_nao_escolhido():
    async def cenario():
        ctx = _ctx(1)
        canal = _canal_fake()
        view1 = despertar.EscolhaClasseView(1, ctx, canal, _deps())
        it1 = _interacao(1)
        await _botao(view1, "Ladino").callback(it1)
        return it1
    it1 = asyncio.run(cenario())
    e = it1.message.embeds[0]
    assert "Ladino" in e.description
    assert dialogos.DESPERTAR["pergunta_oficio"] in e.description


# ---------------- sequência dupla ----------------
def test_segunda_sequencia_nao_sobrescreve_quem_ja_terminou_a_primeira():
    async def cenario():
        _, _, it2a, view3a = await _avancar_ate_pronome(classe_label="Guerreiro", oficio_label="Joalheiro")
        it3a = _interacao(1, mensagem=it2a.message)
        await _botao(view3a, "ele / dele").callback(it3a)  # primeira sequência termina

        _, _, it2b, view3b = await _avancar_ate_pronome(classe_label="Mago", oficio_label="Alquimista")
        it3b = _interacao(1, mensagem=it2b.message)
        await _botao(view3b, "ela / dela").callback(it3b)  # segunda chega depois, não vale mais
        return it3b
    it3b = asyncio.run(cenario())

    j = db.get_jogador(1)
    assert j["classe"] == "guerreiro"   # da primeira, intocada
    assert j["pronome"] == "ele"
    it3b.response.send_message.assert_called_once()
    assert it3b.response.send_message.call_args.kwargs.get("ephemeral") is True


# ---------------- só o autor clica ----------------
def test_outro_jogador_clicando_recebe_recusa_e_view_nao_muda():
    async def cenario():
        ctx = _ctx(1)
        canal = _canal_fake()
        view1 = despertar.EscolhaClasseView(1, ctx, canal, _deps())
        it_outro = _interacao(2)
        permitido = await view1.interaction_check(it_outro)
        return permitido, it_outro
    permitido, it_outro = asyncio.run(cenario())
    assert permitido is False
    it_outro.response.send_message.assert_called_once()
    assert it_outro.response.send_message.call_args.kwargs.get("ephemeral") is True


# ---------------- gate do rpg comecar ----------------
def test_comecar_recusa_quem_ja_tem_classe(monkeypatch):
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, classe="guerreiro")
    obter_canal = AsyncMock()
    monkeypatch.setattr(bot, "obter_ou_criar_canal_privado", obter_canal)
    chamou = AsyncMock()
    monkeypatch.setattr(despertar, "iniciar_despertar", chamou)
    ctx = _ctx(1)

    asyncio.run(bot.comecar.callback(ctx))

    obter_canal.assert_not_called()   # já tem classe -- nem chega a mexer na sala
    chamou.assert_not_called()
    ctx.send.assert_called_once()
    assert "já está na torre" in ctx.send.call_args.args[0]


def test_comecar_libera_despertar_pra_jogador_resetado_com_titulo_e_mortes(monkeypatch):
    """resetar_temporada zera classe/profissão mas mantém a linha (título,
    mortes, criado_em) -- o gate precisa olhar pra classe, não pra linha
    existir, senão os 13 atuais ficam travados em "você já está na torre"
    depois do reset do 0.3. Ver decisoes.md § despertar."""
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, classe="guerreiro", profissao="forja", mortes=7, titulo="veterano")
    db.resetar_temporada()
    j = db.get_jogador(1)
    assert j["classe"] is None
    assert j["mortes"] == 7   # reset preserva -- não é o alvo deste teste, só a premissa

    canal = _canal_fake()
    obter_canal = AsyncMock(return_value=(canal, False))   # sala de antes, reaproveitada
    monkeypatch.setattr(bot, "obter_ou_criar_canal_privado", obter_canal)
    chamou = AsyncMock()
    monkeypatch.setattr(despertar, "iniciar_despertar", chamou)
    ctx = _ctx(1)

    asyncio.run(bot.comecar.callback(ctx))

    obter_canal.assert_called_once_with(ctx)
    chamou.assert_called_once()
    assert chamou.call_args.args == (ctx, canal)
    ctx.send.assert_called_once()   # só o ponteiro pra sala, no canal de origem
    assert canal.mention in ctx.send.call_args.args[0]


def test_comecar_libera_despertar_pra_jogador_novo(monkeypatch):
    canal = _canal_fake()
    obter_canal = AsyncMock(return_value=(canal, True))
    monkeypatch.setattr(bot, "obter_ou_criar_canal_privado", obter_canal)
    chamou = AsyncMock()
    monkeypatch.setattr(despertar, "iniciar_despertar", chamou)
    ctx = _ctx(1)

    asyncio.run(bot.comecar.callback(ctx))

    chamou.assert_called_once()
    assert db.get_jogador(1) is None   # comecar não cria linha nenhuma -- despertar.py que cria, no pronome


def test_comecar_cria_a_sala_antes_de_chamar_o_despertar(monkeypatch):
    ordem = []
    canal = _canal_fake()

    async def obter_canal(ctx_recebido):
        ordem.append("canal")
        return canal, True

    async def iniciar_despertar_fake(ctx_recebido, canal_recebido, *, dialogo_view_cls):
        ordem.append("despertar")

    monkeypatch.setattr(bot, "obter_ou_criar_canal_privado", obter_canal)
    monkeypatch.setattr(despertar, "iniciar_despertar", iniciar_despertar_fake)
    ctx = _ctx(1)

    asyncio.run(bot.comecar.callback(ctx))

    assert ordem == ["canal", "despertar"]


def test_comecar_de_novo_reaproveita_a_mesma_sala_sem_duplicar(monkeypatch):
    """Abandonar no meio (view expira, ninguém termina o pronome) não deixa
    jogador nenhum gravado -- rodar `rpg comecar` de novo cai na mesma busca
    por nome de canal (obter_ou_criar_canal_privado), que devolve o mesmo
    canal em vez de criar outro."""
    canal = _canal_fake()
    obter_canal = AsyncMock(return_value=(canal, False))
    monkeypatch.setattr(bot, "obter_ou_criar_canal_privado", obter_canal)
    chamou = AsyncMock()
    monkeypatch.setattr(despertar, "iniciar_despertar", chamou)
    ctx = _ctx(1)

    asyncio.run(bot.comecar.callback(ctx))
    asyncio.run(bot.comecar.callback(ctx))

    assert obter_canal.call_count == 2
    assert chamou.call_count == 2
    assert chamou.call_args_list[0].args[1] is canal
    assert chamou.call_args_list[1].args[1] is canal


def test_comecar_nao_comeca_despertar_se_a_sala_falhar(monkeypatch):
    """obter_ou_criar_canal_privado já manda a mensagem de erro sozinho
    (permissão, limite de canais) e devolve None -- `rpg comecar` só precisa
    não seguir em frente, sem despertar pela metade."""
    obter_canal = AsyncMock(return_value=(None, False))
    monkeypatch.setattr(bot, "obter_ou_criar_canal_privado", obter_canal)
    chamou = AsyncMock()
    monkeypatch.setattr(despertar, "iniciar_despertar", chamou)
    ctx = _ctx(1)

    asyncio.run(bot.comecar.callback(ctx))

    chamou.assert_not_called()
    assert db.get_jogador(1) is None


# ---------------- rpg pronome saiu ----------------
def test_rpg_pronome_nao_existe_mais():
    assert bot.bot.get_command("pronome") is None
    assert not hasattr(bot, "PronomeView")
