# tests/test_dungeon.py
# Cartão "Vitre 0.4 — Fatia 1: motor da dungeon do andar 9". Só o motor:
# entrada, sorteio, persistência (sobrevive a restart), avanço sala a sala,
# fim por morte, retomada. SEM espelhos de verdade, SEM Orbe, SEM skills de
# ascensão -- ver decisoes.md § Dungeon (fatia 1). Esta fatia não vai pra
# produção (deploy não acontece até a fatia 4).
import asyncio
import json
import random
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot  # noqa: F401 -- popula dungeon.H via bot.instalar() (import cascata via travas.py)
import database as db
import dungeon
import game_data
import travas

SALAS_DE_TESTE = (
    "camara_dos_ecos", "salao_do_espelho_rachado", "piso_instavel",
    "bau_esquecido", "jardim_suspenso",
)


def _jogador(user_id=1, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    padrao = dict(andar=9, nivel=15, classe="guerreiro", forca=20)
    padrao.update(campos)
    db.atualizar_jogador(user_id, **padrao)
    return db.get_jogador(user_id)


def _ctx(user_id=1):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    return ctx


def _msg(ctx):
    return ctx.send.call_args.args[0]


def _sempre_vitoria(monkeypatch):
    """Nenhuma sala de combate mata ninguém -- pra testes que só querem
    exercitar o motor (sorteio/avanço/persistência), não o resultado de uma
    luta de verdade."""
    monkeypatch.setitem(dungeon.H, "simular_combate", lambda s, hp, mob, andar_num: (hp, True, ["vitória"]))


# ==================================================================
# Dados: pool tem os 4 tipos, "achado" nunca "tesouro"
# ==================================================================

def test_pool_tem_os_quatro_tipos_de_sala():
    tipos = {s["tipo"] for s in game_data.DUNGEON_POOL}
    assert tipos == {"combate", "evento", "armadilha", "achado"}


def test_achado_nunca_e_chamado_de_tesouro():
    assert "tesouro" not in {s["tipo"] for s in game_data.DUNGEON_POOL}
    assert not any("tesouro" in s["chave"] for s in game_data.DUNGEON_POOL)


def test_dungeon_espelhos_acessivel_por_get_para_classe_desconhecida():
    assert game_data.DUNGEON_ESPELHOS.get("classe_que_nao_existe") is None
    for classe in ("guerreiro", "mago", "ladino", "orador"):
        assert game_data.DUNGEON_ESPELHOS.get(classe) is not None


# ==================================================================
# Sorteio determinizado
# ==================================================================

def test_sortear_salas_da_5_salas_todas_do_pool_sem_repetir():
    random.seed(12345)
    salas = dungeon.sortear_salas()

    assert len(salas) == game_data.DUNGEON_SALAS_POR_RUN == 5
    assert len(set(salas)) == 5   # sem repetir
    chaves_validas = {s["chave"] for s in game_data.DUNGEON_POOL}
    assert set(salas) <= chaves_validas


def test_sortear_salas_e_reproduzivel_com_semente_fixa():
    random.seed(999)
    a = dungeon.sortear_salas()
    random.seed(999)
    b = dungeon.sortear_salas()
    assert a == b


# ==================================================================
# Persistência e retomada
# ==================================================================

def test_criar_run_persiste_e_comeca_no_indice_0():
    _jogador(1)
    run = dungeon.criar_run(1)

    assert run["indice"] == 0
    assert len(run["salas"]) == 5


def test_retomada_apos_apagar_o_objeto_em_memoria_cai_na_mesma_sala():
    _jogador(1)
    run1 = dungeon.criar_run(1)
    sala_antes = dungeon.sala_atual(run1)
    del run1   # nada em memória sobrevive -- simula o restart

    run2 = dungeon.obter_run(1)
    sala_depois = dungeon.sala_atual(run2)

    assert sala_depois == sala_antes
    assert run2["indice"] == 0


def test_retomada_no_meio_da_run_preserva_o_indice_e_a_sala_certa():
    _jogador(1)
    dungeon.criar_run(1)
    db.atualizar_dungeon_run_indice(1, 2)   # simula progresso já feito antes do restart

    run = dungeon.obter_run(1)

    assert run["indice"] == 2
    assert dungeon.sala_atual(run)["chave"] == run["salas"][2]


# ==================================================================
# Morte encerra a run e dispara a_processar_morte de verdade
# ==================================================================

def test_morte_na_dungeon_apaga_a_run_e_chama_a_processar_morte(monkeypatch):
    j = _jogador(1, moedas=1000)
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))   # indice 0 = "camara_dos_ecos", tipo combate
    run = dungeon.obter_run(1)
    assert dungeon.sala_atual(run)["tipo"] == "combate"

    monkeypatch.setitem(
        dungeon.H, "simular_combate",
        lambda s, hp, mob, andar_num: (0, False, ["log de derrota"]),
    )
    spy = AsyncMock(wraps=bot.a_processar_morte)
    monkeypatch.setitem(dungeon.H, "a_processar_morte", spy)

    ctx = _ctx(1)
    asyncio.run(dungeon.resolver_sala_atual(ctx, j, run))

    spy.assert_awaited_once()
    assert dungeon.obter_run(1) is None   # sem linha órfã
    assert db.get_jogador(1)["moedas"] < 1000   # a_processar_morte de verdade rodou (penalidade aplicada)
    embed = ctx.send.call_args.kwargs["embed"]
    assert "caiu" in embed.fields[0].name.lower()


