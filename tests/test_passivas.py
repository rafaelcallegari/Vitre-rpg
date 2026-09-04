# tests/test_passivas.py
# Step 2a, commit 1: o motor genérico de passivas de ascensão. Cada
# consulta nova de cartões seguintes (Step 2b, 2c...) entra em
# `_assert_neutro` -- ela precisa devolver o valor neutro em qualquer
# cenário possível: sem ascensão, com ascensão desconhecida (ramo removido
# do jogo) e com ascensão válida mas sem essa passiva específica ainda.
# Ver decisoes.md § Step 2a.
import database as db
import game_data
import passivas


def _jogador(ascensao=None):
    db.criar_jogador(1, "Alice")
    if ascensao is not None:
        db.atualizar_jogador(1, ascensao=ascensao)
    return db.get_jogador(1)


def _assert_neutro(j):
    assert passivas.critico_garantido(j, rodada=1) is False
    assert passivas.multiplicador_critico(j) == 1.0
    assert passivas.bonus_moedas(j) == 0.0
    assert passivas.bonus_material(j) == 0.0
    assert passivas.bonus_duracao_travamento(j) == 0
    assert passivas.empilha_brasa(j) is False
    assert passivas.chance_erro_carregado(j) == 0.0
    assert passivas.bonus_reducao_dano(j) == 0.0
    assert passivas.multiplicador_furia_desespero(j, fracao_hp=0.1) == 1.0
    assert passivas.fracao_defesa_ignorada(j) == 0.0


def test_ascensao_null_devolve_neutro_em_todas_as_consultas():
    _assert_neutro(_jogador())


def test_ascensao_desconhecida_nao_quebra_e_devolve_neutro():
    """Ramo que já existiu e foi removido do jogo (Batedor de Carteira, ver
    decisoes.md) não pode virar KeyError num combate em andamento -- é
    exatamente o cenário que `passivas._ramo` existe pra blindar."""
    assert "batedor_de_carteira" not in game_data.ASCENSOES
    _assert_neutro(_jogador(ascensao="batedor_de_carteira"))


def test_ascensao_valida_sem_passiva_de_verdade_ainda_devolve_neutro():
    """monge é um ramo válido em ASCENSOES, mas não tem skill/passiva de
    verdade até seu próprio cartão -- não pode falhar por isso."""
    _assert_neutro(_jogador(ascensao="monge"))


def test_ramos_sem_conteudo_de_verdade_continuam_neutros():
    """Motor genérico: os ramos que ainda não tiveram cartão próprio (Step
    2a fez o Ladino; Step 2b fez os 3 ramos do Mago; Step 2c fez os 3 do
    Guerreiro) continuam sem skill/passiva -- só o Orador segue na fila."""
    tem_conteudo = {
        "assassino", "arqueiro", "mago_gelo", "mago_fogo", "mago_raio",
        "soldado", "mercenario", "espadachim",
    }
    sem_conteudo = set(game_data.ASCENSOES) - tem_conteudo
    assert len(sem_conteudo) == 3
    for chave in sem_conteudo:
        assert game_data.ASCENSOES[chave]["skill"] is None, chave
        assert game_data.ASCENSOES[chave]["passivas"] == [], chave
