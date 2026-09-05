# tests/test_dungeon_pool.py
# Cartão "Exploração de Dungeon", commit 4: as dez salas -- 4 combate, 3
# evento (duas portas cada), 3 achado (um risco diferente cada). Ver
# decisoes.md § Dungeon -- pool e armadilha.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot
import database as db
import dungeon
import game_data


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


def _interacao(user_id):
    it = MagicMock()
    it.user.id = user_id
    it.response = MagicMock()
    it.response.defer = AsyncMock()
    it.edit_original_response = AsyncMock()
    it.followup = MagicMock()
    it.followup.send = AsyncMock()
    return it


def _run_iniciando_em(chave, user_id=1):
    outras = [s["chave"] for s in game_data.DUNGEON_POOL if s["chave"] != chave][:4]
    db.criar_dungeon_run(user_id, [chave] + outras)
    return dungeon.obter_run(user_id)


# ==================================================================
# Estrutura do pool -- dez salas, 4/3/3, cada evento com duas portas
# ==================================================================

def test_pool_tem_exatamente_dez_salas():
    assert len(game_data.DUNGEON_POOL) == 10


def test_distribuicao_e_quatro_combate_tres_evento_tres_achado():
    contagem = {}
    for sala in game_data.DUNGEON_POOL:
        contagem[sala["tipo"]] = contagem.get(sala["tipo"], 0) + 1
    assert contagem == {"combate": 4, "evento": 3, "achado": 3}


def test_todo_evento_declara_exatamente_duas_portas_com_chave_e_label():
    for sala in game_data.DUNGEON_POOL:
        if sala["tipo"] != "evento":
            continue
        assert len(sala["portas"]) == 2, sala["chave"]
        chaves = {p["chave"] for p in sala["portas"]}
        assert len(chaves) == 2, sala["chave"]   # as duas são diferentes
        for porta in sala["portas"]:
            assert porta["label"], sala["chave"]


def test_toda_sala_de_evento_tem_efeito_registrado_e_toda_de_achado_tambem():
    for sala in game_data.DUNGEON_POOL:
        if sala["tipo"] == "evento":
            assert sala["chave"] in dungeon.EFEITOS_EVENTO, sala["chave"]
        elif sala["tipo"] == "achado":
            assert sala["chave"] in dungeon.EFEITOS_ACHADO, sala["chave"]


def test_nome_antigo_que_entregava_a_armadilha_nao_existe_mais():
    """"Piso Instável" (fatia anterior) dizia o que a sala era antes de
    qualquer interação -- contra a própria regra deste cartão."""
    nomes = {s["nome"] for s in game_data.DUNGEON_POOL}
    assert "Piso Instável" not in nomes
    assert "piso_instavel" not in dungeon._POOL_POR_CHAVE


# ==================================================================
# Salão do Espelho Rachado -- olhar custa HP e revela a próxima sala;
# virar as costas não custa e não dá nada
# ==================================================================

def test_espelho_olhar_custa_hp_e_revela_o_nome_da_proxima_sala():
    j = _jogador(1)
    s = bot.stats(j)
    db.atualizar_jogador(1, hp=s["hp_max"])
    j = db.get_jogador(1)
    run = _run_iniciando_em("salao_do_espelho_rachado")
    sala = dungeon.sala_atual(run)
    proxima_nome = dungeon._POOL_POR_CHAVE[run["salas"][1]]["nome"]
    enviados = []

    async def enviar(*, embed, view=None):
        enviados.append(embed)

    asyncio.run(dungeon._evento_espelho(enviar, j, s, run, sala, 1, "olhar", []))

    dano_esperado = max(1, int(game_data.DUNGEON_EVENTO_CUSTO_HP_ESPELHO * s["hp_max"]))
    assert db.get_jogador(1)["hp"] == s["hp_max"] - dano_esperado
    assert proxima_nome in enviados[0].description


def test_espelho_virar_as_costas_nao_custa_nem_da_nada():
    j = _jogador(1)
    s = bot.stats(j)
    db.atualizar_jogador(1, hp=s["hp_max"])
    j = db.get_jogador(1)
    run = _run_iniciando_em("salao_do_espelho_rachado")
    sala = dungeon.sala_atual(run)

    async def enviar(*, embed, view=None):
        pass

    asyncio.run(dungeon._evento_espelho(enviar, j, s, run, sala, 1, "virar", []))

    assert db.get_jogador(1)["hp"] == s["hp_max"]
    assert db.get_inventario(1) == []


# ==================================================================
# Jardim Suspenso -- comer cura bem com risco de veneno; colher dá
# espólio pequeno e nenhuma cura
# ==================================================================

