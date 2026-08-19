# tests/test_classe_profissao_wiki.py
# `rpg classe` e `rpg profissao` deixaram de escolher (isso migrou pro
# despertar, ver test_despertar.py) e viraram wiki: mostram o que o jogador
# já tem, lendo de game_data.py/profissoes.py -- nunca de texto solto no
# comando, senão desatualiza sozinho na primeira mudança de balanceamento.
# A troca de ofício (`rpg profissao trocar`) continua morando em
# `rpg profissao`, por decisão anterior. Ver decisoes.md § despertar.
import asyncio

import bot
import database as db
import game_data
import profissoes


def _ctx(user_id=1, display_name="Alice"):
    from unittest.mock import AsyncMock, MagicMock
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.author.display_name = display_name
    ctx.send = AsyncMock()
    return ctx


def _comando_profissao():
    return bot.bot.get_command("profissao")


# ---------------- rpg classe ----------------
def test_classe_sem_argumento_mostra_a_classe_do_jogador_sem_alterar_banco():
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, classe="guerreiro", profissao="forja", pronome="ele")
    antes = db.get_jogador(1)
    ctx = _ctx()

    asyncio.run(bot.classe_cmd.callback(ctx))

    depois = db.get_jogador(1)
    assert dict(depois) == dict(antes)
    e = ctx.send.call_args.kwargs["embed"]
    assert "Guerreiro" in e.title


def test_classe_com_argumento_mostra_a_classe_pedida_sem_escolher_nada():
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, classe="guerreiro", profissao="forja", pronome="ele")
    ctx = _ctx()

    asyncio.run(bot.classe_cmd.callback(ctx, argumento="mago"))

    e = ctx.send.call_args.kwargs["embed"]
    assert "Mago" in e.title
    j = db.get_jogador(1)
    assert j["classe"] == "guerreiro"   # olhar pro mago não muda a classe travada


def test_classe_sem_classe_aponta_pro_despertar_em_vez_de_menu_de_escolha():
    db.criar_jogador(1, "Alice")   # sem classe -- simula jogador pós-reset de temporada
    ctx = _ctx()

    asyncio.run(bot.classe_cmd.callback(ctx))

    assert ctx.send.call_args.kwargs.get("embed") is None
    texto = ctx.send.call_args.args[0]
    assert "rpg comecar" in texto


def test_classe_nao_aceita_mais_escolher_pelo_argumento():
    """Antes, `rpg classe mago` travava a escolha se o jogador ainda não
    tivesse classe. Agora só mostra a wiki -- escolher só acontece no
    despertar."""
    db.criar_jogador(1, "Alice")   # sem classe
    ctx = _ctx()

    asyncio.run(bot.classe_cmd.callback(ctx, argumento="mago"))

    j = db.get_jogador(1)
    assert j["classe"] is None
    e = ctx.send.call_args.kwargs["embed"]
    assert "Mago" in e.title   # mostrou a wiki, não travou a escolha


def test_classe_wiki_reflete_a_constante_do_jogo(monkeypatch):
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, classe="guerreiro", pronome="ele")
    ctx = _ctx()
    monkeypatch.setitem(game_data.HABILIDADES["golpe_aberto"], "desc", "TEXTO_DE_TESTE_UNICO")
    monkeypatch.setitem(game_data.HABILIDADES["golpe_aberto"], "custo", 999)

    asyncio.run(bot.classe_cmd.callback(ctx))

    e = ctx.send.call_args.kwargs["embed"]
    campo = next(f for f in e.fields if "Golpe Aberto" in f.name)
    assert campo.value == "TEXTO_DE_TESTE_UNICO"
    assert "999" in campo.name


def test_classe_wiki_lista_os_ramos_de_ascensao_da_classe():
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, classe="mago", pronome="ele")
    ctx = _ctx()

    asyncio.run(bot.classe_cmd.callback(ctx))

    e = ctx.send.call_args.kwargs["embed"]
    campo_ascensao = next(f for f in e.fields if "Ascens" in f.name)
    for ramo in ("Mago de Gelo", "Mago de Fogo", "Mago de Raio"):
        assert ramo in campo_ascensao.value
    assert "Soldado" not in campo_ascensao.value   # ramo do guerreiro, não do mago


def test_classe_wiki_falta_1_nivel_fica_no_singular():
    """O tipo de coisa que some numa refatoração de string: nível 15 - 14 é
    diferença 1, e o texto tem que sair "falta 1 nível", nunca "faltam 1"."""
    nivel_ascensao = game_data.ASCENSOES["mago_gelo"]["nivel"]
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, classe="mago", pronome="ele", nivel=nivel_ascensao - 1)
    ctx = _ctx()

    asyncio.run(bot.classe_cmd.callback(ctx))

    e = ctx.send.call_args.kwargs["embed"]
    campo_ascensao = next(f for f in e.fields if "Ascens" in f.name)
    assert "falta 1 nível" in campo_ascensao.value
    assert "faltam 1" not in campo_ascensao.value


