# tests/test_praca.py
# Vitre — A Praça, commit 1: o lugar. Lugar NOMEADO dentro da torre (não
# número de andar) -- viajar pra lá é de graça, de qualquer andar, sem
# cooldown; sair sempre volta pro andar de origem, porque `andar`/
# `andar_max` nunca são tocados (mesmo truque de `sair_pela_porta`/`subir_
# a_escada`, Step B). `mundo.exigir_torre` (já existente) bloqueia cacar/
# explorar/boss/dungeon na Praça de graça -- ela fica DENTRO da torre
# narrativamente, mas `mundo` != TORRE por baixo. Ver decisoes.md § A Praça.
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
# entrar -- de qualquer andar, de graça
# ==================================================================

def test_viajar_praca_de_varios_andares_sempre_volta_pro_de_origem():
    for andar_original in (1, 5, 9, 12, 15):
        _jogador(1, andar=andar_original, andar_max=andar_original, moedas=10000)
        ctx = _ctx(1)
        asyncio.run(bot.viajar.callback(ctx, destino="praca"))
        depois_de_entrar = db.get_jogador(1)
        assert depois_de_entrar["mundo"] == mundo.PRACA
        assert depois_de_entrar["andar"] == andar_original   # nunca mexeu

        ctx2 = _ctx(1)
        asyncio.run(bot.viajar.callback(ctx2, destino="torre"))
        depois_de_sair = db.get_jogador(1)
        assert depois_de_sair["mundo"] == "torre"
        assert depois_de_sair["andar"] == andar_original
        assert depois_de_sair["andar_max"] == andar_original


def test_entrar_na_praca_nao_cobra_moedas_nem_usa_cooldown():
    j = _jogador(1, andar=7, andar_max=7, moedas=500)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino="praca"))
    assert db.get_jogador(1)["moedas"] == j["moedas"]   # nada cobrado
    # sem cooldown -- entra de novo na mesma sessão sem recusa nenhuma
    asyncio.run(bot.viajar.callback(ctx, destino="torre"))
    ctx2 = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx2, destino="praca"))
    assert db.get_jogador(1)["mundo"] == mundo.PRACA


def test_viajar_sem_destino_na_praca_mostra_a_praca():
    _jogador(1, mundo_atual=mundo.PRACA, andar=5, andar_max=5)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino=""))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "praça" in embed.title.lower()
    assert db.get_jogador(1)["mundo"] == mundo.PRACA   # só olhou


# ==================================================================
# só de dentro da torre
# ==================================================================

def test_viajar_praca_de_fora_da_torre_e_recusado():
    _jogador(1, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino="praca"))
    assert db.get_jogador(1)["mundo"] == mundo.MIRANTE   # não alcançou


def test_viajar_praca_do_vilarejo_e_recusado():
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino="praca"))
    assert db.get_jogador(1)["mundo"] == mundo.VILAREJO


# ==================================================================
# convivência, não conteúdo -- caçar/explorar/boss/dungeon recusam
# ==================================================================

def test_cacar_recusa_na_praca():
    _jogador(1, mundo_atual=mundo.PRACA, andar=5, andar_max=5)
    ctx = _ctx(1)
    asyncio.run(bot.cacar.callback(ctx))
    assert "não está na torre" in _msg(ctx).lower() or "porta" in _msg(ctx).lower()


def test_explorar_recusa_na_praca():
    _jogador(1, mundo_atual=mundo.PRACA, andar=5, andar_max=5)
    ctx = _ctx(1)
    asyncio.run(bot.explorar.callback(ctx))
    assert "não está na torre" in _msg(ctx).lower() or "porta" in _msg(ctx).lower()


def test_boss_recusa_na_praca(monkeypatch):
    _jogador(1, mundo_atual=mundo.PRACA, andar=15, andar_max=15)
    ctx = _ctx(1)
    stub = AsyncMock()
    monkeypatch.setattr(combate, "iniciar_luta", stub)
    asyncio.run(bot.bot.get_command("boss").callback(ctx))
    assert "não está na torre" in _msg(ctx).lower() or "porta" in _msg(ctx).lower()
    stub.assert_not_awaited()


