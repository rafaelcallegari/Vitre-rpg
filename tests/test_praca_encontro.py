# tests/test_praca_encontro.py
# A Praça, commit 3: o encontro. `rpg trade` continua exatamente como é
# (só ganhou onde acontecer, ver trocas._estao_juntos e test_mural.py) --
# o que faltava era saber quem mais está lá, senão a Praça é sala de
# espera cega. `rpg praca` lista quem está no mundo == PRACA agora,
# resolvendo nome de exibição via ctx.guild.get_member quando dá, caindo
# pro nome do personagem quando não (sem guild, ou membro que saiu).
# Ver decisoes.md § A Praça.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import database as db
import mundo
import trocas


def _na_praca(user_id=1, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    db.atualizar_jogador(
        user_id, mundo=mundo.PRACA,
        andar=campos.pop("andar", 5), andar_max=campos.pop("andar_max", 5), **campos,
    )
    return db.get_jogador(user_id)


def _fora_da_praca(user_id=1, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    return db.get_jogador(user_id)


def _ctx(user_id=1, guild=None):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    ctx.guild = guild
    return ctx


def _msg(ctx):
    return ctx.send.call_args.args[0] if ctx.send.call_args.args else ""


def _praca(ctx):
    asyncio.run(bot.bot.get_command("praca").callback(ctx))


# ==================================================================
# só funciona na Praça, como o resto do commit 2
# ==================================================================

def test_rpg_praca_fora_da_praca_e_recusado():
    _fora_da_praca(1, andar=3, andar_max=5)
    ctx = _ctx(1)
    _praca(ctx)
    assert "praça" in _msg(ctx).lower()


# ==================================================================
# quem está lá -- o autor sempre está incluído (é quem perguntou)
# ==================================================================

def test_sozinho_na_praca_mostra_mensagem_de_sozinho():
    _na_praca(1)
    ctx = _ctx(1)
    _praca(ctx)
    embed = ctx.send.call_args.kwargs["embed"]
    assert "só você" in embed.description.lower()


def test_com_outro_jogador_lista_os_dois():
    _na_praca(1)
    _na_praca(2)
    ctx = _ctx(1)
    _praca(ctx)
    embed = ctx.send.call_args.kwargs["embed"]
    assert "jogador1" in embed.description.lower()
    assert "jogador2" in embed.description.lower()
    assert "você" in embed.description.lower()   # o autor está marcado


def test_quem_nao_esta_na_praca_nao_aparece_na_lista():
    _na_praca(1)
    _fora_da_praca(2, andar=9, andar_max=9)   # dentro da torre, não na Praça
    ctx = _ctx(1)
    _praca(ctx)
    embed = ctx.send.call_args.kwargs["embed"]
    assert "jogador2" not in embed.description.lower()


def test_usa_o_display_name_do_discord_quando_disponivel():
    _na_praca(1)
    _na_praca(2)
    membro2 = MagicMock()
    membro2.display_name = "Apelido Discord"
    guild = MagicMock()
    guild.get_member = MagicMock(side_effect=lambda uid: membro2 if uid == 2 else None)
    ctx = _ctx(1, guild=guild)
    _praca(ctx)
    embed = ctx.send.call_args.kwargs["embed"]
    assert "apelido discord" in embed.description.lower()


def test_cai_pro_nome_do_personagem_sem_guild():
    """Sem `ctx.guild` (DM, ou membro que já saiu do servidor), a lista
    não quebra -- só usa o nome do personagem salvo no banco."""
    _na_praca(1)
    _na_praca(2)
    ctx = _ctx(1, guild=None)
    _praca(ctx)
    embed = ctx.send.call_args.kwargs["embed"]
    assert "jogador2" in embed.description.lower()


# ==================================================================
# regressão -- rpg trade continua exatamente como é
# ==================================================================

def test_trade_dentro_da_torre_continua_igual_regressao():
    trocas.TROCAS_ATIVAS.clear()   # trocas.py guarda estado em memória, não no banco -- outro teste pode ter deixado 1/2 "presos"
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, andar=3, andar_max=5)
    db.criar_jogador(2, "Bob")
    db.atualizar_jogador(2, andar=3, andar_max=5)
    ctx = _ctx(1)
    ctx.message = MagicMock()
    membro = MagicMock()
    membro.id = 2
    membro.bot = False
    membro.display_name = "Bob"
    ctx.message.mentions = [membro]
    asyncio.run(bot.bot.get_command("trade").callback(ctx))
    ctx.send.assert_awaited_once()
    assert "embed" in ctx.send.call_args.kwargs
