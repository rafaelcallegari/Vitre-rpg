# tests/test_costa_verde.py
# Step F, commit 2: Costa Verde. Cidade de lore -- não vende nada, decisão de
# desenho (o jogador atravessa uma estrada perigosa pra conversar, não pra
# comprar). Eira (renomeada de Suzu no cartão de reescrita) é o segundo elo
# da corrente do Herói (o Ivo, no vilarejo, puxou o fio -- "alguém foi pro
# norte"; a Eira VIU esse alguém passar). Bento (renomeado de Osamu) é o
# contraste com a torre: gente que fala dos próprios mortos como quem fala
# do tempo. Ver decisoes.md § Step F.
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


def _todas_as_falas(chave):
    """Junta abertura + saida + toda resposta de opção -- cada uma pode ser
    string ou lista de linhas (dialogos.linhas), então passa tudo por ela
    antes de juntar num texto só pra buscar substring."""
    dado = dialogos.DIALOGOS[chave]
    partes = [dialogos.linhas(dado["abertura"]), dado.get("saida", "")]
    partes += [dialogos.linhas(o["resposta"]) for o in dado.get("opcoes", [])]
    return " ".join(partes)


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
# Eira -- o segundo elo da corrente (o Herói foi pro norte)
# ==================================================================

def test_eira_esta_em_costa_verde_com_dialogo_valido():
    pessoas = {n["nome"]: n for n in npcs.NPCS[mundo.COSTA_VERDE]}
    assert "Eira" in pessoas
    n = pessoas["Eira"]
    assert n["tipo"] == "conversa"
    assert n["dialogo"] in dialogos.DIALOGOS


def test_eira_tem_duas_opcoes():
    assert len(dialogos.DIALOGOS["eira"]["opcoes"]) == 2


def test_falar_com_eira_avanca_o_fio_sem_nomear_o_inimigo_maior():
    """Segundo elo: ela VIU alguém passar rumo ao norte -- avança a
    história (quem, quando, o que procurava) sem entregar o fim. O
    cartão foi explícito: 'não nomeie o inimigo maior, que ainda não
    foi decidido'."""
    _jogador(1, mundo_atual=mundo.COSTA_VERDE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="eira"))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "montanhas" in embed.description.lower()   # o gancho: o que ele procurava

    todas_as_falas = _todas_as_falas("eira")
    assert "norte" in todas_as_falas.lower()
    assert "inimigo" not in todas_as_falas.lower()


def test_eira_menciona_quando_e_o_que_o_viajante_procurava():
    dado = dialogos.DIALOGOS["eira"]
    respostas = " ".join(dialogos.linhas(o["resposta"]) for o in dado["opcoes"])
    assert "colheita" in respostas.lower()   # quando

    todas_as_falas = _todas_as_falas("eira")
    assert "montanhas" in todas_as_falas.lower()   # o que procurava (abertura)


# ==================================================================
# Bento -- o contraste com a torre (os mortos como quem fala do tempo)
# ==================================================================

def test_bento_esta_em_costa_verde_com_dialogo_valido():
    pessoas = {n["nome"]: n for n in npcs.NPCS[mundo.COSTA_VERDE]}
    assert "Bento" in pessoas
    n = pessoas["Bento"]
    assert n["tipo"] == "conversa"
    assert n["dialogo"] in dialogos.DIALOGOS


def test_bento_tem_tres_opcoes():
    assert len(dialogos.DIALOGOS["bento"]["opcoes"]) == 3


def test_falar_com_bento_menciona_a_torre_como_contraste():
    """'O contraste com a torre é o ponto' -- lá dentro ninguém sabe que
    é abrigo, aqui fora vivem com os mortos sem achar estranho."""
    _jogador(1, mundo_atual=mundo.COSTA_VERDE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="bento"))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "avô" in embed.description.lower()

    dado = dialogos.DIALOGOS["bento"]
    todas_as_falas = " ".join(dialogos.linhas(o["resposta"]) for o in dado["opcoes"])
    assert "torre" in todas_as_falas.lower()


# ==================================================================
# regressão -- Costa Verde não aparece em lugar nenhum além de si mesma
# ==================================================================

def test_eira_e_bento_nao_aparecem_no_vilarejo_nem_na_torre():
    nomes_vilarejo = {n["nome"] for n in npcs.NPCS[mundo.VILAREJO]}
    assert "Eira" not in nomes_vilarejo and "Bento" not in nomes_vilarejo
    for n in npcs.npcs_do_andar(1):
        assert n["nome"] not in ("Eira", "Bento")


def test_nomes_antigos_suzu_e_osamu_nao_sobram_em_lugar_nenhum():
    """O cartão de reescrita pediu: os nomes antigos não podem sobrar em
    lugar nenhum -- nem chave de diálogo, nem nome de NPC."""
    assert "suzu" not in dialogos.DIALOGOS
    assert "osamu" not in dialogos.DIALOGOS
    todos_os_nomes = {n["nome"] for andar in npcs.NPCS.values() for n in andar}
    assert "Suzu" not in todos_os_nomes
    assert "Osamu" not in todos_os_nomes


def test_npcs_de_costa_verde_aparecem_via_rpg_npcs():
    _jogador(1, mundo_atual=mundo.COSTA_VERDE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.listar_npcs.callback(ctx))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "Eira" in embed.description
    assert "Bento" in embed.description


# ==================================================================
# o ritmo -- batida curta, uma linha por vez (cartão de reescrita)
# ==================================================================

def test_abertura_da_eira_renderiza_uma_linha_por_batida():
    """'Se isso for concatenado num parágrafo, perde o efeito inteiro' --
    a abertura precisa continuar como lista de linhas distintas, e
    `dialogos.linhas` precisa juntar com quebra de linha, não espaço."""
    dado = dialogos.DIALOGOS["eira"]
    assert isinstance(dado["abertura"], list)
    assert len(dado["abertura"]) > 1
    texto = dialogos.linhas(dado["abertura"])
    assert texto.count("\n") == len(dado["abertura"]) - 1
    assert " ".join(dado["abertura"]) not in texto   # nunca virou parágrafo


def test_falar_com_eira_mostra_a_abertura_em_linhas_separadas():
    _jogador(1, mundo_atual=mundo.COSTA_VERDE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="eira"))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "\n" in embed.description
