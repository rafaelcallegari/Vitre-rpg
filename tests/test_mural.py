# tests/test_mural.py
# A Praça, commit 2: o mural. Oferta assíncrona -- publica e vai embora,
# outro aceita horas depois, sem precisar dos dois online juntos. Publicar
# É reservar (o item sai do inventário/solta a instância na hora de
# publicar, não na hora de aceitar); cancelar devolve inteiro; dois
# aceites simultâneos só entregam pra um. Ver decisoes.md § A Praça.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import database as db
import mundo
import mural
import trocas


def _jogador(user_id=1, mundo_atual=None, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if mundo_atual is not None:
        campos["mundo"] = mundo_atual
    if campos:
        db.atualizar_jogador(user_id, **campos)
    return db.get_jogador(user_id)


def _na_praca(user_id=1, **campos):
    return _jogador(user_id, mundo_atual=mundo.PRACA, andar=campos.pop("andar", 5), andar_max=campos.pop("andar_max", 5), **campos)


def _ctx(user_id=1):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    return ctx


def _msg(ctx):
    return ctx.send.call_args.args[0] if ctx.send.call_args.args else ctx.send.call_args.kwargs.get("content", "")


def _mural(ctx, argumento=""):
    asyncio.run(bot.bot.get_command("mural").callback(ctx, argumento=argumento))


# ==================================================================
# só funciona na Praça
# ==================================================================

def test_mural_fora_da_praca_e_recusado():
    _jogador(1, andar=3, andar_max=5)
    ctx = _ctx(1)
    _mural(ctx)
    assert "praça" in _msg(ctx).lower()


def test_mural_vazio_mostra_mensagem_padrao():
    _na_praca(1)
    ctx = _ctx(1)
    _mural(ctx)
    embed = ctx.send.call_args.kwargs["embed"]
    assert "nenhuma oferta" in embed.description.lower()


# ==================================================================
# publicar reserva na hora -- sai do inventário, não na hora de aceitar
# ==================================================================

def test_publicar_tira_item_do_inventario_na_hora():
    j = _na_praca(1)
    db.add_item(1, "presa_javali", 5)
    ctx = _ctx(1)
    _mural(ctx, "oferecer presa de javali 3 100")
    assert db.qtd_item(1, "presa_javali") == 2   # 5 - 3, sumiu na publicação
    assert db.get_jogador(1)["moedas"] == j["moedas"]   # nada cobrado ainda

    ctx2 = _ctx(1)
    _mural(ctx2)
    embed = ctx2.send.call_args.kwargs["embed"]
    assert "presa" in embed.description.lower()
    assert "100" in embed.description


def test_publicar_sem_item_suficiente_e_recusado():
    _na_praca(1)
    db.add_item(1, "presa_javali", 2)
    ctx = _ctx(1)
    _mural(ctx, "oferecer presa de javali 5 100")
    assert db.qtd_item(1, "presa_javali") == 2   # nada mexido
    assert "só tem" in _msg(ctx).lower()


def test_publicar_item_nao_vendavel_e_recusado():
    _na_praca(1)
    db.add_item(1, "coroa_velha", 1)
    ctx = _ctx(1)
    _mural(ctx, "oferecer coroa velha 1 100")
    assert "intransferível" in _msg(ctx).lower()
    assert db.tem_item(1, "coroa_velha", 1)   # continua com o jogador


def test_publicar_com_instancia_solta_o_dono_sem_perder_a_mochila_comum():
    """Cópia comum tem prioridade -- só cai pra instância quando não tem
    cópia comum o bastante (mesma regra de `bot.vender`)."""
    _na_praca(1)
    instancia_id = db.criar_instancia(1, "lamina_selo", nivel_melhoria=3)
    db.definir_encantamento(instancia_id, "forca", 7)
    ctx = _ctx(1)
    _mural(ctx, "oferecer lamina_selo 1 500")
    assert db.get_instancia(instancia_id)["dono"] is None   # solta, não deletada
    assert instancia_id not in [i["id"] for i in db.instancias_na_mochila(1)]
    assert db.get_instancia(instancia_id)["nivel_melhoria"] == 3   # intacta


# ==================================================================
# cancelar -- devolve inteiro, só o autor
# ==================================================================

def test_cancelar_devolve_item_comum():
    j = _na_praca(1)
    db.add_item(1, "presa_javali", 5)
    ctx = _ctx(1)
    _mural(ctx, "oferecer presa de javali 3 100")

    ctx2 = _ctx(1)
    _mural(ctx2, "cancelar 1")
    assert db.qtd_item(1, "presa_javali") == 5   # voltou tudo
    assert db.get_jogador(1)["moedas"] == j["moedas"]


def test_cancelar_com_instancia_devolve_com_melhoria_e_encantamento_intactos():
    _na_praca(1)
    instancia_id = db.criar_instancia(1, "lamina_selo", nivel_melhoria=3)
    db.definir_encantamento(instancia_id, "forca", 7)
    ctx = _ctx(1)
    _mural(ctx, "oferecer lamina_selo 1 500")

    ctx2 = _ctx(1)
    _mural(ctx2, "cancelar 1")

    instancia = db.get_instancia(instancia_id)
    assert instancia["dono"] == 1
    assert instancia["nivel_melhoria"] == 3
    assert instancia["encantamento_atributo"] == "forca"
    assert instancia["encantamento_valor"] == 7
    assert instancia_id in [i["id"] for i in db.instancias_na_mochila(1)]


def test_cancelar_oferta_de_outro_jogador_e_recusado():
    _na_praca(1)
    db.add_item(1, "presa_javali", 5)
    ctx = _ctx(1)
    _mural(ctx, "oferecer presa de javali 3 100")

    _na_praca(2)
    ctx2 = _ctx(2)
    _mural(ctx2, "cancelar 1")
    assert "não tem uma oferta" in _msg(ctx2).lower()
    assert db.qtd_item(1, "presa_javali") == 2   # continua reservado -- não voltou


# ==================================================================
# aceitar -- paga moedas, entrega o item, remove a oferta
# ==================================================================

def test_aceitar_paga_moedas_e_entrega_o_item():
    autor = _na_praca(1, moedas=0)
    db.add_item(1, "presa_javali", 5)
    ctx = _ctx(1)
    _mural(ctx, "oferecer presa de javali 3 100")

    comprador = _na_praca(2, moedas=1000)
    ctx2 = _ctx(2)
    _mural(ctx2, "aceitar 1")

    assert db.get_jogador(1)["moedas"] == autor["moedas"] + 100
    assert db.get_jogador(2)["moedas"] == comprador["moedas"] - 100
    assert db.tem_item(2, "presa_javali", 3)
    assert db.qtd_item(1, "presa_javali") == 2   # 5 - 3, os 3 vendidos já tinham saído na publicação


def test_aceitar_com_instancia_entrega_intacta():
    _na_praca(1)
    instancia_id = db.criar_instancia(1, "lamina_selo", nivel_melhoria=3)
    db.definir_encantamento(instancia_id, "forca", 7)
    ctx = _ctx(1)
    _mural(ctx, "oferecer lamina_selo 1 500")

    _na_praca(2, moedas=1000)
    ctx2 = _ctx(2)
    _mural(ctx2, "aceitar 1")

    instancia = db.get_instancia(instancia_id)
    assert instancia["dono"] == 2
    assert instancia["nivel_melhoria"] == 3
    assert instancia["encantamento_atributo"] == "forca"
    assert instancia_id in [i["id"] for i in db.instancias_na_mochila(2)]


def test_aceitar_a_propria_oferta_e_recusado():
    _na_praca(1, moedas=1000)
    db.add_item(1, "presa_javali", 5)
    ctx = _ctx(1)
    _mural(ctx, "oferecer presa de javali 3 100")

    ctx2 = _ctx(1)
    _mural(ctx2, "aceitar 1")
    assert "própria oferta" in _msg(ctx2).lower()


def test_aceitar_sem_moedas_suficientes_e_recusado():
    _na_praca(1)
    db.add_item(1, "presa_javali", 5)
    ctx = _ctx(1)
    _mural(ctx, "oferecer presa de javali 3 100")

    _na_praca(2, moedas=10)
    ctx2 = _ctx(2)
    _mural(ctx2, "aceitar 1")
    assert "faltam" in _msg(ctx2).lower()
    assert not db.tem_item(2, "presa_javali", 1)


# ==================================================================
# dois aceites simultâneos -- só um leva
# ==================================================================

def test_dois_aceites_simultaneos_so_um_leva_o_outro_recebe_recusa_clara():
    _na_praca(1)
    db.add_item(1, "presa_javali", 5)
    ctx = _ctx(1)
    _mural(ctx, "oferecer presa de javali 3 100")

    _na_praca(2, moedas=1000)
    _na_praca(3, moedas=1000)

    # sem await no meio -- simula os dois clicando ao mesmo tempo, o
    # segundo bate numa linha que o primeiro já apagou.
    sucesso1, resultado1 = db.aceitar_oferta_mural(1, 2)
    sucesso2, resultado2 = db.aceitar_oferta_mural(1, 3)

    assert sucesso1 is True
    assert sucesso2 is False
    assert "já deve ter levado" in resultado2.lower()
    assert db.tem_item(2, "presa_javali", 3)
    assert not db.tem_item(3, "presa_javali", 1)
    assert db.get_jogador(3)["moedas"] == 1000   # segundo nunca foi cobrado


# ==================================================================
# oferta sobrevive a restart -- é tabela, não estado em memória
# ==================================================================

def test_oferta_sobrevive_a_uma_leitura_nova_do_banco():
    _na_praca(1)
    db.add_item(1, "presa_javali", 5)
    ctx = _ctx(1)
    _mural(ctx, "oferecer presa de javali 3 100")

    ofertas = db.ofertas_mural_abertas()   # leitura nova e independente -- o mesmo que um restart produziria
    assert len(ofertas) == 1
    assert ofertas[0]["item"] == "presa_javali"
    assert ofertas[0]["preco"] == 100


# ==================================================================
# limite de anúncios por jogador
# ==================================================================

def test_limite_de_ofertas_por_jogador():
    _na_praca(1, moedas=0)
    for item in ("presa_javali", "seda_sussurrante", "osso_enferrujado", "cristal_de_sal", "nucleo_gelado"):
        db.add_item(1, item, 1)
    ctx = _ctx(1)
    for item in ("presa de javali", "seda sussurrante", "osso enferrujado", "cristal de sal", "nucleo gelado"):
        _mural(ctx, f"oferecer {item} 1 10")
    assert db.contar_ofertas_mural(1) == mural.MAX_OFERTAS_POR_JOGADOR

    db.add_item(1, "minerio_negro", 1)
    ctx2 = _ctx(1)
    _mural(ctx2, "oferecer minerio negro 1 10")
    assert "máximo de" in _msg(ctx2).lower()
    assert db.contar_ofertas_mural(1) == mural.MAX_OFERTAS_POR_JOGADOR   # não passou
    assert db.tem_item(1, "minerio_negro", 1)   # não foi reservado


# ==================================================================
# rpg trade entre dois na Praça -- trocas.py ganhou um segundo caso
# ==================================================================

def test_trade_funciona_entre_dois_na_praca_com_andares_diferentes():
    """Achado ao implementar este commit: `rpg trade` só comparava
    `andar`, sem checar `mundo` -- dois jogadores na Praça vindos de
    andares diferentes (nunca vão bater em `andar`) não conseguiam
    trocar, mesmo estando fisicamente juntos. Corrigido em trocas.py."""
    trocas.TROCAS_ATIVAS.clear()   # trocas.py guarda estado em memória, não no banco -- outro teste pode ter deixado 1/2 "presos"
    _na_praca(1, andar=3, andar_max=3)
    _na_praca(2, andar=9, andar_max=9)
    ctx = _ctx(1)
    ctx.message = MagicMock()
    membro = MagicMock()
    membro.id = 2
    membro.bot = False
    membro.display_name = "Jogador2"
    ctx.message.mentions = [membro]
    asyncio.run(bot.bot.get_command("trade").callback(ctx))
    ctx.send.assert_awaited_once()
    # não caiu na recusa de presença -- a troca abriu de verdade (embed +
    # view, não uma mensagem de texto de recusa)
    assert "embed" in ctx.send.call_args.kwargs
    assert "view" in ctx.send.call_args.kwargs


def test_trade_continua_recusando_andares_diferentes_dentro_da_torre_regressao():
    trocas.TROCAS_ATIVAS.clear()
    _jogador(1, andar=1, andar_max=5)
    _jogador(2, andar=3, andar_max=5)
    ctx = _ctx(1)
    ctx.message = MagicMock()
    membro = MagicMock()
    membro.id = 2
    membro.bot = False
    membro.display_name = "Jogador2"
    ctx.message.mentions = [membro]
    asyncio.run(bot.bot.get_command("trade").callback(ctx))
    assert "juntos" in _msg(ctx).lower()


# ==================================================================
# regressão -- quem nunca vai à Praça não sente nada
# ==================================================================

def test_regressao_quem_nunca_visita_a_praca_nao_sente_nada():
    _jogador(1, andar=1, andar_max=5, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino=3))
    depois = db.get_jogador(1)
    assert depois["andar"] == 3
    assert depois["mundo"] == "torre"
