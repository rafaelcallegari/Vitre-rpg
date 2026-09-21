# tests/test_vilarejo.py
# Step C, commit 2: o alquimista (única exceção comercial do vilarejo) e a
# taverna (rpg descansar + a cerveja, que atravessa pra qualquer luta). Ver
# decisoes.md § Step C.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import combate
import database as db
import mundo
import vilarejo

CHEFE_TESTE = {"nome": "Testinho", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0}


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
# o alquimista -- só os quatro elixires, nada além
# ==================================================================

def test_elixires_a_venda_e_exatamente_os_quatro_e_mais_nenhum():
    assert set(vilarejo.elixires_a_venda().keys()) == set(vilarejo.ELIXIRES)
    assert len(vilarejo.ELIXIRES) == 4


def test_comprar_elixir_no_vilarejo_funciona():
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.comprar.callback(ctx, argumento="elixir de ervas 1"))
    assert db.tem_item(1, "elixir_ervas", 1)


def test_comprar_pocao_no_vilarejo_recusa_o_alquimista_nao_vende():
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.comprar.callback(ctx, argumento="pocao pequena 1"))
    assert not db.tem_item(1, "pocao_p", 1)


def test_comprar_elixir_dentro_da_torre_continua_recusado():
    """Regressão: nenhum mercador da torre vende elixir -- `a_venda` já
    cuidava disso ("loja": False) antes do vilarejo existir."""
    _jogador(1, andar=1, andar_max=7, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.comprar.callback(ctx, argumento="elixir de ervas 1"))
    assert not db.tem_item(1, "elixir_ervas", 1)


# ==================================================================
# a taverna -- rpg descansar no vilarejo, trava do Selo tratada por mundo
# ==================================================================

def test_descansar_funciona_no_vilarejo():
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15, hp=1, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.descansar.callback(ctx))
    assert db.get_jogador(1)["hp"] == bot.stats(db.get_jogador(1))["hp_max"]


def test_descansar_continua_recusando_acima_do_selo_na_torre():
    """A trava velha comparava `andar > ANDAR_ACIMA_DO_SELO` cru -- fora
    da torre isso é lixo (o vilarejo tem `andar` sempre 15, congelado,
    maior que o Selo). Tratar o mundo primeiro não pode afrouxar a torre:
    andar 11 (acima do Selo) continua recusando igual sempre."""
    _jogador(1, andar=11, andar_max=11, hp=1, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.descansar.callback(ctx))
    assert "selo" in _msg(ctx).lower()
    assert db.get_jogador(1)["hp"] == 1   # não curou


def test_descansar_recusa_no_mirante():
    """O Mirante não é o vilarejo -- não tem taverna lá, só de passagem."""
    _jogador(1, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15, hp=1, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.descansar.callback(ctx))
    assert db.get_jogador(1)["hp"] == 1


# ==================================================================
# a cerveja -- compra, efeito pendente, consumo único
# ==================================================================

def test_cerveja_so_compra_no_vilarejo():
    _jogador(1, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.cerveja.callback(ctx))
    assert db.get_jogador(1)["cerveja_pendente"] == 0


def test_cerveja_compra_seta_a_flag_pendente_e_cobra_o_preco():
    j = _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.cerveja.callback(ctx))
    depois = db.get_jogador(1)
    assert depois["cerveja_pendente"] == 1
    assert depois["moedas"] == j["moedas"] - vilarejo.PRECO_CERVEJA


def test_cerveja_recusa_segunda_compra_em_cima_de_uma_pendente():
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.cerveja.callback(ctx))
    moedas_depois_da_primeira = db.get_jogador(1)["moedas"]
    asyncio.run(bot.cerveja.callback(ctx))
    assert db.get_jogador(1)["moedas"] == moedas_depois_da_primeira   # não cobrou de novo


def test_consumir_cerveja_pendente_devolve_neutro_sem_compra():
    _jogador(1)
    assert vilarejo.consumir_cerveja_pendente(1) == (1.0, 0.0)


def test_consumir_cerveja_pendente_aplica_uma_vez_so():
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15, moedas=10000)
    vilarejo.comprar_cerveja(1)
    mult, erro = vilarejo.consumir_cerveja_pendente(1)
    assert mult == 1.0 + vilarejo.BONUS_DANO_CERVEJA
    assert erro == vilarejo.CHANCE_ERRO_CERVEJA
    assert db.get_jogador(1)["cerveja_pendente"] == 0
    assert vilarejo.consumir_cerveja_pendente(1) == (1.0, 0.0)   # segunda vez, nada


# ==================================================================
# a cerveja numa luta de verdade (combate.Luta) -- Step 2d/Step A
# ==================================================================

def test_cerveja_aplica_vulneravel_no_chefe_e_chance_erro_no_jogador():
    c = _combatente(1, classe="guerreiro", forca=20)
    vilarejo.comprar_cerveja(1)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    vulneravel = [cond for cond in luta.condicoes if cond["tipo"] == "vulneravel" and cond["alvo"] == "chefe"]
    erro = [cond for cond in luta.condicoes if cond["tipo"] == "chance_erro" and cond["alvo"] == 1]
    assert len(vulneravel) == 1
    assert vulneravel[0]["valor"] == pytest.approx(vilarejo.BONUS_DANO_CERVEJA)
    assert len(erro) == 1
    assert erro[0]["valor"] == vilarejo.CHANCE_ERRO_CERVEJA


