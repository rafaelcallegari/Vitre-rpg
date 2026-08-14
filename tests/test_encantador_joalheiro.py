# tests/test_encantador_joalheiro.py
# Encantador e Joalheiro (Patch 0.3): curva de XP própria, tabela de
# bônus/custo/material compartilhada pelas duas, e o encantamento/joia
# somando corretamente em bot.stats(). Ver decisoes.md § Encantador e Joalheiro.
import bot
import database as db
import profissoes
from game_data import ACESSORIOS_RAIDE, ITENS


def _jogador(**campos):
    db.criar_jogador(1, "Alice")
    if campos:
        db.atualizar_jogador(1, **campos)
    return db.get_jogador(1)


# ---------------------------------------------------------------- curva de XP
def test_xp_para_subir_curva_propria_do_encantador_e_joalheiro():
    esperado = {1: 75, 2: 100, 3: 125, 4: 175, 5: 225, 6: 300, 7: 375, 8: 500}
    for nivel, xp in esperado.items():
        assert profissoes.xp_para_subir(nivel, "encantador") == xp
        assert profissoes.xp_para_subir(nivel, "joalheiro") == xp


def test_forja_e_alquimia_continuam_com_50_vezes_nivel():
    for nivel in range(1, 10):
        assert profissoes.xp_para_subir(nivel, "forja") == 50 * nivel
        assert profissoes.xp_para_subir(nivel, "alquimia") == 50 * nivel
        assert profissoes.xp_para_subir(nivel, None) == 50 * nivel


def test_teto_de_nivel_e_9_pros_oficios_magicos_10_pro_resto():
    assert profissoes.nivel_maximo_de("encantador") == 9
    assert profissoes.nivel_maximo_de("joalheiro") == 9
    assert profissoes.nivel_maximo_de("forja") == 10
    assert profissoes.nivel_maximo_de("alquimia") == 10


def test_75_acoes_de_25_xp_levam_o_encantador_do_zero_ao_nivel_9():
    nivel, xp, subiu_total = 1, 0, 0
    for _ in range(75):
        nivel, xp, subiu = profissoes.aplicar_xp_profissao(nivel, xp, 25, "encantador")
        subiu_total += subiu
    assert nivel == 9
    assert xp == 0   # zera no teto, não acumula xp sobrando
    assert subiu_total == 8   # 1 -> 9, oito subidas


def test_74_acoes_nao_bastam_pro_nivel_9():
    nivel, xp = 1, 0
    for _ in range(74):
        nivel, xp, _ = profissoes.aplicar_xp_profissao(nivel, xp, 25, "encantador")
    assert nivel == 8   # falta a última ação


# ---------------------------------------------------------- bônus por nível
def test_bonus_por_nivel_magico_bate_com_a_tabela_do_pedido():
    esperado = {1: 1, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 5, 8: 6, 9: 7}
    for nivel, bonus in esperado.items():
        assert profissoes.bonus_por_nivel_magico(nivel) == bonus


def test_custo_moedas_por_bonus_bate_com_a_tabela_do_pedido():
    esperado = {1: 400, 2: 900, 3: 1600, 4: 2600, 5: 3800, 6: 5200, 7: 6800}
    assert profissoes.CUSTO_MOEDAS_POR_BONUS == esperado


def test_encantar_as_4_pecas_no_teto_soma_27200():
    bonus, _, _, _, custo = profissoes.custo_magico(9, "encantador")
    assert bonus == 7 and custo == 6800
    assert custo * 4 == 27200


def test_joalheiro_anel_mais_colar_no_teto_soma_13600():
    bonus, _, _, _, custo = profissoes.custo_magico(9, "joalheiro")
    assert bonus == 7 and custo == 6800
    assert custo * 2 == 13600


