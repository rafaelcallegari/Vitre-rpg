# tests/test_entidade_sombria.py
# Step D, commit 4: a Essência das Trevas e a Entidade Sombria. Ela chega
# com a incursão e muda de lugar junto -- só existe no andar corrompido do
# dia. Vende Selo de Efeito (encaixa um efeito do commit 3 num acessório) e
# Salvo-Conduto (absorve a penalidade de morte, um uso, em qualquer lugar da
# torre, um por jogador por vez). Ver decisoes.md § Step D.
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import database as db
import entidade_sombria
import game_data
import incursao
import npcs

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


def _msg(ctx):
    return ctx.send.call_args.args[0]


def _fixar_andar_do_dia(monkeypatch, momento=None):
    momento = momento or datetime(2026, 5, 5, 12, tzinfo=FUSO)
    n = incursao.andar_do_dia(momento)
    monkeypatch.setattr(incursao, "andar_do_dia", lambda m=None: n)
    return n


def _equipar_anel(user_id, item="anel_forca"):
    instancia_id = db.criar_instancia(user_id, item)
    db.atualizar_jogador(user_id, anel=item, anel_instancia_id=instancia_id)
    return instancia_id


# ==================================================================
# a Entidade Sombria só aparece no andar corrompido
# ==================================================================

