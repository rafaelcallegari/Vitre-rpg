# tests/test_dungeon_armadilha.py
# Cartão "Exploração de Dungeon", commit 1: a camada de armadilha. Três
# portas (Percepção/Esquiva/Força), nesta ordem, pra todo personagem; falhar
# as três aplica dano e uma condição que atravessa pra próxima sala. Ver
# decisoes.md § Dungeon -- pool e armadilha.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot
import database as db
import dungeon
import game_data

SALAS_DE_TESTE = (
    "camara_dos_ecos", "salao_do_espelho_rachado", "piso_instavel",
    "bau_esquecido", "corrente_solta",
)


def _jogador(user_id=1, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    padrao = dict(andar=9, nivel=15, classe="guerreiro", forca=20, destreza=15, inteligencia=10)
    padrao.update(campos)
    db.atualizar_jogador(user_id, **padrao)
    return db.get_jogador(user_id)


def _ctx(user_id=1):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    return ctx


def _sempre_vitoria(monkeypatch):
    monkeypatch.setitem(dungeon.H, "simular_combate", lambda s, hp, mob, andar_num: (hp, True, ["vitória"]))


# ==================================================================
# A fórmula do alvo e as portas isoladas -- d20 determinizado
# ==================================================================

def test_alvo_armadilha_sobe_3_por_nivel():
    assert dungeon._alvo_armadilha(1) == game_data.DUNGEON_ARMADILHA_DIFICULDADE_BASE + game_data.DUNGEON_ARMADILHA_DIFICULDADE_POR_NIVEL
    assert dungeon._alvo_armadilha(15) == 3 * 15 + 7 == 52


def test_percepcao_passa_quando_int_mais_d20_bate_o_alvo(monkeypatch):
    monkeypatch.setattr(dungeon.random, "randint", lambda a, b: 20)
    atribs = {"forca": 1, "destreza": 1, "inteligencia": 1}   # baixo em tudo -- só o d20=20 carrega

    resultado = dungeon._resolver_portas_armadilha(atribs, nivel=1)

    assert resultado == "percepcao"


def test_esquiva_passa_quando_percepcao_falha_mas_destreza_basta(monkeypatch):
    alvo = dungeon._alvo_armadilha(1)
    rolls = iter([1, alvo])   # percepção erra feio (INT+1), esquiva bate exatamente o alvo
    monkeypatch.setattr(dungeon.random, "randint", lambda a, b: next(rolls))
    atribs = {"forca": 1, "destreza": 0, "inteligencia": 1}

    resultado = dungeon._resolver_portas_armadilha(atribs, nivel=1)

    assert resultado == "esquiva"


def test_forca_passa_quando_percepcao_e_esquiva_falham(monkeypatch):
    rolls = iter([1, 1, 20])
    monkeypatch.setattr(dungeon.random, "randint", lambda a, b: next(rolls))
    atribs = {"forca": 1, "destreza": 1, "inteligencia": 1}

    resultado = dungeon._resolver_portas_armadilha(atribs, nivel=1)

    assert resultado == "forca"


def test_falhou_quando_as_tres_portas_erram(monkeypatch):
    monkeypatch.setattr(dungeon.random, "randint", lambda a, b: 1)
    atribs = {"forca": 1, "destreza": 1, "inteligencia": 1}

    resultado = dungeon._resolver_portas_armadilha(atribs, nivel=15)

    assert resultado == "falhou"


def test_ordem_e_sempre_percepcao_esquiva_forca():
    """Regressão de fiação -- se todas as três passariam, o resultado é
    sempre o da PRIMEIRA (percepção), nunca outra."""
    atribs = {"forca": 999, "destreza": 999, "inteligencia": 999}
    resultado = dungeon._resolver_portas_armadilha(atribs, nivel=1)
    assert resultado == "percepcao"


# ==================================================================
# Dano da armadilha -- nunca mata, piso em 1 HP
# ==================================================================

def test_aplicar_dano_armadilha_e_15_por_cento_do_hp_maximo():
    j = _jogador(1)
    s = bot.stats(j)
    db.atualizar_jogador(1, hp=s["hp_max"])
    j = db.get_jogador(1)

    dano = dungeon._aplicar_dano_armadilha(1, j, s)

    assert dano == max(1, int(game_data.DUNGEON_ARMADILHA_FRACAO_DANO * s["hp_max"]))
    assert db.get_jogador(1)["hp"] == s["hp_max"] - dano


def test_aplicar_dano_armadilha_nunca_derruba_abaixo_de_1():
    j = _jogador(1)
    s = bot.stats(j)
    db.atualizar_jogador(1, hp=1)
    j = db.get_jogador(1)

    dungeon._aplicar_dano_armadilha(1, j, s)

    assert db.get_jogador(1)["hp"] == 1


# ==================================================================
# As três salas limpas (armadilha=False) nunca disparam nada
# ==================================================================

def test_sala_limpa_nunca_chama_a_resolucao_de_portas(monkeypatch):
    def _explode(*a, **k):
        raise AssertionError("armadilha rolou numa sala limpa")
    monkeypatch.setattr(dungeon, "_resolver_portas_armadilha", _explode)
    _sempre_vitoria(monkeypatch)
    j = _jogador(1)
    db.criar_dungeon_run(1, ["camara_dos_ecos", "salao_do_espelho_rachado",
                             "bau_esquecido", "nicho_da_torre", "jardim_suspenso"])
    run = dungeon.obter_run(1)

    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j, run))   # não deveria levantar


