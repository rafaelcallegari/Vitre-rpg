# tests/test_combate.py
# fator_recompensa_ajuda — regra que a máquina de sidequest vai reusar
# (ver decisoes.md).
import combate


def test_dono_do_andar_leva_fator_cheio():
    assert combate.fator_recompensa_ajuda(5, 5) == 1.0
    assert combate.fator_recompensa_ajuda(3, 5) == 1.0   # diff negativo também é "dono"


def test_fator_cai_conforme_a_distancia_cresce():
    perto = combate.fator_recompensa_ajuda(6, 5)   # diff = 1
    medio = combate.fator_recompensa_ajuda(7, 5)   # diff = 2
    longe = combate.fator_recompensa_ajuda(8, 5)   # diff = 3
    assert perto > medio > longe


def test_fator_nunca_chega_a_zero_por_maior_que_seja_a_diferenca():
    fator = combate.fator_recompensa_ajuda(1000, 5)
    assert fator == combate.FATOR_MINIMO_RECOMPENSA_AJUDA
    assert fator > 0
