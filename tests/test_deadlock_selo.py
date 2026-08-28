# tests/test_deadlock_selo.py
# Bug de produção: jogador com andar_max >= 12 que saía do andar 12+ sem
# morrer (viagem pra baixo, teleporte da Guia, ajuda de party) ficava com
# andar <= 11 e andar_max maior — `rpg viajar {andar_max}` recusava (acima
# do teto de 11) e `rpg boss`/`rpg party` também recusavam (exigiam
# andar == andar_max), sem saída nenhuma. Ver decisoes.md § Teto de `rpg
# viajar` acima do Selo — Bug: deadlock permanente pra quem descia do 12+.
#
# Correção: acima do Selo, `checar_sala_do_chefe` passa a exigir só
# andar <= andar_max. Do 1 ao 10 a regra `==` continua intocada.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import andares_altos
import bot  # noqa: F401 -- import direto popula combate.H (combate.instalar)
import combate
import database as db


def _jogador(user_id, andar, andar_max):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    db.atualizar_jogador(user_id, andar=andar, andar_max=andar_max)
    return db.get_jogador(user_id)


def _ctx(user_id):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    return ctx


def _msg(ctx):
    return ctx.send.call_args.args[0]


# ---------------------------------------------------------------- rpg boss
def _boss(user_id, andar, andar_max, monkeypatch):
    """Roda `rpg boss` de verdade, mas troca `iniciar_luta` por um stub --
    o que importa aqui é só se `checar_sala_do_chefe` deixou passar ou não,
    não o motor de combate inteiro (já coberto em test_combate.py)."""
    _jogador(user_id, andar, andar_max)
    ctx = _ctx(user_id)
    stub = AsyncMock()
    monkeypatch.setattr(combate, "iniciar_luta", stub)
    asyncio.run(bot.bot.get_command("boss").callback(ctx))
    return ctx, stub


def test_boss_hospeda_andar_11_com_andar_max_13_e_o_caso_do_bug(monkeypatch):
    ctx, stub = _boss(1, andar=11, andar_max=13, monkeypatch=monkeypatch)
    stub.assert_awaited_once()
    ctx.send.assert_not_called()


def test_boss_hospeda_andar_13_com_andar_max_13_nao_regrediu(monkeypatch):
    ctx, stub = _boss(2, andar=13, andar_max=13, monkeypatch=monkeypatch)
    stub.assert_awaited_once()
    ctx.send.assert_not_called()


def test_boss_hospeda_andar_11_com_andar_max_11(monkeypatch):
    ctx, stub = _boss(3, andar=11, andar_max=11, monkeypatch=monkeypatch)
    stub.assert_awaited_once()
    ctx.send.assert_not_called()


def test_boss_recusa_andar_7_com_andar_max_13_e_cita_o_andar_11(monkeypatch):
    ctx, stub = _boss(4, andar=7, andar_max=13, monkeypatch=monkeypatch)
    stub.assert_not_awaited()
    assert "não é sua pra abrir" in _msg(ctx)
    assert "rpg viajar 11" in _msg(ctx)
    assert "sobe lutando" in _msg(ctx)


def test_boss_recusa_andar_7_com_andar_max_10_e_cita_o_andar_10(monkeypatch):
    ctx, stub = _boss(5, andar=7, andar_max=10, monkeypatch=monkeypatch)
    stub.assert_not_awaited()
    assert "não é sua pra abrir" in _msg(ctx)
    assert "rpg viajar 10" in _msg(ctx)
    assert "sobe lutando" not in _msg(ctx)   # andar_max não passa do LIMITE_VIAJAR aqui


# ---------------------------------------------------------------- rpg party
def _party(user_id, andar, andar_max):
    _jogador(user_id, andar, andar_max)
    ctx = _ctx(user_id)
    asyncio.run(bot.bot.get_command("party").callback(ctx))
    return ctx


def test_party_hospeda_andar_11_com_andar_max_13_e_o_caso_do_bug():
    ctx = _party(6, andar=11, andar_max=13)
    ctx.send.assert_called_once()
    view = ctx.send.call_args.kwargs.get("view")
    assert isinstance(view, combate.SalaDeEspera)   # abriu sala, não recusou


def test_party_hospeda_andar_13_com_andar_max_13_nao_regrediu():
    ctx = _party(7, andar=13, andar_max=13)
    view = ctx.send.call_args.kwargs.get("view")
    assert isinstance(view, combate.SalaDeEspera)


def test_party_hospeda_andar_11_com_andar_max_11():
    ctx = _party(8, andar=11, andar_max=11)
    view = ctx.send.call_args.kwargs.get("view")
    assert isinstance(view, combate.SalaDeEspera)


def test_party_recusa_andar_7_com_andar_max_13_e_cita_o_andar_11_e_ajudar():
    ctx = _party(9, andar=7, andar_max=13)
    view = ctx.send.call_args.kwargs.get("view")
    assert not isinstance(view, combate.SalaDeEspera)
    assert "rpg viajar 11" in _msg(ctx)
    assert "Se é pra ajudar" in _msg(ctx)   # extra só aparece em party=True


def test_party_recusa_andar_7_com_andar_max_10_e_cita_o_andar_10():
    ctx = _party(10, andar=7, andar_max=10)
    assert "rpg viajar 10" in _msg(ctx)


# ------------------------------------------------------- LIMITE_VIAJAR / módulo
def test_limite_viajar_mora_em_andares_altos_e_bot_reexporta_o_mesmo_valor():
    assert bot.LIMITE_VIAJAR is andares_altos.LIMITE_VIAJAR
    assert combate.LIMITE_VIAJAR is andares_altos.LIMITE_VIAJAR
    assert andares_altos.LIMITE_VIAJAR == andares_altos.ANDAR_ACIMA_DO_SELO + 1
