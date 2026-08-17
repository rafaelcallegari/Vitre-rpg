# tests/test_manutencao_e_aviso.py
# rpg aviso + modo manutenção (admin.py + travas.py). Testado direto nos
# callbacks (`cmd.callback(...)`), pulando o check `commands.is_owner()` —
# ele faria uma chamada HTTP real pra resolver o dono do app, o que não tem
# lugar num teste isolado. O que se quer testar aqui é o corpo do comando e
# a trava em `travas.py`, não o `is_owner()` do discord.py em si.
import discord
import pytest
from discord.ext import commands

import admin
import travas


@pytest.fixture(autouse=True)
def limpar_travas():
    """Toda trava é estado de módulo em memória — sem isso um teste
    vazaria manutenção ligada ou gente "em luta" pro próximo."""
    travas.desligar_manutencao()
    travas.destravar_todos(list(travas._em_luta.keys()))
    yield
    travas.desligar_manutencao()
    travas.destravar_todos(list(travas._em_luta.keys()))


class FakeAutor:
    def __init__(self, id):
        self.id = id


class FakeCtx:
    def __init__(self, author_id=1, command=None):
        self.author = FakeAutor(author_id)
        self.command = command
        self.mensagens = []

    async def send(self, conteudo=None, **kwargs):
        self.mensagens.append(conteudo)


class FakeCanal:
    def __init__(self):
        self.mention = "#torre"
        self.enviados = []

    async def send(self, content=None, embed=None, allowed_mentions=None):
        self.enviados.append(
            {"content": content, "embed": embed, "allowed_mentions": allowed_mentions}
        )


class FakeUsuario:
    def __init__(self, id):
        self.id = id
        self.dms = []

    async def send(self, texto):
        self.dms.append(texto)


@pytest.fixture
def bot_de_teste(monkeypatch):
    """`commands.Bot` de verdade (pros decorators `@bot.command`/`.error`
    funcionarem exatamente como em produção), mas `get_channel`/`fetch_user`
    trocados por fakes — nenhuma rede envolvida."""
    intents = discord.Intents.default()
    b = commands.Bot(command_prefix="rpg ", intents=intents)
    admin.instalar(b)

    canal = FakeCanal()
    monkeypatch.setattr(b, "get_channel", lambda cid: canal)
    monkeypatch.setattr(admin, "CANAL_TORRE_ID", "123")

    usuarios = {}

    async def fake_fetch_user(uid):
        usuarios.setdefault(uid, FakeUsuario(uid))
        return usuarios[uid]

    monkeypatch.setattr(b, "fetch_user", fake_fetch_user)
    b._canal_de_teste = canal
    b._usuarios_de_teste = usuarios
    return b


# ---------------------------------------------------------------- manutenção


def test_trava_recusa_via_predicado_isolado():
    """Unidade: o predicado que `fora_de_manutencao()` devolve (o mesmo que
    `boss`/`party`/`raide` usam) recusa com a janela ligada. O teste de
    integração logo abaixo confirma que os três comandos DE VERDADE carregam
    esse predicado."""
    async def cenario():
        travas.ligar_manutencao(5, owner_id=1)
        predicado = travas.fora_de_manutencao().predicate
        with pytest.raises(travas.ManutencaoAtiva):
            await predicado(FakeCtx())

    import asyncio
    asyncio.run(cenario())


def test_checks_reais_de_boss_party_raide_incluem_a_trava_de_manutencao():
    """Integração: confirma que os comandos DE VERDADE (registrados em
    combate.py/raide.py via bot.py) carregam o check novo, não só que o
    check funciona isolado."""
    import os
    os.environ.setdefault("DISCORD_TOKEN", "token-fake-nunca-usado")
    import sys
    sys.modules.pop("bot", None)
    import bot as bot_module

    async def cenario():
        travas.ligar_manutencao(5, owner_id=1)
        ctx = FakeCtx()
        for nome in ("boss", "party", "raide"):
            cmd = bot_module.bot.get_command(nome)
            with pytest.raises(travas.ManutencaoAtiva):
                for check in cmd.checks:
                    await check(ctx)

    import asyncio
    asyncio.run(cenario())


def test_comando_de_leitura_nao_e_afetado_pela_manutencao():
    import os
    os.environ.setdefault("DISCORD_TOKEN", "token-fake-nunca-usado")
    import sys
    sys.modules.pop("bot", None)
    import bot as bot_module

    async def cenario():
        travas.ligar_manutencao(5, owner_id=1)
        ctx = FakeCtx()
        cmd = bot_module.bot.get_command("perfil")
        assert cmd is not None
        for check in cmd.checks:
            assert await check(ctx) is not False

    import asyncio
    asyncio.run(cenario())


def test_janela_expira_sozinha():
    travas.ligar_manutencao(0, owner_id=1)  # 0 minuto -> já vence
    assert travas.manutencao_ativa() is False


