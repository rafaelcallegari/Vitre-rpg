# tests/test_pronomes.py
# concordar()/sujeito()/possessivo() são função pura — cobertura completa
# cabe aqui, diferente das Views (ver decisoes.md § pronomes do jogador).
import pronomes


def test_concordar_marcador_simples_ele_e_elu_pegam_a_primeira_opcao():
    texto = "Você chega cansad{o|a} demais pra continuar."
    assert pronomes.concordar(texto, "ele") == "Você chega cansado demais pra continuar."
    assert pronomes.concordar(texto, "elu") == "Você chega cansado demais pra continuar."


def test_concordar_marcador_simples_ela_pega_a_segunda_opcao():
    texto = "Você chega cansad{o|a} demais pra continuar."
    assert pronomes.concordar(texto, "ela") == "Você chega cansada demais pra continuar."


def test_concordar_marcador_no_fim_da_palavra():
    # o marcador termina a palavra, sem nada literal depois dele até o espaço
    assert pronomes.concordar("Pront{o|a}!", "ele") == "Pronto!"
    assert pronomes.concordar("Pront{o|a}!", "ela") == "Pronta!"


def test_concordar_varios_marcadores_na_mesma_string():
    texto = "Você foi {o|a} únic{o|a} a sair de pé."
    assert pronomes.concordar(texto, "ele") == "Você foi o único a sair de pé."
    assert pronomes.concordar(texto, "ela") == "Você foi a única a sair de pé."
    assert pronomes.concordar(texto, "elu") == "Você foi o único a sair de pé."


def test_concordar_marcador_vazio_antes_da_barra_e_valido():
    # primeira opção vazia -- ex.: "doutor" (sem sufixo) vs "doutora" (+a)
    assert pronomes.concordar("doutor{|a}", "ele") == "doutor"
    assert pronomes.concordar("doutor{|a}", "ela") == "doutora"
    assert pronomes.concordar("doutor{|a}", "elu") == "doutor"


def test_concordar_texto_sem_marcador_nenhum_volta_intacto():
    texto = "O chefe voltou com o HP cheio."
    assert pronomes.concordar(texto, "ele") == texto
    assert pronomes.concordar(texto, "ela") == texto
    assert pronomes.concordar(texto, "elu") == texto


def test_concordar_marcador_malformado_nao_explode_e_devolve_o_texto():
    # chave sem fechar
    texto1 = "Você chega cansad{o|a demais."
    assert pronomes.concordar(texto1, "ela") == texto1
    # sem barra dentro das chaves
    texto2 = "Você chega cansad{oa} demais."
    assert pronomes.concordar(texto2, "ela") == texto2
    # três alternativas em vez de duas
    texto3 = "Você chega cansad{o|a|x} demais."
    assert pronomes.concordar(texto3, "ela") == texto3


def test_concordar_pronome_invalido_ou_none_cai_na_primeira_opcao():
    texto = "cansad{o|a}"
    assert pronomes.concordar(texto, None) == "cansado"
    assert pronomes.concordar(texto, "qualquer-coisa") == "cansado"


def test_concordar_texto_none_nao_explode():
    assert pronomes.concordar(None, "ela") == ""


def test_sujeito_devolve_o_proprio_pronome_valido():
    assert pronomes.sujeito("ele") == "ele"
    assert pronomes.sujeito("ela") == "ela"
    assert pronomes.sujeito("elu") == "elu"


def test_sujeito_cai_no_default_elu_se_invalido():
    assert pronomes.sujeito(None) == "elu"
    assert pronomes.sujeito("") == "elu"
    assert pronomes.sujeito("outra-coisa") == "elu"


def test_possessivo_mapeia_os_tres():
    assert pronomes.possessivo("ele") == "dele"
    assert pronomes.possessivo("ela") == "dela"
    assert pronomes.possessivo("elu") == "delu"


def test_possessivo_cai_no_default_delu_se_invalido():
    assert pronomes.possessivo(None) == "delu"
    assert pronomes.possessivo("outra-coisa") == "delu"
