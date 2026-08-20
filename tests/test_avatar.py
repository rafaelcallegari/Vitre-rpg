# tests/test_avatar.py
# `rpg avatar` (avatar.py) + `rpg removeravatar` (admin.py). O ponto central
# do desenho é que a URL do CDN do Discord é só CACHE -- quem manda é o ID
# da mensagem repostada em CANAL_ARQUIVO_ID (fonte da verdade), porque a
# assinatura `ex` da URL expira e o arquivo não. Ver decisoes.md § avatar do
# jogador. O teste que prova isso de verdade é
# test_url_valida_nao_dispara_fetch_message /
# test_url_vencida_dispara_refetch_e_atualiza_cache: sem eles, o caminho de
# refresh podia nunca ter sido exercitado até os links vencerem em massa.
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord.ext import commands

import admin
import avatar
import bot
import database as db


# ---------------- fakes ----------------
class FakeAnexoEnviado:
    """Simula um `discord.Attachment` chegando por `ctx.message.attachments`."""

    def __init__(self, dados, content_type, size=None):
        self._dados = dados
        self.content_type = content_type
        self.size = size if size is not None else len(dados)

    async def read(self):
        return self._dados


class FakeAnexoRepostado:
    def __init__(self, url):
        self.url = url


class FakeMensagemRepostada:
    def __init__(self, msg_id, url):
        self.id = msg_id
        self.attachments = [FakeAnexoRepostado(url)]


class _RespostaHTTPFalsa:
    status = 404
    reason = "Not Found"


def _url_com_ex(delta_segundos, msg="avatar"):
    """URL de CDN fake com o parâmetro `ex` (hex, unix seconds) vencendo
    daqui a `delta_segundos` -- negativo para já vencida."""
    ex = int(time.time()) + delta_segundos
    return f"https://cdn.discordapp.com/attachments/1/2/{msg}.png?ex={ex:x}&is=a&hm=b"


class FakeCanalArquivo:
    """Substitui CANAL_ARQUIVO_ID nos testes -- guarda o que foi "enviado"
    (bytes do discord.File) e serve fetch_message pras mensagens que já
    "existem" (pré-registradas via registrar_mensagem)."""

    def __init__(self):
        self.enviados = []
        self.mensagens = {}
        self.fetch_chamadas = 0
        self._proximo_id = 1000

    def registrar_mensagem(self, url=None):
        self._proximo_id += 1
        msg = FakeMensagemRepostada(self._proximo_id, url or _url_com_ex(3600))
        self.mensagens[msg.id] = msg
        return msg

    async def send(self, file=None, **kwargs):
        self.enviados.append(file.fp.read())
        return self.registrar_mensagem()

    async def fetch_message(self, msg_id):
        self.fetch_chamadas += 1
        if msg_id not in self.mensagens:
            raise discord.NotFound(_RespostaHTTPFalsa(), "Unknown Message")
        return self.mensagens[msg_id]


class FakeRespostaHTTP:
    """Substitui a resposta de `aiohttp.ClientSession.get()` nos testes de
    `_baixar_link` -- `content.read(n)` consome de um buffer, igual ao
    StreamReader de verdade."""

    def __init__(self, status=200, headers=None, corpo=b""):
        self.status = status
        self.headers = headers or {}
        self.content = self
        self._corpo = corpo

    async def read(self, n=-1):
        if n is None or n < 0:
            dado, self._corpo = self._corpo, b""
            return dado
        dado, self._corpo = self._corpo[:n], self._corpo[n:]
        return dado

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class FakeSessaoHTTP:
    def __init__(self, resposta):
        self._resposta = resposta

    def get(self, url):
        return self._resposta

    async def close(self):
        pass


class FakeCtx:
    def __init__(self, user_id, anexos=None):
        self.author = MagicMock()
        self.author.id = user_id
        self.message = MagicMock()
        self.message.attachments = anexos or []
        self.send = AsyncMock()
        # `rpg perfil` virou híbrido e chama `ctx.defer()` antes do fetch de
        # avatar (ver decisoes.md § comandos híbridos leva 1) -- Context de
        # verdade sempre tem esse método (no-op fora de interação), então o
        # fake precisa continuar imitando a interface real.
        self.defer = AsyncMock()


