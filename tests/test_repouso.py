# tests/test_repouso.py
# Step F, commit 2: Renzo (Costa Verde) oferece parar -- o par exato da
# porta atrás do trono. Nada é travado (sem trava de comando, sem pausa de
# cooldown, sem perda de recompensa); o peso inteiro da escolha está no
# texto. Duas colunas: `em_repouso` (liga/desliga, par de botões) e
# `ja_parou` (só liga, registro permanente). As linhas de reconhecimento de
# Nara/Eira/Bento aparecem antes da abertura normal só pra quem está em
# repouso naquele momento. Ver decisoes.md § Step F.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import database as db
import dialogos
import mundo
import npcs
import pronomes
import repouso


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


def _em_costa_verde(user_id=1, **campos):
    return _jogador(user_id, mundo_atual=mundo.COSTA_VERDE, andar=15, andar_max=15, **campos)


# ==================================================================
# migração -- ninguém nasce em repouso
# ==================================================================

def test_migracao_ninguem_nasce_em_repouso():
    j = _jogador(1)
    assert j["em_repouso"] == 0
    assert j["ja_parou"] == 0


# ==================================================================
# Renzo existe, com diálogo válido
# ==================================================================

def test_renzo_esta_em_costa_verde_com_dialogo_valido():
    pessoas = {n["nome"]: n for n in npcs.NPCS[mundo.COSTA_VERDE]}
    assert "Renzo" in pessoas
    n = pessoas["Renzo"]
    assert n["tipo"] == "conversa"
    assert n["dialogo"] in dialogos.DIALOGOS
    assert n.get("renzo") is True


# ==================================================================
# a abertura certa conforme o estado
# ==================================================================

def test_falar_com_renzo_fora_do_repouso_mostra_abertura_normal():
    _em_costa_verde(1)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="renzo"))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "ainda estou aqui" in embed.description.lower()
    assert "você voltou" not in embed.description.lower()


def test_falar_com_renzo_em_repouso_mostra_abertura_de_repouso():
    _em_costa_verde(1, em_repouso=1, ja_parou=1)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="renzo"))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "você voltou" in embed.description.lower()
    assert "ainda estou aqui" not in embed.description.lower()


def test_quem_nunca_parou_ve_exatamente_a_abertura_de_sempre():
    """Regressão: sem nunca ter passado por Renzo, a fala dele é idêntica
    à de antes -- nada muda pra quem não usa o recurso."""
    j = _em_costa_verde(1)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="renzo"))
    embed = ctx.send.call_args.kwargs["embed"]
    esperado = pronomes.concordar(dialogos.linhas(dialogos.DIALOGOS["renzo"]["abertura"]), j["pronome"])
    assert embed.description == f"*{esperado}*"


# ==================================================================
# a opção "perguntar o que ele procurava" -- só fora do repouso
# ==================================================================

def test_opcao_de_pergunta_so_existe_fora_do_repouso():
    _em_costa_verde(1)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="renzo"))
    view = ctx.send.call_args.kwargs["view"]
    assert any(getattr(c, "label", None) == "Perguntar o que ele procurava" for c in view.children)


def test_opcao_de_pergunta_some_em_repouso():
    _em_costa_verde(1, em_repouso=1, ja_parou=1)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="renzo"))
    view = ctx.send.call_args.kwargs["view"]
    assert not any(getattr(c, "label", None) == "Perguntar o que ele procurava" for c in view.children)


# ==================================================================
# o par de botões -- liga e desliga, sobrevive a restart
# ==================================================================

def test_par_de_botoes_o_do_estado_atual_vem_desabilitado():
    _em_costa_verde(1)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="renzo"))
    view = ctx.send.call_args.kwargs["view"]
    parar = _botao(view, "Parar, por enquanto")
    voltar = _botao(view, "Voltar a subir")
    assert parar.disabled is False
    assert voltar.disabled is True


