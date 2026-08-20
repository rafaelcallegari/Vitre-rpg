# tests/test_hybrid_commands.py
# Leva 1 da conversão pra `commands.hybrid_command` (App Directory exige
# slash command ou Message Content aprovado em review -- a segunda rota está
# fechada pro Vitre bot). Só os quatro comandos de leitura pura desta leva:
# ajuda, perfil, classe, profissao. Ver decisoes.md § comandos híbridos
# (leva 1).
import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

import admin
import bot
import database as db
import game_data


def _ctx(user_id=1, display_name="Alice", como_slash=False):
    """`como_slash=True` simula uma Context nascida de uma interação --
    `ctx.interaction` não-None é o único jeito de diferenciar os dois modos
    (regra 7: `Context.send`/`Context.defer` decidem sozinhos com base
    nisso, o corpo do comando nunca olha pra `ctx.interaction`)."""
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.author.display_name = display_name
    ctx.send = AsyncMock()
    ctx.defer = AsyncMock()
    ctx.interaction = MagicMock() if como_slash else None
    return ctx


COMANDOS_DA_LEVA = ("ajuda", "perfil", "classe", "profissao")


# ---------------- descrição válida no menu do `/` (regra 1) ----------------
def test_comandos_da_leva_estao_registrados_como_slash_com_descricao_valida():
    for nome in COMANDOS_DA_LEVA:
        cmd = bot.bot.tree.get_command(nome)
        assert cmd is not None, f"`{nome}` não virou app command"
        assert 1 <= len(cmd.description) <= 100, f"`{nome}`: descrição fora de 1-100 chars"


def test_nomes_de_slash_nao_tem_maiuscula_nem_espaco():
    for nome in COMANDOS_DA_LEVA:
        cmd = bot.bot.tree.get_command(nome)
        assert cmd.name == cmd.name.lower()
        assert " " not in cmd.name


# ---------------- rpg ajuda ----------------
def test_ajuda_invocado_como_slash_lista_comandos():
    ctx = _ctx(como_slash=True)

    asyncio.run(bot.ajuda.callback(ctx))

    e = ctx.send.call_args.kwargs["embed"]
    assert "Progressão" in [f.name for f in e.fields]
    assert any("rpg comecar" in f.value for f in e.fields)


# ---------------- rpg perfil ----------------
def test_perfil_invocado_como_slash_defere_e_mostra_a_ficha():
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, classe="guerreiro", pronome="ele")
    ctx = _ctx(como_slash=True)

    asyncio.run(bot.perfil.callback(ctx))

    ctx.defer.assert_awaited_once()
    e = ctx.send.call_args.kwargs["embed"]
    assert "Alice" in e.title
    campo_nivel = next(f for f in e.fields if f.name == "Nível")
    assert "1" in campo_nivel.value


def test_perfil_invocado_por_prefixo_tambem_defere_sem_quebrar():
    """`Context.defer()` de verdade é no-op fora de interação (ver
    discord/ext/commands/context.py) -- aqui só provamos que chamar sem
    checar o modo não quebra nem muda a resposta final."""
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, classe="guerreiro", pronome="ele")
    ctx = _ctx(como_slash=False)

    asyncio.run(bot.perfil.callback(ctx))

    ctx.defer.assert_awaited_once()
    e = ctx.send.call_args.kwargs["embed"]
    assert "Alice" in e.title


# ---------------- rpg classe ----------------
def test_classe_invocado_como_slash_mostra_a_classe_pedida():
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, classe="guerreiro", pronome="ele")
    ctx = _ctx(como_slash=True)

    asyncio.run(bot.classe_cmd.callback(ctx, argumento="mago"))

    e = ctx.send.call_args.kwargs["embed"]
    assert "Mago" in e.title


# ---------------- rpg profissao ----------------
def test_profissao_fallback_registrado_e_com_descricao():
    grupo = bot.bot.get_command("profissao")
    assert grupo.fallback == "ver"
    fallback_cmd = grupo.app_command.get_command("ver")
    assert fallback_cmd is not None
    assert 1 <= len(fallback_cmd.description) <= 100


def test_profissao_trocar_e_subcomando_de_verdade_no_slash():
    grupo = bot.bot.get_command("profissao")
    sub_app = grupo.app_command.get_command("trocar")
    assert sub_app is not None
    assert 1 <= len(sub_app.description) <= 100
    # também precisa existir do lado texto (prefixo), pra `Group.invoke`
    # rotear "rpg profissao trocar ..." pra ele em vez do callback do grupo
    assert grupo.get_command("trocar") is not None