def test_luta_sem_cerveja_pendente_nao_aplica_condicao_nenhuma():
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    assert luta.condicoes == []


def test_cerveja_consumida_na_primeira_luta_nao_reaparece_na_segunda():
    c = _combatente(1, classe="guerreiro", forca=20)
    vilarejo.comprar_cerveja(1)
    combate.Luta([c], CHEFE_TESTE, andar_num=1)
    luta2 = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    assert luta2.condicoes == []


# ==================================================================
# a cerveja em simular_combate (cacar/explorar/dungeon) -- Step C exigiu
# escopo largo: qualquer luta, não só combate.Luta
# ==================================================================

def _stats_simples(atk=100, defesa=0, critico=0.0, destreza=5):
    return {"atribs": {"destreza": destreza}, "equipamento": {"arma": None}, "atk": atk, "def": defesa, "critico": critico}


def test_simular_combate_multiplicador_dano_aumenta_o_dano_causado(monkeypatch):
    monkeypatch.setattr(bot.random, "random", lambda: 0.99)
    monkeypatch.setattr(bot.random, "uniform", lambda a, b: 1.0)
    s = _stats_simples()
    mob = {"hp": 120, "atk": 10, "def": 0}
    hp_normal, venceu_normal, _ = bot.simular_combate(dict(s), 1000, dict(mob), 1)
    hp_boost, venceu_boost, _ = bot.simular_combate(dict(s), 1000, dict(mob), 1, multiplicador_dano=1.5)
    assert venceu_normal is True
    assert venceu_boost is True
    assert hp_boost > hp_normal   # matou mais rápido -- tomou menos contra-ataque


def test_simular_combate_chance_erro_impede_o_golpe_do_jogador(monkeypatch):
    monkeypatch.setattr(bot.random, "random", lambda: 0.99)
    monkeypatch.setattr(bot.random, "uniform", lambda a, b: 1.0)
    s = _stats_simples()
    mob = {"hp": 1, "atk": 0, "def": 0}
    _, venceu_normal, _ = bot.simular_combate(dict(s), 1000, dict(mob), 1)
    _, venceu_com_erro, _ = bot.simular_combate(dict(s), 1000, dict(mob), 1, chance_erro=1.0)
    assert venceu_normal is True
    assert venceu_com_erro is False   # nunca acertou -- 1 hp de mob nunca caiu


def test_simular_combate_defaults_sao_identicos_ao_comportamento_de_antes(monkeypatch):
    """Regressão: sem kwargs, `simular_combate` continua igual -- os
    defaults (1.0, 0.0) não podem mudar nada de quem não bebeu cerveja."""
    monkeypatch.setattr(bot.random, "random", lambda: 0.5)
    monkeypatch.setattr(bot.random, "uniform", lambda a, b: 1.0)
    s = _stats_simples()
    mob = {"hp": 50, "atk": 5, "def": 0}
    r1 = bot.simular_combate(dict(s), 500, dict(mob), 1)
    r2 = bot.simular_combate(dict(s), 500, dict(mob), 1, multiplicador_dano=1.0, chance_erro=0.0)
    assert r1 == r2


def test_cacar_consome_a_cerveja_pendente_uma_vez_so(monkeypatch):
    _jogador(1, classe="guerreiro", forca=50, andar=1, hp=1000, moedas=10000)
    vilarejo.comprar_cerveja(1)
    ctx = _ctx(1)
    monkeypatch.setattr(bot.random, "choice", lambda lista: lista[0])
    asyncio.run(bot.cacar.callback(ctx))
    assert db.get_jogador(1)["cerveja_pendente"] == 0   # consumida


# ==================================================================
# a cerveja atravessa do vilarejo pra torre
# ==================================================================

def test_cerveja_comprada_no_vilarejo_sobrevive_a_viagem_de_volta_pra_torre():
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.cerveja.callback(ctx))
    assert db.get_jogador(1)["cerveja_pendente"] == 1

    asyncio.run(bot.viajar.callback(ctx, destino="mirante"))
    assert db.get_jogador(1)["cerveja_pendente"] == 1   # viajar não mexe na flag

    asyncio.run(bot.viajar.callback(ctx, destino=15))
    depois = db.get_jogador(1)
    assert depois["mundo"] == "torre"
    assert depois["cerveja_pendente"] == 1   # ainda pendente -- efeito atravessou

    mult, erro = vilarejo.consumir_cerveja_pendente(1)
    assert mult > 1.0 and erro > 0.0


# ==================================================================
# regressão -- jogador dentro da torre não sente nada de novo
# ==================================================================

def test_jogador_na_torre_sem_cerveja_npcs_e_comprar_e_descansar_iguais_a_sempre():
    _jogador(1, andar=1, andar_max=5, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.listar_npcs.callback(ctx))
    embed = ctx.send.call_args.kwargs["embed"]
    assert embed.title == "Quem está no andar 1"

    ctx2 = _ctx(1)
    asyncio.run(bot.comprar.callback(ctx2, argumento="pocao pequena 1"))
    assert db.tem_item(1, "pocao_p", 1)   # loja da torre intocada