def test_botao_parar_liga_repouso_e_marca_ja_parou():
    _em_costa_verde(1)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="renzo"))
    view = ctx.send.call_args.kwargs["view"]
    botao = _botao(view, "Parar, por enquanto")

    asyncio.run(botao.callback(_interacao(1)))

    depois = db.get_jogador(1)
    assert depois["em_repouso"] == 1
    assert depois["ja_parou"] == 1


def test_botao_voltar_desliga_repouso_mas_mantem_ja_parou():
    _em_costa_verde(1, em_repouso=1, ja_parou=1)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="renzo"))
    view = ctx.send.call_args.kwargs["view"]
    botao = _botao(view, "Voltar a subir")

    asyncio.run(botao.callback(_interacao(1)))

    depois = db.get_jogador(1)
    assert depois["em_repouso"] == 0
    assert depois["ja_parou"] == 1   # registro permanente -- nunca reseta


def test_estado_do_repouso_sobrevive_a_uma_leitura_nova_do_banco():
    """'Sobrevive a restart' -- é coluna, não estado em memória. Simulado
    aqui como uma leitura NOVA e independente do banco, o mesmo que um
    restart do processo produziria."""
    _em_costa_verde(1)
    repouso.definir(1, db.get_jogador(1), ligar=True)
    releitura = db.get_jogador(1)
    assert releitura["em_repouso"] == 1
    assert releitura["ja_parou"] == 1


# ==================================================================
# nada é travado em repouso
# ==================================================================

def test_repouso_nao_bloqueia_viajar():
    _em_costa_verde(1, em_repouso=1, ja_parou=1, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino="vilarejo"))
    assert db.get_jogador(1)["mundo"] == mundo.VILAREJO


def test_repouso_nao_bloqueia_falar_com_outro_npc():
    _em_costa_verde(1, em_repouso=1, ja_parou=1)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="eira"))
    assert "embed" in ctx.send.call_args.kwargs


# ==================================================================
# flexão de gênero -- sai do pronomes.py, não escrita à mão
# ==================================================================

def test_flexao_de_genero_na_abertura_de_repouso():
    for pronome, esperado in (("ele", "parado"), ("elu", "parado"), ("ela", "parada")):
        _em_costa_verde(1, em_repouso=1, ja_parou=1, pronome=pronome)
        ctx = _ctx(1)
        asyncio.run(bot.falar.callback(ctx, quem="renzo"))
        embed = ctx.send.call_args.kwargs["embed"]
        assert esperado in embed.description.lower()
        assert "{" not in embed.description   # marcador nunca escapa cru


# ==================================================================
# as três linhas de reconhecimento -- só em repouso, nunca elogiam
# ==================================================================

def test_reconhecimento_aparece_antes_da_abertura_para_quem_esta_em_repouso():
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15, em_repouso=1, ja_parou=1)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="nara"))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "você parou" in embed.description.lower()
    posicao_reconhecimento = embed.description.lower().index("você parou")
    posicao_abertura = embed.description.lower().index("torre sempre tivesse sido o destino")
    assert posicao_reconhecimento < posicao_abertura


def test_reconhecimento_some_quando_o_jogador_nao_esta_em_repouso():
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="nara"))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "você parou" not in embed.description.lower()


def test_reconhecimento_aparece_para_eira_e_bento_tambem():
    _em_costa_verde(1, em_repouso=1, ja_parou=1)
    for quem, trecho in (("eira", "ele não parou"), ("bento", "você parou de procurar")):
        ctx = _ctx(1)
        asyncio.run(bot.falar.callback(ctx, quem=quem))
        embed = ctx.send.call_args.kwargs["embed"]
        assert trecho in embed.description.lower()


def test_nenhuma_linha_de_reconhecimento_elogia_a_escolha():
    """'Se alguma virar parabéns na implementação, parar vira recompensa,
    e o recurso inteiro perde o sentido' -- o cartão foi explícito."""
    proibidas = ("parabéns", "orgulho", "bom trabalho", "que bom")
    for linhas in repouso.RECONHECIMENTO.values():
        texto = " ".join(linhas).lower()
        for palavra in proibidas:
            assert palavra not in texto
