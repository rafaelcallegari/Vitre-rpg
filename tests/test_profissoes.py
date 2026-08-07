# tests/test_profissoes.py
# Tabelas e cálculo de melhoria/desmanche — sem tocar no sorteio (`random`
# é do Python, não é nosso).
import profissoes
from game_data import ITENS


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


def test_refund_desmanche_nao_deveria_exceder_material_raro_de_chefe():
    base = profissoes.RECEITAS["lamina_selo"]["materiais"]["fragmento_selo"]  # 2
    materiais, _ = profissoes.refund_desmanche("lamina_selo", 2)
    assert materiais["fragmento_selo"] <= base


def _itens_equipaveis():
    return [k for k, v in ITENS.items() if v["tipo"] in ("arma", "armadura")]


def test_nenhuma_receita_tem_saldo_positivo_no_ciclo_craft_upgrade_desmanche():
    """Para todo material de toda receita: o que o desmanche mais generoso
    (+2, sem desconto de Forjador) devolve nunca pode passar do que craft +
    upgrade juntos gastaram. Sem isso, um item novo com dois materiais pode
    reabrir o mesmo buraco do fragmento_selo sem ninguém notar."""
    receitas_equipaveis = {
        k: v for k, v in profissoes.RECEITAS.items() if ITENS[k]["tipo"] in ("arma", "armadura")
    }
    for chave, receita in receitas_equipaveis.items():
        material_upgrade = profissoes.material_de_upgrade(chave)
        materiais_refund, _ = profissoes.refund_desmanche(chave, profissoes.NIVEL_MAX_UPGRADE)
        for mat, qtd_craft in receita["materiais"].items():
            gasto_upgrade = (
                sum(profissoes.CUSTO_MATERIAL_UPGRADE.values())
                if mat == material_upgrade else 0
            )
            assert materiais_refund[mat] <= qtd_craft + gasto_upgrade, (
                f"{chave}/{mat}: refund {materiais_refund[mat]} > "
                f"craft {qtd_craft} + upgrade {gasto_upgrade}"
            )


def test_custo_melhorar_e_refund_desmanche_funcionam_para_todo_equipavel():
    """Cobre os andares 11-15 (armas elementais) -- o Bug 2: ANDAR_MATERIAL
    só tinha chave pros andares ímpares 1-9, então melhorar uma arma elemental
    estourava KeyError na primeira chamada."""
    for chave in _itens_equipaveis():
        for alvo_nivel in (1, 2):
            for eh_forjador in (False, True):
                profissoes.custo_melhorar(chave, alvo_nivel, eh_forjador)
        for nivel_upgrade in (0, 1, 2):
            profissoes.refund_desmanche(chave, nivel_upgrade)


def test_material_de_upgrade_e_o_mesmo_nas_duas_funcoes():
    for chave in _itens_equipaveis():
        material_custo, _, _ = profissoes.custo_melhorar(chave, 1, eh_forjador=False)
        assert material_custo == profissoes.material_de_upgrade(chave)
