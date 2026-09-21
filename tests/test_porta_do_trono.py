# tests/test_porta_do_trono.py
# Step B, commit 2: a porta atrás do trono. Vencer o chefe do andar 15 não
# reseta mais andar/andar_max pro 10 sozinho -- o jogador fica lá em cima e
# escolhe (Ficar/Sair) via `combate.ViewEscolhaPorta`, oferecida logo depois
# da vitória (`combate._talvez_oferecer_porta`) e, pra quem já venceu antes,
# também por `rpg falar` na porta (npcs.py, "porta": True). Ver decisoes.md
# § Step B.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import combate
import database as db
import game_data

ANDAR_15 = game_data.ANDARES[15]
BOSS = ANDAR_15["boss"]
ANDAR_MAXIMO = game_data.ANDAR_MAXIMO


def _combatente(user_id, andar_max=14, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    db.atualizar_jogador(user_id, classe="guerreiro", forca=20, andar=15, andar_max=andar_max, **campos)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


def _campo(embed, nome):
    return next((f for f in embed.fields if f.name == nome), None)


def _ctx(user_id):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    return ctx


def _interacao(user_id):
    it = MagicMock()
    it.user.id = user_id
    it.response = MagicMock()
    it.response.send_message = AsyncMock()
    it.response.edit_message = AsyncMock()
    it.followup = MagicMock()
    it.followup.send = AsyncMock()
    return it


def _botao(view, label):
    return next(c for c in view.children if getattr(c, "label", None) == label)


# ==================================================================
# recompensar -- vencer o 15 não reseta mais, fica lá em cima
# ==================================================================

def test_vencer_o_15_nao_reseta_fica_no_proprio_andar():
    c = _combatente(1, andar_max=14)
    luta = combate.Luta([c], dict(BOSS), andar_num=15)

    asyncio.run(combate.recompensar(luta, c))

    depois = db.get_jogador(1)
    assert depois["andar"] == 15
    assert depois["andar_max"] == 15   # destrancado, igual qualquer outro andar


def test_embed_de_vitoria_do_15_nao_promete_mais_reset_automatico():
    luta = combate.Luta(combatentes=[], chefe=dict(BOSS), andar_num=15)
    e = asyncio.run(combate.finalizar_vitoria(luta))
    campo = _campo(e, "🌌 O topo, outra vez")
    assert campo is not None
    assert "porta" in campo.value.lower()
    assert "volta pro andar" not in campo.value.lower()


def test_vitoria_normal_fora_do_15_continua_destrancando_o_proximo_andar():
    """Regressão -- andar comum continua exatamente como sempre."""
    luta = combate.Luta(combatentes=[], chefe={**BOSS, "hp": 1}, andar_num=5)
    c = _combatente(2, andar_max=5)
    luta.participantes.append(c)
    e = asyncio.run(combate.finalizar_vitoria(luta))
    assert _campo(e, "⬆️ Andar 6 destrancado") is not None
    assert _campo(e, "🌌 O topo, outra vez") is None


# ==================================================================
# _talvez_oferecer_porta -- só dispara em vitória de verdade no 15
# ==================================================================

def test_nao_oferece_porta_fora_do_andar_15():
    c = _combatente(1)
    luta = combate.Luta([c], {**dict(BOSS), "hp": 1}, andar_num=14)
    luta.hp_chefe = 0
    enviar = AsyncMock()

    asyncio.run(combate._talvez_oferecer_porta(luta, enviar))

    enviar.assert_not_awaited()


def test_oferece_porta_na_vitoria_de_verdade_do_15_um_botao_ficar_e_sair_por_vencedor():
    c1 = _combatente(1)
    c2 = _combatente(2)
    luta = combate.Luta([c1, c2], dict(BOSS), andar_num=15)
    luta.hp_chefe = 0   # vitória
    enviar = AsyncMock(return_value=MagicMock())

    asyncio.run(combate._talvez_oferecer_porta(luta, enviar))

    enviar.assert_awaited_once()
    view = enviar.call_args.kwargs["view"]
    labels = {b.label for b in view.children}
    assert labels == {
        f"Ficar — {c1.nome}", f"Sair — {c1.nome}", f"Ficar — {c2.nome}", f"Sair — {c2.nome}",
    }


def test_jogador_que_vence_pela_primeira_vez_ve_a_cena_como_ja_era():
    c1 = _combatente(1)
    luta = combate.Luta([c1], dict(BOSS), andar_num=15)
    luta.hp_chefe = 0
    asyncio.run(combate.recompensar(luta, c1))
    enviar = AsyncMock(return_value=MagicMock())

    asyncio.run(combate._talvez_oferecer_porta(luta, enviar))

    e = enviar.call_args.kwargs["embed"]
    assert _campo(e, f"🕯️ A Guia detém {c1.nome}") is not None


def test_ver_a_porta_marca_a_coluna_como_vista():
    """Faceta nova, separada da condição de mostrar a cena -- o conserto
    introduz `viu_porta_do_trono` como estado próprio."""
    c1 = _combatente(1)
    luta = combate.Luta([c1], dict(BOSS), andar_num=15)
    luta.hp_chefe = 0
    asyncio.run(combate.recompensar(luta, c1))

    asyncio.run(combate._talvez_oferecer_porta(luta, AsyncMock(return_value=MagicMock())))

    assert db.get_jogador(1)["viu_porta_do_trono"] == 1


def test_veterano_com_vezes_derrotado_alto_e_porta_nunca_vista_ve_a_cena():
    """O conserto: `vezes_derrotado_chefe` já está gasto pra quem zerou a
    torre antes deste pacote -- o gatilho de verdade é `viu_porta_do_
    trono`, coluna própria, 0 pra todo mundo no deploy (veterano
    inclusive)."""
    c = _combatente(1)
    for _ in range(5):
        db.registrar_vitoria_chefe(1, ANDAR_MAXIMO)
    assert db.vezes_derrotado_chefe(1, ANDAR_MAXIMO) == 5   # sanity -- já bem gasto
    assert db.get_jogador(1)["viu_porta_do_trono"] == 0      # mas nunca viu a porta
    luta = combate.Luta([c], dict(BOSS), andar_num=15)
    luta.hp_chefe = 0
    asyncio.run(combate.recompensar(luta, c))
    enviar = AsyncMock(return_value=MagicMock())

    asyncio.run(combate._talvez_oferecer_porta(luta, enviar))

    e = enviar.call_args.kwargs["embed"]
    assert _campo(e, f"🕯️ A Guia detém {c.nome}") is not None


def test_mesmo_jogador_segunda_vez_na_porta_nao_ve_mais():
    c1 = _combatente(1)
    for _ in range(5):
        db.registrar_vitoria_chefe(1, ANDAR_MAXIMO)
    luta1 = combate.Luta([c1], dict(BOSS), andar_num=15)
    luta1.hp_chefe = 0
    asyncio.run(combate.recompensar(luta1, c1))
    asyncio.run(combate._talvez_oferecer_porta(luta1, AsyncMock(return_value=MagicMock())))

    c2 = _combatente(1)   # o mesmo jogador, recarregado do banco pra segunda luta
    luta2 = combate.Luta([c2], dict(BOSS), andar_num=15)
    luta2.hp_chefe = 0
    asyncio.run(combate.recompensar(luta2, c2))
    enviar2 = AsyncMock(return_value=MagicMock())

    asyncio.run(combate._talvez_oferecer_porta(luta2, enviar2))

    e2 = enviar2.call_args.kwargs["embed"]
    assert _campo(e2, f"🕯️ A Guia detém {c2.nome}") is None


def test_quem_fugiu_ou_saiu_nao_recebe_escolha():
    c1 = _combatente(1)
    c2 = _combatente(2)
    c2.fugiu = True
    luta = combate.Luta([c1, c2], dict(BOSS), andar_num=15)
    luta.hp_chefe = 0
    enviar = AsyncMock(return_value=MagicMock())

    asyncio.run(combate._talvez_oferecer_porta(luta, enviar))

    view = enviar.call_args.kwargs["view"]
    labels = {b.label for b in view.children}
    assert f"Ficar — {c2.nome}" not in labels
    assert f"Ficar — {c1.nome}" in labels


# ==================================================================
# BotaoEscolhaPorta -- Ficar / Sair, por jogador
# ==================================================================

def test_botao_ficar_reseta_andar_e_andar_max_pro_10():
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, andar=15, andar_max=15)
    view = combate.ViewEscolhaPorta([(1, "Alice")])
    botao = _botao(view, "Ficar — Alice")

    asyncio.run(botao.callback(_interacao(1)))

    depois = db.get_jogador(1)
    assert depois["andar"] == 10
    assert depois["andar_max"] == 10
    assert depois["mundo"] == "torre"