def test_entidade_sombria_nao_aparece_em_andar_nao_corrompido(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    outro = 1 if n != 1 else 2
    assert not entidade_sombria.npc_presente(outro)
    nomes = {p["nome"] for p in npcs.npcs_do_andar(outro)}
    assert "A Entidade Sombria" not in nomes


def test_entidade_sombria_aparece_no_andar_corrompido_de_hoje(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    assert entidade_sombria.npc_presente(n)
    nomes = {p["nome"] for p in npcs.npcs_do_andar(n)}
    assert "A Entidade Sombria" in nomes


def test_entidade_sombria_muda_de_lugar_com_a_incursao(monkeypatch):
    """Ela 'chega com a incursão e muda de lugar junto' -- muda de andar
    no dia seguinte, exatamente onde o sorteio mudar."""
    dia1 = datetime(2026, 5, 5, 12, tzinfo=FUSO)
    dia2 = datetime(2026, 5, 6, 12, tzinfo=FUSO)
    n1 = incursao.andar_do_dia(dia1)
    n2 = incursao.andar_do_dia(dia2)
    assert entidade_sombria.npc_presente(n1, dia1)
    assert entidade_sombria.npc_presente(n2, dia2)
    if n1 != n2:
        assert not entidade_sombria.npc_presente(n1, dia2)


def test_falar_com_entidade_sombria_no_andar_certo(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    _jogador(1, andar=n, andar_max=n)
    ctx = _ctx(1)
    asyncio.run(bot.falar.callback(ctx, quem="entidade"))
    embed = ctx.send.call_args.kwargs["embed"]
    assert "Selo de Efeito" in str(embed.fields[0].name)
    assert "Salvo-Conduto" in str(embed.fields[1].name)


# ==================================================================
# Essência das Trevas -- não vende, não crafta, não equipa
# ==================================================================

def test_essencia_das_trevas_nao_vendavel_nem_de_loja():
    dado = game_data.ITENS["essencia_das_trevas"]
    assert dado.get("vendavel", True) is False
    assert dado.get("loja", True) is False
    assert dado["tipo"] not in ("arma", "armadura", "anel", "colar")


def test_criatura_de_sombra_pode_dropar_essencia(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    monkeypatch.setattr(bot.random, "choice", lambda lista: lista[0])
    monkeypatch.setattr(bot.random, "random", lambda: 0.0)   # sempre dropa tudo que rolar
    _jogador(1, classe="guerreiro", forca=999, andar=n, andar_max=n, hp=999999, moedas=0)
    ctx = _ctx(1)
    monkeypatch.setattr(bot.random, "uniform", lambda a, b: 1.15)
    asyncio.run(bot.cacar.callback(ctx))
    assert db.qtd_item(1, "essencia_das_trevas") >= 1


def test_criatura_normal_nunca_dropa_essencia(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    outro = 1 if n != 1 else 2
    monkeypatch.setattr(bot.random, "choice", lambda lista: lista[0])
    monkeypatch.setattr(bot.random, "random", lambda: 0.0)
    _jogador(1, classe="guerreiro", forca=999, andar=outro, andar_max=outro, hp=999999, moedas=0)
    ctx = _ctx(1)
    monkeypatch.setattr(bot.random, "uniform", lambda a, b: 1.15)
    asyncio.run(bot.cacar.callback(ctx))
    assert db.qtd_item(1, "essencia_das_trevas") == 0


# ==================================================================
# rpg selo -- Selo de Efeito
# ==================================================================

def test_comprar_selo_falha_sem_essencia_suficiente():
    _jogador(1)
    _equipar_anel(1)
    ok, motivo = entidade_sombria.comprar_selo(1, "anel", "cura_ao_critico")
    assert ok is False
    assert motivo == "sem_essencia"


def test_comprar_selo_falha_sem_a_peca_equipada():
    _jogador(1)
    db.add_item(1, "essencia_das_trevas", entidade_sombria.PRECO_SELO)
    ok, motivo = entidade_sombria.comprar_selo(1, "anel", "cura_ao_critico")
    assert ok is False
    assert motivo == "sem_peca"


def test_comprar_selo_aplica_o_efeito_e_cobra_a_essencia():
    _jogador(1)
    instancia_id = _equipar_anel(1)
    db.add_item(1, "essencia_das_trevas", entidade_sombria.PRECO_SELO)
    ok, motivo = entidade_sombria.comprar_selo(1, "anel", "cura_ao_critico")
    assert ok is True
    assert motivo is None
    assert db.get_instancia(instancia_id)["efeito"] == "cura_ao_critico"
    assert db.qtd_item(1, "essencia_das_trevas") == 0


def test_comprar_selo_sobrescreve_efeito_anterior():
    _jogador(1)
    instancia_id = _equipar_anel(1)
    db.definir_efeito_instancia(instancia_id, "ignora_condicao")
    db.add_item(1, "essencia_das_trevas", entidade_sombria.PRECO_SELO)
    entidade_sombria.comprar_selo(1, "anel", "furia_extra_ao_apanhar")
    assert db.get_instancia(instancia_id)["efeito"] == "furia_extra_ao_apanhar"


def test_encontrar_efeito_casa_por_chave_e_por_nome():
    assert entidade_sombria.encontrar_efeito("cura_ao_critico") == "cura_ao_critico"
    assert entidade_sombria.encontrar_efeito("Fio Vermelho") == "cura_ao_critico"
    assert entidade_sombria.encontrar_efeito("véu cinza") == "ignora_condicao"
    assert entidade_sombria.encontrar_efeito("bobagem") is None


def test_encontrar_efeito_nunca_acha_passiva_de_ascensao():
    """O Selo só vende os TRÊS efeitos do commit 3 -- nunca uma passiva
    de ascensão como Sangue Frio, mesmo que o nome exista em PASSIVAS."""
    assert entidade_sombria.encontrar_efeito("Sangue Frio") is None
    assert entidade_sombria.encontrar_efeito("sangue_frio") is None


def test_rpg_selo_recusa_fora_do_andar_corrompido(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    outro = 1 if n != 1 else 2
    _jogador(1, andar=outro, andar_max=outro)
    _equipar_anel(1)
    db.add_item(1, "essencia_das_trevas", entidade_sombria.PRECO_SELO)
    ctx = _ctx(1)
    asyncio.run(bot.selo_de_efeito.callback(ctx, argumento="anel cura_ao_critico"))
    assert "corrompido" in _msg(ctx).lower()
    assert db.qtd_item(1, "essencia_das_trevas") == entidade_sombria.PRECO_SELO   # não cobrou


def test_rpg_selo_funciona_no_andar_corrompido(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    _jogador(1, andar=n, andar_max=n)
    instancia_id = _equipar_anel(1)
    db.add_item(1, "essencia_das_trevas", entidade_sombria.PRECO_SELO)
    ctx = _ctx(1)
    asyncio.run(bot.selo_de_efeito.callback(ctx, argumento="anel cura_ao_critico"))
    assert db.get_instancia(instancia_id)["efeito"] == "cura_ao_critico"


# ==================================================================
# rpg salvoconduto -- vale em qualquer lugar, um por vez, consumido na morte
# ==================================================================

def test_comprar_salvo_conduto_falha_sem_essencia():
    _jogador(1)
    ok, motivo = entidade_sombria.comprar_salvo_conduto(1)
    assert ok is False
    assert motivo == "sem_essencia"


def test_comprar_salvo_conduto_recusa_segunda_compra():
    _jogador(1)
    db.add_item(1, "essencia_das_trevas", entidade_sombria.PRECO_SALVO_CONDUTO * 2)
    ok1, _ = entidade_sombria.comprar_salvo_conduto(1)
    assert ok1 is True
    ok2, motivo2 = entidade_sombria.comprar_salvo_conduto(1)
    assert ok2 is False
    assert motivo2 == "ja_tem"
    assert db.qtd_item(1, "salvo_conduto") == 1   # nunca mais que um


def test_salvo_conduto_custa_mais_que_o_selo():
    assert entidade_sombria.PRECO_SALVO_CONDUTO > entidade_sombria.PRECO_SELO


def test_salvo_conduto_absorve_a_penalidade_de_morte():
    j = _jogador(1, moedas=1000, andar=5, andar_max=5)
    db.add_item(1, "salvo_conduto", 1)
    s = {"hp_max": 200}
    perda, salvo_conduto = bot.processar_morte(j, s)
    assert perda == 0
    assert salvo_conduto is True
    depois = db.get_jogador(1)
    assert depois["moedas"] == 1000   # nenhuma moeda perdida
    assert db.qtd_item(1, "salvo_conduto") == 0   # consumido


def test_salvo_conduto_protege_a_reconquista_acima_do_selo():
    """'Vale em qualquer lugar' -- inclusive contra a penalidade mais
    dura (reconquista do andar_max acima do Selo)."""
    import andares_altos
    andar_alto = andares_altos.ANDAR_ACIMA_DO_SELO + 3
    j = _jogador(1, moedas=1000, andar=andar_alto, andar_max=andar_alto + 2)
    db.add_item(1, "salvo_conduto", 1)
    s = {"hp_max": 200}
    bot.processar_morte(j, s)
    depois = db.get_jogador(1)
    assert depois["andar_max"] == andar_alto + 2   # não reconquistou nada


def test_salvo_conduto_ainda_derruba_hp_e_soma_morte():
    """Absorve a CONSEQUÊNCIA (moedas/reconquista), não a queda em si."""
    j = _jogador(1, moedas=1000, andar=5, andar_max=5, mortes=2)
    db.add_item(1, "salvo_conduto", 1)
    s = {"hp_max": 200}
    bot.processar_morte(j, s)
    depois = db.get_jogador(1)
    assert depois["hp"] == int(s["hp_max"] * 0.3)
    assert depois["mortes"] == 3


def test_sem_salvo_conduto_penalidade_normal_continua_igual():
    j = _jogador(1, moedas=1000, andar=5, andar_max=5)
    s = {"hp_max": 200}
    perda, salvo_conduto = bot.processar_morte(j, s)
    assert perda == 200
    assert salvo_conduto is False
    assert db.get_jogador(1)["moedas"] == 800


# ==================================================================
# regressão -- fora do andar corrompido, nada disso existe
# ==================================================================

def test_sem_incursao_no_andar_nenhum_comando_novo_muda_nada(monkeypatch):
    n = _fixar_andar_do_dia(monkeypatch)
    outro = 1 if n != 1 else 2
    _jogador(1, andar=outro, andar_max=outro)
    ctx = _ctx(1)
    asyncio.run(bot.salvo_conduto.callback(ctx))
    assert "corrompido" in _msg(ctx).lower()
    assert db.qtd_item(1, "salvo_conduto") == 0