def test_as_salas_declaradas_limpas_no_pool_atual_tem_armadilha_false():
    limpas = {"camara_dos_ecos", "corredor_sussurrante", "salao_do_espelho_rachado",
              "jardim_suspenso", "bau_esquecido", "nicho_da_torre"}
    for chave in limpas:
        sala = dungeon._POOL_POR_CHAVE[chave]
        assert sala["armadilha"] is False, chave


def test_hp_do_jogador_nao_muda_numa_sala_limpa(monkeypatch):
    _sempre_vitoria(monkeypatch)
    j = _jogador(1)
    hp_antes = j["hp"]
    db.criar_dungeon_run(1, ["camara_dos_ecos", "salao_do_espelho_rachado",
                             "bau_esquecido", "nicho_da_torre", "jardim_suspenso"])
    run = dungeon.obter_run(1)

    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j, run))

    # vitória não muda o HP de propósito (mesmo comportamento de sempre) --
    # o que este teste prova é que NENHUM dano de armadilha foi aplicado
    assert db.get_jogador(1)["hp"] == hp_antes


# ==================================================================
# A condição atravessa pra próxima sala -- só quando falha as três
# ==================================================================

def test_falhar_as_tres_grava_condicao_pendente_na_run(monkeypatch):
    monkeypatch.setattr(dungeon.random, "randint", lambda a, b: 1)   # falha as três portas
    monkeypatch.setattr(dungeon.random, "choice", lambda seq: seq[0])   # condição/espólio determinizados
    j = _jogador(1)
    db.criar_dungeon_run(1, ["piso_instavel", "camara_dos_ecos",
                             "bau_esquecido", "nicho_da_torre", "jardim_suspenso"])
    run = dungeon.obter_run(1)

    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j, run))

    run_depois = dungeon.obter_run(1)
    assert run_depois["condicao_armadilha"] is not None
    assert run_depois["condicao_armadilha"]["tipo"] == game_data.DUNGEON_CONDICOES_ARMADILHA[0]["tipo"]


def test_esquivar_ou_resistir_nao_deixa_condicao_pendente(monkeypatch):
    rolls = iter([1, 999])   # percepção erra, esquiva acerta em cheio
    monkeypatch.setattr(dungeon.random, "randint", lambda a, b: next(rolls))
    j = _jogador(1)
    db.criar_dungeon_run(1, ["piso_instavel", "camara_dos_ecos",
                             "bau_esquecido", "nicho_da_torre", "jardim_suspenso"])
    run = dungeon.obter_run(1)

    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j, run))

    assert dungeon.obter_run(1)["condicao_armadilha"] is None


