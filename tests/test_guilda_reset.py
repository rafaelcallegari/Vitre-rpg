# tests/test_guilda_reset.py
# resetar_temporada() zera o caixa da guilda (baú + moedas) mas mantém a
# guilda, os membros e a home de pé -- ver decisoes.md § Baú da guilda zera,
# a guilda sobrevive.
import database as db


def _guilda_com_bau():
    guilda_id = db.criar_guilda("Lâminas do Alvorecer", lider_id=1, andar_home=3, cargo_id=10, canal_id=20)
    db.adicionar_membro_guilda(2, guilda_id)
    db.guilda_add_moedas(guilda_id, 5000)
    db.bau_add_item(guilda_id, "poção pequena", 12)
    return guilda_id


def test_resetar_temporada_esvazia_bau_e_zera_moedas_da_guilda():
    guilda_id = _guilda_com_bau()

    db.resetar_temporada()

    assert db.get_bau(guilda_id) == []
    assert db.get_guilda(guilda_id)["moedas"] == 0


def test_resetar_temporada_mantem_guilda_membros_e_home():
    guilda_id = _guilda_com_bau()

    db.resetar_temporada()

    guilda = db.get_guilda(guilda_id)
    assert guilda is not None
    assert guilda["nome"] == "Lâminas do Alvorecer"
    assert guilda["andar_home"] == 3
    assert guilda["cargo_id"] == 10
    assert db.contar_membros_guilda(guilda_id) == 2
    assert db.guilda_do_membro(1)["id"] == guilda_id
    assert db.guilda_do_membro(2)["id"] == guilda_id


def test_resetar_temporada_nao_afeta_guilda_sem_bau():
    """Guilda que nunca guardou nada no baú não deve quebrar o DELETE em
    massa nem sobrar linha residual de qtd 0."""
    guilda_id = db.criar_guilda("Sem Estoque", lider_id=3, andar_home=1, cargo_id=11, canal_id=21)

    db.resetar_temporada()

    assert db.get_bau(guilda_id) == []
    assert db.get_guilda(guilda_id)["moedas"] == 0
