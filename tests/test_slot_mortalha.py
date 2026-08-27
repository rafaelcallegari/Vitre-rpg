# tests/test_slot_mortalha.py
# Quinto slot de equipamento -- mortalha. Só infraestrutura: nenhuma peça de
# mortalha existe em game_data.ITENS ainda (a peça vem no cartão seguinte),
# então os testes usam itens sintéticos de tipo "mortalha", injetados via
# monkeypatch.setitem em game_data.ITENS (o mesmo dict que bot.py importa
# com `from game_data import ITENS` -- é o mesmo objeto, a mutação aparece
# nos dois lugares). Ver decisoes.md § Slot de mortalha.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import atributos as at
import bot
import database as db
import game_data
import trocas

MORTALHA_A = "mortalha_teste_a"
MORTALHA_B = "mortalha_teste_b"


def _registrar_mortalhas_sinteticas(monkeypatch, andar_min_a=1):
    monkeypatch.setitem(
        game_data.ITENS, MORTALHA_A,
        {"nome": "Mortalha de Teste A", "emoji": "🥻", "tipo": "mortalha", "def": 10, "andar_min": andar_min_a},
    )
    monkeypatch.setitem(
        game_data.ITENS, MORTALHA_B,
        {"nome": "Mortalha de Teste B", "emoji": "🥻", "tipo": "mortalha", "def": 4, "andar_min": 1},
    )


def _jogador(user_id=1, **campos):
    db.criar_jogador(user_id, "Alice")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    return db.get_jogador(user_id)


def _ctx(user_id=1):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    ctx.defer = AsyncMock()   # só `rpg perfil` (híbrido) precisa, os outros ignoram
    return ctx


def _embed_enviado(ctx):
    return ctx.send.call_args.kwargs.get("embed") or ctx.send.call_args.args[0]


# ---------------------------------------------------------------- equipar
def test_equipar_mortalha_ocupa_o_slot(monkeypatch):
    _registrar_mortalhas_sinteticas(monkeypatch)
    _jogador(andar_max=1)
    db.add_item(1, MORTALHA_A, 1)

    asyncio.run(bot.equipar.callback(_ctx(), texto=MORTALHA_A))

    assert db.get_jogador(1)["mortalha"] == MORTALHA_A
    assert not db.tem_item(1, MORTALHA_A, 1)   # saiu da mochila pro slot


def test_equipar_mortalha_desequipa_a_anterior(monkeypatch):
    _registrar_mortalhas_sinteticas(monkeypatch)
    _jogador(andar_max=1)
    db.add_item(1, MORTALHA_A, 1)
    db.add_item(1, MORTALHA_B, 1)
    asyncio.run(bot.equipar.callback(_ctx(), texto=MORTALHA_A))

    asyncio.run(bot.equipar.callback(_ctx(), texto=MORTALHA_B))

    assert db.get_jogador(1)["mortalha"] == MORTALHA_B
    assert db.tem_item(1, MORTALHA_A, 1)        # a anterior voltou pra mochila
    assert not db.tem_item(1, MORTALHA_B, 1)    # a nova saiu dela


def test_equipar_mortalha_de_andar_nao_destrancado_e_recusado(monkeypatch):
    _registrar_mortalhas_sinteticas(monkeypatch, andar_min_a=5)
    _jogador(andar_max=1)
    db.add_item(1, MORTALHA_A, 1)

    ctx = _ctx()
    asyncio.run(bot.equipar.callback(ctx, texto=MORTALHA_A))

    assert db.get_jogador(1)["mortalha"] is None
    assert db.tem_item(1, MORTALHA_A, 1)   # continua guardada na mochila
    assert "andar 5" in ctx.send.call_args.args[0]


# ---------------------------------------------------------------- defesa
def test_defesa_da_mortalha_entra_no_total_e_na_curva_percentual(monkeypatch):
    _registrar_mortalhas_sinteticas(monkeypatch)
    sem = bot.stats(_jogador(andar_max=1))

    com = bot.stats(_jogador(mortalha=MORTALHA_A))   # def 10, sem armadura

    assert com["def"] == sem["def"] + 10
    assert com["def"] == at.defesa(10)
    assert com["reducao"] == at.reducao_dano(at.defesa(10))
    assert com["reducao"] > sem["reducao"]


def test_defesa_da_mortalha_soma_com_a_da_armadura(monkeypatch):
    _registrar_mortalhas_sinteticas(monkeypatch)
    j = _jogador(andar_max=1, armadura="couro", mortalha=MORTALHA_A)   # couro def=5, mortalha def=10
    s = bot.stats(j)
    assert s["def"] == at.defesa(5 + 10)
    assert s["reducao"] == at.reducao_dano(at.defesa(15))