def test_condicao_dano_por_rodada_bate_na_abertura_da_proxima_sala(monkeypatch):
    _sempre_vitoria(monkeypatch)
    j = _jogador(1)
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))
    db.definir_condicao_armadilha(1, {"tipo": "dano_por_rodada", "nome": "Sangramento", "emoji": "🩹", "valor": 0.05})
    hp_antes = db.get_jogador(1)["hp"]
    run = dungeon.obter_run(1)

    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j, run))

    assert db.get_jogador(1)["hp"] < hp_antes
    assert dungeon.obter_run(1) is None or dungeon.obter_run(1)["condicao_armadilha"] is None   # consumida


def test_condicao_consumida_nao_sobrevive_pra_sala_seguinte(monkeypatch):
    """"Pra próxima sala" é UMA sala -- não duas."""
    _sempre_vitoria(monkeypatch)
    j = _jogador(1)
    db.criar_dungeon_run(1, ["camara_dos_ecos", "corredor_sussurrante",
                             "bau_esquecido", "nicho_da_torre", "jardim_suspenso"])
    db.definir_condicao_armadilha(1, {"tipo": "dano_por_rodada", "nome": "Sangramento", "emoji": "🩹", "valor": 0.05})
    run = dungeon.obter_run(1)
    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j, run))
    hp_apos_primeira = db.get_jogador(1)["hp"]

    j2 = db.get_jogador(1)
    run2 = dungeon.obter_run(1)
    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j2, run2))

    assert db.get_jogador(1)["hp"] == hp_apos_primeira   # a segunda sala não sofreu nada


def test_condicao_vulneravel_so_afeta_a_proxima_sala_se_for_combate(monkeypatch):
    """vulneravel/chance_erro não têm tradução fora de combate -- numa
    sala sem luta, elas só somem, sem crashar nem fazer nada."""
    j = _jogador(1)
    db.criar_dungeon_run(1, ["bau_esquecido", "camara_dos_ecos", "salao_do_espelho_rachado",
                             "nicho_da_torre", "jardim_suspenso"])
    db.definir_condicao_armadilha(1, {"tipo": "vulneravel", "nome": "Ferimento Aberto", "emoji": "🩸", "valor": 0.20})
    run = dungeon.obter_run(1)

    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j, run))   # não deveria levantar

    assert dungeon.obter_run(1) is None or dungeon.obter_run(1)["condicao_armadilha"] is None


def test_condicao_vulneravel_infla_o_atk_do_mob_na_proxima_luta():
    s = {"hp_max": 100, "atk": 10, "def": 5}
    mob = {"atk": 20, "def": 3}
    condicao = {"tipo": "vulneravel", "nome": "Ferimento Aberto", "emoji": "🩸", "valor": 0.20}

    s_luta, mob_luta = dungeon._aplicar_condicao_no_combate(condicao, s, mob)

    assert mob_luta["atk"] == int(20 * 1.20)
    assert s_luta["atk"] == 10   # não mexe no atk do jogador
    assert s["atk"] == 10 and mob["atk"] == 20   # os originais não mudam -- são cópias


def test_condicao_chance_erro_reduz_o_atk_do_jogador_na_proxima_luta():
    s = {"hp_max": 100, "atk": 10, "def": 5}
    mob = {"atk": 20, "def": 3}
    condicao = {"tipo": "chance_erro", "nome": "Tontura", "emoji": "💫", "valor": 0.20}

    s_luta, mob_luta = dungeon._aplicar_condicao_no_combate(condicao, s, mob)

    assert s_luta["atk"] == int(10 * 0.80)
    assert mob_luta["atk"] == 20


