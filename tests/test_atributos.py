# tests/test_atributos.py
# Curva de defesa — funções puras, sem banco.
import atributos as at


def test_defesa_zero_ou_negativa_nao_reduz_nada():
    assert at.reducao_dano(0) == 0.0
    assert at.reducao_dano(-10) == 0.0


def test_reducao_cresce_com_defesa_mas_respeita_o_teto():
    baixa = at.reducao_dano(10)
    media = at.reducao_dano(75)
    alta = at.reducao_dano(1_000_000)
    assert baixa < media <= at.TETO_REDUCAO
    assert alta == at.TETO_REDUCAO


def test_aplicar_defesa_nunca_devolve_menos_que_1():
    # dano mínimo contra defesa enorme — nenhuma build pode ficar imortal
    assert at.aplicar_defesa(1, 1_000_000) == 1
    assert at.aplicar_defesa(0, 1_000_000) == 1
    assert at.aplicar_defesa(1, 0) == 1