def test_classe_wiki_faltam_n_niveis_conferido_contra_o_dado():
    nivel_ascensao = game_data.ASCENSOES["mago_gelo"]["nivel"]
    nivel_jogador = nivel_ascensao - 6
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, classe="mago", pronome="ele", nivel=nivel_jogador)
    ctx = _ctx()

    asyncio.run(bot.classe_cmd.callback(ctx))

    e = ctx.send.call_args.kwargs["embed"]
    campo_ascensao = next(f for f in e.fields if "Ascens" in f.name)
    assert f"faltam {nivel_ascensao - nivel_jogador} níveis" in campo_ascensao.value


def test_classe_wiki_nivel_do_ramo_vem_do_dado_nao_de_texto_fixo(monkeypatch):
    """Trocar o "nivel" de um único ramo em game_data tem que mudar a wiki
    sem editar bot.py -- é o critério 6 do cartão da ascensão."""
    monkeypatch.setitem(game_data.ASCENSOES["mago_raio"], "nivel", 30)
    nivel_ordinario = game_data.ASCENSOES["mago_gelo"]["nivel"]
    nivel_jogador = nivel_ordinario - 5   # abaixo do ramo comum, bem abaixo do 30
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, classe="mago", pronome="ele", nivel=nivel_jogador)
    ctx = _ctx()

    asyncio.run(bot.classe_cmd.callback(ctx))

    e = ctx.send.call_args.kwargs["embed"]
    campo_ascensao = next(f for f in e.fields if "Ascens" in f.name)
    # título perde o nível único (ramos da base já não abrem todos juntos)
    assert "nível" not in campo_ascensao.name.lower()
    # cada ramo passa a listar o próprio nível
    assert "Mago de Raio — nível 30" in campo_ascensao.value
    assert f"Mago de Gelo — nível {nivel_ordinario}" in campo_ascensao.value
    # distância aponta pro ramo mais próximo (o nível ordinário, não o 30)
    assert f"faltam {nivel_ordinario - nivel_jogador} níveis" in campo_ascensao.value


def test_ascencao_sem_personagem_nao_quebra():
    ctx = _ctx()   # sem db.criar_jogador -- simula quem nunca deu `rpg comecar`

    asyncio.run(bot.ascencao.callback(ctx))

    e = ctx.send.call_args.kwargs["embed"]
    assert "rpg comecar" in e.footer.text


def test_ascencao_so_marca_base_quando_a_descricao_promete(monkeypatch):
    """Se a descrição promete marca (níveis divergem em algum lugar entre os
    12 ramos), pelo menos uma base tem que sair marcada -- e tem que ser a
    base cujos ramos não batem com o nível das demais. Sem esse teste, a
    marca podia usar só divergência interna à base (que nunca acontece hoje)
    e a descrição prometeria uma marca que a tela nunca mostra."""
    for chave in ("mago_gelo", "mago_fogo", "mago_raio"):
        monkeypatch.setitem(game_data.ASCENSOES[chave], "nivel", 12)
    ctx = _ctx()

    asyncio.run(bot.ascencao.callback(ctx))

    e = ctx.send.call_args.kwargs["embed"]
    assert "bases marcadas abaixo" in e.description
    campo_mago = next(f for f in e.fields if "Mago" in f.name)
    assert "divergem" in campo_mago.name
    campo_guerreiro = next(f for f in e.fields if "Guerreiro" in f.name)
    assert "divergem" not in campo_guerreiro.name


# ---------------- rpg profissao ----------------
def test_profissao_sem_argumento_mostra_a_ficha_sem_alterar_banco():
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, profissao="forja", prof_nivel=1, prof_xp=0, pronome="ele")
    antes = db.get_jogador(1)
    ctx = _ctx()

    asyncio.run(_comando_profissao().callback(ctx))

    depois = db.get_jogador(1)
    assert dict(depois) == dict(antes)
    e = ctx.send.call_args.kwargs["embed"]
    assert "nível 1" in e.title


def test_profissao_sem_oficio_aponta_pro_despertar():
    db.criar_jogador(1, "Alice")   # sem ofício -- simula jogador pós-reset de temporada
    ctx = _ctx()

    asyncio.run(_comando_profissao().callback(ctx))

    texto = ctx.send.call_args.args[0]
    assert "rpg comecar" in texto


def test_profissao_nao_aceita_mais_escolher_pelo_argumento():
    db.criar_jogador(1, "Alice")   # sem ofício
    ctx = _ctx()

    asyncio.run(_comando_profissao().callback(ctx, argumento="forja"))

    j = db.get_jogador(1)
    assert j["profissao"] is None
    texto = ctx.send.call_args.args[0]
    assert "rpg comecar" in texto


def test_profissao_troca_continua_funcionando_pelo_rpg_profissao():
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(
        1, profissao="forja", prof_nivel=5, prof_xp=300, moedas=profissoes.CUSTO_TROCA + 100,
        pronome="ele",
    )
    ctx = _ctx()

    asyncio.run(_comando_profissao().callback(ctx, argumento="trocar alquimia"))

    j = db.get_jogador(1)
    assert j["profissao"] == "alquimia"
    assert j["prof_nivel"] == 1
    assert j["prof_xp"] == 0
    assert j["moedas"] == 100