def test_morte_na_dungeon_nao_deixa_linha_orfa_mesmo_sem_ler_a_run_de_novo(monkeypatch):
    """A limpeza acontece dentro da MESMA transação da penalidade de morte
    (database.atualizar_jogador_e_apagar_dungeon_run) -- não é dungeon.py
    que apaga depois, então testa direto sem intermediar."""
    j = _jogador(1)
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))
    run = dungeon.obter_run(1)

    monkeypatch.setitem(
        dungeon.H, "simular_combate",
        lambda s, hp, mob, andar_num: (0, False, ["derrota"]),
    )

    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j, run))

    with db.conectar() as conn:
        n = conn.execute("SELECT COUNT(*) FROM dungeon_run WHERE user_id = ?", (1,)).fetchone()[0]
    assert n == 0


# ==================================================================
# Duas entradas seguidas não duplicam a run
# ==================================================================

def test_dois_rpg_dungeon_seguidos_nao_criam_duas_runs(monkeypatch):
    _jogador(1)
    _sempre_vitoria(monkeypatch)

    ctx1 = _ctx(1)
    asyncio.run(bot.bot.get_command("dungeon").callback(ctx1, argumento=""))
    ctx2 = _ctx(1)
    asyncio.run(bot.bot.get_command("dungeon").callback(ctx2, argumento=""))

    with db.conectar() as conn:
        n = conn.execute("SELECT COUNT(*) FROM dungeon_run WHERE user_id = ?", (1,)).fetchone()[0]
    assert n == 1


def test_criar_dungeon_run_duas_vezes_direto_no_banco_nao_duplica_nem_sobrescreve():
    """Unidade da guarda em si (a PK de dungeon_run.user_id via ON CONFLICT
    DO NOTHING) -- sem passar pelo check de app (`obter_run` antes de
    criar) que o comando faz. Valida a rede de segurança, não só o caminho
    feliz do comando."""
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))
    outras_salas = ["corredor_sussurrante", "jardim_suspenso", "corrente_solta", "nicho_da_torre", "bau_esquecido"]
    db.criar_dungeon_run(1, outras_salas)   # segunda tentativa -- deveria ser ignorada

    with db.conectar() as conn:
        n = conn.execute("SELECT COUNT(*) FROM dungeon_run WHERE user_id = ?", (1,)).fetchone()[0]
    assert n == 1

    run = db.get_dungeon_run(1)
    assert run["salas"] == list(SALAS_DE_TESTE)   # a primeira run venceu, não a segunda


def test_insert_or_ignore_engole_qualquer_violacao_de_constraint_nao_so_pk_duplicada():
    """O comentário acima de criar_dungeon_run (database.py) descreve INSERT
    OR IGNORE, não ON CONFLICT DO NOTHING -- e a diferença importa: IGNORE
    engole TODA violação de constraint da tabela, não só a PK duplicada que
    o teste acima cobre. Prova com o NOT NULL de `indice` (criar_dungeon_run
    nunca manda um `indice` diferente de 0, então isso só dá pra forçar
    direto no banco). Depois prova a outra metade: a run válida seguinte
    grava normalmente, com as salas certas -- a tentativa inválida não
    deixou o banco num estado que atrapalhe a próxima escrita."""
    with db.conectar() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO dungeon_run (user_id, salas, indice, iniciada_em) "
            "VALUES (?, ?, NULL, ?)",
            (1, json.dumps(list(SALAS_DE_TESTE)), time.time()),
        )
    assert db.get_dungeon_run(1) is None   # violou NOT NULL, IGNORE engoliu, nada gravou

    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))
    run = db.get_dungeon_run(1)
    assert run is not None
    assert run["salas"] == list(SALAS_DE_TESTE)
    assert run["indice"] == 0


