# tests/test_mortalha_luz_sombra.py
# «Mortalha de Luz»/«Mortalha de Sombra»: forja com a Selen (ignora ofício),
# e a skill de equipamento (uma vez por luta, sem gastar recurso nem a
# rodada). Ver decisoes.md § Mortalha de Luz/Sombra.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula combate.H/profissoes.H/comercio.H via instalar()
import combate
import database as db
import game_data
import trocas

PECAS_MORTALHA = ("molde_do_manto", "fio_do_manto", "forro_do_manto", "fecho_do_manto")
CHEFE_TESTE = {"nome": "Testinho", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0}


def _jogador(user_id=1, **campos):
    db.criar_jogador(user_id, "Alice")
    if campos:
        db.atualizar_jogador(user_id, **campos)
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
    it.response.is_done.return_value = True   # já deferiu antes de chamar responder()
    it.response.send_message = AsyncMock()
    it.edit_original_response = AsyncMock()
    return it


def _dar_pecas(user_id):
    for p in PECAS_MORTALHA:
        db.add_item(user_id, p, 1)


def _combatente(user_id, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


def _forjar(ctx_user_id, elemento):
    ctx = _ctx(ctx_user_id)
    asyncio.run(bot.bot.get_command("forjarmortalha").callback(ctx, escolha=elemento))
    return ctx


# ---------------------------------------------------------------- forja
def test_forjar_com_as_quatro_pecas_consome_e_entrega_a_escolhida():
    _jogador(andar=9)
    _dar_pecas(1)

    _forjar(1, "luz")

    assert db.tem_item(1, "mortalha_luz", 1)
    for peca in PECAS_MORTALHA:
        assert not db.tem_item(1, peca, 1)


def test_forjar_sem_alguma_peca_nao_consome_nada():
    _jogador(andar=9)
    db.add_item(1, "molde_do_manto", 1)
    db.add_item(1, "fio_do_manto", 1)
    db.add_item(1, "forro_do_manto", 1)   # falta o fecho

    _forjar(1, "luz")

    assert not db.tem_item(1, "mortalha_luz", 1)
    assert db.tem_item(1, "molde_do_manto", 1)
    assert db.tem_item(1, "fio_do_manto", 1)
    assert db.tem_item(1, "forro_do_manto", 1)


def test_nao_forjador_consegue_forjar():
    _jogador(andar=9, profissao=None)
    _dar_pecas(1)

    _forjar(1, "sombra")

    assert db.tem_item(1, "mortalha_sombra", 1)


def test_segunda_forja_e_impossivel_pecas_ja_foram():
    _jogador(andar=9)
    _dar_pecas(1)
    _forjar(1, "luz")
    assert db.tem_item(1, "mortalha_luz", 1)

    _forjar(1, "sombra")   # tenta de novo, sem repor as peças

    assert not db.tem_item(1, "mortalha_sombra", 1)
    inv = {i["item"]: i["qtd"] for i in db.get_inventario(1)}
    assert inv.get("mortalha_luz", 0) == 1   # só a primeira, nunca dobrou


def test_forjar_fora_do_andar_9_e_recusado():
    _jogador(andar=1)
    _dar_pecas(1)

    _forjar(1, "luz")

    assert not db.tem_item(1, "mortalha_luz", 1)
    assert db.tem_item(1, "molde_do_manto", 1)   # nada foi consumido


def test_forjar_com_escolha_invalida_recusa_sem_consumir():
    _jogador(andar=9)
    _dar_pecas(1)

    _forjar(1, "")

    assert not db.tem_item(1, "mortalha_luz", 1)
    assert not db.tem_item(1, "mortalha_sombra", 1)
    assert db.tem_item(1, "molde_do_manto", 1)


# ---------------------------------------------------------------- item/equipar/trade
def test_equipar_com_andar_14_travado_e_recusado():
    _jogador(andar_max=1)
    db.add_item(1, "mortalha_luz", 1)

    asyncio.run(bot.equipar.callback(_ctx(), texto="mortalha de luz"))

    assert db.get_jogador(1)["mortalha"] is None
    assert db.tem_item(1, "mortalha_luz", 1)


def test_equipar_com_andar_14_destrancado_funciona():
    _jogador(andar_max=14)
    db.add_item(1, "mortalha_sombra", 1)

    asyncio.run(bot.equipar.callback(_ctx(), texto="mortalha de sombra"))

    assert db.get_jogador(1)["mortalha"] == "mortalha_sombra"


def test_mortalha_nao_vende():
    _jogador()
    db.add_item(1, "mortalha_luz", 1)

    asyncio.run(bot.vender.callback(_ctx(), argumento="mortalha de luz 1"))

    assert db.tem_item(1, "mortalha_luz", 1)


def test_mortalha_nao_desmancha():
    _jogador()
    db.add_item(1, "mortalha_sombra", 1)

    asyncio.run(bot.bot.get_command("desmanchar").callback(_ctx(), argumento="mortalha de sombra"))

    assert db.tem_item(1, "mortalha_sombra", 1)


def test_mortalha_nao_pode_ser_ofertada_em_troca():
    motivo = trocas._checar_item_para_oferta("mortalha_luz", {"itens": {}, "instancias": {}})
    assert motivo is not None


# ---------------------------------------------------------------- não encanta, não melhora
def test_encantar_mortalha_recusa_com_mensagem_propria():
    _jogador(mortalha="mortalha_luz", profissao="encantador", andar=1)
    ctx = _ctx()

    asyncio.run(bot.bot.get_command("encantar").callback(ctx, argumento="mortalha for"))

    texto = ctx.send.call_args.args[0]
    assert "não aceita encantamento" in texto
    assert "Uso:" not in texto   # não é o erro genérico de tipo desconhecido


def test_melhorar_mortalha_recusa_com_mensagem_propria():
    _jogador(mortalha="mortalha_sombra", andar=1)
    ctx = _ctx()

    asyncio.run(bot.bot.get_command("melhorar").callback(ctx, argumento="mortalha"))

    texto = ctx.send.call_args.args[0]
    assert "não sobe de nível" in texto
    assert "Uso:" not in texto


def test_recusas_da_mortalha_nao_consomem_material_nem_moeda():
    j = _jogador(mortalha="mortalha_luz", profissao="encantador", andar=1, moedas=1000)
    db.add_item(1, "essencia_do_vento", 99)   # material de Encantador do andar 1

    asyncio.run(bot.bot.get_command("encantar").callback(_ctx(), argumento="mortalha for"))
    asyncio.run(bot.bot.get_command("melhorar").callback(_ctx(), argumento="mortalha"))

    depois = db.get_jogador(1)
    assert depois["moedas"] == 1000
    assert db.tem_item(1, "essencia_do_vento", 99)


def test_encantar_continua_funcionando_normalmente_nos_outros_slots():
    _jogador(arma="espada_ferro", profissao="encantador", andar=1, moedas=100000)
    for material in ("essencia_do_vento", "pena_do_trovao", "eco_cristalizado"):
        db.add_item(1, material, 20)
    ctx = _ctx()

    asyncio.run(bot.bot.get_command("encantar").callback(ctx, argumento="arma for"))

    instancia_id = db.get_jogador(1)["arma_instancia_id"]
    assert instancia_id is not None
    assert db.get_instancia(instancia_id)["encantamento_atributo"] == "forca"


def test_melhorar_continua_funcionando_normalmente_na_arma():
    _jogador(arma="espada_ferro", andar=1, moedas=100000)
    db.add_item(1, "presa_javali", 10)

    asyncio.run(bot.bot.get_command("melhorar").callback(_ctx(), argumento="arma"))

    # sucesso ou falha, o comando processou de verdade (gastou material) --
    # não caiu numa recusa antecipada como a da mortalha.
    assert not db.tem_item(1, "presa_javali", 10)


# ---------------------------------------------------------------- botão na luta
def test_botao_mortalha_nao_aparece_sem_a_peca_equipada():
    c = _combatente(1)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    assert not any(isinstance(item, combate.BotaoMortalha) for item in painel.children)


def test_botao_mortalha_aparece_com_a_peca_equipada():
    c = _combatente(1, mortalha="mortalha_luz")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    assert any(isinstance(item, combate.BotaoMortalha) for item in painel.children)


def _botao_mortalha(painel):
    return next(i for i in painel.children if isinstance(i, combate.BotaoMortalha))


def test_mortalha_de_luz_cura_hp_cheio_sem_gastar_a_rodada_e_ainda_ataca(monkeypatch):
    monkeypatch.setitem(combate.H, "calcular_dano", lambda atk, defesa, crit: (50, False))
    c = _combatente(1, mortalha="mortalha_luz", hp=1)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_mortalha(painel)

    asyncio.run(botao.callback(_interacao(1)))

    assert c.hp == c.s["hp_max"]
    assert c.mortalha_usada is True
    assert c.acao is None   # não gastou a rodada -- ninguém "agiu" ainda

    hp_chefe_antes = luta.hp_chefe
    asyncio.run(painel.registrar_acao(_interacao(1), c, "atacar"))
    assert hp_chefe_antes - luta.hp_chefe == 50   # o ataque aconteceu na mesma rodada, normalmente


def test_mortalha_de_luz_uma_vez_por_luta():
    c = _combatente(1, mortalha="mortalha_luz", hp=1)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_mortalha(painel)

    asyncio.run(botao.callback(_interacao(1)))
    c.hp = 1   # simula ter levado dano de novo depois de curar

    it2 = _interacao(1)
    asyncio.run(botao.callback(it2))

    it2.response.send_message.assert_awaited_once()
    mensagem = it2.response.send_message.call_args.args[0]
    assert "já ativou" in mensagem   # recusa de "já usou", não de "não tem"
    assert c.hp == 1   # segunda tentativa não curou de novo


def test_mortalha_de_luz_nao_consome_pocao_nem_elixir():
    c = _combatente(1, mortalha="mortalha_luz", hp=1)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_mortalha(painel)

    asyncio.run(botao.callback(_interacao(1)))

    assert c.pocoes_usadas == 0
    assert c.elixires_usados == 0


def test_mortalha_de_sombra_dobra_o_dano_do_golpe_uma_vez(monkeypatch):
    monkeypatch.setitem(combate.H, "calcular_dano", lambda atk, defesa, crit: (100, False))
    c = _combatente(1, mortalha="mortalha_sombra")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_mortalha(painel)

    asyncio.run(botao.callback(_interacao(1)))
    assert c.sombra_ativa is True

    hp_antes = luta.hp_chefe
    asyncio.run(painel.registrar_acao(_interacao(1), c, "atacar"))

    assert hp_antes - luta.hp_chefe == 200   # 100 base x2
    assert c.sombra_ativa is False           # não sobrevive além da rodada em que foi usada


def test_mortalha_de_sombra_nao_dobra_de_novo_na_rodada_seguinte(monkeypatch):
    monkeypatch.setitem(combate.H, "calcular_dano", lambda atk, defesa, crit: (100, False))
    c = _combatente(1, mortalha="mortalha_sombra")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_mortalha(painel)

    asyncio.run(botao.callback(_interacao(1)))
    asyncio.run(painel.registrar_acao(_interacao(1), c, "atacar"))   # rodada 1: dobrado

    hp_antes = luta.hp_chefe
    asyncio.run(painel.registrar_acao(_interacao(1), c, "atacar"))   # rodada 2: normal

    assert hp_antes - luta.hp_chefe == 100


# ---------------------------------------------------------------- Sombra x habilidade
def _sem_variancia(monkeypatch):
    """Trava ±15%/crítico de `_rolar_dano_habilidade` num valor fixo, pra
    comparar dano com e sem Sombra sem depender de RNG."""
    monkeypatch.setattr(combate.random, "uniform", lambda a, b: 1.0)
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita, nunca atordoa


def test_sombra_dobra_dano_de_dardo_arcano(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["dardo_arcano"]

    combate._efeito_dardo_arcano(luta, c, dados)
    dano_normal = luta.hp_chefe_max - luta.hp_chefe

    luta.hp_chefe = luta.hp_chefe_max
    c.sombra_ativa = True
    combate._efeito_dardo_arcano(luta, c, dados)
    dano_dobrado = luta.hp_chefe_max - luta.hp_chefe

    assert dano_dobrado == dano_normal * 2


def test_sombra_dobra_golpe_aberto_mas_nao_o_sangramento_que_ele_aplica(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["golpe_aberto"]

    combate._efeito_golpe_aberto(luta, c, dados)
    dano_normal = luta.hp_chefe_max - luta.hp_chefe
    sangramento_normal = luta.condicoes[-1]["valor"]

    luta.hp_chefe = luta.hp_chefe_max
    luta.condicoes.clear()
    c.sombra_ativa = True
    combate._efeito_golpe_aberto(luta, c, dados)
    dano_dobrado = luta.hp_chefe_max - luta.hp_chefe
    sangramento_com_sombra = luta.condicoes[-1]["valor"]

    assert dano_dobrado == dano_normal * 2
    assert sangramento_com_sombra == sangramento_normal == combate.VALOR_SANGRAMENTO


def test_sombra_dobra_os_dois_golpes_de_corte_rapido(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="ladino", destreza=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["corte_rapido"]

    combate._efeito_corte_rapido(luta, c, dados)
    dano_normal = luta.hp_chefe_max - luta.hp_chefe

    luta.hp_chefe = luta.hp_chefe_max
    c.sombra_ativa = True
    combate._efeito_corte_rapido(luta, c, dados)
    dano_dobrado = luta.hp_chefe_max - luta.hp_chefe

    assert dano_dobrado == dano_normal * 2   # os dois golpes do laço dobraram


def test_sombra_nao_dobra_a_cura_de_palavra_de_alento():
    c = _combatente(1, classe="orador", inteligencia=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["palavra_de_alento"]

    combate._efeito_palavra_de_alento(luta, c, dados, alvo_id=c.id)
    valor_sem_sombra = luta.condicoes[-1]["valor"]

    luta.condicoes.clear()
    c.sombra_ativa = True
    combate._efeito_palavra_de_alento(luta, c, dados, alvo_id=c.id)
    valor_com_sombra = luta.condicoes[-1]["valor"]

    assert valor_com_sombra == valor_sem_sombra == combate.CURA_POR_RODADA_ALENTO


def test_sombra_nao_dobra_o_buff_de_voto_de_ferro():
    c = _combatente(1, classe="orador", inteligencia=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["voto_de_ferro"]

    c.sombra_ativa = True
    combate._efeito_voto_de_ferro(luta, c, dados)

    assert luta.condicoes[-1]["valor"] == combate.REDUCAO_VOTO_DE_FERRO


def test_sombra_nao_dobra_a_condicao_de_ruptura():
    c = _combatente(1, classe="mago", inteligencia=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["ruptura"]

    c.sombra_ativa = True
    combate._efeito_ruptura(luta, c, dados)

    assert luta.condicoes[-1]["valor"] == combate.VULNERAVEL_RUPTURA


def test_ativar_sombra_e_depois_defender_consome_o_uso_da_luta():
    c = _combatente(1, mortalha="mortalha_sombra")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_mortalha(painel)

    asyncio.run(botao.callback(_interacao(1)))
    assert c.sombra_ativa is True

    asyncio.run(painel.registrar_acao(_interacao(1), c, "defender"))

    assert c.mortalha_usada is True    # a peça já foi usada nesta luta, sem volta
    assert c.sombra_ativa is False     # e o buff da rodada foi embora sem servir pra nada


def test_botao_mortalha_continua_presente_e_habilitado_apos_uso():
    """Regressão: `self.disabled = True` no callback apagava o botão pra
    PARTY INTEIRA (view compartilhada), não só pra quem já usou -- ver
    decisoes.md § Mortalha de Luz/Sombra."""
    c = _combatente(1, mortalha="mortalha_luz")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_mortalha(painel)

    asyncio.run(botao.callback(_interacao(1)))

    assert botao.disabled is False
    assert botao in painel.children


def test_segundo_jogador_da_party_ainda_usa_a_propria_mortalha_apos_o_primeiro():
    """O bug: um botão compartilhado desabilitado pelo primeiro clique
    travava a party inteira no Discord de verdade (um botão `disabled` não
    dispatcha clique nenhum, nem do segundo jogador), mesmo com
    `mortalha_usada` sendo por jogador. A asserção de `disabled` no meio é o
    que amarra este teste ao sintoma real -- sem ela, chamar `.callback()`
    direto (como o teste faz) ignoraria o `disabled` que só o Discord
    checaria de verdade."""
    c1 = _combatente(1, mortalha="mortalha_luz", hp=1)
    c2 = _combatente(2, mortalha="mortalha_sombra")
    luta = combate.Luta([c1, c2], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_mortalha(painel)

    asyncio.run(botao.callback(_interacao(1)))
    assert c1.mortalha_usada is True
    assert c1.hp == c1.s["hp_max"]   # efeito de luz aplicou
    assert botao.disabled is False   # senão o Discord nunca entregaria o clique do segundo jogador

    it2 = _interacao(2)
    asyncio.run(botao.callback(it2))

    it2.response.send_message.assert_not_called()   # segundo jogador não foi recusado
    assert c2.mortalha_usada is True
    assert c2.sombra_ativa is True   # efeito de sombra também aplicou, na mesma luta


def test_mortalha_recusa_quem_nao_tem_a_peca_equipada():
    c = _combatente(1)   # sem mortalha nenhuma
    outro = _combatente(2, mortalha="mortalha_luz")   # só pra o botão aparecer no painel
    luta = combate.Luta([c, outro], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_mortalha(painel)

    it = _interacao(1)
    asyncio.run(botao.callback(it))

    it.response.send_message.assert_awaited_once()
    mensagem = it.response.send_message.call_args.args[0]
    assert "não tem" in mensagem.lower()
    assert "Selen" in mensagem   # explica onde conseguir, não só recusa seca
    assert c.mortalha_usada is False


def test_painel_novo_da_mesma_luta_nao_mostra_o_botao_depois_de_usado():
    """`_continuar()` roda quando a rodada estoura por timeout com gente
    ainda na luta -- o painel novo não pode reoferecer a skill já usada."""
    c = _combatente(1, mortalha="mortalha_luz")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_mortalha(painel)
    asyncio.run(botao.callback(_interacao(1)))

    novo_painel = painel._continuar(luta)

    assert not any(isinstance(i, combate.BotaoMortalha) for i in novo_painel.children)


def test_em_party_cura_da_luz_nao_vaza_pros_aliados():
    c1 = _combatente(1, mortalha="mortalha_luz", hp=1)
    c2 = _combatente(2, hp=1)
    luta = combate.Luta([c1, c2], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_mortalha(painel)

    asyncio.run(botao.callback(_interacao(1)))

    assert c1.hp == c1.s["hp_max"]
    assert c2.hp == 1


def test_em_party_jogador_sem_mortalha_leva_recusa_ao_clicar_no_botao_compartilhado():
    c1 = _combatente(1, mortalha="mortalha_luz")
    c2 = _combatente(2)   # sem mortalha nenhuma
    luta = combate.Luta([c1, c2], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_mortalha(painel)

    it = _interacao(2)
    asyncio.run(botao.callback(it))

    it.response.send_message.assert_awaited_once()
    assert c2.mortalha_usada is False
    assert c1.mortalha_usada is False   # não foi consumida por engano no lugar errado
