# tests/test_passivas.py
# Step 2a, commit 1: o motor genérico de passivas de ascensão. Nenhuma
# passiva de verdade existe ainda (game_data.PASSIVAS está vazio e todo
# ramo em ASCENSOES tem "passivas": []) -- as quatro consultas têm que
# devolver o valor neutro em qualquer cenário possível: sem ascensão, com
# ascensão desconhecida (ramo removido do jogo) e com ascensão válida mas
# sem essa passiva específica ainda. Ver decisoes.md § Step 2a.
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


def test_ascensao_null_devolve_neutro_nas_quatro_consultas():
    _assert_neutro(_jogador())


def test_ascensao_desconhecida_nao_quebra_e_devolve_neutro():
    """Ramo que já existiu e foi removido do jogo (Batedor de Carteira, ver
    decisoes.md) não pode virar KeyError num combate em andamento -- é
    exatamente o cenário que `passivas._ramo` existe pra blindar."""
    assert "batedor_de_carteira" not in game_data.ASCENSOES
    _assert_neutro(_jogador(ascensao="batedor_de_carteira"))


def test_ascensao_valida_sem_passiva_de_verdade_ainda_devolve_neutro():
    """mago_raio é um ramo válido em ASCENSOES, mas não tem skill/passiva
    de verdade até seu próprio cartão -- não pode falhar por isso."""
    _assert_neutro(_jogador(ascensao="mago_raio"))


def test_ramos_sem_conteudo_de_verdade_continuam_neutros():
    """Motor genérico: os ramos que ainda não tiveram cartão próprio (Step
    2a fez o Ladino; Step 2b fez Mago de Gelo no commit 1, Mago de Fogo no
    commit 2) continuam sem skill/passiva."""
    tem_conteudo = {"assassino", "arqueiro", "mago_gelo", "mago_fogo"}
    sem_conteudo = set(game_data.ASCENSOES) - tem_conteudo
    assert len(sem_conteudo) == 7
    for chave in sem_conteudo:
        assert game_data.ASCENSOES[chave]["skill"] is None, chave
        assert game_data.ASCENSOES[chave]["passivas"] == [], chave