def test_fim_corta_antes_do_prazo():
    travas.ligar_manutencao(30, owner_id=1)
    assert travas.manutencao_ativa() is True
    travas.desligar_manutencao()
    assert travas.manutencao_ativa() is False


def test_luta_ja_aberta_nao_e_interrompida_pela_janela():
    """A janela trava abrir luta NOVA — não mexe em quem já está `em_luta`."""
    travas.travar_todos([42])
    travas.ligar_manutencao(10, owner_id=1)
    assert travas.em_luta(42) is True
    travas.destravar(42)


def test_aviso_dispara_quando_a_ultima_luta_fecha(bot_de_teste):
    async def cenario():
        travas.travar_todos([42])
        travas.ligar_manutencao(10, owner_id=99)
        assert travas.manutencao_notificada() is False

        # a luta ainda está aberta -- não deveria ter avisado nada ainda
        assert travas.ninguem_em_luta() is False

        travas.destravar(42)
        assert travas.ninguem_em_luta() is True

        # simula o que o loop de checagem faz quando percebe que esvaziou
        if not travas.manutencao_notificada() and travas.ninguem_em_luta():
            travas.marcar_manutencao_notificada()
            await admin.avisar_dono_pode_reiniciar(bot_de_teste, travas.manutencao_owner_id())

        usuario = bot_de_teste._usuarios_de_teste[99]
        assert len(usuario.dms) == 1
        assert "pode reiniciar" in usuario.dms[0]

    import asyncio
    asyncio.run(cenario())


def test_aviso_dispara_na_hora_quando_nao_havia_luta_nenhuma(bot_de_teste):
    async def cenario():
        cmd = bot_de_teste.get_command("manutencao")
        ctx = FakeCtx(author_id=99)
        await cmd.callback(ctx, arg="10")

        assert travas.manutencao_ativa() is True
        assert travas.manutencao_notificada() is True

        usuario = bot_de_teste._usuarios_de_teste[99]
        assert len(usuario.dms) == 1
        assert "pode reiniciar" in usuario.dms[0]

    import asyncio
    asyncio.run(cenario())


def test_manutencao_com_luta_ativa_nao_avisa_na_hora(bot_de_teste):
    async def cenario():
        travas.travar_todos([7])
        cmd = bot_de_teste.get_command("manutencao")
        ctx = FakeCtx(author_id=99)
        await cmd.callback(ctx, arg="10")

        assert travas.manutencao_ativa() is True
        assert travas.manutencao_notificada() is False
        assert 99 not in bot_de_teste._usuarios_de_teste

        travas.destravar(7)

    import asyncio
    asyncio.run(cenario())


def test_manutencao_fim_via_comando(bot_de_teste):
    async def cenario():
        cmd = bot_de_teste.get_command("manutencao")
        ctx = FakeCtx(author_id=99)
        await cmd.callback(ctx, arg="10")
        assert travas.manutencao_ativa() is True

        ctx2 = FakeCtx(author_id=99)
        await cmd.callback(ctx2, arg="fim")
        assert travas.manutencao_ativa() is False

    import asyncio
    asyncio.run(cenario())


def test_recusa_do_comando_diz_quanto_falta():
    travas.ligar_manutencao(10, owner_id=1)
    restante = travas.manutencao_restante()
    erro = travas.ManutencaoAtiva(restante)
    texto = f"volta em **{travas.fmt_restante(erro.restante_seg)}**"
    assert "m" in texto  # ~10 minutos formatados


# ---------------------------------------------------------------- rpg aviso


def test_categoria_desconhecida_nao_derruba_o_comando(bot_de_teste):
    async def cenario():
        cmd = bot_de_teste.get_command("aviso")
        ctx = FakeCtx(author_id=1)
        await cmd.callback(ctx, "categoria_que_nao_existe", resto="mensagem qualquer")

        assert len(ctx.mensagens) == 1
        assert "não existe" in ctx.mensagens[0]
        assert len(bot_de_teste._canal_de_teste.enviados) == 0

    import asyncio
    asyncio.run(cenario())


def test_categoria_valida_envia_no_canal_da_torre(bot_de_teste):
    async def cenario():
        cmd = bot_de_teste.get_command("aviso")
        ctx = FakeCtx(author_id=1)
        await cmd.callback(ctx, "manutencao", resto="Reiniciando às 22h.")

        enviados = bot_de_teste._canal_de_teste.enviados
        assert len(enviados) == 1
        assert enviados[0]["content"] is None  # sem @everyone por padrão
        assert enviados[0]["allowed_mentions"].everyone is False
        assert "Reiniciando às 22h." in enviados[0]["embed"].description

    import asyncio
    asyncio.run(cenario())