# ==================================================================
# rpg dungeon sair
# ==================================================================

def test_dungeon_sair_apaga_a_run_sem_chamar_a_processar_morte(monkeypatch):
    j = _jogador(1)
    dungeon.criar_run(1)
    spy = AsyncMock(wraps=bot.a_processar_morte)
    monkeypatch.setitem(dungeon.H, "a_processar_morte", spy)

    ctx = _ctx(1)
    asyncio.run(bot.bot.get_command("dungeon").get_command("sair").callback(ctx))

    spy.assert_not_awaited()
    assert dungeon.obter_run(1) is None
    assert "sem penalidade" in _msg(ctx)


def test_dungeon_sair_sem_run_aberta_nao_quebra():
    _jogador(1)
    ctx = _ctx(1)

    asyncio.run(bot.bot.get_command("dungeon").get_command("sair").callback(ctx))

    assert "não está" in _msg(ctx)


# ==================================================================
# Entrada recusada
# ==================================================================

def test_entrada_recusada_fora_do_andar_9():
    _jogador(1, andar=5, nivel=20)
    ctx = _ctx(1)

    asyncio.run(bot.bot.get_command("dungeon").callback(ctx, argumento=""))

    assert "andar 9" in _msg(ctx)
    assert dungeon.obter_run(1) is None


def test_entrada_recusada_nivel_abaixo_de_15():
    _jogador(1, andar=9, nivel=10)
    ctx = _ctx(1)

    asyncio.run(bot.bot.get_command("dungeon").callback(ctx, argumento=""))

    assert str(game_data.NIVEL_ASCENSAO_PADRAO) in _msg(ctx)
    assert dungeon.obter_run(1) is None


def test_entrada_aceita_no_andar_9_nivel_15(monkeypatch):
    _jogador(1, andar=9, nivel=15)
    _sempre_vitoria(monkeypatch)
    ctx = _ctx(1)

    asyncio.run(bot.bot.get_command("dungeon").callback(ctx, argumento=""))

    run = dungeon.obter_run(1)
    assert run is not None
    assert run["indice"] == 1   # resolveu a sala 0 (vitória forçada) e avançou
    assert "embed" in ctx.send.call_args.kwargs   # mandou um embed de resultado, não uma recusa de texto


# ==================================================================
# rpg viajar recusado com run aberta
# ==================================================================

def test_trava_dungeon_recusa_via_predicado_isolado():
    async def cenario():
        _jogador(1)
        dungeon.criar_run(1)
        predicado = travas.fora_de_dungeon().predicate
        with pytest.raises(travas.DungeonAberta):
            await predicado(_ctx(1))

    asyncio.run(cenario())


def test_predicado_de_dungeon_libera_quem_nao_tem_run_aberta():
    async def cenario():
        _jogador(1)
        predicado = travas.fora_de_dungeon().predicate
        assert await predicado(_ctx(1)) is True

    asyncio.run(cenario())


def test_viajar_de_verdade_inclui_a_trava_de_dungeon():
    """Integração: confirma que o comando `rpg viajar` REGISTRADO (via
    bot.py) carrega o check novo -- não só que o predicado isolado funciona.
    Mesmo padrão de test_manutencao_e_aviso.py."""
    _jogador(1, andar=9, moedas=1000)
    dungeon.criar_run(1)
    ctx = _ctx(1)
    cmd = bot.bot.get_command("viajar")

    async def cenario():
        with pytest.raises(travas.DungeonAberta):
            for check in cmd.checks:
                await check(ctx)

    asyncio.run(cenario())


def test_on_command_error_dungeon_aberta_manda_a_mensagem_certa():
    ctx = _ctx(1)
    ctx.command = bot.bot.get_command("viajar")

    asyncio.run(bot.on_command_error(ctx, travas.DungeonAberta()))

    assert _msg(ctx) == travas.MENSAGEM_DUNGEON_ABERTA