class FakeMembro:
    def __init__(self, id, display_name):
        self.id = id
        self.display_name = display_name


@pytest.fixture(autouse=True)
def limpar_cache_canal():
    """`avatar._canal_cache` é estado de módulo (ver decisoes.md § canal de
    arquivo indisponível) -- sem isso um teste que resolve o canal vazaria
    o objeto fake pro próximo, que espera resolver o dele próprio."""
    avatar._canal_cache = None
    yield
    avatar._canal_cache = None


@pytest.fixture
def bot_de_teste(monkeypatch):
    intents = discord.Intents.default()
    b = commands.Bot(command_prefix="rpg ", intents=intents)
    avatar.instalar(b)
    canal = FakeCanalArquivo()
    monkeypatch.setattr(b, "get_channel", lambda cid: canal)
    monkeypatch.setenv("CANAL_ARQUIVO_ID", "123")
    b._canal_de_teste = canal
    return b


# ---------------- rpg avatar por anexo ----------------
def test_definir_avatar_por_anexo_salva_msg_id_e_url(bot_de_teste):
    db.criar_jogador(1, "Alice")
    anexo = FakeAnexoEnviado(b"png-bytes", "image/png")
    ctx = FakeCtx(1, anexos=[anexo])
    cmd = bot_de_teste.get_command("avatar")

    asyncio.run(cmd.callback(ctx))

    canal = bot_de_teste._canal_de_teste
    assert canal.enviados == [b"png-bytes"]
    j = db.get_jogador(1)
    assert j["avatar_msg_id"] is not None
    assert j["avatar_url"] == canal.mensagens[j["avatar_msg_id"]].attachments[0].url
    ctx.send.assert_called_once()
    assert "atualizado" in ctx.send.call_args.args[0]


# ---------------- rpg avatar por link ----------------
def test_definir_avatar_por_link_baixa_reposta_salva(bot_de_teste, monkeypatch):
    db.criar_jogador(1, "Alice")
    baixar = AsyncMock(return_value=(b"dados-do-link", "image/webp"))
    monkeypatch.setattr(avatar, "_baixar_link", baixar)
    ctx = FakeCtx(1)
    cmd = bot_de_teste.get_command("avatar")

    asyncio.run(cmd.callback(ctx, link="http://exemplo.com/foto.webp"))

    baixar.assert_awaited_once_with("http://exemplo.com/foto.webp")
    canal = bot_de_teste._canal_de_teste
    assert canal.enviados == [b"dados-do-link"]
    j = db.get_jogador(1)
    assert j["avatar_msg_id"] is not None
    assert j["avatar_url"] is not None


def test_baixar_link_aceita_imagem_valida():
    resposta = FakeRespostaHTTP(status=200, headers={"Content-Type": "image/png"}, corpo=b"dados")
    sessao = FakeSessaoHTTP(resposta)

    resultado = asyncio.run(avatar._baixar_link("http://exemplo.com/a.png", sessao=sessao))

    assert resultado == (b"dados", "image/png")


# ---------------- formato e tamanho recusados ----------------
def test_recusa_anexo_com_tipo_nao_aceito(bot_de_teste):
    db.criar_jogador(1, "Alice")
    anexo = FakeAnexoEnviado(b"gif-bytes", "image/gif")
    ctx = FakeCtx(1, anexos=[anexo])
    cmd = bot_de_teste.get_command("avatar")

    asyncio.run(cmd.callback(ctx))

    ctx.send.assert_called_once_with(avatar.MSG_TIPO_INVALIDO)
    assert db.get_jogador(1)["avatar_msg_id"] is None


def test_recusa_anexo_acima_do_limite(bot_de_teste):
    db.criar_jogador(1, "Alice")
    anexo = FakeAnexoEnviado(b"x", "image/png", size=avatar.TAMANHO_MAXIMO_BYTES + 1)
    ctx = FakeCtx(1, anexos=[anexo])
    cmd = bot_de_teste.get_command("avatar")

    asyncio.run(cmd.callback(ctx))

    ctx.send.assert_called_once_with(avatar.MSG_TAMANHO_INVALIDO)


