# tests/test_incursao.py
# Step D, commit 1: o andar corrompido. O Herói selou a torre de dentro; a
# porta (Step B) ficou aberta; a incursão é a consequência. Um andar por
# dia, sorteado entre 2 e o Selo (10), determinístico (sem tabela nova --
# ver incursao.py) e o mesmo pra todo mundo. Ver decisoes.md § Step D.
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import database as db
import incursao

FUSO = ZoneInfo("America/Sao_Paulo")


def _jogador(user_id=1, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    return db.get_jogador(user_id)


def _ctx(user_id=1):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    return ctx


# ==================================================================
# o sorteio -- determinístico, sem estado, o mesmo pra todo mundo
# ==================================================================

def test_andar_do_dia_e_sempre_o_mesmo_no_mesmo_dia():
    momento = datetime(2026, 3, 5, 10, 0, tzinfo=FUSO)
    assert incursao.andar_do_dia(momento) == incursao.andar_do_dia(momento)


def test_andar_do_dia_sobrevive_a_restart():
    """"Restart" = nada mais que chamar a função de novo -- sem estado
    salvo, não tem "de novo" pra sortear. Duas chamadas independentes, sem
    nenhum cache entre elas, têm que bater."""
    momento = datetime(2026, 3, 5, 23, 59, tzinfo=FUSO)
    primeira = incursao.andar_do_dia(momento)
    segunda = incursao.andar_do_dia(momento)
    assert primeira == segunda


def test_andar_do_dia_muda_no_dia_seguinte_quase_sempre():
    """Não é garantido matematicamente (podia repetir por acaso), mas
    varrendo 30 dias tem que aparecer pelo menos uma troca -- prova que a
    função depende da DATA, não é uma constante disfarçada."""
    valores = {
        incursao.andar_do_dia(datetime(2026, 3, dia, 12, tzinfo=FUSO))
        for dia in range(1, 31)
    }
    assert len(valores) > 1


def test_andar_do_dia_dentro_do_intervalo_em_muitos_dias():
    for dia in range(1, 29):
        n = incursao.andar_do_dia(datetime(2026, 1, dia, 12, tzinfo=FUSO))
        assert incursao.ANDAR_MIN_INCURSAO <= n <= incursao.ANDAR_MAX_INCURSAO


# ==================================================================
# andar 1 e acima do Selo nunca são sorteados
# ==================================================================

def test_andar_1_nunca_e_sorteado():
    for dia in range(1, 29):
        assert incursao.andar_do_dia(datetime(2026, 6, dia, 12, tzinfo=FUSO)) != 1


def test_andares_acima_do_selo_nunca_sao_sorteados():
    for dia in range(1, 29):
        n = incursao.andar_do_dia(datetime(2026, 6, dia, 12, tzinfo=FUSO))
        assert n <= incursao.ANDAR_MAX_INCURSAO
        assert incursao.ANDAR_MAX_INCURSAO == 10   # o Selo -- trava explícita, não achismo


def test_andar_esta_corrompido_bate_com_andar_do_dia():
    momento = datetime(2026, 4, 10, 12, tzinfo=FUSO)
    n = incursao.andar_do_dia(momento)
    assert incursao.andar_esta_corrompido(n, momento) is True
    assert incursao.andar_esta_corrompido(n + 1 if n < 10 else n - 1, momento) is False


# ==================================================================
# rpg cacar/explorar no andar corrompido -- vira de sombra, mesmo chefe
# ==================================================================

def _fixar_andar_do_dia(monkeypatch, momento=None):
    """Calcula o andar corrompido com a função de VERDADE (não a mockada)
    antes de sobrescrever -- `lambda: incursao.andar_do_dia(...)` recursa
    pra sempre depois do setattr, porque o lookup de `incursao.andar_do_dia`
    dentro do lambda passa a apontar pro próprio mock."""
    momento = momento or datetime(2026, 5, 5, 12, tzinfo=FUSO)
    n = incursao.andar_do_dia(momento)
    monkeypatch.setattr(incursao, "andar_do_dia", lambda m=None: n)
    return n


def test_cacar_no_andar_corrompido_mostra_criatura_de_sombra(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    _jogador(1, classe="guerreiro", forca=20, andar=n, andar_max=n)
    ctx = _ctx(1)
    monkeypatch.setattr(bot.random, "choice", lambda lista: lista[0])
    asyncio.run(bot.cacar.callback(ctx))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "Sombra de" in embed.title


def test_cacar_fora_do_andar_corrompido_nao_muda_nada(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    outro = 1 if n != 1 else 2
    _jogador(1, classe="guerreiro", forca=20, andar=outro, andar_max=outro)
    ctx = _ctx(1)
    monkeypatch.setattr(bot.random, "choice", lambda lista: lista[0])
    asyncio.run(bot.cacar.callback(ctx))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "Sombra de" not in embed.title


def test_explorar_no_andar_corrompido_mostra_criaturas_de_sombra(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    _jogador(1, classe="guerreiro", forca=20, andar=n, andar_max=n, moedas=0)
    ctx = _ctx(1)
    monkeypatch.setattr(bot.random, "choice", lambda lista: lista[0])
    asyncio.run(bot.explorar.callback(ctx))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "Sombra de" in embed.description


def test_boss_no_andar_corrompido_continua_normal(monkeypatch):
    """'Não tem chefe novo -- o chefe do andar segue normal.' Regressão:
    o combate de chefe (rpg boss) não passa pelo motor de incursão --
    `iniciar_luta` recebe o `andar_num` de sempre, sem desvio nenhum."""
    n = _fixar_andar_do_dia(monkeypatch)
    import combate
    stub = AsyncMock()
    monkeypatch.setattr(combate, "iniciar_luta", stub)
    _jogador(1, classe="guerreiro", forca=20, andar=n, andar_max=n)
    ctx = _ctx(1)
    asyncio.run(bot.bot.get_command("boss").callback(ctx))
    stub.assert_awaited_once()
    assert stub.await_args.args[2] == n   # andar_num intocado -- boss.callback(ctx, [uid], j["andar"])


# ==================================================================
# rpg incursao -- discoverability
# ==================================================================

def test_rpg_incursao_mostra_o_andar_de_hoje(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    _jogador(1)
    ctx = _ctx(1)
    asyncio.run(bot.incursao_do_dia.callback(ctx))
    embed = ctx.send.call_args.kwargs["embed"]
    assert str(n) in embed.description
