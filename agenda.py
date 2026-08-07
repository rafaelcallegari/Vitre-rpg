# agenda.py
# Avisos automáticos por horário e backup automático do banco. Dois
# tasks.loop independentes. Não importa bot.py — só precisa da instância do bot.

import datetime as dt
import os
import time

import discord
from discord.ext import tasks

import database as db
from npcs import FUSO, HORARIOS_CARROCA, JANELA_CARROCA_MIN

CANAL_TORRE_ID = os.getenv("CANAL_TORRE_ID")

_HORARIOS_TASK = [dt.time(hour=h, minute=m, tzinfo=FUSO) for h, m in HORARIOS_CARROCA]

INTERVALO_BACKUP_HORAS = 2
UM_DIA_SEG = 24 * 3600
UMA_SEMANA_SEG = 7 * 24 * 3600

_loop_carroca = None   # criado em instalar(), ligado em iniciar()
_loop_backup = None    # idem


def _mtime_ou_nunca(caminho):
    return os.path.getmtime(caminho) if os.path.exists(caminho) else -1


def _rotacionar_backups():
    """Escada 3/1/1: 3 cópias de 2 em 2h (~6h de profundidade, giram entre
    si), 1 diária (até 24h atrás) e 1 semanal (até 7 dias atrás) — 5 cópias
    iguais de 2 em 2h só cobririam ~10h e não pegariam corrupção silenciosa
    que demora mais que um dia pra aparecer.

    Decide o que sobrescrever pelo mtime do arquivo que já está em backups/,
    nunca por estado guardado no banco ou em memória — assim o esquema
    continua correto mesmo se o bot reiniciar no meio do ciclo, sem precisar
    de tabela nova."""
    os.makedirs(db.BACKUP_DIR, exist_ok=True)
    agora = time.time()

    recentes = [os.path.join(db.BACKUP_DIR, f"recente_{i}.db") for i in (1, 2, 3)]
    alvo = min(recentes, key=_mtime_ou_nunca)
    db.backup_banco_para(alvo)

    diario = os.path.join(db.BACKUP_DIR, "diario.db")
    if _mtime_ou_nunca(diario) < agora - UM_DIA_SEG:
        db.backup_banco_para(diario)

    semanal = os.path.join(db.BACKUP_DIR, "semanal.db")
    if _mtime_ou_nunca(semanal) < agora - UMA_SEMANA_SEG:
        db.backup_banco_para(semanal)


def instalar(bot):
    """Registra os loops de backup e aviso da carroça.

    Só registra — não inicia. tasks.Loop.start() precisa rodar dentro do
    event loop de verdade do bot, senão a task nasce presa no loop errado.

    O backup é registrado ANTES da checagem de CANAL_TORRE_ID de propósito:
    ele não depende de canal nenhum e tem que rodar sempre, mesmo em servidor
    sem esse .env configurado.
    """
    global _loop_carroca, _loop_backup

    @tasks.loop(hours=INTERVALO_BACKUP_HORAS)
    async def backup_automatico():
        try:
            _rotacionar_backups()
        except Exception as erro:
            # mesmo raciocínio do avisar_carroca: uma falha não pode
            # derrubar o loop, senão os próximos horários também somem.
            print(f"agenda.py: falha no backup automático — {erro}")

    @backup_automatico.before_loop
    async def esperar_bot_backup():
        await bot.wait_until_ready()

    _loop_backup = backup_automatico
    print(f"agenda.py carregado — backup automático a cada {INTERVALO_BACKUP_HORAS}h "
          "(escada 3/1/1 em backups/).")

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
    if _loop_backup is not None and not _loop_backup.is_running():
        _loop_backup.start()
    if _loop_carroca is not None and not _loop_carroca.is_running():
        _loop_carroca.start()