# ------------------------------------------------------- material por tier
def test_material_do_encantador_segue_a_escada_de_andares_impares():
    esperado_material = {
        1: "essencia_do_vento", 2: "essencia_do_vento",   # bonus 1/2 -> andar 1
        3: "essencia_da_agua", 4: "essencia_da_agua",     # bonus 3/4 -> andar 3
        5: "essencia_do_gelo",                            # bonus 5 -> andar 5
        6: "essencia_de_fogo",                            # bonus 6 -> andar 7
        7: "essencia_estelar",                            # bonus 7 -> andar 9
    }
    for bonus, material_esperado in esperado_material.items():
        material, qtd, extra = profissoes.material_magico(bonus, "encantador")
        assert material == material_esperado, f"bônus {bonus}: {material} != {material_esperado}"
        assert qtd == 3
        if bonus == 7:
            assert extra == {"eco_cristalizado": 1}
        else:
            assert extra == {}


def test_material_do_joalheiro_segue_a_escada_de_andares_pares():
    esperado_material = {
        1: "ambar_de_seiva", 2: "ambar_de_seiva",     # bonus 1/2 -> andar 2
        3: "lagrima_de_sal", 4: "lagrima_de_sal",     # bonus 3/4 -> andar 4
        5: "rubi_fosco",                              # bonus 5 -> andar 6
        6: "vitral_partido",                          # bonus 6 -> andar 8
        7: "perola_do_eco",                           # bonus 7 -> andar 10
    }
    for bonus, material_esperado in esperado_material.items():
        material, _, _ = profissoes.material_magico(bonus, "joalheiro")
        assert material == material_esperado, f"bônus {bonus}: {material} != {material_esperado}"


def test_custo_magico_compoe_nivel_para_bonus_e_bonus_para_material():
    """A composição nivel -> bônus -> material que os comandos de verdade
    usam -- nível 3 rende bônus 2 (não bônus 3), então o material é o do
    1º andar da escada, não o do 2º. Pega exatamente o tipo de erro que
    testar bonus->material sozinho não pegaria."""
    bonus, material, _, _, custo = profissoes.custo_magico(3, "encantador")
    assert bonus == 2
    assert material == "essencia_do_vento"
    assert custo == 900

    bonus, material, _, _, custo = profissoes.custo_magico(9, "joalheiro")
    assert bonus == 7
    assert material == "perola_do_eco"
    assert custo == 6800


def test_todos_os_materiais_magicos_existem_no_catalogo_com_preco_do_andar():
    precos_por_andar = {1: 12, 2: 30, 3: 55, 4: 85, 5: 120, 6: 160, 7: 210, 8: 265, 9: 330, 10: 400}
    materiais_por_andar = {
        1: "essencia_do_vento", 3: "essencia_da_agua", 5: "essencia_do_gelo",
        7: "essencia_de_fogo", 9: "essencia_estelar",
        2: "ambar_de_seiva", 4: "lagrima_de_sal", 6: "rubi_fosco",
        8: "vitral_partido", 10: "perola_do_eco",
    }
    for andar, chave in materiais_por_andar.items():
        assert chave in ITENS
        assert ITENS[chave]["preco"] == precos_por_andar[andar]
        assert ITENS[chave]["tipo"] == "material"


# ------------------------------------------------------------ instâncias
def test_criar_instancia_com_joia_grava_atributo_e_valor():
    db.criar_jogador(1, "Alice")
    instancia_id = db.criar_instancia(1, "anel_joia", joia_atributo="forca", joia_valor=4)
    instancia = db.get_instancia(instancia_id)
    assert instancia["joia_atributo"] == "forca"
    assert instancia["joia_valor"] == 4
    assert instancia["encantamento_atributo"] is None


def test_definir_e_remover_encantamento():
    db.criar_jogador(1, "Alice")
    instancia_id = db.criar_instancia(1, "espada_ferro")
    db.definir_encantamento(instancia_id, "constituicao", 5)
    instancia = db.get_instancia(instancia_id)
    assert instancia["encantamento_atributo"] == "constituicao"
    assert instancia["encantamento_valor"] == 5

    db.remover_encantamento(instancia_id)
    instancia = db.get_instancia(instancia_id)
    assert instancia["encantamento_atributo"] is None
    assert instancia["encantamento_valor"] is None


