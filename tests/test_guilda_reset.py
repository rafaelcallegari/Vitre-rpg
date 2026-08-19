# tests/test_guilda_reset.py
# resetar_temporada() zera o caixa da guilda (baú + moedas) e a home (volta
# pro andar 1) mas mantém a guilda, os membros e o cargo de pé -- ver
# decisoes.md § Salão da Guilda -- home reset. O reset de home é reversão
# deliberada de uma decisão anterior (a guilda "sobrevivia inteira", home
# incluída) -- ver o commit do Salão da Guilda pro raciocínio de por que
# manter a home antiga junto com o Salão zerado virou inconsistência.
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


def test_resetar_temporada_mantem_guilda_membros_e_cargo_mas_zera_home():
    guilda_id = _guilda_com_bau()

    db.resetar_temporada()

    guilda = db.get_guilda(guilda_id)
    assert guilda is not None
    assert guilda["nome"] == "Lâminas do Alvorecer"
    assert guilda["cargo_id"] == 10
    assert db.contar_membros_guilda(guilda_id) == 2
    assert db.guilda_do_membro(1)["id"] == guilda_id
    assert db.guilda_do_membro(2)["id"] == guilda_id
    # home volta pro andar 1 -- guilda tinha home 3 antes do reset
    assert guilda["andar_home"] == 1


def test_resetar_temporada_zera_home_mesmo_em_andar_alto():
    """Caso mais realista de produção: guilda com home no andar 10 (tier
    alto conquistado na temporada anterior) precisa voltar pro andar 1 --
    não só sair do valor não-1 qualquer, é especificamente o "1" que
    representa o Salão em tier 0."""
    guilda_id = db.criar_guilda("Coroados", lider_id=5, andar_home=10, cargo_id=50, canal_id=60)

    db.resetar_temporada()

    assert db.get_guilda(guilda_id)["andar_home"] == 1


def test_resetar_temporada_nao_afeta_guilda_sem_bau():
    """Guilda que nunca guardou nada no baú não deve quebrar o DELETE em
    massa nem sobrar linha residual de qtd 0."""
    guilda_id = db.criar_guilda("Sem Estoque", lider_id=3, andar_home=1, cargo_id=11, canal_id=21)

    db.resetar_temporada()

    assert db.get_bau(guilda_id) == []
    assert db.get_guilda(guilda_id)["moedas"] == 0
