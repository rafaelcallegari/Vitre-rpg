# tests/test_estrada.py
# Step E, commit 1: a estrada. `rpg viajar` fora da torre (Mirante <->
# vilarejo) passa a poder ser interrompido por um encontro -- a viagem para,
# a luta acontece, vencendo o jogador chega ao destino. A escada de volta
# pro andar 15 (a porta) fica de fora -- não é "estrada". Ver decisoes.md
# § Step E.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import combate
import database as db
import estrada
import game_data
import incursao
import mundo


def _jogador(user_id=1, mundo_atual=None, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if mundo_atual is not None:
        campos["mundo"] = mundo_atual
    if campos:
        db.atualizar_jogador(user_id, **campos)
    return db.get_jogador(user_id)


def _ctx(user_id=1):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    return ctx


def _msg(ctx):
    return ctx.send.call_args.args[0]


def _combatente(user_id, **campos):
    j = _jogador(user_id, **campos)
    return combate.Combatente(j, bot.stats(j))


# ==================================================================
# houve_encontro -- probabilidade pura
# ==================================================================

def test_houve_encontro_sempre_true_com_chance_maxima(monkeypatch):
    monkeypatch.setattr(estrada, "CHANCE_ENCONTRO_ESTRADA", 1.0)
    assert all(estrada.houve_encontro() for _ in range(20))


def test_houve_encontro_sempre_false_com_chance_zero(monkeypatch):
    monkeypatch.setattr(estrada, "CHANCE_ENCONTRO_ESTRADA", 0.0)
    assert not any(estrada.houve_encontro() for _ in range(20))


# ==================================================================
# encontro acontece -- a viagem para, a luta começa
# ==================================================================

def test_encontro_no_mirante_indo_pro_vilarejo_nao_move_o_jogador_ainda(monkeypatch):
    monkeypatch.setattr(estrada, "houve_encontro", lambda: True)
    _jogador(1, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino="vilarejo"))
    assert db.get_jogador(1)["mundo"] == mundo.MIRANTE   # não chegou ainda
    assert "view" in ctx.send.call_args.kwargs
    assert isinstance(ctx.send.call_args.kwargs["view"], estrada.PainelEstrada)


def test_encontro_no_vilarejo_indo_pro_mirante_nao_move_o_jogador_ainda(monkeypatch):
    monkeypatch.setattr(estrada, "houve_encontro", lambda: True)
    _jogador(1, mundo_atual=mundo.VILAREJO, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino="mirante"))
    assert db.get_jogador(1)["mundo"] == mundo.VILAREJO   # não chegou ainda
    assert isinstance(ctx.send.call_args.kwargs["view"], estrada.PainelEstrada)


def test_sem_encontro_viagem_completa_normalmente(monkeypatch):
    monkeypatch.setattr(estrada, "houve_encontro", lambda: False)
    _jogador(1, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino="vilarejo"))
    assert db.get_jogador(1)["mundo"] == mundo.VILAREJO   # chegou direto
    assert "view" not in ctx.send.call_args.kwargs or not isinstance(
        ctx.send.call_args.kwargs.get("view"), estrada.PainelEstrada
    )


# ==================================================================
# vitória leva ao destino
# ==================================================================

