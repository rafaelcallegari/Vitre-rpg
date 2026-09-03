# tests/test_ladino.py
# Step 2a, commit 2: as duas skills do Ladino (Golpe Fatal/assassino,
# Flecha Perfurante/arqueiro) e as duas passivas de combate (Sangue
# Frio/assassino, Olho de Águia/arqueiro). Ver decisoes.md § Step 2a.
import bot
import combate
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
    """Trava ±15%/crítico num valor fixo -- mesmo truque de test_condicoes.py."""
    monkeypatch.setattr(combate.random, "uniform", lambda a, b: 1.0)
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita "de sorte"


# ==================================================================
# Gate de ascensão nas skills -- "rpg habilidades" só mostra (e só deixa
# lançar, via hab.lancaveis) quem está no ramo certo
# ==================================================================

def test_nao_ascendido_nao_conhece_nenhuma_das_duas_skills():
    j = _combatente(1, classe="ladino", destreza=20).jogador
    conhec = hab.conhecidas(j)
    assert "golpe_fatal" not in conhec
    assert "flecha_perfurante" not in conhec


def test_assassino_conhece_golpe_fatal_mas_nao_flecha_perfurante():
    j = _combatente(1, classe="ladino", destreza=20, ascensao="assassino").jogador
    conhec = hab.conhecidas(j)
    assert "golpe_fatal" in conhec
    assert "flecha_perfurante" not in conhec


def test_arqueiro_conhece_flecha_perfurante_mas_nao_golpe_fatal():
    j = _combatente(1, classe="ladino", destreza=20, ascensao="arqueiro").jogador
    conhec = hab.conhecidas(j)
    assert "flecha_perfurante" in conhec
    assert "golpe_fatal" not in conhec


def test_skills_de_ascensao_nao_tem_requisito_de_atributo():
    """A ascensão É o requisito -- ver decisoes.md § Step 2a."""
    assert "requisito" not in game_data.HABILIDADES["golpe_fatal"]
    assert "requisito" not in game_data.HABILIDADES["flecha_perfurante"]


def test_classe_wiki_mostra_o_requisito_de_ascensao_das_duas_skills():
    e = bot.embed_info_classe("ladino")
    campo_golpe = next(f for f in e.fields if "Golpe Fatal" in f.name)
    campo_flecha = next(f for f in e.fields if "Flecha Perfurante" in f.name)
    assert "requer ascensão: Assassino" in campo_golpe.name
    assert "requer ascensão: Arqueiro" in campo_flecha.name


# ==================================================================
# Golpe Fatal (assassino) -- escala com o HP que o chefe já perdeu
# ==================================================================

def test_golpe_fatal_causa_mais_dano_quanto_mais_baixo_o_hp_do_alvo(monkeypatch):
    _sem_variancia(monkeypatch)
    dados = game_data.HABILIDADES["golpe_fatal"]

    c_cheio = _combatente(1, classe="ladino", destreza=20, ascensao="assassino")
    luta_cheio = combate.Luta([c_cheio], CHEFE_TESTE, andar_num=1)
    luta_cheio.rodada = 2   # fora da rodada 1 -- não entra o Sangue Frio, só o formato do golpe
    combate._efeito_golpe_fatal(luta_cheio, c_cheio, dados)
    dano_cheio = luta_cheio.hp_chefe_max - luta_cheio.hp_chefe

    c_baixo = _combatente(2, classe="ladino", destreza=20, ascensao="assassino")
    luta_baixo = combate.Luta([c_baixo], CHEFE_TESTE, andar_num=1)
    luta_baixo.rodada = 2
    luta_baixo.hp_chefe = 1   # o chefe já está agonizando quando o golpe acontece
    hp_antes = luta_baixo.hp_chefe
    combate._efeito_golpe_fatal(luta_baixo, c_baixo, dados)
    dano_baixo = hp_antes - luta_baixo.hp_chefe

    assert dano_baixo > dano_cheio