def test_recusa_link_que_nao_devolve_imagem(bot_de_teste, monkeypatch):
    db.criar_jogador(1, "Alice")
    monkeypatch.setattr(avatar, "_baixar_link", AsyncMock(return_value=None))
    ctx = FakeCtx(1)
    cmd = bot_de_teste.get_command("avatar")

    asyncio.run(cmd.callback(ctx, link="http://exemplo.com/pagina.html"))

    ctx.send.assert_called_once_with(avatar.MSG_LINK_INVALIDO)


def test_baixar_link_recusa_tipo_nao_aceito():
    resposta = FakeRespostaHTTP(status=200, headers={"Content-Type": "text/html"}, corpo=b"<html>")
    sessao = FakeSessaoHTTP(resposta)

    resultado = asyncio.run(avatar._baixar_link("http://exemplo.com/pagina", sessao=sessao))

    assert resultado is None


def test_baixar_link_recusa_acima_do_limite():
    grande = b"x" * (avatar.TAMANHO_MAXIMO_BYTES + 100)
    resposta = FakeRespostaHTTP(status=200, headers={"Content-Type": "image/jpeg"}, corpo=grande)
    sessao = FakeSessaoHTTP(resposta)

    resultado = asyncio.run(avatar._baixar_link("http://exemplo.com/a.jpg", sessao=sessao))

    assert resultado is None


# ---------------- cache da URL: o desenho inteiro depende disto ----------------
def test_url_expirada_trata_url_sem_ex_como_vencida():
    assert avatar._url_expirada("https://cdn.discordapp.com/attachments/1/2/x.png") is True


def test_url_expirada_respeita_margem_de_seguranca():
    quase_vencendo = _url_com_ex(60)  # vence em 1min, margem é 5min
    assert avatar._url_expirada(quase_vencendo) is True


def test_url_valida_nao_dispara_fetch_message(bot_de_teste):
    db.criar_jogador(1, "Alice")
    url_fresca = _url_com_ex(3600)
    db.atualizar_jogador(1, avatar_msg_id=42, avatar_url=url_fresca)
    j = db.get_jogador(1)
    canal = bot_de_teste._canal_de_teste

    url = asyncio.run(avatar.obter_avatar_atualizado(bot_de_teste, j))

    assert url == url_fresca
    assert canal.fetch_chamadas == 0


def test_url_vencida_dispara_refetch_e_atualiza_cache(bot_de_teste):
    db.criar_jogador(1, "Alice")
    canal = bot_de_teste._canal_de_teste
    url_nova = _url_com_ex(3600, msg="nova")
    mensagem = canal.registrar_mensagem(url_nova)
    db.atualizar_jogador(1, avatar_msg_id=mensagem.id, avatar_url=_url_com_ex(-10, msg="velha"))
    j = db.get_jogador(1)

    url = asyncio.run(avatar.obter_avatar_atualizado(bot_de_teste, j))

    assert url == url_nova
    assert canal.fetch_chamadas == 1
    assert db.get_jogador(1)["avatar_url"] == url_nova


# ---------------- fetch_message falhando não pode quebrar o rpg perfil ----------------
def test_fetch_message_falhando_nao_quebra_perfil(monkeypatch):
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, avatar_msg_id=999999, avatar_url=_url_com_ex(-10))

    canal = FakeCanalArquivo()  # sem a mensagem 999999 -> fetch_message levanta NotFound
    monkeypatch.setattr(bot.bot, "get_channel", lambda cid: canal)
    monkeypatch.setenv("CANAL_ARQUIVO_ID", "123")

    ctx = FakeCtx(1)

    asyncio.run(bot.perfil.callback(ctx))

    ctx.send.assert_called_once()
    embed = ctx.send.call_args.kwargs["embed"]
    assert "thumbnail" not in embed.to_dict()


