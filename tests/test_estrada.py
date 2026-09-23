# tests/test_estrada.py
# Step E, commit 1: a estrada. `rpg viajar` fora da torre (Mirante <->
# vilarejo) passa a poder ser interrompido por um encontro -- a viagem para,
# a luta acontece, vencendo o jogador chega ao destino. A escada de volta
# pro andar 15 (a porta) fica de fora -- não é "estrada". Ver decisoes.md
# § Step E.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import combate
import database as db
import estrada
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


def _combatente(user_id, **campos):
    j = _jogador(user_id, **campos)
    return combate.Combatente(j, bot.stats(j))


# ==================================================================
# houve_encontro -- probabilidade pura
# ==================================================================

def test_houve_encontro_sempre_true_com_chance_maxima(monkeypatch):
    monkeypatch.setattr(estrada, "CHANCE_ENCONTRO_ESTRADA", 1.0)
    assert all(estrada.houve_encontro() for _ in range(20))


def test_houve_encontro_sempre_false_com_chance_zero(monkeypatch):
    monkeypatch.setattr(estrada, "CHANCE_ENCONTRO_ESTRADA", 0.0)
    assert not any(estrada.houve_encontro() for _ in range(20))


# ==================================================================
# encontro acontece -- a viagem para, a luta começa
# ==================================================================

def test_encontro_no_mirante_indo_pro_vilarejo_nao_move_o_jogador_ainda(monkeypatch):
    monkeypatch.setattr(estrada, "houve_encontro", lambda: True)
    _jogador(1, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino="vilarejo"))
    assert db.get_jogador(1)["mundo"] == mundo.MIRANTE   # não chegou ainda
    assert "view" in ctx.send.call_args.kwargs
    assert isinstance(ctx.send.call_args.kwargs["view"], estrada.PainelEstrada)


def test_encontro_no_vilarejo_indo_pro_mirante_nao_move_o_jogador_ainda(monkeypatch):
    monkeypatch.setattr(estrada, "houve_encontro", lambda: True)
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino="mirante"))
    assert db.get_jogador(1)["mundo"] == mundo.VILAREJO   # não chegou ainda
    assert isinstance(ctx.send.call_args.kwargs["view"], estrada.PainelEstrada)


def test_sem_encontro_viagem_completa_normalmente(monkeypatch):
    monkeypatch.setattr(estrada, "houve_encontro", lambda: False)
    _jogador(1, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino="vilarejo"))
    assert db.get_jogador(1)["mundo"] == mundo.VILAREJO   # chegou direto
    assert "view" not in ctx.send.call_args.kwargs or not isinstance(
        ctx.send.call_args.kwargs.get("view"), estrada.PainelEstrada
    )


# ==================================================================
# vitória leva ao destino
# ==================================================================

def test_vitoria_na_estrada_completa_a_viagem():
    c = _combatente(1, classe="guerreiro", forca=20, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    luta = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    for inimigo in luta.inimigos:
        inimigo.hp = 0   # vitória forçada

    asyncio.run(estrada._finalizar_vitoria_estrada(luta, 1, mundo.VILAREJO))

    assert db.get_jogador(1)["mundo"] == mundo.VILAREJO


def test_vitoria_na_estrada_nunca_chama_processar_morte(monkeypatch):
    stub = MagicMock()
    monkeypatch.setattr(bot, "processar_morte", stub)
    c = _combatente(1, classe="guerreiro", forca=20, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    luta = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    for inimigo in luta.inimigos:
        inimigo.hp = 0

    asyncio.run(estrada._finalizar_vitoria_estrada(luta, 1, mundo.VILAREJO))

    stub.assert_not_called()


# ==================================================================
# derrota não mata -- a viagem se resolve sem morte
# ==================================================================

def test_derrota_na_estrada_nunca_chama_processar_morte(monkeypatch):
    stub = MagicMock()
    monkeypatch.setattr(bot, "processar_morte", stub)
    c = _combatente(1, classe="guerreiro", forca=20, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    luta = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    c.hp = 0
    c.caiu = True

    asyncio.run(estrada._finalizar_derrota_estrada(luta, 1, mundo.VILAREJO))

    stub.assert_not_called()


def test_derrota_na_estrada_ainda_completa_a_viagem():
    """'A viagem se resolve sem morte' -- perder não impede de chegar,
    só custa (commit 3 decide o quê)."""
    c = _combatente(1, classe="guerreiro", forca=20, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    luta = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    c.hp = 0
    c.caiu = True

    asyncio.run(estrada._finalizar_derrota_estrada(luta, 1, mundo.VILAREJO))

    assert db.get_jogador(1)["mundo"] == mundo.VILAREJO


# ==================================================================
# fugir -- nem punição, nem chegada
# ==================================================================

def test_fuga_na_estrada_nao_completa_a_viagem():
    c = _combatente(1, classe="guerreiro", forca=20, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    luta = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    c.fugiu = True

    asyncio.run(estrada._finalizar_abandono_estrada(luta))

    assert db.get_jogador(1)["mundo"] == mundo.MIRANTE   # continua onde estava


# ==================================================================
# regressão -- o resto de rpg viajar não muda
# ==================================================================

def test_viajar_dentro_da_torre_nunca_passa_pela_estrada(monkeypatch):
    chamou = []
    monkeypatch.setattr(estrada, "houve_encontro", lambda: chamou.append(True) or True)
    _jogador(1, andar=1, andar_max=5, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino=3))
    assert db.get_jogador(1)["andar"] == 3   # viagem normal, sem desvio
    assert chamou == []   # estrada.houve_encontro nunca foi consultado


def test_escada_do_mirante_pro_andar_15_nunca_tem_encontro(monkeypatch):
    """A porta/escada não é 'estrada' -- é o mesmo degrau de sempre."""
    chamou = []
    monkeypatch.setattr(estrada, "houve_encontro", lambda: chamou.append(True) or True)
    _jogador(1, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino=15))
    assert db.get_jogador(1)["mundo"] == "torre"   # chegou, sem desvio de encontro
    assert chamou == []