def test_dungeon_recusa_na_praca():
    _jogador(1, mundo_atual=mundo.PRACA, andar=9, andar_max=9, nivel=15)
    ctx = _ctx(1)
    asyncio.run(dungeon._executar_entrar_ou_continuar(ctx, db.get_jogador(1)))
    assert "não está na torre" in _msg(ctx).lower() or "porta" in _msg(ctx).lower()
    assert dungeon.obter_run(1) is None


def test_party_recusa_na_praca():
    _jogador(1, mundo_atual=mundo.PRACA, andar=15, andar_max=15)
    ctx = _ctx(1)
    ctx.guild = MagicMock()
    asyncio.run(bot.bot.get_command("party").callback(ctx))
    assert "não está na torre" in _msg(ctx).lower() or "porta" in _msg(ctx).lower()


# ==================================================================
# achados varrendo os comandos -- `andar`/`colher` também liam o andar
# congelado sem perguntar onde o jogador está (mesmo bug, achado aqui)
# ==================================================================

def test_rpg_andar_recusa_na_praca():
    _jogador(1, mundo_atual=mundo.PRACA, andar=5, andar_max=5)
    ctx = _ctx(1)
    asyncio.run(bot.andar_info.callback(ctx))
    assert "não está na torre" in _msg(ctx).lower() or "porta" in _msg(ctx).lower()


def test_rpg_andar_continua_funcionando_dentro_da_torre_regressao():
    _jogador(1, andar=3, andar_max=5)
    ctx = _ctx(1)
    asyncio.run(bot.andar_info.callback(ctx))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "andar 3" in embed.title.lower()


def test_rpg_colher_recusa_na_praca_mesmo_com_andar_congelado_em_1():
    _jogador(1, mundo_atual=mundo.PRACA, andar=1, andar_max=5)
    ctx = _ctx(1)
    asyncio.run(bot.colher.callback(ctx))
    assert "flor nenhuma" in _msg(ctx).lower()


def test_guia_acima_do_selo_nao_fala_na_praca(monkeypatch):
    """Achado no mesmo sweep: o hook `falar_guia_acima_do_selo` lia
    `andar` sem checar `na_torre` -- alguém com andar CONGELADO acima do
    Selo (11+) ouviria a Guia comentar mesmo estando na Praça (ou no
    Mirante/vilarejo), onde ela não existe."""
    j = _jogador(1, mundo_atual=mundo.PRACA, andar=12, andar_max=12, acoes_andar_alto=bot.GUIA_A_CADA_ACOES - 1)
    ctx = _ctx(1)
    ctx.command_failed = False
    ctx.command = MagicMock()
    asyncio.run(bot.falar_guia_acima_do_selo(ctx))
    ctx.send.assert_not_called()


def test_guia_acima_do_selo_continua_falando_dentro_da_torre_regressao():
    _jogador(1, andar=12, andar_max=12, acoes_andar_alto=bot.GUIA_A_CADA_ACOES - 1)
    ctx = _ctx(1)
    ctx.command_failed = False
    ctx.command = MagicMock()
    asyncio.run(bot.falar_guia_acima_do_selo(ctx))
    ctx.send.assert_awaited_once()


# ==================================================================
# regressão -- quem nunca vai à Praça não sente nada
# ==================================================================

def test_quem_nunca_visita_a_praca_nao_sente_nada():
    _jogador(1, andar=1, andar_max=5, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino=3))
    depois = db.get_jogador(1)
    assert depois["andar"] == 3
    assert depois["mundo"] == "torre"


def test_cacar_continua_funcionando_dentro_da_torre_regressao(monkeypatch):
    _jogador(1, classe="guerreiro", forca=20, andar=1)
    ctx = _ctx(1)
    monkeypatch.setattr(bot.random, "choice", lambda lista: lista[0])
    asyncio.run(bot.cacar.callback(ctx))
    ctx.send.assert_awaited_once()
    embed = ctx.send.call_args.kwargs.get("embed") or ctx.send.call_args.args[0]
    assert embed is not None
