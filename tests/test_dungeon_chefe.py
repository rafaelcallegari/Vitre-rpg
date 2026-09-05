# tests/test_dungeon_chefe.py
# Cartão "Step 3 — os 4 espelhos e o motor de decisão de chefe", commits
# 2 e 3: a sala do chefe (a integração dungeon.py <-> a luta de verdade
# contra o espelho) e o Orbe de Ascensão. Os efeitos do espelho em si
# (as 12 habilidades revertidas) têm arquivo próprio, tests/test_espelhos.py.
# Ver decisoes.md § Step 3.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot
import database as db
import dungeon
import game_data

SALAS_DE_TESTE = (
    "camara_dos_ecos", "salao_do_espelho_rachado", "bau_esquecido",
    "jardim_suspenso", "nicho_da_torre",
)

# Só combate/achado (armadilha=True sempre, mas auto-resolvem se a
# armadilha não cair em "percepção") -- usada nos testes que precisam
# de várias salas resolvendo em sequência sem parar numa escolha de
# botão. Nenhum evento aqui (evento sempre precisa de um clique).
SALAS_AUTO_RESOLVIVEIS = (
    "camara_dos_ecos", "corredor_sussurrante", "corrente_solta",
    "covil_ocupado", "bau_esquecido",
)


def _jogador(user_id=1, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    padrao = dict(andar=9, nivel=15, classe="guerreiro", forca=20, destreza=15, inteligencia=10)
    padrao.update(campos)
    db.atualizar_jogador(user_id, **padrao)
    return db.get_jogador(user_id)


def _forcar_esquiva(monkeypatch):
    """Trava as rolagens da armadilha em "esquiva" -- INT=10+40=50 falha
    o alvo 52, DES=15+40=55 passa. Mesma técnica de test_dungeon_
    armadilha.py -- combate/achado sempre carregam a camada agora, um
    teste ponta a ponta precisa neutralizá-la pra continuar auto-
    resolvendo sem parar numa escolha de botão da Percepção."""
    monkeypatch.setattr(dungeon.random, "randint", lambda a, b: 40)


def _ctx(user_id=1):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    return ctx


def _sempre_vitoria(monkeypatch):
    monkeypatch.setitem(dungeon.H, "simular_combate", lambda s, hp, mob, andar_num: (hp, True, ["vitória"]))


# ==================================================================
# Catálogo -- o Orbe não é espólio, não é material, não é tesouro
# ==================================================================

def test_orbe_e_um_tipo_proprio_nao_vendavel_nem_na_loja():
    orbe = game_data.ITENS["orbe_de_ascensao"]
    assert orbe["tipo"] == "orbe"
    assert orbe["tipo"] not in ("espolio", "material", "tesouro")
    assert orbe.get("vendavel", True) is False
    assert orbe.get("loja", True) is False


def test_rpg_vender_recusa_o_orbe_com_mensagem_propria():
    j = _jogador(1)
    db.add_item(1, "orbe_de_ascensao")
    ctx = _ctx(1)

    asyncio.run(bot.vender.callback(ctx, argumento="orbe de ascensao"))

    assert db.tem_item(1, "orbe_de_ascensao")   # continua com o item -- não vendeu
    msg = ctx.send.call_args.args[0]
    assert "ascensão" in msg.lower()
    assert "material de fabricação" not in msg   # não é a mensagem genérica errada


# ==================================================================
# conceder_orbe -- concede uma vez, nunca duplica
# ==================================================================

def test_conceder_orbe_da_o_item_na_primeira_vez():
    _jogador(1)

    concedido = dungeon.conceder_orbe(1)

    assert concedido is True
    assert db.tem_item(1, "orbe_de_ascensao")


def test_conceder_orbe_nao_duplica_na_segunda_vez():
    _jogador(1)
    dungeon.conceder_orbe(1)

    concedido_de_novo = dungeon.conceder_orbe(1)

    assert concedido_de_novo is False
    inventario = {i["item"]: i["qtd"] for i in db.get_inventario(1)}
    assert inventario["orbe_de_ascensao"] == 1   # nunca 2


# ==================================================================
# Completar a sala 5 avança pra sala do chefe -- não apaga a run ainda
# ==================================================================

def test_completar_a_quinta_sala_nao_apaga_a_run_avanca_pro_indice_do_chefe(monkeypatch):
    _sempre_vitoria(monkeypatch)
    _forcar_esquiva(monkeypatch)
    j = _jogador(1)
    db.criar_dungeon_run(1, list(SALAS_AUTO_RESOLVIVEIS))
    db.atualizar_dungeon_run_indice(1, game_data.DUNGEON_SALAS_POR_RUN - 1)   # já na última
    run = dungeon.obter_run(1)

    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j, run))

    run_depois = dungeon.obter_run(1)
    assert run_depois is not None   # a run continua -- ainda não acabou
    assert run_depois["indice"] == game_data.DUNGEON_SALAS_POR_RUN


