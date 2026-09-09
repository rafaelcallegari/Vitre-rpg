# tests/test_multi_inimigo.py
# Step A: multi-inimigo no motor de combate -- refatoração pura, nada muda
# pra quem já joga hoje (nenhum chefe existente ganha companhia, nenhum
# conteúdo novo). A suíte existente inteira é a rede de segurança principal
# (roda sem alteração nenhuma -- ver decisoes.md § Step A); este arquivo só
# cobre o mínimo novo que o cartão pede: dois inimigos de verdade dentro de
# uma `Luta`, com estado independente.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord

import bot  # noqa: F401 -- popula combate.H
import combate
import condicoes
import database as db
import game_data


CHEFE_A = {"nome": "Inimigo A", "hp": 100, "atk": 10, "def": 0, "xp": 0, "moedas": 0}
CHEFE_B = {"nome": "Inimigo B", "hp": 80, "atk": 5, "def": 0, "xp": 0, "moedas": 0}


def _combatente(user_id, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


def _interacao(user_id):
    it = MagicMock()
    it.user.id = user_id
    it.response = MagicMock()
    it.response.defer = AsyncMock()
    it.response.is_done.return_value = True
    it.response.send_message = AsyncMock()
    it.edit_original_response = AsyncMock()
    return it


def _botao(view, label):
    return next(c for c in view.children if getattr(c, "label", None) == label)


# ==================================================================
# Commit 1 -- a Luta aceita uma lista
# ==================================================================

def test_luta_aceita_lista_de_inimigos_um_objeto_por_dict():
    c = _combatente(1)
    luta = combate.Luta([c], [CHEFE_A, CHEFE_B], andar_num=1)

    assert len(luta.inimigos) == 2
    assert luta.inimigos[0].id == "chefe"
    assert luta.inimigos[1].id == "chefe_1"
    assert luta.inimigos[0].nome == "Inimigo A"
    assert luta.inimigos[1].nome == "Inimigo B"
    assert luta.inimigos[0].hp == luta.inimigos[0].hp_max == 100
    assert luta.inimigos[1].hp == luta.inimigos[1].hp_max == 80


def test_chefe_unico_dict_continua_virando_lista_de_um_ponte_intacta():
    """Todo chamador de hoje (raide.py, dungeon.py, iniciar_luta) passa um
    dict sozinho -- "chefe sozinho vira lista de um" precisa ser 100%
    transparente: luta.chefe/hp_chefe/hp_chefe_max continuam funcionando
    exatamente como sempre, porque são a mesma memória de inimigos[0]."""
    c = _combatente(1)
    luta = combate.Luta([c], CHEFE_A, andar_num=1)

    assert len(luta.inimigos) == 1
    assert luta.inimigos[0].id == "chefe"
    assert luta.chefe is luta.inimigos[0].dados
    assert luta.hp_chefe == luta.inimigos[0].hp == 100

    luta.hp_chefe -= 30   # escreve pela ponte antiga
    assert luta.inimigos[0].hp == 70   # aparece no objeto novo


def test_matar_um_inimigo_nao_encerra_a_luta_matar_todos_encerra():
    c = _combatente(1)
    luta = combate.Luta([c], [CHEFE_A, CHEFE_B], andar_num=1)
    assert len(luta.inimigos_ativos) == 2

    luta.inimigos[0].hp = 0
    assert len(luta.inimigos_ativos) == 1
    assert luta.inimigos_ativos == [luta.inimigos[1]]

    luta.inimigos[1].hp = 0
    assert luta.inimigos_ativos == []


def test_fim_da_luta_so_dispara_quando_todos_os_inimigos_morrem():
    c = _combatente(1)
    luta = combate.Luta([c], [CHEFE_A, CHEFE_B], andar_num=1)
    painel = combate.PainelLuta(luta)

    luta.inimigos[0].hp = 0
    assert asyncio.run(painel.fim_da_luta()) is None   # um morreu, o outro segue

    luta.inimigos[1].hp = 0
    resultado = asyncio.run(painel.fim_da_luta())
    assert resultado is not None   # os dois mortos -- luta termina


def test_hp_escala_por_inimigo_independente_com_dois_donos():
    """Decisão do Step A (ver decisoes.md): cada inimigo escala o próprio
    HP por dono, igual sempre escalou pro chefe único -- não só o
    principal, não fixo pro grupo."""
    c1 = _combatente(1)
    c2 = _combatente(2)
    luta = combate.Luta([c1, c2], [CHEFE_A, CHEFE_B], andar_num=1)

    assert luta.inimigos[0].hp == 100 * 2
    assert luta.inimigos[1].hp == 80 * 2


def test_hp_fixo_acima_do_selo_vale_pra_cada_inimigo():
    c1 = _combatente(1)
    c2 = _combatente(2)
    luta = combate.Luta([c1, c2], [CHEFE_A, CHEFE_B], andar_num=11)

    assert luta.inimigos[0].hp == 100
    assert luta.inimigos[1].hp == 80


# ==================================================================
# Commit 2 -- o alvo de condição vira id
# ==================================================================

def test_condicao_em_cada_inimigo_e_independente():
    c = _combatente(1)
    luta = combate.Luta([c], [CHEFE_A, CHEFE_B], andar_num=1)

    condicoes.aplicar(luta, "chefe", "dano_por_rodada", "Queimadura", "🔥", duracao=1, valor=0.10)
    condicoes.aplicar(luta, "chefe_1", "vulneravel", "Ruptura", "💠", duracao=5, valor=0.20)

    assert condicoes.multiplicador_dano_causado(luta, "chefe") == 1.0   # sem vulnerável
    assert condicoes.multiplicador_dano_causado(luta, "chefe_1") == 1.2  # a Ruptura é só dele

    antes_a, antes_b = luta.inimigos[0].hp, luta.inimigos[1].hp
    condicoes.tick(luta)
    assert luta.inimigos[0].hp == antes_a - 10   # 10% de 100 -- só o "chefe" tomou a Queimadura
    assert luta.inimigos[1].hp == antes_b        # "chefe_1" intacto


def test_condicao_no_segundo_inimigo_usa_o_nome_e_o_hp_max_dele():
    c = _combatente(1)
    luta = combate.Luta([c], [CHEFE_A, CHEFE_B], andar_num=1)
    condicoes.aplicar(luta, "chefe_1", "dano_por_rodada", "Sangramento", "🩸", duracao=1, valor=0.5)

    condicoes.tick(luta)

    assert luta.inimigos[1].hp == 40   # 50% de 80 (hp_max do CHEFE_B), não do CHEFE_A
    assert "Inimigo B" in luta.log[-1]


def test_condicao_em_inimigo_morto_para_de_tickar():
    c = _combatente(1)
    luta = combate.Luta([c], [CHEFE_A, CHEFE_B], andar_num=1)
    condicoes.aplicar(luta, "chefe_1", "dano_por_rodada", "Sangramento", "🩸", duracao=5, valor=1000)

    condicoes.tick(luta)
    assert luta.inimigos[1].hp <= 0

    hp_antes = luta.inimigos[1].hp
    condicoes.tick(luta)
    assert luta.inimigos[1].hp == hp_antes   # já não está ativo -- não desce mais


def test_alvo_forcado_com_dois_inimigos_aponta_para_um_so():
    c1 = _combatente(1)
    c2 = _combatente(2)
    luta = combate.Luta([c1, c2], [CHEFE_A, CHEFE_B], andar_num=1)
    condicoes.aplicar(luta, "chefe_1", "redireciona", "Provocação", "📣", duracao=1, valor=c1.id)

    assert condicoes.alvo_forcado(luta, "chefe_1") is c1
    assert condicoes.alvo_forcado(luta, "chefe") is None   # a provocação é só do chefe_1
    assert condicoes.alvo_forcado(luta) is None            # default "chefe" -- mesma coisa


# ==================================================================
# Commit 3 -- os botões miram inimigo (generaliza BotaoAlvoHabilidade/
# MenuAlvoHabilidade, o mesmo widget que a Palavra de Alento já usa pra
# aliado). Nenhuma skill real usa "inimigo_escolhido" ainda -- infra pura
# -- então os testes montam uma sintética via monkeypatch.
# ==================================================================

def _instalar_skill_de_teste(monkeypatch, efeito):
    dados = {"nome": "Teste", "emoji": "🎯", "custo": 0, "recurso": "mana", "alvo": "inimigo_escolhido"}
    monkeypatch.setitem(combate.HABILIDADES, "teste_alvo_inimigo", dados)
    monkeypatch.setitem(combate.EFEITOS_HABILIDADE, "teste_alvo_inimigo", efeito)
    return dados


def _botao_habilidade_de_teste(dados, painel, c):
    view = discord.ui.View()
    view.painel = painel
    view.combatente = c
    botao = combate.BotaoHabilidade("teste_alvo_inimigo", dados)
    view.add_item(botao)
    return botao


def test_alvos_possiveis_de_inimigo_escolhido_e_a_lista_de_inimigos_ativos():
    c = _combatente(1)
    luta = combate.Luta([c], [CHEFE_A, CHEFE_B], andar_num=1)
    dados = {"alvo": "inimigo_escolhido"}

    assert combate._alvos_possiveis(luta, dados) == luta.inimigos_ativos


def test_com_um_inimigo_so_nada_muda_na_tela_resolve_direto(monkeypatch):
    """"Com um inimigo só, nada muda na tela" -- hoje SEMPRE (nenhum chefe
    tem companhia ainda), então toda skill inimigo_escolhido resolve
    direto, sem o passo extra de escolha."""
    alvos_atingidos = []

    def _efeito(luta, c, dados, alvo_id):
        alvos_atingidos.append(alvo_id)

    dados = _instalar_skill_de_teste(monkeypatch, _efeito)
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = combate.Luta([c], CHEFE_A, andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_habilidade_de_teste(dados, painel, c)

    asyncio.run(botao.callback(_interacao(1)))

    assert alvos_atingidos == ["chefe"]   # resolveu contra o único inimigo, sem menu


def test_alvo_de_habilidade_escolhido_pelo_jogador_acerta_quem_ele_escolheu(monkeypatch):
    def _efeito(luta, c, dados, alvo_id):
        luta.inimigo_por_id(alvo_id).hp -= 10

    dados = _instalar_skill_de_teste(monkeypatch, _efeito)
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = combate.Luta([c], [CHEFE_A, CHEFE_B], andar_num=1)
    painel = combate.PainelLuta(luta)
    botao = _botao_habilidade_de_teste(dados, painel, c)

    it1 = _interacao(1)
    asyncio.run(botao.callback(it1))
    view_alvo = it1.edit_original_response.call_args.kwargs["view"]
    labels = {item.label for item in view_alvo.children if isinstance(item, combate.BotaoAlvoHabilidade)}
    assert labels == {"Inimigo A", "Inimigo B"}   # menu apareceu, um botão por inimigo

    hp_a_antes, hp_b_antes = luta.inimigos[0].hp, luta.inimigos[1].hp
    it2 = _interacao(1)
    asyncio.run(_botao(view_alvo, "Inimigo B").callback(it2))

    assert luta.inimigos[1].hp == hp_b_antes - 10   # só quem foi escolhido tomou dano
    assert luta.inimigos[0].hp == hp_a_antes        # o outro, intacto
