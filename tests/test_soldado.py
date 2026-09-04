# tests/test_soldado.py
# Step 2c, commit 1: Muralha de Escudos (skill) e Disciplina (passiva) do
# Soldado. Ver decisoes.md § Step 2c.
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


def _sobrevive_n_ticks_e_expira_no_seguinte(luta, nome, n):
    """Mesma técnica de tests/test_condicoes.py (bloco 4, contrato N+1)."""
    for i in range(n):
        condicoes.tick(luta)
        assert any(c["nome"] == nome for c in luta.condicoes), f"'{nome}' sumiu cedo demais, tick {i + 1}/{n}"
    condicoes.tick(luta)
    assert not any(c["nome"] == nome for c in luta.condicoes), f"'{nome}' deveria ter expirado no tick {n + 1}"


# ==================================================================
# Gate de ascensão
# ==================================================================

def test_nao_ascendido_nao_conhece_muralha_de_escudos():
    j = _combatente(1, classe="guerreiro", forca=20).jogador
    assert "muralha_de_escudos" not in hab.conhecidas(j)


def test_soldado_conhece_muralha_de_escudos():
    j = _combatente(1, classe="guerreiro", forca=20, ascensao="soldado").jogador
    assert "muralha_de_escudos" in hab.conhecidas(j)


def test_muralha_de_escudos_nao_tem_requisito_de_atributo():
    """A ascensão É o requisito -- ver decisoes.md § Step 2a."""
    assert "requisito" not in game_data.HABILIDADES["muralha_de_escudos"]


# ==================================================================
# Dano -- passa por at.aplicar_defesa (ver decisoes.md § Step 2c)
# ==================================================================

def test_muralha_de_escudos_aplica_a_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="soldado")
    dados = game_data.HABILIDADES["muralha_de_escudos"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    combate._efeito_muralha_de_escudos(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    c2 = _combatente(2, classe="guerreiro", forca=20, ascensao="soldado")
    luta_com_def = combate.Luta([c2], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_muralha_de_escudos(luta_com_def, c2, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def < dano_sem_def


# ==================================================================
# Redireciona -- o chefe é obrigado a atacar o soldado por 2 rodadas
# (regra N+1: duracao guardada = 3)
# ==================================================================

def test_muralha_de_escudos_forca_o_chefe_a_atacar_por_2_rodadas(monkeypatch):
    """Não reusa o helper de nome (a condição de redireciona E a de
    reduz_dano compartilham o nome "Muralha de Escudos") -- conta ticks
    filtrando por tipo, pra provar a duração desta condição especificamente."""
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="soldado")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    combate._efeito_muralha_de_escudos(luta, c, game_data.HABILIDADES["muralha_de_escudos"])

    def _redireciona_ativo():
        return any(cc["tipo"] == "redireciona" and cc["valor"] == c.id for cc in luta.condicoes)

    assert _redireciona_ativo()
    for i in range(2):
        condicoes.tick(luta)
        assert _redireciona_ativo(), f"redireciona sumiu cedo demais, tick {i + 1}/2"
    condicoes.tick(luta)
    assert not _redireciona_ativo()


def test_alvo_forcado_aponta_pro_soldado_enquanto_o_redirecionamento_dura(monkeypatch):
    """condicoes.alvo_forcado (usado em Luta.turno_do_chefe) não tinha
    nenhum usuário no jogo até esta skill -- prova o caminho real."""
    _sem_variancia(monkeypatch)
    soldado = _combatente(1, classe="guerreiro", forca=20, ascensao="soldado")
    outro = _combatente(2, classe="guerreiro", forca=20)
    luta = combate.Luta([soldado, outro], CHEFE_TESTE, andar_num=1)

    combate._efeito_muralha_de_escudos(luta, soldado, game_data.HABILIDADES["muralha_de_escudos"])

    assert condicoes.alvo_forcado(luta) is soldado


def test_muralha_de_escudos_reduz_o_dano_recebido_enquanto_o_redirecionamento_dura(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="soldado")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    combate._efeito_muralha_de_escudos(luta, c, game_data.HABILIDADES["muralha_de_escudos"])

    assert condicoes.reducao_dano_recebido(luta, c.id) == combate.REDUCAO_MURALHA_DE_ESCUDOS
    _sobrevive_n_ticks_e_expira_no_seguinte(luta, "Muralha de Escudos", 2)
    assert condicoes.reducao_dano_recebido(luta, c.id) == 0.0


# ==================================================================
# Disciplina -- redução PERMANENTE, soma com Muralha e Voto de Ferro, teto
# de 0.5 pro total combinado
# ==================================================================

def test_disciplina_reduz_dano_permanentemente_sem_precisar_de_condicao():
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="soldado")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    assert condicoes.reducao_dano_recebido(luta, c.id) == 0.0   # nenhuma condição -- Disciplina não é condição
    assert combate._reducao_dano_total(luta, c) == game_data.PASSIVAS["disciplina"]["valor"]


def test_sem_disciplina_reducao_total_e_so_a_das_condicoes():
    c = _combatente(1, classe="guerreiro", forca=20)   # sem ascensão
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    condicoes.aplicar(luta, c.id, "reduz_dano", "Voto de Ferro", "🛡️", duracao=3, valor=combate.REDUCAO_VOTO_DE_FERRO)

    assert combate._reducao_dano_total(luta, c) == combate.REDUCAO_VOTO_DE_FERRO


def test_muralha_mais_voto_de_ferro_mais_disciplina_nao_passa_de_50_por_cento(monkeypatch):
    """O caso que o cartão pediu explicitamente: os três juntos ULTRAPASSAM
    0.5 antes do teto (0.20 + 0.20 + 0.15 = 0.55) -- prova que o teto
    entra em ação de verdade, não só coincide com o valor já baixo."""
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20, ascensao="soldado")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    combate._efeito_muralha_de_escudos(luta, c, game_data.HABILIDADES["muralha_de_escudos"])
    condicoes.aplicar(luta, c.id, "reduz_dano", "Voto de Ferro", "🛡️", duracao=3, valor=combate.REDUCAO_VOTO_DE_FERRO)

    soma_bruta = combate.REDUCAO_MURALHA_DE_ESCUDOS + combate.REDUCAO_VOTO_DE_FERRO + game_data.PASSIVAS["disciplina"]["valor"]
    assert soma_bruta > 0.5   # sanity: o cenário realmente testa o teto, não só soma pouco

    assert combate._reducao_dano_total(luta, c) == 0.5
