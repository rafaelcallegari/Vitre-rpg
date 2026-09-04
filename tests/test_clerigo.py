# tests/test_clerigo.py
# Step 2d, commit 3: Graça Divina (Reerguer em party / Chama Divina solo),
# auto-ressurreição (solo, uma por luta) e Bênção do Clérigo. Ver
# decisoes.md § Step 2d.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot
import combate
import condicoes
import database as db
import dungeon
import game_data
import habilidades as hab
import passivas

CHEFE_TESTE = {"nome": "Testinho", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0}


def _combatente(user_id, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


def _sem_variancia(monkeypatch):
    monkeypatch.setattr(combate.random, "uniform", lambda a, b: 1.0)
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita, nunca proca a arma


# ==================================================================
# Gate de ascensão
# ==================================================================

def test_nao_ascendido_nao_conhece_graca_divina():
    j = _combatente(1, classe="orador", inteligencia=20).jogador
    assert "graca_divina" not in hab.conhecidas(j)


def test_clerigo_conhece_graca_divina():
    j = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo").jogador
    assert "graca_divina" in hab.conhecidas(j)


def test_graca_divina_nao_tem_requisito_de_atributo():
    """A ascensão É o requisito -- ver decisoes.md § Step 2a."""
    assert "requisito" not in game_data.HABILIDADES["graca_divina"]


# ==================================================================
# Chama Divina (solo) -- dano aplica defesa
# ==================================================================

def test_chama_divina_aplica_a_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    dados = game_data.HABILIDADES["graca_divina"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    assert luta_sem_def.em_party is False
    combate._efeito_graca_divina(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    c2 = _combatente(2, classe="orador", inteligencia=20, ascensao="clerigo")
    luta_com_def = combate.Luta([c2], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_graca_divina(luta_com_def, c2, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def < dano_sem_def


# ==================================================================
# Reerguer (party) -- levanta um caído com 60% do HP máximo, limite de 2
# POR LUTA (não por aliado)
# ==================================================================

def test_reerguer_levanta_o_caido_com_60_por_cento_do_hp():
    clerigo = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    guerreiro = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([clerigo, guerreiro], CHEFE_TESTE, andar_num=1)
    assert luta.em_party is True
    guerreiro.caiu = True
    assert [c.id for c in luta.ativos] == [clerigo.id]

    combate._efeito_graca_divina(luta, clerigo, game_data.HABILIDADES["graca_divina"])

    assert guerreiro.caiu is False
    assert guerreiro.hp == int(combate.FRACAO_HP_REERGUER * guerreiro.s["hp_max"])
    assert {c.id for c in luta.ativos} == {clerigo.id, guerreiro.id}
    assert luta.reergueres_usados == 1


def test_reerguer_revivido_nao_trava_esperando_todo_mundo_escolher():
    """O ponto de maior risco do commit: o revivido precisa de uma ação
    pra esta rodada, senão o "esperando todo mundo" (registrar_acao) fica
    esperando alguém que nunca teve chance de clicar em nada."""
    clerigo = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    guerreiro = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([clerigo, guerreiro], CHEFE_TESTE, andar_num=1)
    guerreiro.caiu = True

    combate._efeito_graca_divina(luta, clerigo, game_data.HABILIDADES["graca_divina"])

    assert guerreiro.acao is not None
    assert guerreiro.defendendo is True   # proteção extra na rodada em que voltou


def test_reerguer_limite_e_2_por_luta_nao_por_aliado():
    """Três quedas na mesma luta -- só as duas primeiras podem ser
    levantadas, mesmo sendo TRÊS aliados diferentes."""
    clerigo = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    a = _combatente(2, classe="guerreiro", forca=20)
    b = _combatente(3, classe="guerreiro", forca=20)
    c3 = _combatente(4, classe="guerreiro", forca=20)
    luta = combate.Luta([clerigo, a, b, c3], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["graca_divina"]

    a.caiu = True
    combate._efeito_graca_divina(luta, clerigo, dados)
    assert a.caiu is False
    assert luta.reergueres_usados == 1

    b.caiu = True
    combate._efeito_graca_divina(luta, clerigo, dados)
    assert b.caiu is False
    assert luta.reergueres_usados == 2

    c3.caiu = True
    assert combate._pode_lancar_graca_divina(luta, clerigo) is False   # esgotado -- some do menu
    combate._efeito_graca_divina(luta, clerigo, dados)   # chamada direta (bypassa o menu)
    assert c3.caiu is True   # NÃO foi levantado -- limite de 2 já bateu
    assert luta.reergueres_usados == 2


def test_reerguer_sem_ninguem_caido_nao_faz_nada_nem_gasta_o_contador():
    clerigo = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    guerreiro = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([clerigo, guerreiro], CHEFE_TESTE, andar_num=1)

    combate._efeito_graca_divina(luta, clerigo, game_data.HABILIDADES["graca_divina"])

    assert luta.reergueres_usados == 0


# ==================================================================
# _pode_lancar_graca_divina -- filtro do menu (Reerguer some quando não
# tem serventia; Chama Divina nunca some)
# ==================================================================

def test_pode_lancar_graca_divina_em_party_sem_caido_e_false():
    clerigo = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    guerreiro = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([clerigo, guerreiro], CHEFE_TESTE, andar_num=1)

    assert combate._pode_lancar_graca_divina(luta, clerigo) is False


def test_pode_lancar_graca_divina_em_party_com_caido_e_true():
    clerigo = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    guerreiro = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([clerigo, guerreiro], CHEFE_TESTE, andar_num=1)
    guerreiro.caiu = True

    assert combate._pode_lancar_graca_divina(luta, clerigo) is True


def test_pode_lancar_graca_divina_solo_e_sempre_true():
    clerigo = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    luta = combate.Luta([clerigo], CHEFE_TESTE, andar_num=1)

    assert combate._pode_lancar_graca_divina(luta, clerigo) is True


def test_menu_de_habilidades_esconde_graca_divina_sem_caido():
    clerigo = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo", mana=100)
    guerreiro = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([clerigo, guerreiro], CHEFE_TESTE, andar_num=1)
    painel = MagicMock()
    painel.luta = luta

    menu = combate.MenuHabilidades(painel, clerigo)

    chaves = [item.chave for item in menu.children if isinstance(item, combate.BotaoHabilidade)]
    assert "graca_divina" not in chaves


def test_menu_de_habilidades_mostra_graca_divina_com_caido():
    clerigo = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo", mana=100)
    guerreiro = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([clerigo, guerreiro], CHEFE_TESTE, andar_num=1)
    guerreiro.caiu = True
    painel = MagicMock()
    painel.luta = luta

    menu = combate.MenuHabilidades(painel, clerigo)

    chaves = [item.chave for item in menu.children if isinstance(item, combate.BotaoHabilidade)]
    assert "graca_divina" in chaves


# ==================================================================
# Auto-ressurreição -- só luta SOLO, uma vez por luta
# ==================================================================

def test_auto_ressurreicao_clerigo_solo_volta_com_60_por_cento(monkeypatch):
    c = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    c.hp = -5
    c.caiu = True

    combate._talvez_auto_ressuscitar(luta)

    assert c.caiu is False
    assert c.hp == int(combate.FRACAO_HP_AUTO_RESSURREICAO * c.s["hp_max"])
    assert luta.auto_ressurreicao_usada is True


def test_auto_ressurreicao_so_dispara_uma_vez_por_luta():
    c = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    c.hp = 0
    c.caiu = True
    combate._talvez_auto_ressuscitar(luta)
    assert c.caiu is False

    c.hp = 0   # cai de novo, mais tarde na mesma luta
    c.caiu = True
    combate._talvez_auto_ressuscitar(luta)

    assert c.caiu is True   # NÃO ressuscita de novo -- já usou


def test_auto_ressurreicao_nao_dispara_em_party():
    clerigo = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    guerreiro = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([clerigo, guerreiro], CHEFE_TESTE, andar_num=1)
    clerigo.hp = 0
    clerigo.caiu = True
    guerreiro.hp = 0
    guerreiro.caiu = True   # ninguém ativo, mas é PARTY

    combate._talvez_auto_ressuscitar(luta)

    assert clerigo.caiu is True   # não voltou -- auto-ressurreição é só solo


def test_auto_ressurreicao_nao_dispara_pra_quem_nao_e_clerigo():
    c = _combatente(1, classe="orador", inteligencia=20)   # sem ascensão
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    c.hp = 0
    c.caiu = True

    combate._talvez_auto_ressuscitar(luta)

    assert c.caiu is True


def test_fim_da_luta_ressuscita_o_clerigo_solo_em_vez_de_declarar_derrota(monkeypatch):
    """Prova o caminho real -- via Luta.fim_da_luta, não a função interna
    direto -- que o clérigo solo não recebe finalizar_derrota."""
    c = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    c.hp = 0
    c.caiu = True

    resultado = asyncio.run(painel.fim_da_luta())

    assert resultado is None   # a luta NÃO acabou -- continua
    assert c.caiu is False
    assert luta.encerrada is False


# ==================================================================
# Bênção -- curas do clérigo atravessam parte da redução de cura recebida
# ==================================================================

def test_bencao_reduz_a_reducao_de_cura_consultada_pra_curas_do_clerigo():
    alvo = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([alvo], CHEFE_TESTE, andar_num=1)
    alvo.hp = 1   # bem abaixo do máximo, senão o teto do `min(hp_max, ...)` mascara a cura
    condicoes.aplicar(luta, alvo.id, "reduz_cura", "Ferida Sombria", "🌑", duracao=5, valor=0.5)

    j_clerigo = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo").jogador
    bonus = passivas.fracao_reducao_cura_ignorada(j_clerigo)
    assert bonus > 0   # sanity -- Bênção realmente devolve algo

    condicoes.aplicar(
        luta, alvo.id, "cura_por_rodada", "Palavra de Alento", "🕊️",
        duracao=1, valor=100, origem=1, bonus_cura_ignorado=bonus,
    )
    hp_antes = alvo.hp

    condicoes.tick(luta)

    cura_recebida = alvo.hp - hp_antes
    cura_esperada = int(100 * (1 - max(0.0, 0.5 - bonus)))
    assert cura_recebida == cura_esperada
    assert cura_recebida > 50   # mais do que os 50% que "Ferida Sombria" sozinha deixaria passar


def test_sem_bencao_a_reducao_de_cura_recebida_nao_muda():
    alvo = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([alvo], CHEFE_TESTE, andar_num=1)
    alvo.hp = 1
    condicoes.aplicar(luta, alvo.id, "reduz_cura", "Ferida Sombria", "🌑", duracao=5, valor=0.5)
    condicoes.aplicar(
        luta, alvo.id, "cura_por_rodada", "Palavra de Alento", "🕊️",
        duracao=1, valor=100, origem=1,   # sem bonus_cura_ignorado -- mago/orador comum
    )
    hp_antes = alvo.hp

    condicoes.tick(luta)

    assert alvo.hp - hp_antes == 50   # comportamento de sempre, sem Bênção


def test_efeito_palavra_de_alento_de_um_clerigo_ja_carrega_o_bonus_de_bencao():
    """Regressão de fiação -- o efeito de verdade (não o condicoes.aplicar
    direto) precisa passar o bônus certo pro clérigo lançador."""
    clerigo = _combatente(1, classe="orador", inteligencia=20, ascensao="clerigo")
    alvo = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([clerigo, alvo], CHEFE_TESTE, andar_num=1)

    combate._efeito_palavra_de_alento(luta, clerigo, game_data.HABILIDADES["palavra_de_alento"], alvo_id=alvo.id)

    cond = luta.condicoes[-1]
    assert cond["bonus_cura_ignorado"] == game_data.PASSIVAS["bencao"]["valor"]


# ==================================================================
# Integração com a dungeon -- auto-ressurreição ANTES de processar_morte,
# senão a run é apagada e a penalidade cobrada de quem não morreu
# ==================================================================

SALAS_DE_TESTE = (
    "camara_dos_ecos", "salao_do_espelho_rachado", "piso_instavel",
    "bau_esquecido", "jardim_suspenso",
)


def _jogador_dungeon(user_id=1, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    padrao = dict(andar=9, nivel=15, classe="orador", inteligencia=20)
    padrao.update(campos)
    db.atualizar_jogador(user_id, **padrao)
    return db.get_jogador(user_id)


def _ctx_dungeon(user_id=1):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    return ctx


def test_clerigo_na_dungeon_auto_ressuscita_em_vez_de_perder_a_run(monkeypatch):
    j = _jogador_dungeon(1, ascensao="clerigo", moedas=1000)
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))
    run = dungeon.obter_run(1)
    monkeypatch.setitem(
        dungeon.H, "simular_combate",
        lambda s, hp, mob, andar_num: (0, False, ["derrota"]),
    )
    spy = AsyncMock(wraps=bot.a_processar_morte)
    monkeypatch.setitem(dungeon.H, "a_processar_morte", spy)

    ctx = _ctx_dungeon(1)
    asyncio.run(dungeon.resolver_sala_atual(ctx, j, run))

    spy.assert_not_awaited()                        # processar_morte NUNCA rodou
    assert dungeon.obter_run(1) is not None          # a run continua -- não foi apagada
    assert dungeon.obter_run(1)["indice"] == run["indice"]   # nem avançou -- mesma sala pra tentar de novo
    assert db.get_jogador(1)["moedas"] == 1000       # nenhuma penalidade cobrada
    hp_esperado = int(combate.FRACAO_HP_AUTO_RESSURREICAO * bot.stats(j)["hp_max"])
    assert db.get_jogador(1)["hp"] == hp_esperado
    embed = ctx.send.call_args.kwargs["embed"]
    assert "recusa a cair" in embed.fields[0].name.lower()


def test_nao_clerigo_na_dungeon_continua_perdendo_a_run_normalmente(monkeypatch):
    """Regressão: o caminho de morte de sempre (Step 1, corrigido no
    cartão de correção da run) não pode mudar pra quem não é clérigo."""
    j = _jogador_dungeon(1, classe="guerreiro", forca=20, moedas=1000)   # sem ascensão
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))
    run = dungeon.obter_run(1)
    monkeypatch.setitem(
        dungeon.H, "simular_combate",
        lambda s, hp, mob, andar_num: (0, False, ["derrota"]),
    )

    asyncio.run(dungeon.resolver_sala_atual(_ctx_dungeon(1), j, run))

    assert dungeon.obter_run(1) is None   # a run foi apagada -- comportamento de sempre
    assert db.get_jogador(1)["moedas"] < 1000   # penalidade cobrada normalmente
