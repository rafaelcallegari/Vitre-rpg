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
import game_data
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


# ==================================================================
# commit 2 -- as criaturas escalam por inteiro (vida, defesa E dano)
# ==================================================================

def test_andar_referencia_e_o_andar_max_do_jogador():
    j = _jogador(1, andar_max=9)
    assert incursao.andar_referencia(j) == 9


def test_andar_referencia_trava_no_andar_maximo_do_jogo():
    j = _jogador(1, andar_max=999)
    assert incursao.andar_referencia(j) == game_data.ANDAR_MAXIMO


def test_andar_referencia_e_pelo_menos_1():
    j = _jogador(1, andar_max=0)
    assert incursao.andar_referencia(j) == 1


def test_sortear_criatura_pega_hp_atk_def_do_andar_de_referencia_nao_do_corrompido(monkeypatch):
    """O ponto inteiro do commit: se só o dano escalasse, a vida seguiria
    a do andar baixo sorteado -- aqui hp/def também têm que vir do andar
    9 (o progresso real do jogador), não do 2 (o andar sorteado)."""
    n = _fixar_andar_do_dia(monkeypatch, datetime(2026, 7, 1, 12, tzinfo=FUSO))
    assert n != 9   # a incursão de hoje não pode ser o próprio andar de referência
    monkeypatch.setattr(incursao.random, "randrange", lambda _n: 0)
    j = _jogador(1, andar_max=9)
    mob = incursao.sortear_criatura(j)
    referencia = game_data.ANDARES[9]["monstros"][0]
    assert mob["hp"] == referencia["hp"]
    assert mob["atk"] == referencia["atk"]
    assert mob["def"] == referencia["def"]
    assert mob["hp"] != game_data.ANDARES[n]["monstros"][0]["hp"]   # não é o andar sorteado


def test_sortear_criatura_nome_vem_do_andar_corrompido_nao_do_de_referencia(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch, datetime(2026, 7, 1, 12, tzinfo=FUSO))
    monkeypatch.setattr(incursao.random, "randrange", lambda _n: 0)
    j = _jogador(1, andar_max=9)
    mob = incursao.sortear_criatura(j)
    nome_local = game_data.ANDARES[n]["monstros"][0]["nome"]
    assert mob["nome"] == f"Sombra de {nome_local}"


def test_sortear_criatura_xp_e_moedas_dobram(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch, datetime(2026, 7, 1, 12, tzinfo=FUSO))
    monkeypatch.setattr(incursao.random, "randrange", lambda _n: 1)
    j = _jogador(1, andar_max=6)
    mob = incursao.sortear_criatura(j)
    referencia = game_data.ANDARES[6]["monstros"][1]
    assert mob["xp"] == referencia["xp"] * 2
    assert mob["moedas"] == referencia["moedas"] * 2


def test_sortear_criatura_marca_corrompido():
    j = _jogador(1, andar_max=5)
    mob = incursao.sortear_criatura(j)
    assert mob["corrompido"] is True


def test_criatura_do_mesmo_jogador_e_o_mesmo_desafio_em_qualquer_andar_corrompido(monkeypatch):
    """'Efeito colateral aceito' do cartão: andar 2 corrompido e andar 9
    corrompido são o MESMO desafio pro MESMO jogador -- só o nome muda."""
    monkeypatch.setattr(incursao.random, "randrange", lambda _n: 2)
    j = _jogador(1, andar_max=7)
    monkeypatch.setattr(incursao, "andar_do_dia", lambda m=None: 2)
    mob_no_2 = incursao.sortear_criatura(j)
    monkeypatch.setattr(incursao, "andar_do_dia", lambda m=None: 9)
    mob_no_9 = incursao.sortear_criatura(j)
    assert mob_no_2["hp"] == mob_no_9["hp"]
    assert mob_no_2["atk"] == mob_no_9["atk"]
    assert mob_no_2["def"] == mob_no_9["def"]
    assert mob_no_2["xp"] == mob_no_9["xp"]
    assert mob_no_2["nome"] != mob_no_9["nome"]   # o flavor local muda, o desafio não


def test_cacar_no_andar_corrompido_usa_sortear_criatura(monkeypatch):
    """Fiação ponta a ponta -- prova que `cacar` realmente chama
    `incursao.sortear_criatura` (e não só o transform de nome do commit
    1) pro jogador de verdade, não um cenário isolado."""
    n = _fixar_andar_do_dia(monkeypatch)
    capturado = {}

    def _espiao(jogador, momento=None):
        capturado["andar_max"] = jogador["andar_max"]
        referencia = game_data.ANDARES[incursao.andar_referencia(jogador)]["monstros"][0]
        return {**referencia, "nome": "Sombra de Teste", "corrompido": True,
                "xp": referencia["xp"] * 2, "moedas": referencia["moedas"] * 2}

    monkeypatch.setattr(incursao, "sortear_criatura", _espiao)
    _jogador(1, classe="guerreiro", forca=20, andar=n, andar_max=9, hp=99999)
    ctx = _ctx(1)
    asyncio.run(bot.cacar.callback(ctx))
    assert capturado["andar_max"] == 9


def test_xp_e_dinheiro_dobram_so_no_andar_corrompido(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch, datetime(2026, 7, 1, 12, tzinfo=FUSO))
    monkeypatch.setattr(incursao.random, "randrange", lambda _n: 0)
    _jogador(1, classe="guerreiro", forca=999, andar=n, andar_max=9, hp=999999)
    ctx = _ctx(1)
    # combate determinístico: força vitória sem depender de random de dano
    import combate as combate_mod  # noqa: F401 -- só garante módulo carregado
    monkeypatch.setattr(bot.random, "random", lambda: 0.01)
    monkeypatch.setattr(bot.random, "uniform", lambda a, b: 1.15)
    asyncio.run(bot.cacar.callback(ctx))
    embed = ctx.send.call_args.kwargs["embed"]
    referencia = game_data.ANDARES[9]["monstros"][0]
    esperado_xp = referencia["xp"] * 2
    esperado_moedas = referencia["moedas"] * 2
    campo = embed.fields[0].value
    assert f"+{esperado_xp} XP" in campo
    assert f"+{esperado_moedas} 🪙" in campo


# ==================================================================
# regressão -- andar não corrompido não muda nada (commit 2 inclusive)
# ==================================================================

def test_cacar_fora_da_incursao_usa_stats_normais_do_proprio_andar(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    outro = 1 if n != 1 else 2
    monkeypatch.setattr(bot.random, "choice", lambda lista: lista[0])
    capturado = {}
    real_simular = bot.simular_combate

    def _espiao_simular(s, hp, mob, andar_num, **kw):
        capturado["mob"] = mob
        capturado["andar_num"] = andar_num
        return real_simular(s, hp, mob, andar_num, **kw)

    monkeypatch.setattr(bot, "simular_combate", _espiao_simular)
    _jogador(1, classe="guerreiro", forca=20, andar=outro, andar_max=outro)
    ctx = _ctx(1)
    asyncio.run(bot.cacar.callback(ctx))
    assert capturado["mob"] == game_data.ANDARES[outro]["monstros"][0]
    assert capturado["andar_num"] == outro
