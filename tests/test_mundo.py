# tests/test_mundo.py
# Step B, commit 1: o jogador passa a ter mundo, não só andar. `mundo.
# na_torre`/`mundo.exigir_torre` são a trava central -- todo comando que
# assume torre (cacar/explorar/boss/party/dungeon/npcs/falar) passa por
# ela. Ver decisoes.md § Step B.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import combate
import database as db
import dungeon
import mundo


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


def _msg(ctx):
    return ctx.send.call_args.args[0]


# ==================================================================
# migração / default -- ninguém existente sente nada
# ==================================================================

def test_jogador_novo_comeca_dentro_da_torre():
    j = _jogador()
    assert j["mundo"] == "torre"
    assert mundo.na_torre(j) is True


def test_na_torre_false_quando_mundo_e_fora():
    j = _jogador(mundo_atual="fora")
    assert mundo.na_torre(j) is False


# ==================================================================
# exigir_torre -- a trava central
# ==================================================================

def test_exigir_torre_deixa_passar_quem_esta_na_torre():
    j = _jogador()
    ctx = _ctx()
    ok = asyncio.run(mundo.exigir_torre(ctx, j))
    assert ok is True
    ctx.send.assert_not_called()


def test_exigir_torre_recusa_em_personagem_quem_esta_fora():
    j = _jogador(mundo_atual="fora")
    ctx = _ctx()
    ok = asyncio.run(mundo.exigir_torre(ctx, j))
    assert ok is False
    ctx.send.assert_awaited_once()
    texto = ctx.send.call_args.args[0]
    assert "não está na torre" in texto.lower() or "porta" in texto.lower()


# ==================================================================
# regressão -- dentro da torre, ninguém sente nada
# ==================================================================

def test_cacar_funciona_normalmente_dentro_da_torre(monkeypatch):
    _jogador(1, classe="guerreiro", forca=20, andar=1)
    ctx = _ctx(1)
    monkeypatch.setattr(bot.random, "choice", lambda lista: lista[0])
    asyncio.run(bot.cacar.callback(ctx))
    ctx.send.assert_awaited_once()
    embed = ctx.send.call_args.kwargs.get("embed") or ctx.send.call_args.args[0]
    assert embed is not None   # rodou até o fim, sem cair na recusa de mundo


# ==================================================================
# jogador fora da torre -- os comandos recusam, em personagem
# ==================================================================

def test_cacar_recusa_fora_da_torre():
    _jogador(1, mundo_atual="fora")
    ctx = _ctx(1)
    asyncio.run(bot.cacar.callback(ctx))
    assert "porta" in _msg(ctx).lower() or "não está na torre" in _msg(ctx).lower()


def test_explorar_recusa_fora_da_torre():
    _jogador(1, mundo_atual="fora")
    ctx = _ctx(1)
    asyncio.run(bot.explorar.callback(ctx))
    assert "porta" in _msg(ctx).lower() or "não está na torre" in _msg(ctx).lower()


def test_npcs_recusa_fora_da_torre():
    _jogador(1, mundo_atual="fora")
    ctx = _ctx(1)
    asyncio.run(bot.listar_npcs.callback(ctx))
    assert "porta" in _msg(ctx).lower() or "não está na torre" in _msg(ctx).lower()


def test_falar_recusa_fora_da_torre():
    _jogador(1, mundo_atual="fora")
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="qualquer"))
    assert "porta" in _msg(ctx).lower() or "não está na torre" in _msg(ctx).lower()


def test_boss_recusa_fora_da_torre(monkeypatch):
    _jogador(1, mundo_atual="fora", andar=15, andar_max=15)
    ctx = _ctx(1)
    stub = AsyncMock()
    monkeypatch.setattr(combate, "iniciar_luta", stub)
    asyncio.run(bot.bot.get_command("boss").callback(ctx))
    assert "porta" in _msg(ctx).lower() or "não está na torre" in _msg(ctx).lower()
    stub.assert_not_awaited()


def test_party_recusa_fora_da_torre():
    _jogador(1, mundo_atual="fora", andar=15, andar_max=15)
    ctx = _ctx(1)
    ctx.guild = MagicMock()
    asyncio.run(bot.bot.get_command("party").callback(ctx))
    assert "porta" in _msg(ctx).lower() or "não está na torre" in _msg(ctx).lower()


def test_dungeon_recusa_fora_da_torre():
    _jogador(1, mundo_atual="fora", andar=9, andar_max=9, nivel=15)
    ctx = _ctx(1)
    asyncio.run(dungeon._executar_entrar_ou_continuar(ctx, db.get_jogador(1)))
    assert "porta" in _msg(ctx).lower() or "não está na torre" in _msg(ctx).lower()
    assert dungeon.obter_run(1) is None   # não criou run nenhuma


# ==================================================================
# commit 3 -- o mirante, a escada e o `rpg viajar` bimundo
# ==================================================================

def test_viajar_fora_sem_destino_mostra_o_mirante():
    _jogador(1, mundo_atual="fora", andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino=0))
    embed = ctx.send.call_args.kwargs["embed"]
    assert embed.title == mundo.TITULO_MIRANTE
    assert "escada" in embed.description.lower()
    assert db.get_jogador(1)["mundo"] == "fora"   # só olhou, não viajou


def test_viajar_15_fora_sobe_a_escada_de_volta_pra_torre():
    _jogador(1, mundo_atual="fora", andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino=15))
    depois = db.get_jogador(1)
    assert depois["mundo"] == "torre"
    assert depois["andar"] == 15        # o andar de antes sobrevive à ida e volta
    assert depois["andar_max"] == 15


def test_viajar_outro_destino_fora_recusa_as_cidades_ainda_nao_existem():
    _jogador(1, mundo_atual="fora", andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino=3))
    assert db.get_jogador(1)["mundo"] == "fora"   # continua fora -- não viajou
    assert "cidades" in _msg(ctx).lower()


def test_viajar_dentro_da_torre_continua_igual_regressao(monkeypatch):
    """O jogador dentro da torre não pode sentir nada do Step B -- viajar
    numérico comum continua funcionando exatamente como sempre."""
    _jogador(1, andar=1, andar_max=5, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino=3))
    depois = db.get_jogador(1)
    assert depois["andar"] == 3
    assert depois["mundo"] == "torre"
