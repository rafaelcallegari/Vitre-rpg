# tests/test_dungeon_espolio.py
# Cartão "Exploração de Dungeon", commit 2: a tabela de espólio (~8 itens,
# faixas de valor) e o Instinto de Ladrão valendo dentro da dungeon. Ver
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
    padrao = dict(andar=9, nivel=15, classe="ladino", destreza=20)
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
# A tabela: ~8 itens, tipo próprio, não equipa nem crafta, faixas de valor
# ==================================================================

def _espolios():
    return {k: v for k, v in game_data.ITENS.items() if v.get("tipo") == "espolio"}


def test_tabela_de_espolio_tem_pelo_menos_oito_itens():
    assert len(_espolios()) >= 8


def test_espolio_nunca_e_chamado_de_material_nem_de_tesouro():
    """São dois tipos que JÁ existem no catálogo com significado próprio
    -- material entra em receita, tesouro é o item de andar do Salão da
    guilda. Espólio não pode ser confundido com nenhum dos dois."""
    for chave, dado in _espolios().items():
        assert dado["tipo"] not in ("material", "tesouro"), chave


def test_todo_espolio_e_vendavel_e_fora_da_loja():
    for chave, dado in _espolios().items():
        assert dado.get("vendavel", True) is True, chave   # não tem graça achar e não poder vender
        assert dado.get("loja", True) is False, chave       # não tem graça comprar de volta


def test_espolio_nao_tem_atributo_de_equipamento_nem_bonus_de_ataque_defesa():
    """Sem função nenhuma além de vender -- não equipa, não crafta."""
    for chave, dado in _espolios().items():
        assert "atk" not in dado, chave
        assert "def" not in dado, chave
        assert "atributo" not in dado, chave


def test_espolio_tem_faixas_de_valor_nao_um_preco_so():
    precos = sorted(dado["preco"] for dado in _espolios().values())
    assert precos[0] < precos[-1] // 2   # o mais barato é bem menos da metade do mais caro -- faixas de verdade
    assert len(set(precos)) >= 5   # não são todos parecidos


def test_dungeon_espolios_deriva_da_tabela_e_pega_todos():
    """`dungeon._ESPOLIOS` não é uma lista escrita à mão -- cresce
    sozinha quando a tabela cresce."""
    assert set(dungeon._ESPOLIOS) == set(_espolios())


# ==================================================================
# `rpg vender` -- espólio vende a preço CHEIO, igual material (não os
# 50% de equipamento usado)
# ==================================================================

def test_espolio_vende_a_preco_cheio_nao_pela_metade():
    _jogador(1, moedas=0)
    db.add_item(1, "mecanismo_retorcido")

    asyncio.run(bot.vender.callback(_ctx(1), argumento="mecanismo retorcido"))

    assert db.get_jogador(1)["moedas"] == game_data.ITENS["mecanismo_retorcido"]["preco"]


def test_todos_os_espolios_vendem_pelo_preco_de_tabela():
    _jogador(1, moedas=0)
    for chave, dado in _espolios().items():
        db.atualizar_jogador(1, moedas=0)
        db.add_item(1, chave)

        asyncio.run(bot.vender.callback(_ctx(1), argumento=dado["nome"]))

        assert db.get_jogador(1)["moedas"] == dado["preco"], chave


# ==================================================================
# Instinto de Ladrão vale dentro da dungeon (drops de combate)
# ==================================================================

def test_instinto_de_ladrao_aumenta_moedas_de_vitoria_na_dungeon(monkeypatch):
    _sempre_vitoria(monkeypatch)
    ladino = _jogador(1, classe="ladino", ascensao="assassino", destreza=20, moedas=0)
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))
    run = dungeon.obter_run(1)

    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), ladino, run))

    andar = game_data.ANDARES[9]
    moedas_possiveis_com_bonus = {
        m["moedas"] + int(m["moedas"] * game_data.PASSIVAS["instinto_ladino"]["valor_moedas"])
        for m in andar["monstros"]
    }
    assert db.get_jogador(1)["moedas"] in moedas_possiveis_com_bonus


def test_sem_instinto_de_ladrao_moedas_de_vitoria_sao_o_valor_cru_do_mob(monkeypatch):
    _sempre_vitoria(monkeypatch)
    guerreiro = _jogador(1, classe="guerreiro", forca=20, moedas=0)   # sem ascensão
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))
    run = dungeon.obter_run(1)

    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), guerreiro, run))

    andar = game_data.ANDARES[9]
    moedas_possiveis_sem_bonus = {m["moedas"] for m in andar["monstros"]}
    assert db.get_jogador(1)["moedas"] in moedas_possiveis_sem_bonus
