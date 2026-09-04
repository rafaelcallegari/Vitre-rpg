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
    assert passivas.mana_recuperada_por_golpe(j) == 0
    assert passivas.e_clerigo(j) is False
    assert passivas.fracao_reducao_cura_ignorada(j) == 0.0
    assert passivas.fracao_absorcao_aliado(j) == 0.0


def test_ascensao_null_devolve_neutro_em_todas_as_consultas():
    _assert_neutro(_jogador())


def test_ascensao_desconhecida_nao_quebra_e_devolve_neutro():
    """Ramo que já existiu e foi removido do jogo (Batedor de Carteira, ver
    decisoes.md) não pode virar KeyError num combate em andamento -- é
    exatamente o cenário que `passivas._ramo` existe pra blindar."""
    assert "batedor_de_carteira" not in game_data.ASCENSOES
    _assert_neutro(_jogador(ascensao="batedor_de_carteira"))


def test_ascensao_valida_so_afeta_as_proprias_passivas_nunca_as_de_outro_ramo():
    """Step 2d fechou o pacote com o Paladino -- não existe mais nenhum
    ramo válido em ASCENSOES sem skill/passiva de verdade, então
    `_assert_neutro` (que bate contra TODAS as consultas) não serve mais
    pra nenhum jogador ascendido de verdade. O risco que sobra é o
    oposto: um monge não pode, por engano, disparar a passiva de OUTRO
    ramo -- aqui checa isso direto, e confirma que a passiva do próprio
    monge (Corpo Desperto) continua funcionando."""
    j = _jogador(ascensao="monge")
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
    assert passivas.e_clerigo(j) is False
    assert passivas.fracao_reducao_cura_ignorada(j) == 0.0
    assert passivas.fracao_absorcao_aliado(j) == 0.0
    assert passivas.mana_recuperada_por_golpe(j) == game_data.PASSIVAS["corpo_desperto"]["valor"]


def test_todos_os_ramos_agora_tem_skill_e_passiva_de_verdade():
    """Motor genérico: Step 2a fez o Ladino; Step 2b os 3 do Mago; Step 2c
    os 3 do Guerreiro; Step 2d fechou Monge, Clérigo e Paladino -- os 11
    ramos de ASCENSOES têm conteúdo agora, nenhum sobra na fila."""
    for chave, dados in game_data.ASCENSOES.items():
        assert dados["skill"] is not None, chave
        assert dados["passivas"] != [], chave