def test_encantamento_convive_com_melhoria_na_mesma_instancia():
    """Arma pode estar +2 de melhoria (Forjador) E encantada ao mesmo tempo
    -- as duas camadas moram na mesma linha de `instancias` sem se pisar."""
    db.criar_jogador(1, "Alice")
    instancia_id = db.criar_instancia(1, "espada_ferro", nivel_melhoria=2)
    db.definir_encantamento(instancia_id, "forca", 3)
    instancia = db.get_instancia(instancia_id)
    assert instancia["nivel_melhoria"] == 2
    assert instancia["encantamento_atributo"] == "forca" and instancia["encantamento_valor"] == 3


# ------------------------------------------------------------------ bot.stats
def test_stats_soma_encantamento_da_arma_ao_atributo_efetivo():
    j = _jogador(arma="espada_ferro")
    instancia_id = db.criar_instancia(1, "espada_ferro")
    db.definir_encantamento(instancia_id, "forca", 3)
    db.atualizar_jogador(1, arma_instancia_id=instancia_id)
    j = db.get_jogador(1)

    s = bot.stats(j)
    base = db.get_jogador(1)["forca"]
    assert s["atribs"]["forca"] == base + 3


def test_stats_soma_joia_do_joalheiro_e_encantamento_do_encantador_no_mesmo_anel():
    """anel de Joalheiro (+4 INT) encantado por Encantador (+7 FOR) --
    'anel de Joalheiro 9 encantado por Encantador 9 = +14 num slot' do
    pedido é sobre dois anéis diferentes; aqui confere que os DOIS bônus da
    MESMA peça somam em atributos DIFERENTES sem se anular."""
    j = _jogador()
    instancia_id = db.criar_instancia(1, "anel_joia", joia_atributo="inteligencia", joia_valor=4)
    db.definir_encantamento(instancia_id, "forca", 7)
    db.atualizar_jogador(1, anel="anel_joia", anel_instancia_id=instancia_id)
    j = db.get_jogador(1)

    s = bot.stats(j)
    assert s["atribs"]["inteligencia"] == j["inteligencia"] + 4
    assert s["atribs"]["forca"] == j["forca"] + 7


def test_atributo_de_joia_e_encantamento_nao_conta_pro_requisito_de_skill():
    """Mesma regra que já valia pra acessório de raide: o bônus só entra no
    atributo EFETIVO (s['atribs']), nunca na coluna crua que requisito de
    skill/upar lê -- ver decisoes.md § Acessórios."""
    j = _jogador()
    instancia_id = db.criar_instancia(1, "anel_joia", joia_atributo="inteligencia", joia_valor=4)
    db.definir_encantamento(instancia_id, "forca", 7)
    db.atualizar_jogador(1, anel="anel_joia", anel_instancia_id=instancia_id)
    j = db.get_jogador(1)
    assert j["inteligencia"] == 5 and j["forca"] == 5   # BASE, sem nenhum dos dois bônus


def test_texto_equipamento_mostra_o_encantamento_junto_do_bonus_da_joia():
    j = _jogador()
    instancia_id = db.criar_instancia(1, "anel_joia", joia_atributo="inteligencia", joia_valor=4)
    db.definir_encantamento(instancia_id, "forca", 7)
    db.atualizar_jogador(1, anel="anel_joia", anel_instancia_id=instancia_id)
    j = db.get_jogador(1)

    s = bot.stats(j)
    texto = bot.texto_equipamento(s)
    assert "+4 INT" in texto
    assert "+7 FOR (encantado)" in texto


# --------------------------------------------------------------- raide/loot
def test_acessorios_raide_nao_inclui_itens_do_joalheiro():
    assert "anel_joia" not in ACESSORIOS_RAIDE
    assert "colar_joia" not in ACESSORIOS_RAIDE
    assert len(ACESSORIOS_RAIDE) == 8   # os 8 originais, nada mais


def test_acessorios_raide_continuam_os_mesmos_oito_de_sempre():
    assert set(ACESSORIOS_RAIDE) == {
        "anel_forca", "anel_destreza", "anel_constituicao", "anel_inteligencia",
        "colar_forca", "colar_destreza", "colar_constituicao", "colar_inteligencia",
    }
