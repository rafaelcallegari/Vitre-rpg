# tests/test_combate.py
# Vitória de chefe em party: todo participante leva tudo igual (ver
# decisoes.md § Ajuda de veterano na party) — mais os dois cartões de
# combate: HP final congelado ao sair da luta (bug de produção) e HP de
# chefe fixo acima do Selo.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula combate.H (combate.instalar), sem conectar em nada
import combate
import database as db
import game_data


# ---------------- fakes/helpers compartilhados pelas seções abaixo ----------------
CHEFE_TESTE = {"nome": "Testinho", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0}


def _combatente(user_id, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


# ================================================================
# Bug: HP de quem saiu da luta era regravado por cima da cura externa
# ================================================================
# `turno_do_chefe()` (fim de rodada) e `on_timeout()` percorrem
# `Luta.participantes` (a lista inteira, não `ativos`) chamando
# `salvar_estado()` pra todo mundo, rodada após rodada -- inclusive quem já
# fugiu/saiu/caiu. Sem guarda, cada chamada regravava o HP CONGELADO no
# momento da saída por cima de qualquer cura que acontecesse depois (poção
# fora da luta). Ver decisoes.md § HP final é congelado ao sair da luta.

def test_hp_de_quem_fugiu_nao_e_regravado_por_cima_da_cura_externa():
    c = _combatente(1, hp=50)
    outro = _combatente(2, hp=100)   # continua ativo -- sem isso turno_do_chefe() sai de cara
    luta = combate.Luta([c, outro], CHEFE_TESTE, andar_num=1)

    c.fugiu = True
    c.salvar_estado()   # mesma chamada que o botão Fugir faz

    db.atualizar_jogador(1, hp=90)   # cura FORA da luta, depois que ele já saiu

    luta.turno_do_chefe()   # simula a rodada seguinte resolvendo

    assert db.get_jogador(1)["hp"] == 90


def test_hp_de_quem_saiu_por_timeout_nao_e_regravado_por_cima_da_cura_externa():
    c = _combatente(1, hp=50)
    outro = _combatente(2, hp=100)
    luta = combate.Luta([c, outro], CHEFE_TESTE, andar_num=1)
    painel = combate.PainelLuta(luta)
    painel.mensagem = MagicMock()
    painel.mensagem.edit = AsyncMock()
    outro.acao = "defender"   # só falta a ação de c -- ele é quem "sumiu"

    asyncio.run(painel.on_timeout())

    assert c.saiu is True
    db.atualizar_jogador(1, hp=90)   # cura FORA da luta, depois que ele já saiu

    luta.turno_do_chefe()   # simula mais uma rodada acontecendo

    assert db.get_jogador(1)["hp"] == 90


def test_hp_de_quem_caiu_grava_zero_uma_vez_e_nao_regrava_depois():
    c = _combatente(1, hp=10)
    outro = _combatente(2, hp=999)
    luta = combate.Luta([c, outro], CHEFE_TESTE, andar_num=1)

    c.hp = -5
    c.caiu = True
    c.salvar_estado()
    assert db.get_jogador(1)["hp"] == 0

    c.hp = 999   # nunca deveria acontecer de verdade -- só prova que a guarda segura
    luta.turno_do_chefe()   # o laço de fim de rodada roda de novo porque `outro` segue ativo

    assert db.get_jogador(1)["hp"] == 0


def test_hp_e_mana_de_quem_continua_lutando_sao_salvos_por_rodada():
    """Não regride: a guarda só se aplica a quem SAIU -- quem segue ativo
    continua tendo HP/mana persistidos toda rodada, igual sempre foi."""
    c = _combatente(1, hp=50, mana=10)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    # rodada 1: RODADA_1_SEM_CHEFE mantém o chefe parado -- HP/mana só mudam
    # pela linha abaixo, não por um ataque, então a asserção é determinística
    c.hp = 77
    c.mana = 33

    luta.turno_do_chefe()

    j = db.get_jogador(1)
    assert j["hp"] == 77
    assert j["mana"] == 33


# ================================================================
# HP de chefe fixo acima do Selo (andar 11+)
# ================================================================

def test_hp_do_chefe_escala_por_dono_ate_o_andar_10():
    c1 = _combatente(1)
    c2 = _combatente(2)
    luta = combate.Luta([c1, c2], {**CHEFE_TESTE, "hp": 1000}, andar_num=10)
    assert luta.hp_chefe == 2000


def test_hp_do_chefe_e_fixo_a_partir_do_andar_11():
    c1 = _combatente(1)
    c2 = _combatente(2)
    luta = combate.Luta([c1, c2], {**CHEFE_TESTE, "hp": 1000}, andar_num=11)
    assert luta.hp_chefe == 1000


def test_texto_da_sala_de_party_reflete_a_regra_do_andar():
    chefe = {"hp": 1000}
    texto_baixo = combate.texto_regra_hp_chefe(10, chefe)
    texto_alto = combate.texto_regra_hp_chefe(11, chefe)
    assert "por dono" in texto_baixo
    assert "fixo" in texto_alto
    assert "por dono" not in texto_alto


def test_sala_de_espera_embed_usa_o_texto_certo_por_andar():
    db.criar_jogador(1, "Alice")
    j = db.get_jogador(1)
    sala_baixa = combate.SalaDeEspera(anfitriao=1, jogador=j, andar_num=1)
    sala_alta = combate.SalaDeEspera(anfitriao=1, jogador=j, andar_num=11)

    assert "por dono" in sala_baixa.embed().description
    assert "fixo" in sala_alta.embed().description


def test_raide_continua_escalando_por_participante_nao_muda():
    """raide.py usa Luta com andar_num=ANDAR_REFERENCIA_RAIDE (7, abaixo do
    limiar) e donos_ids=None (todo mundo é dono) -- confirma que a regra
    nova de HP fixo não vaza pra raide."""
    c1 = _combatente(1)
    c2 = _combatente(2)
    c3 = _combatente(3)
    luta = combate.Luta([c1, c2, c3], game_data.RAIDE_CHEFE, game_data.ANDAR_REFERENCIA_RAIDE)
    assert luta.hp_chefe == game_data.RAIDE_CHEFE["hp"] * 3


# ================================================================
# Bug: embed de vitória não anunciava o tesouro (nem qualquer drop novo) --
# a linha do dono tinha "🔷 Fragmento" fixo no texto, escrito quando só
# existia um drop de chefe possível. A gravação em inventário sempre esteve
# certa (recompensar() já rolava `chefe["drops"]" inteiro); só a MENSAGEM
# ficou presa no que existia quando foi escrita -- mesmo formato de bug do
# § Padrão — mapa de domínio nunca é subscript direto. Ver decisoes.md §
# Embed de vitória anuncia todo drop do chefe, não só o fragmento fixo.
# ================================================================

def _luta_1v1(chefe, andar_num):
    c = _combatente(1)
    return c, combate.Luta([c], chefe, andar_num)


def test_embed_de_vitoria_lista_fragmento_e_tesouro_no_andar_1():
    chefe = dict(game_data.ANDARES[1]["boss"])
    _, luta = _luta_1v1(chefe, andar_num=1)

    e = asyncio.run(combate.finalizar_vitoria(luta))

    campo = next(f for f in e.fields if f.name == "Recompensas")
    assert "Fragmento do Selo" in campo.value
    assert "Coroa Velha" in campo.value


def test_embed_de_vitoria_lista_o_tesouro_certo_no_andar_10():
    """Caminho idêntico ao andar 1 (mesmo `rolar_drops`, mesma lista de
    drops 100%) -- cobre um segundo andar pra provar que não é coincidência
    de posição na lista de drops."""
    chefe = dict(game_data.ANDARES[10]["boss"])
    _, luta = _luta_1v1(chefe, andar_num=10)

    e = asyncio.run(combate.finalizar_vitoria(luta))

    campo = next(f for f in e.fields if f.name == "Recompensas")
    assert "Fragmento do Selo" in campo.value
    assert "Martelo do Arquiteto" in campo.value


def test_embed_de_vitoria_acima_do_selo_primeira_vez_mostra_o_material():
    """Andar 11+ usa o caminho de chance (100% na primeira vitória da
    conta) -- caminho DIFERENTE do rolar_drops de 1-10 (ver
    recompensar()), então precisa de teste próprio."""
    chefe = dict(game_data.ANDARES[11]["boss"])
    _, luta = _luta_1v1(chefe, andar_num=11)

    e = asyncio.run(combate.finalizar_vitoria(luta))

    campo = next(f for f in e.fields if f.name == "Recompensas")
    assert "Pluma Etérea" not in campo.value  # isso é drop de monstro comum, não de chefe
    assert game_data.ITENS["sopro_contido"]["nome"] in campo.value


def test_embed_de_vitoria_acima_do_selo_repeticao_com_sorte_mostra_item(monkeypatch):
    chefe = dict(game_data.ANDARES[11]["boss"])
    c, luta = _luta_1v1(chefe, andar_num=11)
    db.registrar_vitoria_chefe(c.id, 11)
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)  # sempre passa o 15%

    e = asyncio.run(combate.finalizar_vitoria(luta))

    campo = next(f for f in e.fields if f.name == "Recompensas")
    assert game_data.ITENS["sopro_contido"]["nome"] in campo.value