def test_golpe_fatal_aplica_a_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="ladino", destreza=20, ascensao="assassino")
    dados = game_data.HABILIDADES["golpe_fatal"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    luta_sem_def.rodada = 2
    combate._efeito_golpe_fatal(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    luta_com_def = combate.Luta([c], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    luta_com_def.rodada = 2
    combate._efeito_golpe_fatal(luta_com_def, c, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def < dano_sem_def


# ==================================================================
# Flecha Perfurante (arqueiro) -- ignora a defesa do chefe
# ==================================================================

def test_flecha_perfurante_ignora_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="ladino", destreza=20, ascensao="arqueiro")
    dados = game_data.HABILIDADES["flecha_perfurante"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    combate._efeito_flecha_perfurante(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    luta_com_def = combate.Luta([c], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_flecha_perfurante(luta_com_def, c, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def == dano_sem_def


# ==================================================================
# Sangue Frio (assassino) -- primeiro golpe da rodada 1 crítica garantido,
# uma vez por combatente, não vaza entre membros da party
# ==================================================================

def test_rolar_critico_sangue_frio_dispara_uma_vez_por_combatente(monkeypatch):
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita de sorte
    c1 = _combatente(1, classe="ladino", ascensao="assassino")
    c2 = _combatente(2, classe="ladino", ascensao="assassino")
    luta = combate.Luta([c1, c2], CHEFE_TESTE, andar_num=1)   # rodada 1

    assert combate._rolar_critico(luta, c1) is True     # primeiro golpe de c1: garantido
    assert c1.sangue_frio_disparado is True
    assert combate._rolar_critico(luta, c1) is False    # segundo golpe de c1, mesma luta: não garante mais

    assert combate._rolar_critico(luta, c2) is True     # c2 é outro combatente -- não depende de c1
    assert c2.sangue_frio_disparado is True


def test_rolar_critico_sangue_frio_so_vale_na_rodada_1(monkeypatch):
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)
    c = _combatente(1, classe="ladino", ascensao="assassino")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    luta.rodada = 2

    assert combate._rolar_critico(luta, c) is False


def test_rolar_critico_neutro_pra_quem_nao_tem_sangue_frio(monkeypatch):
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)
    c = _combatente(1, classe="ladino", ascensao="arqueiro")   # outro ramo, sem Sangue Frio
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    assert combate._rolar_critico(luta, c) is False


def test_sangue_frio_realmente_eleva_o_dano_do_primeiro_golpe(monkeypatch):
    """random() sempre alto (nunca critaria de sorte) -- só sai maior se o
    Sangue Frio estiver forçando o crítico."""
    _sem_variancia(monkeypatch)
    dados = game_data.HABILIDADES["golpe_fatal"]

    c_com = _combatente(1, classe="ladino", destreza=20, ascensao="assassino")
    luta_com = combate.Luta([c_com], CHEFE_TESTE, andar_num=1)   # rodada 1 -- Sangue Frio entra
    combate._efeito_golpe_fatal(luta_com, c_com, dados)
    dano_com = luta_com.hp_chefe_max - luta_com.hp_chefe

    c_sem = _combatente(2, classe="ladino", destreza=20, ascensao="assassino")
    luta_sem = combate.Luta([c_sem], CHEFE_TESTE, andar_num=1)
    luta_sem.rodada = 2   # fora da rodada 1 -- Sangue Frio não se aplica
    combate._efeito_golpe_fatal(luta_sem, c_sem, dados)
    dano_sem = luta_sem.hp_chefe_max - luta_sem.hp_chefe

    assert dano_com > dano_sem


# ==================================================================
# Olho de Águia (arqueiro) -- aumenta o multiplicador do crítico, não a
# chance -- tem que valer nas DUAS rolagens (ataque normal e skill)
# ==================================================================

def test_olho_de_aguia_aumenta_o_dano_do_critico_no_ataque_normal(monkeypatch):
    _sem_variancia(monkeypatch)
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)   # sempre crita

    c_com = _combatente(1, classe="ladino", destreza=20, ascensao="arqueiro")
    luta_com = combate.Luta([c_com], CHEFE_TESTE, andar_num=1)
    dano_com, critico_com = combate._rolar_ataque_normal(luta_com, c_com, c_com.s["atk"], 0, c_com.s["critico"])

    c_sem = _combatente(2, classe="ladino", destreza=20)   # sem ascensão -- sem Olho de Águia
    luta_sem = combate.Luta([c_sem], CHEFE_TESTE, andar_num=1)
    dano_sem, critico_sem = combate._rolar_ataque_normal(luta_sem, c_sem, c_sem.s["atk"], 0, c_sem.s["critico"])

    assert critico_com and critico_sem   # os dois critaram -- random()=0.0 sempre passa
    assert dano_com > dano_sem


def test_olho_de_aguia_aumenta_o_dano_do_critico_na_skill(monkeypatch):
    _sem_variancia(monkeypatch)
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)   # sempre crita
    dados = game_data.HABILIDADES["flecha_perfurante"]

    c_com = _combatente(1, classe="ladino", destreza=20, ascensao="arqueiro")
    luta_com = combate.Luta([c_com], CHEFE_TESTE, andar_num=1)
    combate._efeito_flecha_perfurante(luta_com, c_com, dados)
    dano_com = luta_com.hp_chefe_max - luta_com.hp_chefe

    c_sem = _combatente(2, classe="ladino", destreza=20)   # sem ascensão -- sem Olho de Águia
    luta_sem = combate.Luta([c_sem], CHEFE_TESTE, andar_num=1)
    combate._efeito_flecha_perfurante(luta_sem, c_sem, dados)
    dano_sem = luta_sem.hp_chefe_max - luta_sem.hp_chefe

    assert dano_com > dano_sem