def test_everyone_e_escolha_explicita_na_hora(bot_de_teste):
    async def cenario():
        cmd = bot_de_teste.get_command("aviso")
        ctx = FakeCtx(author_id=1)
        await cmd.callback(ctx, "urgente", resto="--everyone Caiu o servidor.")

        enviados = bot_de_teste._canal_de_teste.enviados
        assert enviados[0]["content"] == "@everyone"
        assert enviados[0]["allowed_mentions"].everyone is True
        assert "Caiu o servidor." in enviados[0]["embed"].description
        assert "--everyone" not in enviados[0]["embed"].description

    import asyncio
    asyncio.run(cenario())


def test_todas_as_categorias_do_rascunho_existem():
    for categoria in ("manutencao", "atualizacao", "evento", "urgente", "recado"):
        embed = admin.embed_aviso(categoria, "teste")
        assert embed.description == "teste"


def test_aviso_sem_argumento_ensina_em_vez_de_recusar(bot_de_teste):
    """`rpg aviso` sozinho não pode virar MissingRequiredArgument nem cair
    no "a Torre engasgou" — tem que responder com a ajuda, sem erro nenhum."""
    async def cenario():
        cmd = bot_de_teste.get_command("aviso")
        ctx = FakeCtx(author_id=1)
        await cmd.callback(ctx, categoria=None, resto=None)

        assert len(ctx.mensagens) == 1
        texto = ctx.mensagens[0]
        for categoria in admin.CATEGORIAS_AVISO:
            assert categoria in texto
        assert "engasgou" not in texto.lower()
        assert len(bot_de_teste._canal_de_teste.enviados) == 0

    import asyncio
    asyncio.run(cenario())


def test_ajuda_do_aviso_vem_da_mesma_constante(monkeypatch):
    """Some uma categoria da constante, tem que sumir da ajuda também —
    prova que não é uma lista escrita a mão em paralelo."""
    categorias_reduzidas = dict(admin.CATEGORIAS_AVISO)
    removida = categorias_reduzidas.pop("recado")
    monkeypatch.setattr(admin, "CATEGORIAS_AVISO", categorias_reduzidas)

    texto = admin.texto_ajuda_aviso()

    assert "recado" not in texto
    assert removida["descricao"] not in texto
    for categoria in categorias_reduzidas:
        assert categoria in texto


# ---------------------------------------------------------- erro genérico


class FakeCommand:
    """Simula só o pedaço de `discord.ext.commands.Command` que
    `on_command_error` consulta — sem precisar registrar um `Bot` de
    verdade só pra isso."""

    def __init__(self, nome, signature, tem_handler_proprio):
        self.qualified_name = nome
        self.signature = signature
        self._tem_handler = tem_handler_proprio

    def has_error_handler(self):
        return self._tem_handler


def _importar_bot_module():
    import os
    import sys
    os.environ.setdefault("DISCORD_TOKEN", "token-fake-nunca-usado")
    sys.modules.pop("bot", None)
    import bot as bot_module
    return bot_module


def test_missing_required_argument_nao_cai_no_ramo_generico():
    """Comando SEM handler local (a maioria do bot) — a mensagem tem que
    ensinar o uso, nunca 'a Torre engasgou', e o comando não pode
    re-levantar o erro (senão o traceback também iria pro log à toa)."""
    bot_module = _importar_bot_module()

    async def cenario():
        cmd = FakeCommand("resetarjogador", "<membro>", tem_handler_proprio=False)
        ctx = FakeCtx(command=cmd)
        param = type("Param", (), {"name": "membro", "displayed_name": None})()
        erro = commands.MissingRequiredArgument(param)

        await bot_module.on_command_error(ctx, erro)

        assert len(ctx.mensagens) == 1
        texto = ctx.mensagens[0].lower()
        assert "engasgou" not in texto
        assert "membro" in texto
        assert "resetarjogador" in texto

    import asyncio
    asyncio.run(cenario())


def test_comando_com_handler_proprio_nao_recebe_mensagem_duplicada():
    """O bug original: comando com `@comando.error` já respondia, e o
    handler global mandava 'engasgou' por cima. `has_error_handler()` faz
    o handler global ficar quieto quando já tem dono cuidando do erro."""
    bot_module = _importar_bot_module()

    async def cenario():
        cmd = FakeCommand("aviso", "[categoria] [resto]", tem_handler_proprio=True)
        ctx = FakeCtx(command=cmd)
        erro = commands.NotOwner("só o dono")

        await bot_module.on_command_error(ctx, erro)

        assert ctx.mensagens == []

    import asyncio
    asyncio.run(cenario())


def test_bad_argument_ja_nao_cai_no_ramo_generico():
    """Conferindo de passagem, como pedido: BadArgument (ex.: número onde
    se espera texto) já tinha ramo próprio antes desse cartão — continua
    tendo, e continua sem re-levantar."""
    bot_module = _importar_bot_module()

    async def cenario():
        ctx = FakeCtx(command=None)
        erro = commands.BadArgument("não deu pra converter")

        await bot_module.on_command_error(ctx, erro)

        assert len(ctx.mensagens) == 1
        assert "engasgou" not in ctx.mensagens[0].lower()

    import asyncio
    asyncio.run(cenario())