# ---------------- avatar é cosmético: sobrevive ao reset de temporada ----------------
def test_avatar_sobrevive_ao_resetar_temporada():
    db.criar_jogador(1, "Alice")
    url = _url_com_ex(3600)
    db.atualizar_jogador(1, avatar_msg_id=42, avatar_url=url)

    db.resetar_temporada()

    j = db.get_jogador(1)
    assert j["avatar_msg_id"] == 42
    assert j["avatar_url"] == url


# ---------------- rpg removeravatar (admin.py) ----------------
def test_removeravatar_admin_remove_avatar_de_outro_jogador():
    db.criar_jogador(1, "Dono")
    db.criar_jogador(2, "Bob")
    db.atualizar_jogador(2, avatar_msg_id=7, avatar_url=_url_com_ex(3600))

    intents = discord.Intents.default()
    b = commands.Bot(command_prefix="rpg ", intents=intents)
    admin.instalar(b)
    cmd = b.get_command("removeravatar")

    ctx = FakeCtx(1)
    membro = FakeMembro(2, "Bob")

    asyncio.run(cmd.callback(ctx, membro))

    j = db.get_jogador(2)
    assert j["avatar_msg_id"] is None
    assert j["avatar_url"] is None
    ctx.send.assert_called_once()
    assert "Bob" in ctx.send.call_args.args[0]


def test_removeravatar_recusa_quem_ja_esta_sem_avatar():
    db.criar_jogador(1, "Dono")
    db.criar_jogador(2, "Bob")

    intents = discord.Intents.default()
    b = commands.Bot(command_prefix="rpg ", intents=intents)
    admin.instalar(b)
    cmd = b.get_command("removeravatar")

    ctx = FakeCtx(1)
    membro = FakeMembro(2, "Bob")

    asyncio.run(cmd.callback(ctx, membro))

    ctx.send.assert_called_once()
    assert "já está sem avatar" in ctx.send.call_args.args[0]


# ---------------- canal de arquivo indisponível: as três causas não podem
# virar a mesma mensagem de novo (ver decisoes.md § canal de arquivo
# indisponível) ----------------
def test_env_var_ausente_e_canal_nao_resolvido_geram_mensagens_diferentes(bot_de_teste, monkeypatch):
    db.criar_jogador(1, "Alice")

    monkeypatch.delenv("CANAL_ARQUIVO_ID", raising=False)
    ctx_sem_id = FakeCtx(1, anexos=[FakeAnexoEnviado(b"a", "image/png")])
    cmd = bot_de_teste.get_command("avatar")
    asyncio.run(cmd.callback(ctx_sem_id))

    monkeypatch.setenv("CANAL_ARQUIVO_ID", "999999")
    monkeypatch.setattr(bot_de_teste, "get_channel", lambda cid: None)
    monkeypatch.setattr(
        bot_de_teste, "fetch_channel",
        AsyncMock(side_effect=discord.NotFound(_RespostaHTTPFalsa(), "Unknown Channel")),
    )
    avatar._canal_cache = None
    ctx_nao_resolvido = FakeCtx(1, anexos=[FakeAnexoEnviado(b"a", "image/png")])
    asyncio.run(cmd.callback(ctx_nao_resolvido))

    msg_sem_id = ctx_sem_id.send.call_args.args[0]
    msg_nao_resolvido = ctx_nao_resolvido.send.call_args.args[0]
    assert msg_sem_id == avatar.MSG_CANAL_SEM_ID
    assert msg_nao_resolvido == avatar.MSG_CANAL_NAO_ENCONTRADO
    assert msg_sem_id != msg_nao_resolvido


def test_bot_sem_permissao_de_anexar_gera_mensagem_propria(bot_de_teste, monkeypatch):
    """Diferente de canal não resolvido -- aqui o canal existe e o bot o
    enxerga, só falta a permissão de Anexar Arquivos, que só aparece como
    Forbidden na hora do `send`, não antes."""
    db.criar_jogador(1, "Alice")
    canal = bot_de_teste._canal_de_teste

    async def send_proibido(file=None, **kwargs):
        raise discord.Forbidden(_RespostaHTTPFalsa(), "Missing Permissions")

    monkeypatch.setattr(canal, "send", send_proibido)
    ctx = FakeCtx(1, anexos=[FakeAnexoEnviado(b"a", "image/png")])
    cmd = bot_de_teste.get_command("avatar")

    asyncio.run(cmd.callback(ctx))

    ctx.send.assert_called_once_with(avatar.MSG_CANAL_SEM_PERMISSAO)