def test_vitoria_na_estrada_completa_a_viagem():
    c = _combatente(1, classe="guerreiro", forca=20, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    luta = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    for inimigo in luta.inimigos:
        inimigo.hp = 0   # vitória forçada

    asyncio.run(estrada._finalizar_vitoria_estrada(luta, 1, mundo.VILAREJO))

    assert db.get_jogador(1)["mundo"] == mundo.VILAREJO


def test_vitoria_na_estrada_nunca_chama_processar_morte(monkeypatch):
    stub = MagicMock()
    monkeypatch.setattr(bot, "processar_morte", stub)
    c = _combatente(1, classe="guerreiro", forca=20, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    luta = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    for inimigo in luta.inimigos:
        inimigo.hp = 0

    asyncio.run(estrada._finalizar_vitoria_estrada(luta, 1, mundo.VILAREJO))

    stub.assert_not_called()


# ==================================================================
# derrota não mata -- a viagem se resolve sem morte
# ==================================================================

def test_derrota_na_estrada_nunca_chama_processar_morte(monkeypatch):
    stub = MagicMock()
    monkeypatch.setattr(bot, "processar_morte", stub)
    c = _combatente(1, classe="guerreiro", forca=20, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    luta = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    c.hp = 0
    c.caiu = True

    asyncio.run(estrada._finalizar_derrota_estrada(luta, 1, mundo.VILAREJO))

    stub.assert_not_called()


def test_derrota_na_estrada_ainda_completa_a_viagem():
    """'A viagem se resolve sem morte' -- perder não impede de chegar,
    só custa (commit 3 decide o quê)."""
    c = _combatente(1, classe="guerreiro", forca=20, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    luta = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    c.hp = 0
    c.caiu = True

    asyncio.run(estrada._finalizar_derrota_estrada(luta, 1, mundo.VILAREJO))

    assert db.get_jogador(1)["mundo"] == mundo.VILAREJO


# ==================================================================
# fugir -- nem punição, nem chegada
# ==================================================================

def test_fuga_na_estrada_nao_completa_a_viagem():
    c = _combatente(1, classe="guerreiro", forca=20, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    luta = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    c.fugiu = True

    asyncio.run(estrada._finalizar_abandono_estrada(luta))

    assert db.get_jogador(1)["mundo"] == mundo.MIRANTE   # continua onde estava


# ==================================================================
# regressão -- o resto de rpg viajar não muda
# ==================================================================

def test_viajar_dentro_da_torre_nunca_passa_pela_estrada(monkeypatch):
    chamou = []
    monkeypatch.setattr(estrada, "houve_encontro", lambda: chamou.append(True) or True)
    _jogador(1, andar=1, andar_max=5, moedas=10000)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino=3))
    assert db.get_jogador(1)["andar"] == 3   # viagem normal, sem desvio
    assert chamou == []   # estrada.houve_encontro nunca foi consultado


def test_escada_do_mirante_pro_andar_15_nunca_tem_encontro(monkeypatch):
    """A porta/escada não é 'estrada' -- é o mesmo degrau de sempre."""
    chamou = []
    monkeypatch.setattr(estrada, "houve_encontro", lambda: chamou.append(True) or True)
    _jogador(1, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    ctx = _ctx(1)
    asyncio.run(bot.viajar.callback(ctx, destino=15))
    assert db.get_jogador(1)["mundo"] == "torre"   # chegou, sem desvio de encontro
    assert chamou == []


# ==================================================================
# commit 2 -- os ladrões, de 1 a 4
# ==================================================================

def test_grupo_sempre_entre_um_e_quatro():
    j = _jogador(1, andar_max=5)
    for _ in range(60):
        grupo = estrada.sortear_grupo(j)
        assert estrada.GRUPO_MIN <= len(grupo) <= estrada.GRUPO_MAX


def test_grupo_nunca_tem_nomes_repetidos():
    j = _jogador(1, andar_max=5)
    for _ in range(60):
        grupo = estrada.sortear_grupo(j)
        nomes = [b["nome"] for b in grupo]
        assert len(nomes) == len(set(nomes))


def test_bandidos_nunca_dao_xp_nem_moedas():
    j = _jogador(1, andar_max=5)
    for _ in range(20):
        for bandido in estrada.sortear_grupo(j):
            assert bandido["xp"] == 0
            assert bandido["moedas"] == 0


def test_bandidos_falam():
    j = _jogador(1, andar_max=5)
    grupo = estrada.sortear_grupo(j)
    assert all(b.get("fala") for b in grupo)


def test_grupo_de_um_leva_o_hp_e_atk_cheios_do_andar_de_referencia(monkeypatch):
    """Um grupo de tamanho 1 não divide nada -- é o próprio monstro de
    referência, hp e atk cheios."""
    monkeypatch.setattr(estrada.random, "randint", lambda a, b: 1)
    j = _jogador(1, andar_max=6)
    referencia = incursao.andar_referencia(j)
    grupo = estrada.sortear_grupo(j)
    assert len(grupo) == 1
    possiveis_hp = {m["hp"] for m in game_data.ANDARES[referencia]["monstros"]}
    possiveis_atk = {m["atk"] for m in game_data.ANDARES[referencia]["monstros"]}
    assert grupo[0]["hp"] in possiveis_hp
    assert grupo[0]["atk"] in possiveis_atk


def test_grupo_de_quatro_nao_e_quatro_vezes_um(monkeypatch):
    """'Um grupo de quatro não pode ser quatro vezes um' -- hp/atk por
    bandido ficam por volta de 1/4 do monstro de referência, calibrando
    o TOTAL do grupo contra o jogador, não cada bandido isolado."""
    monkeypatch.setattr(estrada.random, "randint", lambda a, b: 4)
    j = _jogador(1, andar_max=6)
    referencia = incursao.andar_referencia(j)
    grupo = estrada.sortear_grupo(j)
    assert len(grupo) == 4
    hp_max_base = max(m["hp"] for m in game_data.ANDARES[referencia]["monstros"])
    for bandido in grupo:
        assert bandido["hp"] <= hp_max_base // 4 + 1
        assert bandido["hp"] >= 1   # nunca zera


def test_defesa_do_bandido_nao_divide_pelo_tamanho_do_grupo(monkeypatch):
    """A defesa não soma entre bandidos do jeito que hp/atk somam --
    fica igual à do monstro de referência não importa o tamanho do
    grupo."""
    j = _jogador(1, andar_max=6)
    referencia = incursao.andar_referencia(j)
    possiveis_def = {m["def"] for m in game_data.ANDARES[referencia]["monstros"]}

    monkeypatch.setattr(estrada.random, "randint", lambda a, b: 1)
    grupo_1 = estrada.sortear_grupo(j)
    monkeypatch.setattr(estrada.random, "randint", lambda a, b: 4)
    grupo_4 = estrada.sortear_grupo(j)

    assert all(b["def"] in possiveis_def for b in grupo_1)
    assert all(b["def"] in possiveis_def for b in grupo_4)


def test_escalonamento_usa_andar_max_nao_o_andar_congelado(monkeypatch):
    """Fora da torre `andar` é só congelado (Step B) -- escalar por ele
    seria escalar por onde o jogador estava quando saiu, não por quanto
    ele progrediu de verdade. Trava o grupo em tamanho 1 (sem divisão)
    pra comparar hp bruto direto contra o andar de cada um."""
    monkeypatch.setattr(estrada.random, "randint", lambda a, b: 1)
    fraco = _jogador(1, andar=15, andar_max=2)
    forte = _jogador(2, andar=15, andar_max=9)   # mesmo andar congelado, andar_max bem diferente

    hp_fraco = {m["hp"] for m in game_data.ANDARES[2]["monstros"]}
    hp_forte = {m["hp"] for m in game_data.ANDARES[9]["monstros"]}
    assert not (hp_fraco & hp_forte)   # garantia de que os dois andares têm HP distinto

    grupo_fraco = estrada.sortear_grupo(fraco)
    grupo_forte = estrada.sortear_grupo(forte)
    assert grupo_fraco[0]["hp"] in hp_fraco
    assert grupo_forte[0]["hp"] in hp_forte


# ==================================================================
# grupo real dentro de uma Luta -- cada bandido com estado independente
# (usa a lista de inimigos de verdade, não a ponte inimigos[0])
# ==================================================================

def test_grupo_de_quatro_cada_bandido_tem_hp_independente():
    c = _combatente(1, classe="guerreiro", forca=20, andar_max=6)
    grupo = [
        {"nome": "A", "hp": 40, "atk": 5, "def": 0, "xp": 0, "moedas": 0},
        {"nome": "B", "hp": 40, "atk": 5, "def": 0, "xp": 0, "moedas": 0},
        {"nome": "C", "hp": 40, "atk": 5, "def": 0, "xp": 0, "moedas": 0},
        {"nome": "D", "hp": 40, "atk": 5, "def": 0, "xp": 0, "moedas": 0},
    ]
    luta = combate.Luta([c], grupo, andar_num=6)
    assert len(luta.inimigos) == 4

    luta.inimigos[1].hp -= 15

    assert luta.inimigos[0].hp == 40
    assert luta.inimigos[1].hp == 25
    assert luta.inimigos[2].hp == 40
    assert luta.inimigos[3].hp == 40


def test_derrotar_um_bandido_nao_encerra_o_grupo_de_quatro():
    c = _combatente(1, classe="guerreiro", forca=20, andar_max=6)
    grupo = [{"nome": n, "hp": 10, "atk": 1, "def": 0, "xp": 0, "moedas": 0} for n in "ABCD"]
    luta = combate.Luta([c], grupo, andar_num=6)
    luta.inimigos[0].hp = 0

    assert luta.inimigos_ativos == luta.inimigos[1:]
    assert len(luta.inimigos_ativos) == 3


# ==================================================================
# Luta.embed mostra TODOS os inimigos -- não só o principal
# ==================================================================

def test_embed_mostra_um_campo_por_bandido():
    c = _combatente(1, classe="guerreiro", forca=20, andar_max=6)
    grupo = [{"nome": n, "hp": 30, "atk": 1, "def": 0, "xp": 0, "moedas": 0} for n in ("Um", "Dois", "Três")]
    luta = combate.Luta([c], grupo, andar_num=6)
    e = luta.embed()
    nomes_nos_fields = [f.name for f in e.fields]
    assert "Um" in nomes_nos_fields
    assert "Dois" in nomes_nos_fields
    assert "Três" in nomes_nos_fields


def test_embed_marca_bandido_derrotado_mas_continua_mostrando():
    c = _combatente(1, classe="guerreiro", forca=20, andar_max=6)
    grupo = [{"nome": "Vivo", "hp": 30, "atk": 1, "def": 0, "xp": 0, "moedas": 0},
             {"nome": "Morto", "hp": 30, "atk": 1, "def": 0, "xp": 0, "moedas": 0}]
    luta = combate.Luta([c], grupo, andar_num=6)
    luta.inimigos[1].hp = 0
    e = luta.embed()
    campo_morto = next(f for f in e.fields if f.name.startswith("Morto"))
    assert "derrotado" in campo_morto.name.lower()


def test_embed_solo_continua_mostrando_um_campo_so_regressao():
    """Regressão: pra qualquer luta de hoje (chefe da torre, sempre um
    inimigo só), o embed continua mostrando exatamente um field pro
    inimigo -- byte a byte igual ao de antes do Step E."""
    c = _combatente(1, classe="guerreiro", forca=20, andar_max=6)
    luta = combate.Luta([c], {"nome": "Chefinho", "hp": 100, "atk": 5, "def": 0, "xp": 10, "moedas": 10}, andar_num=1)
    e = luta.embed()
    nomes_de_inimigo = [f.name for f in e.fields if f.name == "Chefinho"]
    assert len(nomes_de_inimigo) == 1


# ==================================================================
# commit 3 -- perder é ser roubado
# ==================================================================

def test_roubar_nada_pra_levar_nao_registra_roubo_nenhum():
    _jogador(1, moedas=0)
    msg = estrada.roubar(1)
    assert "não tinha nada" in msg.lower()
    assert db.roubos_pendentes(1) == []


def test_roubar_sem_moedas_forca_peca():
    _jogador(1, moedas=0, arma="lamina_selo", arma_instancia_id=None)
    estrada.roubar(1)
    pendentes = db.roubos_pendentes(1)
    assert len(pendentes) == 1
    assert pendentes[0]["tipo"] == "item"


def test_roubar_sem_peca_equipada_forca_moedas():
    _jogador(1, moedas=1000)
    estrada.roubar(1)
    pendentes = db.roubos_pendentes(1)
    assert len(pendentes) == 1
    assert pendentes[0]["tipo"] == "moedas"


def test_roubar_dinheiro_e_peca_os_dois_acontecem_em_muitas_tentativas():
    tipos = set()
    for i in range(60):
        _jogador(i, moedas=1000, arma="lamina_selo", arma_instancia_id=None)
        estrada.roubar(i)
        tipos.add(db.roubos_pendentes(i)[0]["tipo"])
    assert tipos == {"moedas", "item"}


def test_roubar_moedas_deduz_do_jogador_e_registra_o_valor():
    j = _jogador(1, moedas=1000)
    estrada.roubar(1)
    depois = db.get_jogador(1)
    pendente = db.roubos_pendentes(1)[0]
    assert pendente["tipo"] == "moedas"
    assert depois["moedas"] == j["moedas"] - pendente["valor"]
    assert pendente["valor"] > 0


def test_roubar_peca_sem_instancia_desequipa_e_registra_sem_instancia_id():
    _jogador(1, moedas=0, arma="lamina_selo", arma_instancia_id=None)
    estrada.roubar(1)
    depois = db.get_jogador(1)
    assert depois["arma"] is None
    pendente = db.roubos_pendentes(1)[0]
    assert pendente["item"] == "lamina_selo"
    assert pendente["instancia_id"] is None


def test_roubar_peca_com_instancia_guarda_a_instancia_inteira():
    """'Minha recomendação: guarda a instância inteira' -- melhoria e
    encantamento sobrevivem ao roubo, só o dono muda (fica NULL
    enquanto pendente)."""
    _jogador(1, moedas=0)
    instancia_id = db.criar_instancia(1, "lamina_selo", nivel_melhoria=3)
    db.definir_encantamento(instancia_id, "forca", 7)
    db.atualizar_jogador(1, arma="lamina_selo", arma_instancia_id=instancia_id)

    estrada.roubar(1)

    depois = db.get_jogador(1)
    assert depois["arma"] is None
    assert depois["arma_instancia_id"] is None
    instancia = db.get_instancia(instancia_id)
    assert instancia["nivel_melhoria"] == 3          # intacta
    assert instancia["encantamento_atributo"] == "forca"
    assert instancia["encantamento_valor"] == 7
    assert instancia["dono"] is None                 # solta, some da mochila
    assert instancia_id not in [i["id"] for i in db.instancias_na_mochila(1)]

    pendente = db.roubos_pendentes(1)[0]
    assert pendente["instancia_id"] == instancia_id


def test_roubar_nunca_mexe_em_andar_ou_andar_max():
    """A estrada pune com prejuízo, não com a reconquista da torre --
    isso é penalidade de morte (bot.processar_morte), nunca daqui."""
    j = _jogador(1, moedas=1000, andar=12, andar_max=14)
    estrada.roubar(1)
    depois = db.get_jogador(1)
    assert depois["andar"] == 12
    assert depois["andar_max"] == 14


def test_derrota_na_estrada_chama_roubar_e_mostra_no_embed(monkeypatch):
    c = _combatente(1, classe="guerreiro", forca=20, moedas=1000, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    luta = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    c.hp = 0
    c.caiu = True

    e = asyncio.run(estrada._finalizar_derrota_estrada(luta, 1, mundo.VILAREJO))

    assert len(db.roubos_pendentes(1)) == 1
    campo_assaltado = next(f for f in e.fields if f.name == "Assaltado")
    assert "Levaram" in campo_assaltado.value


# ==================================================================
# commit 4 -- o revide
# ==================================================================

def test_devolver_sem_nada_pendente_devolve_none():
    _jogador(1, moedas=1000)
    assert estrada.devolver_um_roubo(1) is None


def test_devolver_moedas_soma_de_volta_e_apaga_o_roubo():
    j = _jogador(1, moedas=1000)
    estrada.roubar(1)   # nesse jogador só há moedas pra roubar
    perdido = j["moedas"] - db.get_jogador(1)["moedas"]

    msg = estrada.devolver_um_roubo(1)

    assert "Devolveram" in msg
    assert db.get_jogador(1)["moedas"] == j["moedas"]   # voltou ao valor original
    assert db.roubos_pendentes(1) == []
    assert perdido > 0


def test_devolver_item_sem_instancia_devolve_pra_mochila():
    _jogador(1, moedas=0, arma="lamina_selo", arma_instancia_id=None)
    estrada.roubar(1)   # sem moedas -- força peça

    estrada.devolver_um_roubo(1)

    assert db.tem_item(1, "lamina_selo", 1)
    assert db.roubos_pendentes(1) == []


def test_devolver_item_com_instancia_restaura_o_dono():
    _jogador(1, moedas=0)
    instancia_id = db.criar_instancia(1, "lamina_selo", nivel_melhoria=2)
    db.definir_encantamento(instancia_id, "forca", 4)
    db.atualizar_jogador(1, arma="lamina_selo", arma_instancia_id=instancia_id)
    estrada.roubar(1)
    assert db.get_instancia(instancia_id)["dono"] is None

    estrada.devolver_um_roubo(1)

    instancia = db.get_instancia(instancia_id)
    assert instancia["dono"] == 1
    assert instancia["nivel_melhoria"] == 2          # intacta
    assert instancia["encantamento_atributo"] == "forca"
    assert instancia["encantamento_valor"] == 4
    assert instancia_id in [i["id"] for i in db.instancias_na_mochila(1)]
    assert db.roubos_pendentes(1) == []


def test_grupo_diferente_devolve_o_que_outro_grupo_levou():
    """'Não precisa ser o mesmo que roubou' -- o roubo é registrado por
    JOGADOR, não por grupo de bandidos. Qualquer vitória de estrada
    posterior devolve, mesmo vindo de outro encontro."""
    c = _combatente(1, classe="guerreiro", forca=999, moedas=1000, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    grupo_1 = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    c.hp = 0
    c.caiu = True
    asyncio.run(estrada._finalizar_derrota_estrada(grupo_1, 1, mundo.VILAREJO))
    assert len(db.roubos_pendentes(1)) == 1

    j2 = db.get_jogador(1)
    c2 = combate.Combatente(j2, bot.stats(j2))
    grupo_2 = combate.Luta([c2], estrada.sortear_grupo(c2.jogador), andar_num=15)
    for inimigo in grupo_2.inimigos:
        inimigo.hp = 0

    e = asyncio.run(estrada._finalizar_vitoria_estrada(grupo_2, 1, mundo.MIRANTE))

    assert db.roubos_pendentes(1) == []
    assert any(f.name == "🤝 O revide" for f in e.fields)


def test_duas_perdas_acumuladas_uma_vitoria_devolve_so_uma():
    """'Uma por vitória dá mais vida à estrada' -- decisão registrada e
    testada: uma vitória nunca zera mais de um roubo pendente."""
    _jogador(1, moedas=1000, arma="lamina_selo", arma_instancia_id=None)
    estrada.roubar(1)   # primeira perda
    db.atualizar_jogador(1, moedas=1000)   # garante moedas de novo pro segundo roubo
    estrada.roubar(1)   # segunda perda
    assert len(db.roubos_pendentes(1)) == 2

    estrada.devolver_um_roubo(1)

    assert len(db.roubos_pendentes(1)) == 1


def test_devolucao_e_fifo_o_mais_antigo_primeiro():
    _jogador(1, moedas=1000, arma="lamina_selo", arma_instancia_id=None)
    estrada.roubar(1)
    primeiro_roubo_id = db.roubos_pendentes(1)[0]["id"]
    db.atualizar_jogador(1, moedas=1000, armadura="couro_batido", armadura_instancia_id=None)
    estrada.roubar(1)
    assert len(db.roubos_pendentes(1)) == 2

    estrada.devolver_um_roubo(1)

    restantes = db.roubos_pendentes(1)
    assert len(restantes) == 1
    assert restantes[0]["id"] != primeiro_roubo_id   # o mais antigo foi o que saiu


def test_vitoria_sem_nada_pendente_nao_mostra_campo_de_revide():
    c = _combatente(1, classe="guerreiro", forca=20, mundo_atual=mundo.MIRANTE, andar=15, andar_max=15)
    luta = combate.Luta([c], estrada.sortear_grupo(c.jogador), andar_num=15)
    for inimigo in luta.inimigos:
        inimigo.hp = 0

    e = asyncio.run(estrada._finalizar_vitoria_estrada(luta, 1, mundo.VILAREJO))

    assert not any(f.name == "🤝 O revide" for f in e.fields)
