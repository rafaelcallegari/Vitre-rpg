# tests/test_espadachim.py
# Step 2c, commit 3: Sequência (skill) e Fio da Lâmina (passiva) do
# Espadachim. Fio da Lâmina retrofita TODO ponto de dano-com-defesa do
# motor (ataque normal e toda skill anterior) -- ver decisoes.md § Step 2c.
import atributos as at
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
    monkeypatch.setattr(combate.random, "uniform", lambda a, b: 1.0)
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita, nunca proca a arma


# ==================================================================
# Gate de ascensão
# ==================================================================

def test_nao_ascendido_nao_conhece_sequencia():
    j = _combatente(1, classe="guerreiro", forca=20).jogador
    assert "sequencia" not in hab.conhecidas(j)


def test_espadachim_conhece_sequencia():
    j = _combatente(1, classe="guerreiro", forca=20, ascensao="espadachim").jogador
    assert "sequencia" in hab.conhecidas(j)


def test_sequencia_nao_tem_requisito_de_atributo():
    """A ascensão É o requisito -- ver decisoes.md § Step 2a."""
    assert "requisito" not in game_data.HABILIDADES["sequencia"]


# ==================================================================
# Sequência -- 3 golpes, cada um mais forte, cada um com crítico separado
# ==================================================================

def test_sequencia_aplica_a_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="espadachim")
    dados = game_data.HABILIDADES["sequencia"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    combate._efeito_sequencia(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    luta_com_def = combate.Luta([c], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_sequencia(luta_com_def, c, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def < dano_sem_def


def test_sequencia_cada_golpe_usa_o_multiplicador_certo_da_tupla(monkeypatch):
    """Os 3 multiplicadores vêm de MULTIPLICADORES_SEQUENCIA, não de 3
    constantes soltas -- prova golpe a golpe, com defesa zero pra isolar
    só o multiplicador."""
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="espadachim")
    dados = game_data.HABILIDADES["sequencia"]
    chefe_sem_def = {**CHEFE_TESTE, "def": 0}
    base = hab.poder_base(c.jogador, combate._bonus_arma_de(c)) * combate._multiplicador_afinidade(c)

    for multiplicador in combate.MULTIPLICADORES_SEQUENCIA:
        luta = combate.Luta([c], chefe_sem_def, andar_num=1)
        dano_golpe_unico = int(combate._rolar_dano_habilidade(luta, c, multiplicador))
        assert dano_golpe_unico == max(1, int(base * multiplicador))


def test_sequencia_soma_dos_tres_multiplicadores_e_2_0():
    assert sum(combate.MULTIPLICADORES_SEQUENCIA) == 2.0


def test_sequencia_tres_golpes_cada_um_pode_critar_separado(monkeypatch):
    """Mesmo padrão do Corte Rápido: cada golpe rola crítico com o próprio
    random(), não um crítico só valendo pros três."""
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="espadachim", destreza=1)
    dados = game_data.HABILIDADES["sequencia"]
    luta = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)

    chamadas = {"n": 0}
    original = combate.random.random

    def _contar(*a, **k):
        chamadas["n"] += 1
        return original(*a, **k)

    monkeypatch.setattr(combate.random, "random", _contar)
    combate._efeito_sequencia(luta, c, dados)

    assert chamadas["n"] >= 3   # pelo menos uma rolagem de crítico por golpe (mais as da arma elemental)


# ==================================================================
# Fio da Lâmina -- perfuração PARCIAL (nunca pula aplicar_defesa), vale no
# ataque normal E em toda skill (retrofit do motor inteiro)
# ==================================================================

def test_defesa_efetiva_reduz_25_por_cento_pra_quem_tem_fio_da_lamina():
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="espadachim")
    luta = combate.Luta([c], {**CHEFE_TESTE, "def": 100}, andar_num=1)

    assert combate._defesa_efetiva(luta, c) == 75.0   # 100 * (1 - 0.25)


def test_defesa_efetiva_e_a_crua_pra_quem_nao_tem_a_passiva():
    c = _combatente(1, classe="guerreiro", forca=20)   # sem ascensão
    luta = combate.Luta([c], {**CHEFE_TESTE, "def": 100}, andar_num=1)

    assert combate._defesa_efetiva(luta, c) == 100


def test_fio_da_lamina_vale_no_ataque_normal(monkeypatch):
    _sem_variancia(monkeypatch)
    com = _combatente(1, classe="guerreiro", forca=20, ascensao="espadachim")
    sem = _combatente(2, classe="guerreiro", forca=20)
    # def=40 fica ABAIXO do teto de redução (60%, alcançado a partir de 75
    # de defesa) -- em def=100 os dois lados já bateriam no teto igual e a
    # diferença de 25% desapareceria por coincidência, não provando nada
    luta = combate.Luta([com, sem], {**CHEFE_TESTE, "def": 40}, andar_num=1)

    dano_com, _ = combate._rolar_ataque_normal(luta, com, com.s["atk"], combate._defesa_efetiva(luta, com), com.s["critico"])
    dano_sem, _ = combate._rolar_ataque_normal(luta, sem, sem.s["atk"], combate._defesa_efetiva(luta, sem), sem.s["critico"])

    assert dano_com > dano_sem   # mesma base (mesma força), defesa efetiva menor pra quem tem a passiva


def test_fio_da_lamina_vale_em_skills_anteriores_ao_espadachim(monkeypatch):
    """A retrofit precisa valer em TODA skill que já existia, não só na
    Sequência -- Golpe Aberto (Step 1, Guerreiro base) é o exemplo aqui."""
    _sem_variancia(monkeypatch)
    dados = game_data.HABILIDADES["golpe_aberto"]

    com = _combatente(1, classe="guerreiro", forca=20, ascensao="espadachim")
    luta_com = combate.Luta([com], {**CHEFE_TESTE, "def": 40}, andar_num=1)   # abaixo do teto -- ver nota acima
    combate._efeito_golpe_aberto(luta_com, com, dados)
    dano_com = luta_com.hp_chefe_max - luta_com.hp_chefe

    sem = _combatente(2, classe="guerreiro", forca=20)
    luta_sem = combate.Luta([sem], {**CHEFE_TESTE, "def": 40}, andar_num=1)
    combate._efeito_golpe_aberto(luta_sem, sem, dados)
    dano_sem = luta_sem.hp_chefe_max - luta_sem.hp_chefe

    assert dano_com > dano_sem


def test_fio_da_lamina_nunca_pula_aplicar_defesa_e_so_perfuracao_parcial():
    """Perfuração PARCIAL: com defesa alta o suficiente, ainda sobra
    redução -- não vira Dardo Arcano/Flecha Perfurante (defesa zero)."""
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="espadachim")
    luta = combate.Luta([c], {**CHEFE_TESTE, "def": 1000}, andar_num=1)

    defesa_efetiva = combate._defesa_efetiva(luta, c)
    assert defesa_efetiva == 750.0   # 1000 * 0.75 -- não é 0
    assert at.reducao_dano(defesa_efetiva) > 0   # ainda reduz dano, só menos