# ================================================================
# Contexto do tesouro no embed de vitória (Salão da Guilda)
# ================================================================

def test_embed_de_vitoria_com_guilda_mostra_progresso_do_salao():
    """Com guilda, a linha do tesouro traz a projeção de progresso (ex.
    "1/6 pro tier ...") e NÃO menciona irreversibilidade -- esse aviso é
    só na hora do depósito de verdade (`rpg guilda depositar`)."""
    chefe = dict(game_data.ANDARES[1]["boss"])
    c, luta = _luta_1v1(chefe, andar_num=1)
    db.criar_guilda("Ordem de Teste", c.id, 1, cargo_id=10, canal_id=20)

    e = asyncio.run(combate.finalizar_vitoria(luta))

    campo = next(f for f in e.fields if f.name == "Recompensas")
    assert "Salão de **Ordem de Teste**" in campo.value
    assert "1/6" in campo.value
    assert "pro tier 1" in campo.value
    assert "não pode ser desfeito" not in campo.value.lower()


def test_embed_de_vitoria_sem_guilda_mostra_convite_sem_numero():
    """Sem guilda, a linha é convite (fundar/entrar), sem número de
    progresso -- o jogador não tem Salão nenhum pra progredir."""
    chefe = dict(game_data.ANDARES[1]["boss"])
    _, luta = _luta_1v1(chefe, andar_num=1)

    e = asyncio.run(combate.finalizar_vitoria(luta))

    campo = next(f for f in e.fields if f.name == "Recompensas")
    assert "tesouro de guilda" in campo.value
    assert "rpg guilda criar" in campo.value
    assert "/6" not in campo.value  # sem guilda, sem projeção de tier