def test_repostar_cai_pra_fetch_channel_quando_cache_esta_frio(monkeypatch):
    """`get_channel` devolvendo None (canal novo, ainda fora do cache de
    guild) não pode virar "canal indisponível" direto -- só depois de
    `fetch_channel` também falhar."""
    db.criar_jogador(1, "Alice")
    monkeypatch.setenv("CANAL_ARQUIVO_ID", "999")
    intents = discord.Intents.default()
    b = commands.Bot(command_prefix="rpg ", intents=intents)
    avatar.instalar(b)
    canal = FakeCanalArquivo()
    monkeypatch.setattr(b, "get_channel", lambda cid: None)
    monkeypatch.setattr(b, "fetch_channel", AsyncMock(return_value=canal))
    ctx = FakeCtx(1, anexos=[FakeAnexoEnviado(b"png-bytes", "image/png")])
    cmd = b.get_command("avatar")

    asyncio.run(cmd.callback(ctx))

    assert canal.enviados == [b"png-bytes"]
    j = db.get_jogador(1)
    assert j["avatar_msg_id"] is not None
    ctx.send.assert_called_once()
    assert "atualizado" in ctx.send.call_args.args[0]


# ---------------- caminho de sucesso não regride com o resolver novo ----------------
def test_caminho_de_sucesso_continua_funcionando_com_o_resolver_novo(bot_de_teste):
    db.criar_jogador(1, "Alice")
    anexo = FakeAnexoEnviado(b"png-bytes", "image/png")
    ctx = FakeCtx(1, anexos=[anexo])
    cmd = bot_de_teste.get_command("avatar")

    asyncio.run(cmd.callback(ctx))

    canal = bot_de_teste._canal_de_teste
    assert canal.enviados == [b"png-bytes"]
    j = db.get_jogador(1)
    assert j["avatar_msg_id"] is not None
    assert j["avatar_url"] is not None
    ctx.send.assert_called_once()
    assert "atualizado" in ctx.send.call_args.args[0]


# ---------------- diagnóstico no on_ready ----------------
def test_diagnosticar_canal_loga_env_var_ausente(monkeypatch, capsys):
    monkeypatch.delenv("CANAL_ARQUIVO_ID", raising=False)
    intents = discord.Intents.default()
    b = commands.Bot(command_prefix="rpg ", intents=intents)

    asyncio.run(avatar.diagnosticar_canal(b))

    saida = capsys.readouterr().out
    assert "não configurado" in saida


def test_diagnosticar_canal_loga_nome_do_canal_quando_resolve_do_cache(monkeypatch, capsys):
    monkeypatch.setenv("CANAL_ARQUIVO_ID", "999")
    intents = discord.Intents.default()
    b = commands.Bot(command_prefix="rpg ", intents=intents)
    canal = MagicMock()
    canal.name = "arquivo-avatares"
    monkeypatch.setattr(b, "get_channel", lambda cid: canal)

    asyncio.run(avatar.diagnosticar_canal(b))

    saida = capsys.readouterr().out
    assert "arquivo-avatares" in saida
    assert "resolvido do cache" in saida


def test_diagnosticar_canal_loga_causa_quando_fetch_channel_tambem_falha(monkeypatch, capsys):
    monkeypatch.setenv("CANAL_ARQUIVO_ID", "999")
    intents = discord.Intents.default()
    b = commands.Bot(command_prefix="rpg ", intents=intents)
    monkeypatch.setattr(b, "get_channel", lambda cid: None)
    monkeypatch.setattr(
        b, "fetch_channel",
        AsyncMock(side_effect=discord.Forbidden(_RespostaHTTPFalsa(), "Missing Access")),
    )

    asyncio.run(avatar.diagnosticar_canal(b))

    saida = capsys.readouterr().out
    assert "Forbidden" in saida