# ---------------------------------------------------------------- trade
def test_mortalha_equipada_nao_entra_em_troca(monkeypatch):
    _registrar_mortalhas_sinteticas(monkeypatch)
    db.criar_jogador(1, "Alice")
    db.criar_jogador(2, "Bob")
    db.atualizar_jogador(1, andar=1)
    db.atualizar_jogador(2, andar=1)
    instancia_id = db.criar_instancia(1, MORTALHA_A)
    db.atualizar_jogador(1, mortalha=MORTALHA_A, mortalha_instancia_id=instancia_id)

    troca = trocas.Troca(1, 2, andar=1)
    troca.ofertas[1] = {"itens": {}, "instancias": {MORTALHA_A: instancia_id}, "moedas": 0}
    troca.ofertas[2] = {"itens": {}, "instancias": {}, "moedas": 0}

    sucesso, motivo = trocas._commitar_troca(troca)

    assert sucesso is False
    assert isinstance(motivo, str) and motivo
    assert db.get_instancia(instancia_id)["dono"] == 1   # nada moveu


def test_mortalha_desequipada_entra_em_troca_normalmente(monkeypatch):
    _registrar_mortalhas_sinteticas(monkeypatch)
    db.criar_jogador(1, "Alice")
    db.criar_jogador(2, "Bob")
    db.atualizar_jogador(1, andar=1)
    db.atualizar_jogador(2, andar=1)
    instancia_id = db.criar_instancia(1, MORTALHA_A)
    # nunca equipada (mortalha/mortalha_instancia_id continuam None) -- "na
    # mochila" é estado derivado, ver database.py § instâncias de item.

    troca = trocas.Troca(1, 2, andar=1)
    troca.ofertas[1] = {"itens": {}, "instancias": {MORTALHA_A: instancia_id}, "moedas": 0}
    troca.ofertas[2] = {"itens": {}, "instancias": {}, "moedas": 0}

    sucesso, motivo = trocas._commitar_troca(troca)

    assert (sucesso, motivo) == (True, None)
    assert db.get_instancia(instancia_id)["dono"] == 2


# ---------------------------------------------------------------- perfil/inventário
def test_perfil_mostra_slot_de_mortalha_vazio():
    _jogador(andar_max=1)
    ctx = _ctx()

    asyncio.run(bot.perfil.callback(ctx))

    campo = next(f for f in _embed_enviado(ctx).fields if f.name == "Equipado")
    assert "🥻 —" in campo.value


def test_perfil_mostra_slot_de_mortalha_cheio(monkeypatch):
    _registrar_mortalhas_sinteticas(monkeypatch)
    _jogador(andar_max=1, mortalha=MORTALHA_A)
    ctx = _ctx()

    asyncio.run(bot.perfil.callback(ctx))

    campo = next(f for f in _embed_enviado(ctx).fields if f.name == "Equipado")
    assert "🥻 Mortalha de Teste A" in campo.value


def test_status_mostra_slot_de_mortalha_vazio_e_cheio(monkeypatch):
    """`rpg status` (texto_equipamento) é a outra tela que mostra
    equipamento -- mesma checagem que `rpg perfil`, formato de linha
    diferente (com o bônus resolvido, não só o nome)."""
    _registrar_mortalhas_sinteticas(monkeypatch)
    vazio = bot.texto_equipamento(bot.stats(_jogador(andar_max=1)))
    assert "🥻 Mortalha: *vazio*" in vazio

    cheio = bot.texto_equipamento(bot.stats(_jogador(mortalha=MORTALHA_A)))
    assert "Mortalha de Teste A" in cheio and "+10 DEF" in cheio


def test_inventario_mostra_mortalha_desequipada_na_mochila(monkeypatch):
    _registrar_mortalhas_sinteticas(monkeypatch)
    _jogador(andar_max=1)
    db.add_item(1, MORTALHA_A, 1)
    ctx = _ctx()

    asyncio.run(bot.inventario.callback(ctx))

    embed = _embed_enviado(ctx)
    assert any(f.name == "🥻 Mortalha de Teste A" and f.value == "x1" for f in embed.fields)


# ---------------------------------------------------------------- regressão dos outros 4 slots
def test_os_outros_quatro_slots_continuam_funcionando():
    j = _jogador(
        andar_max=1, arma="espada_ferro", armadura="couro",
        anel="anel_forca", colar="colar_inteligencia",
    )
    s = bot.stats(j)

    assert s["equipamento"]["arma"][0] == "espada_ferro"
    assert s["equipamento"]["armadura"][0] == "couro"
    assert s["equipamento"]["anel"][0] == "anel_forca"
    assert s["equipamento"]["colar"][0] == "colar_inteligencia"
    assert s["equipamento"]["mortalha"] is None
    assert s["def"] == at.defesa(5)   # só a armadura -- mortalha vazia não soma nada