# ================================================================
# Vitória de chefe: todo participante leva tudo igual
# ================================================================
# `c.caiu` deixou de excluir alguém de `recompensar()` -- só fuga (`fugiu`)
# e saída por timeout (`saiu`) ficam de fora. `combatente.dono` continua
# existindo, mas só escala o HP do chefe nos andares 1-10 -- recompensa,
# drop e progressão de andar não olham mais pra ele. Ver decisoes.md §
# Ajuda de veterano na party.

def test_recompensar_caido_leva_xp_moedas_drop_e_andar_iguais_a_quem_ficou_de_pe():
    chefe = dict(game_data.ANDARES[1]["boss"])
    caido, luta = _luta_1v1(chefe, andar_num=1)
    caido.hp = 0
    caido.caiu = True

    nivel, subiu, xp_ganho, moedas_ganho, itens_dropados = asyncio.run(
        combate.recompensar(luta, caido)
    )

    assert xp_ganho == chefe["xp"]
    assert moedas_ganho == chefe["moedas"]
    assert "coroa_velha" in itens_dropados
    assert "fragmento_selo" in itens_dropados
    j = db.get_jogador(caido.id)
    s = bot.stats(j)
    assert j["andar"] == 2
    assert j["moedas"] == chefe["moedas"]
    assert j["hp"] == s["hp_max"]
    assert j["mana"] == s["mana_max"]


def test_finalizar_vitoria_inclui_quem_caiu_e_exclui_fugiu_e_saiu():
    chefe = dict(game_data.ANDARES[1]["boss"])
    caido = _combatente(1)
    fugiu = _combatente(2)
    sumiu = _combatente(3)
    de_pe = _combatente(4)
    luta = combate.Luta([caido, fugiu, sumiu, de_pe], chefe, andar_num=1)
    caido.hp = 0
    caido.caiu = True
    fugiu.fugiu = True
    sumiu.saiu = True

    e = asyncio.run(combate.finalizar_vitoria(luta))

    campo = next(f for f in e.fields if f.name == "Recompensas")
    assert "Jogador1" in campo.value
    assert "Jogador4" in campo.value
    assert "Jogador2" not in campo.value
    assert "Jogador3" not in campo.value
    assert "(ajuda)" not in campo.value
    assert db.get_jogador(1)["andar"] == 2   # caiu, mas a party venceu
    assert db.get_jogador(2)["andar"] == 1   # fugiu -- sem recompensa, sem andar
    assert db.get_jogador(3)["andar"] == 1   # saiu por timeout -- idem