def test_jardim_comer_cura_e_pode_envenenar(monkeypatch):
    monkeypatch.setattr(dungeon.random, "random", lambda: 0.99)   # nunca envenena
    j = _jogador(1)
    s = bot.stats(j)
    db.atualizar_jogador(1, hp=1)
    j = db.get_jogador(1)
    run = _run_iniciando_em("jardim_suspenso")
    sala = dungeon.sala_atual(run)

    async def enviar(*, embed, view=None):
        pass

    asyncio.run(dungeon._evento_jardim(enviar, j, s, run, sala, 1, "comer", []))

    cura_esperada = max(1, int(game_data.DUNGEON_EVENTO_CURA_JARDIM_COMER * s["hp_max"]))
    assert db.get_jogador(1)["hp"] == min(s["hp_max"], 1 + cura_esperada)
    assert db.get_inventario(1) == []   # comer não dá espólio


def test_jardim_comer_pode_envenenar_e_tirar_parte_da_cura(monkeypatch):
    monkeypatch.setattr(dungeon.random, "random", lambda: 0.0)   # sempre envenena
    j = _jogador(1)
    s = bot.stats(j)
    db.atualizar_jogador(1, hp=1)
    j = db.get_jogador(1)
    run = _run_iniciando_em("jardim_suspenso")
    sala = dungeon.sala_atual(run)

    async def enviar(*, embed, view=None):
        pass

    asyncio.run(dungeon._evento_jardim(enviar, j, s, run, sala, 1, "comer", []))

    cura = max(1, int(game_data.DUNGEON_EVENTO_CURA_JARDIM_COMER * s["hp_max"]))
    veneno = max(1, int(game_data.DUNGEON_EVENTO_DANO_VENENO_JARDIM * s["hp_max"]))
    assert db.get_jogador(1)["hp"] == max(1, min(s["hp_max"], 1 + cura) - veneno)


def test_jardim_colher_da_espolio_pequeno_sem_curar():
    j = _jogador(1)
    s = bot.stats(j)
    db.atualizar_jogador(1, hp=1)
    j = db.get_jogador(1)
    run = _run_iniciando_em("jardim_suspenso")
    sala = dungeon.sala_atual(run)

    async def enviar(*, embed, view=None):
        pass

    asyncio.run(dungeon._evento_jardim(enviar, j, s, run, sala, 1, "colher", []))

    assert db.get_jogador(1)["hp"] == 1   # nenhuma cura
    itens = {i["item"] for i in db.get_inventario(1)}
    assert itens
    assert itens <= set(dungeon._ESPOLIOS_BAIXOS)


# ==================================================================
# Fonte Parada -- beber enche mana e deixa uma condição; lavar cura
# pouco e é seguro
# ==================================================================

def test_fonte_beber_enche_mana_e_deixa_uma_condicao_pendente():
    j = _jogador(1, inteligencia=20)
    s = bot.stats(j)
    db.atualizar_jogador(1, mana=0)
    j = db.get_jogador(1)
    run = _run_iniciando_em("fonte_parada")
    sala = dungeon.sala_atual(run)

    async def enviar(*, embed, view=None):
        pass

    asyncio.run(dungeon._evento_fonte(enviar, j, s, run, sala, 1, "beber", []))

    assert db.get_jogador(1)["mana"] == s["mana_max"]
    condicao = dungeon.obter_run(1)["condicao_armadilha"]
    assert condicao is not None
    assert condicao["tipo"] in {c["tipo"] for c in game_data.DUNGEON_CONDICOES_ARMADILHA}


def test_fonte_lavar_cura_pouco_e_e_seguro():
    j = _jogador(1)
    s = bot.stats(j)
    db.atualizar_jogador(1, hp=1, mana=0)
    j = db.get_jogador(1)
    run = _run_iniciando_em("fonte_parada")
    sala = dungeon.sala_atual(run)

    async def enviar(*, embed, view=None):
        pass

    asyncio.run(dungeon._evento_fonte(enviar, j, s, run, sala, 1, "lavar", []))

    cura_esperada = max(1, int(game_data.DUNGEON_EVENTO_CURA_FONTE_LAVAR * s["hp_max"]))
    assert db.get_jogador(1)["hp"] == min(s["hp_max"], 1 + cura_esperada)
    assert db.get_jogador(1)["mana"] == 0   # lavar não mexe em mana
    assert dungeon.obter_run(1)["condicao_armadilha"] is None   # seguro -- nenhuma condição


# ==================================================================
# Os três achados -- riscos diferentes (garantido médio / alta
# variância / garantido baixo)
# ==================================================================

def test_bau_esquecido_da_espolio_garantido_de_valor_medio():
    j = _jogador(1)
    s = bot.stats(j)
    run = _run_iniciando_em("bau_esquecido")
    sala = dungeon.sala_atual(run)

    async def enviar(*, embed, view=None):
        pass

    asyncio.run(dungeon._achado_bau_esquecido(enviar, j, s, run, sala, 1, []))

    itens = {i["item"] for i in db.get_inventario(1)}
    assert itens
    assert itens <= set(dungeon._ESPOLIOS_MEDIOS)