def test_botao_sair_muda_o_mundo_sem_tocar_no_andar():
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, andar=15, andar_max=15)
    view = combate.ViewEscolhaPorta([(1, "Alice")])
    botao = _botao(view, "Sair — Alice")

    asyncio.run(botao.callback(_interacao(1)))

    depois = db.get_jogador(1)
    assert depois["mundo"] == "mirante"   # a porta sempre dá no Mirante -- Step C
    assert depois["andar"] == 15      # preservado -- é pra onde a escada devolve
    assert depois["andar_max"] == 15


def test_clique_de_quem_nao_e_o_dono_do_par_e_recusado_sem_gravar():
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, andar=15, andar_max=15)
    view = combate.ViewEscolhaPorta([(1, "Alice")])
    botao = _botao(view, "Sair — Alice")
    it = _interacao(999)   # outro jogador

    asyncio.run(botao.callback(it))

    it.response.send_message.assert_awaited_once()
    assert db.get_jogador(1)["mundo"] == "torre"   # nada mudou


def test_escolha_de_um_vencedor_nao_desabilita_o_par_do_outro():
    db.criar_jogador(1, "Alice")
    db.criar_jogador(2, "Bob")
    db.atualizar_jogador(1, andar=15, andar_max=15)
    db.atualizar_jogador(2, andar=15, andar_max=15)
    view = combate.ViewEscolhaPorta([(1, "Alice"), (2, "Bob")])
    botao_alice = _botao(view, "Ficar — Alice")

    asyncio.run(botao_alice.callback(_interacao(1)))

    disabled = {b.label for b in view.children if b.disabled}
    assert disabled == {"Ficar — Alice", "Sair — Alice"}
    assert not any(b.disabled for b in view.children if "Bob" in b.label)