def test_resolver_a_sala_do_indice_do_chefe_inicia_uma_luta_de_verdade():
    """Commit 3 substitui o placeholder do commit 2 -- a sala do chefe
    agora abre uma luta de verdade (combate.Luta + PainelEspelho)
    contra o espelho da própria classe, não concede o Orbe direto."""
    j = _jogador(1, classe="guerreiro", forca=20)
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))
    db.atualizar_dungeon_run_indice(1, game_data.DUNGEON_SALAS_POR_RUN)
    run = dungeon.obter_run(1)
    ctx = _ctx(1)

    asyncio.run(dungeon.resolver_sala_atual(ctx, j, run))

    painel = ctx.send.call_args.kwargs["view"]
    assert isinstance(painel, dungeon.PainelEspelho)
    chave_espelho = game_data.DUNGEON_ESPELHOS["guerreiro"]
    assert painel.luta.chefe["nome"] == game_data.DUNGEON_ESPELHOS_DADOS[chave_espelho]["nome"]
    assert not db.tem_item(1, "orbe_de_ascensao")   # ainda não venceu -- ainda não tem o Orbe
    assert dungeon.obter_run(1) is not None   # a luta começou, a run não acabou ainda


def test_vencer_o_espelho_concede_o_orbe_e_termina_a_run():
    j = _jogador(1, classe="guerreiro", forca=20)
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))
    db.atualizar_dungeon_run_indice(1, game_data.DUNGEON_SALAS_POR_RUN)
    run = dungeon.obter_run(1)
    ctx = _ctx(1)
    asyncio.run(dungeon.resolver_sala_atual(ctx, j, run))
    painel = ctx.send.call_args.kwargs["view"]

    painel.luta.hp_chefe = 0   # simula a vitória sem depender de RNG de combate real
    embed = asyncio.run(painel.fim_da_luta())

    assert db.tem_item(1, "orbe_de_ascensao")
    assert dungeon.obter_run(1) is None   # a run termina na vitória
    assert embed is not None
    assert "Orbe" in embed.fields[-1].name


def test_vencer_de_novo_com_orbe_ja_existente_nao_concede_outro():
    j = _jogador(1, classe="guerreiro", forca=20)
    db.add_item(1, "orbe_de_ascensao")   # já tinha de uma descida anterior
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))
    db.atualizar_dungeon_run_indice(1, game_data.DUNGEON_SALAS_POR_RUN)
    run = dungeon.obter_run(1)
    ctx = _ctx(1)
    asyncio.run(dungeon.resolver_sala_atual(ctx, j, run))
    painel = ctx.send.call_args.kwargs["view"]

    painel.luta.hp_chefe = 0
    embed = asyncio.run(painel.fim_da_luta())

    inventario = {i["item"]: i["qtd"] for i in db.get_inventario(1)}
    assert inventario["orbe_de_ascensao"] == 1   # continua 1, não virou 2
    assert dungeon.obter_run(1) is None   # a run ainda termina normalmente
    assert "Orbe" not in embed.fields[-1].name   # não anuncia um Orbe que não concedeu


def test_perder_para_o_espelho_processa_morte_de_dungeon_e_apaga_a_run():
    j = _jogador(1, classe="guerreiro", forca=20, moedas=1000)
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))
    db.atualizar_dungeon_run_indice(1, game_data.DUNGEON_SALAS_POR_RUN)
    run = dungeon.obter_run(1)
    ctx = _ctx(1)
    asyncio.run(dungeon.resolver_sala_atual(ctx, j, run))
    painel = ctx.send.call_args.kwargs["view"]
    c = painel.luta.participantes[0]

    c.hp = 0
    c.caiu = True
    embed = asyncio.run(painel.fim_da_luta())

    assert dungeon.obter_run(1) is None   # a run acabou -- mesma penalidade de qualquer morte na dungeon
    assert db.get_jogador(1)["moedas"] < 1000
    assert embed is not None


def test_run_inteira_ponta_a_ponta_ate_vencer_o_espelho(monkeypatch):
    """As 5 salas + a sala do chefe, uma chamada de cada vez -- prova o
    fluxo inteiro, não só o índice isolado."""
    _sempre_vitoria(monkeypatch)
    _forcar_esquiva(monkeypatch)
    j = _jogador(1, classe="guerreiro", forca=20)
    db.criar_dungeon_run(1, list(SALAS_AUTO_RESOLVIVEIS))

    for _ in range(game_data.DUNGEON_SALAS_POR_RUN):
        run = dungeon.obter_run(1)
        assert run is not None
        j = db.get_jogador(1)
        asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j, run))

    run_no_chefe = dungeon.obter_run(1)
    assert run_no_chefe is not None
    assert run_no_chefe["indice"] == game_data.DUNGEON_SALAS_POR_RUN

    j = db.get_jogador(1)
    ctx = _ctx(1)
    asyncio.run(dungeon.resolver_sala_atual(ctx, j, run_no_chefe))
    painel = ctx.send.call_args.kwargs["view"]
    assert dungeon.obter_run(1) is not None   # a luta do espelho começou -- ainda não acabou

    painel.luta.hp_chefe = 0
    asyncio.run(painel.fim_da_luta())

    assert dungeon.obter_run(1) is None
    assert db.tem_item(1, "orbe_de_ascensao")
    assert db.tem_item(1, "orbe_de_ascensao")
