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


def test_primeira_vitoria_no_15_traz_a_fala_da_guia_repeticao_nao():
    c1 = _combatente(1)   # primeira vez
    c2 = _combatente(2)   # já venceu antes
    db.registrar_vitoria_chefe(2, ANDAR_MAXIMO)
    luta = combate.Luta([c1, c2], dict(BOSS), andar_num=15)
    luta.hp_chefe = 0
    # mesma ordem do fluxo de verdade: finalizar_vitoria roda recompensar()
    # (que registra a vitória em chefes_derrotados) ANTES de
    # _talvez_oferecer_porta ver quem está na primeira vez.
    asyncio.run(combate.recompensar(luta, c1))
    asyncio.run(combate.recompensar(luta, c2))
    enviar = AsyncMock(return_value=MagicMock())

    asyncio.run(combate._talvez_oferecer_porta(luta, enviar))

    e = enviar.call_args.kwargs["embed"]
    assert _campo(e, f"🕯️ A Guia detém {c1.nome}") is not None
    assert _campo(e, f"🕯️ A Guia detém {c2.nome}") is None


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
    assert depois["mundo"] == "fora"
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
    e = ctx.send.call_args.kwargs["embed"]
    assert "Guia" not in (e.description or "") and not e.fields   # sem a fala -- não é a primeira vez
