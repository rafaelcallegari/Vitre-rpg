# travas.py
# Trava jogadores em luta de chefe pra impedir comando de texto durante o
# combate por turnos — a View controla os botões, mas o canal continuava
# aceitando `rpg comprar`/`rpg upar`/etc no meio da luta, o que anula o
# planejamento de recurso que é o ponto do turno. Não importa combate.py/
# bot.py (evita import circular): é só o registro e o check; combate.py e
# raide.py chamam travar_todos()/destravar()/destravar_todos() nos pontos
# certos do ciclo de vida da luta (ver decisoes.md).

import time

from discord.ext import commands

# registro em memória, de propósito: luta não sobrevive a restart do bot
# (View e estado da Luta são só RAM), então a trava também não deveria —
# uma trava sobrevivendo a restart soft-lockaria todo mundo que estava
# lutando quando o bot caiu.
_em_luta = {}   # user_id -> timestamp de quando entrou na luta

# rede de segurança: TIMEOUT_RODADA (combate.py) é 60s por rodada, e
# nenhuma luta realista passa perto de 20 rodadas. Bem acima disso pra só
# pegar o caso de uma View morrer por exceção sem passar pelo destravar()
# — não é o caminho normal de saída, é o último resort.
EXPIRACAO_SEGUNDOS = 20 * 60

MENSAGEM_BLOQUEIO = "⚔️ Você está numa luta de chefe agora — resolve isso primeiro (ou foge)."


class EmLutaDeChefe(commands.CheckFailure):
    """Levantado quando um comando travado é chamado durante luta de chefe."""


def travar_todos(user_ids):
    agora = time.time()
    for uid in user_ids:
        _em_luta[uid] = agora


def destravar(user_id):
    _em_luta.pop(user_id, None)


def destravar_todos(user_ids):
    for uid in user_ids:
        _em_luta.pop(uid, None)


def em_luta(user_id):
    """True se travado e a trava ainda não expirou. Expirada conta como
    livre e já limpa a entrada — cobre a View que morreu sem limpar."""
    inicio = _em_luta.get(user_id)
    if inicio is None:
        return False
    if time.time() - inicio > EXPIRACAO_SEGUNDOS:
        del _em_luta[user_id]
        return False
    return True


def fora_de_luta():
    """Check pra comandos inteiros (`@bot.command` + `@travas.fora_de_luta()`
    logo abaixo). Pra ações dentro de um comando com sub-ações (ex.: `rpg
    guilda depositar`, que divide o mesmo `@bot.command` com sub-ações
    somente-leitura que não precisam travar), use bloqueado() direto."""
    async def predicado(ctx):
        if em_luta(ctx.author.id):
            raise EmLutaDeChefe()
        return True
    return commands.check(predicado)


async def bloqueado(ctx):
    """Pra sub-ações dentro de um comando com dispatch manual (guildas.py).
    Manda a mensagem e devolve True (bloqueado) se o autor está em luta —
    quem chama só precisa dar `return` quando vier True."""
    if em_luta(ctx.author.id):
        await ctx.send(MENSAGEM_BLOQUEIO)
        return True
    return False
