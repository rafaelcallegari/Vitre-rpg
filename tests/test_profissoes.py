# tests/test_profissoes.py
# Tabelas e cálculo de melhoria/desmanche — sem tocar no sorteio (`random`
# é do Python, não é nosso).
import pytest

import profissoes


def test_chance_upgrade_tabelas():
    assert profissoes.CHANCE_UPGRADE[1] == 1.0
    assert profissoes.CHANCE_UPGRADE[2] == 0.70
    assert profissoes.CHANCE_UPGRADE_FORJADOR[2] == 0.85


def test_custo_melhorar_cobra_25_por_cento_menos_para_forjador():
    material, qtd_normal, moedas_normal = profissoes.custo_melhorar(
        "lamina_selo", 1, eh_forjador=False
    )
    _, qtd_forjador, moedas_forjador = profissoes.custo_melhorar(
        "lamina_selo", 1, eh_forjador=True
    )
    assert material == "pena_do_trovao"
    assert (qtd_normal, moedas_normal) == (2, 6400)
    assert (qtd_forjador, moedas_forjador) == (1, 4800)
    assert moedas_forjador == round(moedas_normal * 0.75)

    _, qtd_normal2, moedas_normal2 = profissoes.custo_melhorar(
        "lamina_selo", 2, eh_forjador=False
    )
    _, qtd_forjador2, moedas_forjador2 = profissoes.custo_melhorar(
        "lamina_selo", 2, eh_forjador=True
    )
    assert (qtd_normal2, moedas_normal2) == (3, 16000)
    assert (qtd_forjador2, moedas_forjador2) == (2, 12000)
    assert moedas_forjador2 == round(moedas_normal2 * 0.75)


def test_refund_desmanche_devolve_metade_e_nunca_mais_que_a_base_do_craft():
    base = profissoes.RECEITAS["couro_batido"]["materiais"]["presa_javali"]  # 3
    for nivel_upgrade in (0, 1, 2):
        materiais, _ = profissoes.refund_desmanche("couro_batido", nivel_upgrade)
        assert materiais["presa_javali"] <= base

    materiais0, xp0 = profissoes.refund_desmanche("couro_batido", 0)
    assert materiais0["presa_javali"] == max(1, int(base * 0.5))
    assert xp0 == int(profissoes.RECEITAS["couro_batido"]["xp"] * 0.40)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Bug real encontrado por este cartão, não corrigido de propósito "
        "(ver decisoes.md secao 'Suite de testes'): refund_desmanche soma "
        "+nivel_upgrade a cada material da receita sem checar se aquele "
        "material especifico foi gasto na melhoria. Para itens cujo material "
        "de craft (fragmento_selo, drop de chefe) difere do material de "
        "melhoria (pena_do_trovao, ANDAR_MATERIAL do andar), desmanchar uma "
        "peca +2 devolve MAIS fragmento_selo (3) do que foi gasto no craft "
        "(2) -- melhorar+desmanchar vira forma de lavar material raro de chefe."
    ),
)
def test_refund_desmanche_nao_deveria_exceder_material_raro_de_chefe():
    base = profissoes.RECEITAS["lamina_selo"]["materiais"]["fragmento_selo"]  # 2
    materiais, _ = profissoes.refund_desmanche("lamina_selo", 2)
    assert materiais["fragmento_selo"] <= base
