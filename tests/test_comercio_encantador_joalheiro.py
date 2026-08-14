# tests/test_comercio_encantador_joalheiro.py
# Fluxos ponta-a-ponta do EncantadorView/JoalheiroView via interações fake --
# mesma estratégia de tests/test_comercio.py (discord.py não conecta de
# verdade sem subir o bot). Ver decisoes.md § Encantador e Joalheiro.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula comercio.H (comercio.instalar)
import comercio
import database as db
import npcs

ENCANTADOR = next(n for n in npcs.NPCS[1] if n["tipo"] == "encantador")   # Baldo, andar 1
JOALHEIRO = next(n for n in npcs.NPCS[2] if n["tipo"] == "joalheiro")     # Orin, andar 2


def _interacao(user_id, mensagem=None):
    it = MagicMock()
    it.user.id = user_id
    it.response = MagicMock()
    it.response.is_done.return_value = False
    it.response.send_message = AsyncMock()
    it.response.edit_message = AsyncMock()
    it.followup.send = AsyncMock()
    it.message = mensagem or MagicMock()
    it.message.embeds = [MagicMock()]
    it.message.edit = AsyncMock()
    return it


def _botao(view, label):
    return next(c for c in view.children if getattr(c, "label", None) == label)


def _jogador(moedas=10000, andar=1, andar_max=1, profissao=None, **campos):
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(
        1, moedas=moedas, andar=andar, andar_max=andar_max,
        profissao=profissao, prof_nivel=9, prof_xp=0, **campos,
    )
    return db.get_jogador(1)


def test_encantador_recusa_quem_nao_e_do_oficio():
    _jogador(profissao="forja", andar=1, arma="espada_ferro")
    view = comercio.EncantadorView(1, ENCANTADOR, 1, "elu")
    it = _interacao(1)
    asyncio.run(_botao(view, "Encantar").callback(it))
    it.response.send_message.assert_called_once()
    assert it.response.send_message.call_args.kwargs["ephemeral"] is True


def test_encantar_arma_via_botao_ponta_a_ponta():
    """Escolhe a peça (arma), depois o atributo (FOR) -- dois selects em
    sequência, mesmo padrão do fluxo de compra. No final a arma tem
    encantamento e o custo (moedas nível 9 = bônus 7 = 6800) foi cobrado."""
    _jogador(profissao="encantador", andar=1, arma="espada_ferro")
    db.add_item(1, "essencia_estelar", 3)   # nível 9 -> bônus 7 -> material do andar 9
    db.add_item(1, "eco_cristalizado", 1)
    view = comercio.EncantadorView(1, ENCANTADOR, 1, "elu")
    it = _interacao(1)

    async def cenario():
        await _botao(view, "Encantar").callback(it)
        sel_slot = it.response.edit_message.call_args.kwargs["view"].children[0]
        assert sel_slot.options[0].value == "arma"

        it2 = _interacao(1, mensagem=it.message)
        await sel_slot._ao_escolher(it2, "arma")
        sel_atributo = it2.response.edit_message.call_args.kwargs["view"].children[0]

        it3 = _interacao(1, mensagem=it2.message)
        await sel_atributo._ao_escolher(it3, "forca")
        return it3

    it3 = asyncio.run(cenario())
    j = db.get_jogador(1)
    assert j["moedas"] == 10000 - 6800   # nível 9 -> bônus 7 -> 6800
    instancia = db.get_instancia(j["arma_instancia_id"])
    assert instancia["encantamento_atributo"] == "forca"
    assert instancia["encantamento_valor"] == 7
    it3.message.edit.assert_called_once()   # painel principal restaurado


def test_desencantar_so_lista_peca_ja_encantada():
    j = _jogador(profissao="encantador", andar=1, arma="espada_ferro", armadura="couro")
    instancia_id = db.criar_instancia(1, "espada_ferro")
    db.definir_encantamento(instancia_id, "forca", 3)
    db.atualizar_jogador(1, arma_instancia_id=instancia_id)

    view = comercio.EncantadorView(1, ENCANTADOR, 1, "elu")
    it = _interacao(1)
    asyncio.run(_botao(view, "Desencantar").callback(it))
    opcoes = it.response.edit_message.call_args.kwargs["view"].children[0].options
    assert [o.value for o in opcoes] == ["arma"]   # armadura não está encantada, não aparece


def test_lapidar_anel_via_botao_cria_instancia_na_mochila():
    _jogador(profissao="joalheiro", andar=2)
    db.add_item(1, "perola_do_eco", 3)   # nível 9 -> bônus 7 -> material do andar 10
    db.add_item(1, "eco_cristalizado", 1)
    view = comercio.JoalheiroView(1, JOALHEIRO, 2, "elu")
    it = _interacao(1)

    async def cenario():
        await _botao(view, "Lapidar").callback(it)
        sel_tipo = it.response.edit_message.call_args.kwargs["view"].children[0]
        assert {o.value for o in sel_tipo.options} == {"anel", "colar"}

        it2 = _interacao(1, mensagem=it.message)
        await sel_tipo._ao_escolher(it2, "anel")
        sel_atributo = it2.response.edit_message.call_args.kwargs["view"].children[0]

        it3 = _interacao(1, mensagem=it2.message)
        await sel_atributo._ao_escolher(it3, "inteligencia")
        return it3

    asyncio.run(cenario())
    j = db.get_jogador(1)
    assert j["moedas"] == 10000 - 6800   # nível 9 -> bônus 7
    mochila = db.instancias_na_mochila(1)
    assert len(mochila) == 1
    instancia = mochila[0]
    assert instancia["item"] == "anel_joia"
    assert instancia["joia_atributo"] == "inteligencia"
    assert instancia["joia_valor"] == 7