def test_profissao_ver_invocado_como_slash_mostra_ficha_sem_alterar_banco():
    import profissoes

    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, profissao="forja", prof_nivel=1, prof_xp=0, pronome="ele")
    antes = db.get_jogador(1)
    ctx = _ctx(como_slash=True)

    asyncio.run(bot.bot.get_command("profissao").callback(ctx))

    depois = db.get_jogador(1)
    assert dict(depois) == dict(antes)
    e = ctx.send.call_args.kwargs["embed"]
    assert "nível 1" in e.title


def test_profissao_trocar_subcomando_troca_de_verdade():
    import profissoes

    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(
        1, profissao="forja", prof_nivel=5, prof_xp=300,
        moedas=profissoes.CUSTO_TROCA + 100, pronome="ele",
    )
    ctx = _ctx(como_slash=True)
    trocar = bot.bot.get_command("profissao").get_command("trocar")

    asyncio.run(trocar.callback(ctx, nova="alquimia"))

    j = db.get_jogador(1)
    assert j["profissao"] == "alquimia"
    assert j["prof_nivel"] == 1
    assert j["moedas"] == 100
    texto = ctx.send.call_args.args[0]
    assert "alquimia".title() in texto or "Alquimia" in texto


# ---------------- regra 6: erro em slash cai no mesmo on_command_error ----------------
def test_erro_em_comando_hibrido_convergiu_pro_mesmo_handler_nos_dois_modos():
    """`HybridCommand`/`HybridGroup` sempre despacham erro via
    `Command.dispatch_error`, que sempre termina em
    `ctx.bot.dispatch('command_error', ctx, erro)` (discord/ext/commands/
    core.py) -- é o MESMO caminho usado por comando de prefixo puro, então
    `on_command_error` não precisa de nenhum espelho em `tree.on_error`.
    Prova direta: chamar o handler com um erro de conversão (`BadArgument`)
    pra `perfil`, uma vez simulando prefixo (`ctx.interaction=None`) e outra
    simulando slash (`ctx.interaction` setado) -- mesma mensagem nos dois."""
    erro = commands.BadArgument("membro inválido")

    ctx_prefixo = _ctx(como_slash=False)
    ctx_prefixo.command = bot.perfil
    ctx_slash = _ctx(como_slash=True)
    ctx_slash.command = bot.perfil

    asyncio.run(bot.on_command_error(ctx_prefixo, erro))
    asyncio.run(bot.on_command_error(ctx_slash, erro))

    msg_prefixo = ctx_prefixo.send.call_args.args[0]
    msg_slash = ctx_slash.send.call_args.args[0]
    assert msg_prefixo == msg_slash == "Não entendi os argumentos. Confere `rpg ajuda`."


# ---------------- rpg sync (regra 5) ----------------
def _bot_de_teste_com_sync(monkeypatch):
    intents = discord.Intents.default()
    b = commands.Bot(command_prefix="rpg ", intents=intents)
    admin.instalar(b)
    return b


def test_sync_e_restrito_ao_dono():
    b = commands.Bot(command_prefix="rpg ", intents=discord.Intents.default())
    admin.instalar(b)
    cmd = b.get_command("sync")
    assert cmd is not None
    assert any(getattr(c, "__qualname__", "").startswith("is_owner") for c in cmd.checks)


def test_sync_com_guild_id_sincroniza_so_aquela_guild(monkeypatch):
    b = _bot_de_teste_com_sync(monkeypatch)
    copiados = []
    monkeypatch.setattr(b.tree, "copy_global_to", lambda *, guild: copiados.append(guild))
    monkeypatch.setattr(b.tree, "sync", AsyncMock(return_value=[MagicMock(), MagicMock()]))

    ctx = _ctx()
    cmd = b.get_command("sync")
    asyncio.run(cmd.callback(ctx, guild_id=999))

    assert copiados == [discord.Object(id=999)]
    b.tree.sync.assert_awaited_once_with(guild=discord.Object(id=999))
    texto = ctx.send.call_args.args[0]
    assert "999" in texto
    assert "2 comando" in texto


def test_sync_sem_argumento_sincroniza_global(monkeypatch):
    b = _bot_de_teste_com_sync(monkeypatch)
    monkeypatch.setattr(b.tree, "sync", AsyncMock(return_value=[MagicMock()]))

    ctx = _ctx()
    cmd = b.get_command("sync")
    asyncio.run(cmd.callback(ctx, guild_id=None))

    b.tree.sync.assert_awaited_once_with()
    texto = ctx.send.call_args.args[0]
    assert "globalmente" in texto