def test_estatua_de_maos_abertas_da_espolio_garantido_de_valor_baixo():
    j = _jogador(1)
    s = bot.stats(j)
    run = _run_iniciando_em("estatua_de_maos_abertas")
    sala = dungeon.sala_atual(run)

    async def enviar(*, embed, view=None):
        pass

    asyncio.run(dungeon._achado_estatua_de_maos_abertas(enviar, j, s, run, sala, 1, []))

    itens = {i["item"] for i in db.get_inventario(1)}
    assert itens <= set(dungeon._ESPOLIOS_BAIXOS)


def test_nicho_da_torre_pode_dar_o_pior_ou_o_melhor_da_run(monkeypatch):
    j = _jogador(1)
    s = bot.stats(j)
    run = _run_iniciando_em("nicho_da_torre")
    sala = dungeon.sala_atual(run)

    async def enviar(*, embed, view=None):
        pass

    monkeypatch.setattr(dungeon.random, "random", lambda: 0.0)   # sempre no lado "alto"
    asyncio.run(dungeon._achado_nicho_da_torre(enviar, j, s, run, sala, 1, []))
    itens_alto = {i["item"] for i in db.get_inventario(1)}
    assert itens_alto <= set(dungeon._ESPOLIOS_ALTOS)

    db.remove_item(1, next(iter(itens_alto)), 99)
    monkeypatch.setattr(dungeon.random, "random", lambda: 0.99)   # sempre no lado "baixo"
    asyncio.run(dungeon._achado_nicho_da_torre(enviar, j, s, run, sala, 1, []))
    itens_baixo = {i["item"] for i in db.get_inventario(1)} - itens_alto
    assert itens_baixo <= set(dungeon._ESPOLIOS_BAIXOS)


def test_as_tres_faixas_de_espolio_nao_se_sobrepoem():
    assert set(dungeon._ESPOLIOS_BAIXOS) & set(dungeon._ESPOLIOS_MEDIOS) == set()
    assert set(dungeon._ESPOLIOS_MEDIOS) & set(dungeon._ESPOLIOS_ALTOS) == set()
    assert set(dungeon._ESPOLIOS_BAIXOS) | set(dungeon._ESPOLIOS_MEDIOS) | set(dungeon._ESPOLIOS_ALTOS) == set(dungeon._ESPOLIOS)


# ==================================================================
# Fiação ponta a ponta -- o botão de verdade chama o efeito certo
# (mesma lacuna que o wiring de combate já tinha pego antes: uma
# unidade isolada não prova que o botão de verdade dispara ela)
# ==================================================================

def test_resolver_evento_apresenta_as_portas_certas_com_os_labels_do_pool():
    j = _jogador(1)
    run = _run_iniciando_em("fonte_parada")
    sala = dungeon.sala_atual(run)
    ctx = _ctx(1)

    asyncio.run(dungeon.resolver_sala_atual(ctx, j, run))

    view = ctx.send.call_args.kwargs["view"]
    assert isinstance(view, dungeon._ViewEscolhaEvento)
    rotulos = {item.label for item in view.children}
    assert rotulos == {p["label"] for p in sala["portas"]}
    assert dungeon.obter_run(1)["indice"] == run["indice"]   # não avançou -- espera o clique


def test_clicar_no_botao_do_evento_de_verdade_chama_o_efeito_e_avanca_a_sala():
    j = _jogador(1)
    s = bot.stats(j)
    db.atualizar_jogador(1, mana=0)
    j = db.get_jogador(1)
    run = _run_iniciando_em("fonte_parada")
    sala = dungeon.sala_atual(run)
    view = dungeon._ViewEscolhaEvento(1, j, s, run, sala, [])
    botao_beber = next(b for b in view.children if b.escolha == "beber")

    asyncio.run(botao_beber.callback(_interacao(1)))

    assert db.get_jogador(1)["mana"] == s["mana_max"]   # o efeito de "beber" rodou de verdade
    assert dungeon.obter_run(1)["indice"] == run["indice"] + 1   # a sala avançou


def test_clicar_no_botao_da_armadilha_de_verdade_chama_desarmar():
    j = _jogador(1)
    s = bot.stats(j)
    run = _run_iniciando_em("bau_esquecido")
    sala = dungeon.sala_atual(run)
    view = dungeon._ViewEscolhaArmadilha(1, j, s, run, sala, condicao=None)
    botao_desarmar = next(b for b in view.children if b.escolha == "desarmar")

    asyncio.run(botao_desarmar.callback(_interacao(1)))

    itens = {i["item"] for i in db.get_inventario(1)}
    assert itens & set(dungeon._ESPOLIOS)   # o mecanismo desarmado de verdade virou espólio
