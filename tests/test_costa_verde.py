# tests/test_costa_verde.py
# Step F, commit 2: Costa Verde. Cidade de lore -- não vende nada, decisão de
# desenho (o jogador atravessa uma estrada perigosa pra conversar, não pra
# comprar). Suzu é o segundo elo da corrente do Herói (o Ivo, no vilarejo,
# puxou o fio -- "alguém foi pro norte"; a Suzu VIU esse alguém passar).
# Osamu é o contraste com a torre: gente que fala dos próprios mortos como
# quem fala do tempo. Ver decisoes.md § Step F.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import dialogos
import mundo
import npcs


def _jogador(user_id=1, mundo_atual=None, **campos):
    import database as db
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
# Costa Verde não vende nada
# ==================================================================

def test_costa_verde_nao_tem_npc_comercial_nenhum():
    tipos_comerciais = {"mercador", "ferreiro", "carroceiro", "taverneiro", "encantador", "joalheiro", "alquimista"}
    for n in npcs.NPCS[mundo.COSTA_VERDE]:
        assert n["tipo"] not in tipos_comerciais


def test_comprar_em_costa_verde_e_sempre_recusado():
    _jogador(1, mundo_atual=mundo.COSTA_VERDE, andar=15, andar_max=15, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.comprar.callback(ctx, argumento="elixir de ervas 1"))
    import database as db
    assert not db.tem_item(1, "elixir_ervas", 1)
    assert "ninguém vendendo" in _msg(ctx).lower()


# ==================================================================
# Suzu -- o segundo elo da corrente (o Herói foi pro norte)
# ==================================================================

def test_suzu_esta_em_costa_verde_com_dialogo_valido():
    pessoas = {n["nome"]: n for n in npcs.NPCS[mundo.COSTA_VERDE]}
    assert "Suzu" in pessoas
    n = pessoas["Suzu"]
    assert n["tipo"] == "conversa"
    assert n["dialogo"] in dialogos.DIALOGOS


def test_falar_com_suzu_avanca_o_fio_sem_nomear_o_inimigo_maior():
    """Segundo elo: ela VIU alguém passar rumo ao norte -- avança a
    história (quem, quando, o que procurava) sem entregar o fim. O
    cartão foi explícito: 'não nomeie o inimigo maior, que ainda não
    foi decidido'."""
    _jogador(1, mundo_atual=mundo.COSTA_VERDE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="suzu"))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "montanhas" in embed.description.lower()   # o gancho: o que ele procurava

    dado = dialogos.DIALOGOS["suzu"]
    todas_as_falas = " ".join([dado["abertura"], dado.get("saida", "")] + [o["resposta"] for o in dado.get("opcoes", [])])
    assert "norte" in todas_as_falas.lower()
    assert "inimigo" not in todas_as_falas.lower()


def test_suzu_menciona_quando_e_o_que_o_viajante_procurava():
    dado = dialogos.DIALOGOS["suzu"]
    todas_as_falas = " ".join([o["resposta"] for o in dado["opcoes"]])
    assert "colheita" in todas_as_falas.lower()   # quando
    assert "montanhas" in todas_as_falas.lower()   # o que procurava


# ==================================================================
# Osamu -- o contraste com a torre (os mortos como quem fala do tempo)
# ==================================================================

def test_osamu_esta_em_costa_verde_com_dialogo_valido():
    pessoas = {n["nome"]: n for n in npcs.NPCS[mundo.COSTA_VERDE]}
    assert "Osamu" in pessoas
    n = pessoas["Osamu"]
    assert n["tipo"] == "conversa"
    assert n["dialogo"] in dialogos.DIALOGOS


def test_falar_com_osamu_menciona_a_torre_como_contraste():
    """'O contraste com a torre é o ponto' -- lá dentro ninguém sabe que
    é abrigo, aqui fora vivem com os mortos sem achar estranho."""
    _jogador(1, mundo_atual=mundo.COSTA_VERDE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="osamu"))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "avô" in embed.description.lower()

    dado = dialogos.DIALOGOS["osamu"]
    todas_as_falas = " ".join(o["resposta"] for o in dado["opcoes"])
    assert "torre" in todas_as_falas.lower()


# ==================================================================
# regressão -- Costa Verde não aparece em lugar nenhum além de si mesma
# ==================================================================

def test_suzu_e_osamu_nao_aparecem_no_vilarejo_nem_na_torre():
    nomes_vilarejo = {n["nome"] for n in npcs.NPCS[mundo.VILAREJO]}
    assert "Suzu" not in nomes_vilarejo and "Osamu" not in nomes_vilarejo
    for n in npcs.npcs_do_andar(1):
        assert n["nome"] not in ("Suzu", "Osamu")


def test_npcs_de_costa_verde_aparecem_via_rpg_npcs():
    _jogador(1, mundo_atual=mundo.COSTA_VERDE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.listar_npcs.callback(ctx))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "Suzu" in embed.description
    assert "Osamu" in embed.description