# ==================================================================
# rpg falar porta -- passagem livre pra quem já venceu, flavor pra quem não
# ==================================================================

def _jogador_falar(user_id, ja_venceu):
    db.criar_jogador(user_id, f"J{user_id}")
    db.atualizar_jogador(user_id, andar=15, andar_max=15)
    if ja_venceu:
        db.registrar_vitoria_chefe(user_id, ANDAR_MAXIMO)


def test_falar_na_porta_sem_nunca_ter_vencido_e_so_flavor():
    _jogador_falar(1, ja_venceu=False)
    ctx = _ctx(1)

    asyncio.run(bot.falar.callback(ctx, quem="porta"))

    view = ctx.send.call_args.kwargs["view"]
    assert not any(isinstance(c, combate.BotaoEscolhaPorta) for c in view.children)


def test_falar_na_porta_depois_de_ja_ter_vencido_abre_a_escolha_sem_lutar():
    _jogador_falar(1, ja_venceu=True)
    ctx = _ctx(1)

    asyncio.run(bot.falar.callback(ctx, quem="porta"))

    view = ctx.send.call_args.kwargs["view"]
    labels = {c.label for c in view.children}
    assert "Ficar — J1" in labels and "Sair — J1" in labels


def test_falar_na_porta_veterano_que_nunca_viu_ela_antes_ve_a_cena():
    """O conserto: `rpg falar porta` também é "a primeira vez que vê a
    porta" pra quem zerou a torre há muito tempo e só agora esbarra nela
    de novo, sem lutar -- não só na vitória."""
    _jogador_falar(1, ja_venceu=True)
    ctx = _ctx(1)

    asyncio.run(bot.falar.callback(ctx, quem="porta"))

    e = ctx.send.call_args.kwargs["embed"]
    assert any("Guia" in f.name for f in e.fields)
    assert db.get_jogador(1)["viu_porta_do_trono"] == 1


def test_falar_na_porta_segunda_vez_de_verdade_nao_mostra_a_fala_de_novo():
    _jogador_falar(1, ja_venceu=True)
    db.atualizar_jogador(1, viu_porta_do_trono=1)   # já viu, de um encontro anterior
    ctx = _ctx(1)

    asyncio.run(bot.falar.callback(ctx, quem="porta"))

    e = ctx.send.call_args.kwargs["embed"]
    assert not e.fields   # sem a fala -- não é mais a primeira vez
