# agenda.py
# Avisos automáticos por horário. Por enquanto só a carroça do Bramm: um
# tasks.loop que dispara exatamente nos horários da carroça e avisa no canal
# configurado. Não importa bot.py — só precisa da instância do bot.

import datetime as dt
import os

import discord
from discord.ext import tasks

from npcs import FUSO, HORARIOS_CARROCA, JANELA_CARROCA_MIN

CANAL_TORRE_ID = os.getenv("CANAL_TORRE_ID")

_HORARIOS_TASK = [dt.time(hour=h, minute=m, tzinfo=FUSO) for h, m in HORARIOS_CARROCA]

_loop_carroca = None   # criado em instalar(), ligado em iniciar()


def instalar(bot):
    """Registra o loop de aviso da carroça. Sem CANAL_TORRE_ID no .env, fica desligado.

    Só registra — não inicia. tasks.Loop.start() precisa rodar dentro do
    event loop de verdade do bot, senão a task nasce presa no loop errado.
    """
    global _loop_carroca
    if not CANAL_TORRE_ID:
        print("agenda.py: CANAL_TORRE_ID não configurado no .env — aviso da carroça desligado.")
        return

    @tasks.loop(time=_HORARIOS_TASK)
    async def avisar_carroca():
        canal = bot.get_channel(int(CANAL_TORRE_ID))
        if canal is None:
            print(f"agenda.py: canal {CANAL_TORRE_ID} não encontrado — aviso da carroça pulado.")
            return
        sai_em = (dt.datetime.now(FUSO) + dt.timedelta(minutes=JANELA_CARROCA_MIN)).strftime("%H:%M")
        try:
            await canal.send(
                "@everyone 🐎 **A carroça do Bramm chegou!** Ela fica até as "
                f"**{sai_em}** — `rpg viajar <andar>` não custa nada enquanto ela estiver aqui.",
                allowed_mentions=discord.AllowedMentions(everyone=True),
            )
        except discord.HTTPException as erro:
            # canal sem permissão de "Mencionar @everyone", ou outra falha da API —
            # não pode derrubar o loop, senão os próximos horários também somem.
            print(f"agenda.py: falha ao avisar a carroça — {erro}")

    @avisar_carroca.before_loop
    async def esperar_bot():
        await bot.wait_until_ready()

    _loop_carroca = avisar_carroca
    horarios = ", ".join(f"{h:02d}:{m:02d}" for h, m in HORARIOS_CARROCA)
    print(f"agenda.py carregado — aviso da carroça em {horarios} (America/Sao_Paulo).")


def iniciar():
    """Chama isso de dentro de on_ready — é quando o event loop do bot já existe de verdade."""
    if _loop_carroca is not None and not _loop_carroca.is_running():
        _loop_carroca.start()
