# tests/test_mago_raio.py
# Step 2b, commit 3: Interrupção (skill) e Reflexos (passiva) do Mago de
# Raio. Reflexos foi reescrita numa correção posterior -- ver decisoes.md
# § Step 2b (correção): a versão original (iniciativa garantida na rodada
# 1) era no-op porque RODADA_1_SEM_CHEFE já garante isso pra todo mundo.
import bot
import combate
import condicoes
import database as db
import game_data
import habilidades as hab

CHEFE_TESTE = {"nome": "Testinho", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0}


def _combatente(user_id, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


def _sem_variancia(monkeypatch):
    monkeypatch.setattr(combate.random, "uniform", lambda a, b: 1.0)
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita, nunca proca a arma


# ==================================================================
# Gate de ascensão
# ==================================================================

def test_nao_ascendido_nao_conhece_interrupcao():
    j = _combatente(1, classe="mago", inteligencia=20).jogador
    assert "interrupcao" not in hab.conhecidas(j)


def test_mago_raio_conhece_interrupcao():
    j = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio").jogador
    assert "interrupcao" in hab.conhecidas(j)


def test_interrupcao_nao_tem_requisito_de_atributo():
    """A ascensão É o requisito -- ver decisoes.md § Step 2a."""
    assert "requisito" not in game_data.HABILIDADES["interrupcao"]


# ==================================================================
# Dano -- passa por at.aplicar_defesa (ver decisoes.md § Step 2b)
# ==================================================================

def test_interrupcao_aplica_a_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    dados = game_data.HABILIDADES["interrupcao"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    combate._efeito_interrupcao(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    c2 = _combatente(2, classe="mago", inteligencia=20, ascensao="mago_raio")
    luta_com_def = combate.Luta([c2], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_interrupcao(luta_com_def, c2, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def < dano_sem_def


# ==================================================================
# Interrupção -- cancela o golpe carregado, e SÓ isso
# ==================================================================

def test_interrupcao_cancela_a_carga_e_o_golpe_seguinte_do_chefe_nao_e_carregado(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    dados = game_data.HABILIDADES["interrupcao"]
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    luta.carregando = True

    combate._efeito_interrupcao(luta, c, dados)

    assert luta.carregando is False

    # rodada seguinte: turno_do_chefe não pode soltar o golpe carregado --
    # espiona dano_do_chefe pra confirmar carregado=False (nunca o 3x)
    chamadas = []
    original = combate.dano_do_chefe

    def _espiao(chefe, s, andar_num, defendendo=False, carregado=False):
        chamadas.append(carregado)
        return original(chefe, s, andar_num, defendendo=defendendo, carregado=carregado)

    monkeypatch.setattr(combate, "dano_do_chefe", _espiao)
    luta.rodada = 2   # RODADA_1_SEM_CHEFE só trava a rodada 1
    luta.turno_do_chefe()

    assert chamadas == [False]


def test_interrupcao_contra_chefe_nao_carregando_e_so_dano(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    dados = game_data.HABILIDADES["interrupcao"]
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    assert luta.carregando is False

    combate._efeito_interrupcao(luta, c, dados)

    assert luta.carregando is False   # continua False -- não tinha nada pra cancelar
    assert luta.hp_chefe < luta.hp_chefe_max   # mas o dano aconteceu normalmente


def test_interrupcao_nao_cancela_nada_alem_da_carga(monkeypatch):
    """Fronteira dura: preparando_condicao é OUTRO estado de ação do chefe
    (telegraph elemental, andares 11+, roda independente do golpe
    carregado -- ver Luta._talvez_telegrafar_condicao) que também pode
    estar pendente na mesma rodada. Interrupção cancela `carregando` e
    NADA mais -- se alguém um dia generalizar isto pra "cancela qualquer
    ação pendente do chefe", este teste cai."""
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    dados = game_data.HABILIDADES["interrupcao"]
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    luta.carregando = True
    luta.preparando_condicao = {"tipo": "vulneravel", "nome": "Marca", "emoji": "✨", "alvo_id": c.id}

    combate._efeito_interrupcao(luta, c, dados)

    assert luta.carregando is False                    # isto, cancela
    assert luta.preparando_condicao is not None         # isto, NUNCA -- não é carga


# ==================================================================
# Reflexos -- 35% de chance de escapar ILESO só do golpe CARREGADO (ver
# decisoes.md § Step 2b correção -- a versão de iniciativa era no-op
# porque RODADA_1_SEM_CHEFE já garantia isso de graça pra todo mundo)
# ==================================================================

def _forcar_golpe_carregado(luta, monkeypatch):
    """Chefe já está carregando; força o ramo `elif self.carregando` de
    Luta.turno_do_chefe (sem erro de Corrente, sem condição pendente).
    rodada=2 pula RODADA_1_SEM_CHEFE, que travaria o chefe inteiro na
    rodada 1 -- sem isso nenhum dos dois ramos abaixo seria alcançado."""
    luta.carregando = True
    luta.rodada = 2
    monkeypatch.setattr(condicoes, "chance_de_erro", lambda *a, **k: 0.0)


def test_golpe_carregado_numa_party_mista_so_o_mago_de_raio_pode_errar(monkeypatch):
    raio = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    sem_ascensao = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([raio, sem_ascensao], {**CHEFE_TESTE, "atk": 50}, andar_num=1)
    _forcar_golpe_carregado(luta, monkeypatch)
    # abaixo de 0.35 (chance do raio) mas não usado pro sem_ascensao (chance 0.0 -- nunca erra)
    monkeypatch.setattr(combate.random, "random", lambda: 0.30)
    hp_raio_antes, hp_sem_antes = raio.hp, sem_ascensao.hp

    luta.turno_do_chefe()

    assert raio.hp == hp_raio_antes        # errou -- Reflexos consultado com 0.30 < 0.35
    assert sem_ascensao.hp < hp_sem_antes  # tomou o golpe normal, sem chance de errar


def test_reflexos_so_vale_no_golpe_carregado_nao_no_ataque_normal(monkeypatch):
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    luta = combate.Luta([c], {**CHEFE_TESTE, "atk": 50}, andar_num=1)
    luta.carregando = False   # ataque normal, não carregado
    luta.rodada = 2           # pula RODADA_1_SEM_CHEFE
    monkeypatch.setattr(condicoes, "chance_de_erro", lambda *a, **k: 0.0)
    monkeypatch.setattr(combate, "CHANCE_CARREGAR", 0.0)   # não deixa o chefe decidir carregar em vez de atacar
    monkeypatch.setattr(combate.at, "chance_esquiva", lambda *a, **k: 0.0)   # sem esquiva de sorte
    monkeypatch.setattr(combate.random, "random", lambda: 0.30)   # abaixo dos 0.35 do Reflexos, se ele valesse aqui
    hp_antes = c.hp

    luta.turno_do_chefe()

    assert c.hp < hp_antes   # ataque normal acerta na taxa de sempre -- Reflexos não se aplica aqui


def test_reflexos_nao_cancela_a_carga_nem_protege_os_outros_alvos(monkeypatch):
    raio = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    outro = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([raio, outro], {**CHEFE_TESTE, "atk": 50}, andar_num=1)
    _forcar_golpe_carregado(luta, monkeypatch)
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)   # garante o miss do raio (0.0 < 0.35)
    hp_outro_antes = outro.hp

    luta.turno_do_chefe()

    assert luta.carregando is False    # a carga resolveu (consumida) mesmo com o miss individual
    assert outro.hp < hp_outro_antes   # o outro alvo tomou o golpe carregado normalmente


def test_sem_ascensao_ou_outro_ramo_nunca_erra_o_carregado(monkeypatch):
    sem_ascensao = _combatente(1, classe="mago", inteligencia=20)
    outro_ramo = _combatente(2, classe="mago", inteligencia=20, ascensao="mago_gelo")
    luta = combate.Luta([sem_ascensao, outro_ramo], {**CHEFE_TESTE, "atk": 50}, andar_num=1)
    _forcar_golpe_carregado(luta, monkeypatch)
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)   # o mínimo possível -- erraria com QUALQUER chance > 0
    hp_sem_antes, hp_gelo_antes = sem_ascensao.hp, outro_ramo.hp

    luta.turno_do_chefe()

    assert sem_ascensao.hp < hp_sem_antes
    assert outro_ramo.hp < hp_gelo_antes


def test_resolver_abertura_do_chefe_continua_no_op_sem_reflexos_nenhum():
    """A versão antiga (iniciativa garantida) saiu -- ver decisoes.md §
    Step 2b correção. Esta função continua existindo só como o código
    morto que já era antes do Step 2b (RODADA_1_SEM_CHEFE=True sempre)."""
    c = _combatente(1, classe="mago", inteligencia=20, ascensao="mago_raio")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    hp_antes = c.hp

    combate._resolver_abertura_do_chefe(luta, [c], andar_num=1)

    assert c.hp == hp_antes