def test_resolver_combate_de_verdade_passa_a_condicao_pro_simular_combate(monkeypatch):
    """Fiação ponta a ponta -- `_aplicar_condicao_no_combate` sozinha
    (testada acima) não prova que `_resolver_combate` REALMENTE a chama;
    intercepta `simular_combate` e olha os argumentos que ele recebeu de
    verdade."""
    capturado = {}

    def _espiao(s, hp, mob, andar_num):
        capturado["mob_atk"] = mob["atk"]
        return hp, True, ["vitória"]

    monkeypatch.setitem(dungeon.H, "simular_combate", _espiao)
    j = _jogador(1)
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))   # índice 0 = "camara_dos_ecos", combate
    db.definir_condicao_armadilha(1, {"tipo": "vulneravel", "nome": "Ferimento Aberto", "emoji": "🩸", "valor": 0.20})
    run = dungeon.obter_run(1)

    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j, run))

    mobs_possiveis = {m["nome"]: m["atk"] for m in game_data.ANDARES[9]["monstros"]}
    assert capturado["mob_atk"] in {int(atk * 1.20) for atk in mobs_possiveis.values()}
    assert capturado["mob_atk"] not in mobs_possiveis.values()   # não é o atk cru -- foi inflado


def test_sem_condicao_nenhuma_o_combate_nao_muda():
    s = {"hp_max": 100, "atk": 10, "def": 5}
    mob = {"atk": 20, "def": 3}

    s_luta, mob_luta = dungeon._aplicar_condicao_no_combate(None, s, mob)

    assert s_luta is s and mob_luta is mob   # nem cópia -- devolve os originais direto


# ==================================================================
# Percepção passa -> escolha (desarmar dá espólio / contornar não dá nada)
# ==================================================================

def test_percepcao_apresenta_a_escolha_com_dois_botoes(monkeypatch):
    monkeypatch.setattr(dungeon.random, "randint", lambda a, b: 999)   # percepção sempre passa
    j = _jogador(1)
    db.criar_dungeon_run(1, ["piso_instavel", "camara_dos_ecos",
                             "bau_esquecido", "nicho_da_torre", "jardim_suspenso"])
    run = dungeon.obter_run(1)
    ctx = _ctx(1)

    asyncio.run(dungeon.resolver_sala_atual(ctx, j, run))

    assert ctx.send.await_count == 1
    view = ctx.send.call_args.kwargs["view"]
    assert isinstance(view, dungeon._ViewEscolhaArmadilha)
    escolhas = {item.escolha for item in view.children}
    assert escolhas == {"desarmar", "contornar"}
    # a sala não avançou ainda -- espera o clique
    assert dungeon.obter_run(1)["indice"] == run["indice"]


def test_desarmar_da_espolio_e_nao_deixa_condicao_pendente():
    j = _jogador(1)
    s = bot.stats(j)
    db.criar_dungeon_run(1, ["piso_instavel", "camara_dos_ecos",
                             "bau_esquecido", "nicho_da_torre", "jardim_suspenso"])
    run = dungeon.obter_run(1)
    sala = dungeon.sala_atual(run)
    enviados = []

    async def enviar(*, embed, view=None):
        enviados.append(embed)

    asyncio.run(dungeon._resolver_desarmar(enviar, j, s, run, sala, condicao=None, user_id=1))

    inventario = {i["item"]: i["qtd"] for i in db.get_inventario(1)}
    assert any(item in dungeon._ESPOLIOS for item in inventario)
    assert len(enviados) == 1


def test_contornar_nao_da_nada():
    j = _jogador(1)
    s = bot.stats(j)
    db.criar_dungeon_run(1, ["piso_instavel", "camara_dos_ecos",
                             "bau_esquecido", "nicho_da_torre", "jardim_suspenso"])
    run = dungeon.obter_run(1)
    sala = dungeon.sala_atual(run)

    async def enviar(*, embed, view=None):
        pass

    asyncio.run(dungeon._resolver_contornar(enviar, j, s, run, sala, condicao=None))

    assert db.get_inventario(1) == []