def test_party_de_tres_no_andar_1_todos_levam_o_tesouro_do_chefe():
    chefe = dict(game_data.ANDARES[1]["boss"])
    c1, c2, c3 = _combatente(1), _combatente(2), _combatente(3)
    luta = combate.Luta([c1, c2, c3], chefe, andar_num=1)

    asyncio.run(combate.finalizar_vitoria(luta))

    for uid in (1, 2, 3):
        itens = [i["item"] for i in db.get_inventario(uid)]
        assert "coroa_velha" in itens
        assert "fragmento_selo" in itens


def test_ajuda_anda_um_andar_mas_andar_max_fica_intacto():
    """Quem entrou só de ajuda (andar_max acima do andar do chefe) se
    desloca pro próximo andar, mas `andar_max` não muda -- ela já tinha
    destrancado mais longe. `max(j["andar_max"], novo_andar)` cobre isso."""
    chefe = dict(game_data.ANDARES[1]["boss"])
    dono = _combatente(1, andar=1, andar_max=1)
    ajuda = _combatente(2, andar=1, andar_max=5)
    luta = combate.Luta([dono, ajuda], chefe, andar_num=1, donos_ids=[dono.id])

    asyncio.run(combate.finalizar_vitoria(luta))

    j_ajuda = db.get_jogador(ajuda.id)
    assert j_ajuda["andar"] == 2
    assert j_ajuda["andar_max"] == 5


def test_hp_do_chefe_nao_escala_por_ajuda_so_por_dono():
    dono = _combatente(1, andar=5, andar_max=5)
    ajuda = _combatente(2, andar=5, andar_max=8)
    luta = combate.Luta(
        [dono, ajuda], {**CHEFE_TESTE, "hp": 1000}, andar_num=5, donos_ids=[dono.id]
    )
    assert luta.hp_chefe == 1000


def test_ajuda_acima_do_selo_segunda_vitoria_no_mesmo_chefe_cai_pra_quinze_por_cento(monkeypatch):
    """Sem isso, a ajuda ficaria pra sempre em 100% -- e andar 11 é
    alcançável por `rpg viajar`, virando farm infinito (ver decisoes.md).
    `a_registrar_vitoria_chefe` agora roda pra todo participante, não só
    pro dono, então a segunda vitória DELA já deve ter sido contada."""
    chefe = dict(game_data.ANDARES[11]["boss"])
    ajuda = _combatente(1, andar=11, andar_max=12)
    dono = _combatente(2, andar=11, andar_max=11)
    luta = combate.Luta([ajuda, dono], chefe, andar_num=11, donos_ids=[dono.id])
    db.registrar_vitoria_chefe(ajuda.id, 11)
    monkeypatch.setattr(combate.random, "random", lambda: 0.2)  # falha o 15%, passaria no 100%

    asyncio.run(combate.finalizar_vitoria(luta))

    itens = [i["item"] for i in db.get_inventario(ajuda.id)]
    assert "sopro_contido" not in itens


def test_derrota_total_ainda_cobra_a_processar_morte_de_todo_mundo():
    """Não regride: a punição de morte continua sendo só da derrota total
    (`finalizar_derrota`) -- quem cai numa luta VENCIDA não paga isso (ver
    `test_recompensar_caido_leva_xp_moedas_drop_e_andar_iguais_a_quem_ficou_de_pe`)."""
    c1 = _combatente(1, moedas=1000)
    c2 = _combatente(2, moedas=2000)
    luta = combate.Luta([c1, c2], CHEFE_TESTE, andar_num=1)
    c1.caiu = True
    c2.caiu = True

    e = asyncio.run(combate.finalizar_derrota(luta))

    assert db.get_jogador(1)["moedas"] == 800
    assert db.get_jogador(2)["moedas"] == 1600
    campo = next(f for f in e.fields if f.name == "Derrota")
    assert "Jogador1" in campo.value
    assert "Jogador2" in campo.value
