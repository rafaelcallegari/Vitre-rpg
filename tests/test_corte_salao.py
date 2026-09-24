# tests/test_corte_salao.py
# Corte do Salão da Guilda (ver decisoes.md § Corte do Salão da Guilda).
# Commit 1: a migração 27 devolve cada tesouro da temporada atual à mochila
# de quem depositou, antes de qualquer remoção. Os depósitos entram por SQL
# direto em guilda_salao, sem passar por função de feature -- é o estado
# que o banco de produção tem hoje, e é isso que a migração precisa ler.
import database as db


def _jogador(user_id, nome="Jogadora"):
    db.criar_jogador(user_id, nome)
    return db.get_jogador(user_id)


def _guilda(nome, lider_id, membros_extra=(), andar_home=1):
    guilda_id = db.criar_guilda(nome, lider_id, andar_home, cargo_id=10, canal_id=20)
    for uid in membros_extra:
        db.adicionar_membro_guilda(uid, guilda_id)
    return guilda_id


def _deposito_legado(guilda_id, item, user_id, temporada=None, mensagem=None):
    with db.conectar() as conn:
        if temporada is None:
            temporada = conn.execute("SELECT numero FROM estado_temporada WHERE id = 1").fetchone()["numero"]
        conn.execute(
            """INSERT INTO guilda_salao (guilda_id, item, user_id, mensagem, depositado_em, temporada)
               VALUES (?, ?, ?, ?, 0, ?)""",
            (guilda_id, item, user_id, mensagem, temporada),
        )


def _qtd(user_id, item):
    return next((i["qtd"] for i in db.get_inventario(user_id) if i["item"] == item), 0)


def _linhas_salao():
    with db.conectar() as conn:
        return conn.execute("SELECT COUNT(*) FROM guilda_salao").fetchone()[0]


# ------------------------------------------------------------ commit 1
def test_devolucao_coloca_cada_tesouro_na_mochila_de_quem_depositou():
    for uid in (1, 2, 3):
        _jogador(uid)
    g = _guilda("Ordem A", 1, membros_extra=(2, 3))
    _deposito_legado(g, "coroa_velha", 1)
    _deposito_legado(g, "novelo_da_rainha", 1)
    _deposito_legado(g, "coroa_velha", 2)  # mesmo tesouro, outro depositante
    _deposito_legado(g, "lasca_do_guardiao", 3, mensagem="pra guilda")

    db.init_db()

    assert _qtd(1, "coroa_velha") == 1
    assert _qtd(1, "novelo_da_rainha") == 1
    assert _qtd(2, "coroa_velha") == 1
    assert _qtd(3, "lasca_do_guardiao") == 1
    assert _qtd(2, "novelo_da_rainha") == 0  # ninguém recebe o que não depositou
    assert _linhas_salao() == 0


def test_devolucao_soma_com_o_que_ja_estava_na_mochila():
    _jogador(1)
    g = _guilda("Ordem B", 1)
    db.add_item(1, "coroa_velha", 1)  # caiu de novo depois do depósito
    _deposito_legado(g, "coroa_velha", 1)

    db.init_db()

    assert _qtd(1, "coroa_velha") == 2


def test_devolucao_vai_pra_quem_ja_saiu_da_guilda_ou_teve_a_guilda_dissolvida():
    for uid in (1, 2, 3):
        _jogador(uid)
    g = _guilda("Ordem C", 1, membros_extra=(2,))
    _deposito_legado(g, "coroa_velha", 2)
    db.remover_membro_guilda(2)
    g2 = _guilda("Ordem D", 3)
    _deposito_legado(g2, "novelo_da_rainha", 3)
    db.apagar_guilda(g2)

    db.init_db()

    assert _qtd(2, "coroa_velha") == 1
    assert _qtd(3, "novelo_da_rainha") == 1


def test_devolucao_e_idempotente():
    _jogador(1)
    g = _guilda("Ordem E", 1)
    _deposito_legado(g, "coroa_velha", 1)

    db.init_db()
    db.init_db()

    assert _qtd(1, "coroa_velha") == 1


def test_temporada_passada_nao_volta():
    """Tesouro de temporada passada teria sido apagado pelo reset se não
    estivesse no Salão -- devolver daria à temporada nova um item que
    ninguém ganhou nela."""
    _jogador(1)
    g = _guilda("Ordem F", 1)
    _deposito_legado(g, "coroa_velha", 1)
    db.avancar_temporada()
    _deposito_legado(g, "novelo_da_rainha", 1)

    db.init_db()

    assert _qtd(1, "coroa_velha") == 0
    assert _qtd(1, "novelo_da_rainha") == 1


def test_devolucao_deixa_rastro_no_log_da_guilda():
    _jogador(1)
    g = _guilda("Ordem G", 1)
    _deposito_legado(g, "coroa_velha", 1)

    db.init_db()

    log = db.get_guilda_log(g)
    assert any(e["acao"] == "salao_devolvido" and e["item"] == "coroa_velha" for e in log)
