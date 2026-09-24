# tests/test_corte_salao.py
# Corte do Salão da Guilda (ver decisoes.md § Corte do Salão da Guilda).
# A migração 27 devolve cada tesouro da temporada atual à mochila de quem
# depositou e só depois derruba guilda_salao. O SCHEMA não cria mais a
# tabela, então os testes recriam ela com o schema que produção tem desde
# 20/08 e depositam por SQL direto -- é esse estado que a migração lê.
import database as db


def _jogador(user_id, nome="Jogadora"):
    db.criar_jogador(user_id, nome)
    return db.get_jogador(user_id)


def _guilda(nome, lider_id, membros_extra=(), andar_home=1):
    guilda_id = db.criar_guilda(nome, lider_id, andar_home, cargo_id=10, canal_id=20)
    for uid in membros_extra:
        db.adicionar_membro_guilda(uid, guilda_id)
    return guilda_id


SCHEMA_SALAO_LEGADO = """
CREATE TABLE IF NOT EXISTS guilda_salao (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    guilda_id     INTEGER,
    item          TEXT,
    user_id       INTEGER,
    mensagem      TEXT,
    depositado_em REAL,
    temporada     INTEGER
)"""


def _tem_tabela_salao():
    with db.conectar() as conn:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'guilda_salao'"
        ).fetchone() is not None


def _deposito_legado(guilda_id, item, user_id, temporada=None, mensagem=None):
    with db.conectar() as conn:
        conn.execute(SCHEMA_SALAO_LEGADO)
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


# ------------------------------------------------------------ devolução
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
    assert not _tem_tabela_salao()  # devolveu e SÓ ENTÃO removeu


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


def test_banco_novo_nao_cria_o_salao():
    assert not _tem_tabela_salao()
    db.init_db()
    assert not _tem_tabela_salao()


def test_devolucao_e_remocao_sao_uma_transacao_so(monkeypatch):
    """Se a devolução falhar no meio, a tabela NÃO cai -- senão o tesouro
    que não voltou some junto."""
    _jogador(1)
    g = _guilda("Ordem H", 1)
    _deposito_legado(g, "coroa_velha", 1)

    def _quebra(conn):
        conn.execute("INSERT INTO inventario (user_id, item, qtd) VALUES (1, 'coroa_velha', 1)")
        raise RuntimeError("falhou no meio")

    monkeypatch.setattr(db, "_devolver_tesouros_salao", _quebra)
    try:
        db.init_db()
    except RuntimeError:
        pass

    assert _tem_tabela_salao()
    assert _linhas_salao() == 1
    assert _qtd(1, "coroa_velha") == 0


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


# ------------------------------------------------------ tier da guilda
# Home e raide pelo tier da guilda: média do andar_max dos membros, teto 10
# por membro, piso de MEMBROS_PARA_VALER. Sem tesouro nenhum.
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import bot  # noqa: F401 -- side effect: liga H de guildas.py/raide.py via instalar()
import guildas
from game_data import TIERS_GUILDA


class FakeCtx:
    def __init__(self, user_id):
        self.author = SimpleNamespace(id=user_id, display_name=f"user{user_id}")
        self.message = SimpleNamespace(mentions=[])
        self.guild = None
        self.send = AsyncMock()


def _guilda_com_andares(nome, andares, andar_home=1):
    """Líder é o user 1; andares[i] vira o andar_max do membro i+1."""
    for i, a in enumerate(andares, start=1):
        _jogador(i)
        db.atualizar_jogador(i, andar_max=a)
    return _guilda(nome, 1, membros_extra=range(2, len(andares) + 1), andar_home=andar_home)


def test_media_tem_teto_no_selo():
    assert guildas.media_andar_max([15, 1, 2]) == (10 + 1 + 2) / 3
    assert guildas.media_andar_max([]) == 0


def test_tiers_por_media_batem_com_home_e_raide_de_antes():
    assert [t["andar_home_max"] for t in TIERS_GUILDA] == [3, 5, 8, 10]
    assert [t["cooldown_raide"] for t in TIERS_GUILDA] == [7200, 7200, 5400, 3600]
    assert guildas.tier_por_media(2.9)["tier"] == 0
    assert guildas.tier_por_media(3)["tier"] == 1
    assert guildas.tier_por_media(6.99)["tier"] == 1
    assert guildas.tier_por_media(7)["tier"] == 2
    assert guildas.tier_por_media(10)["tier"] == 3


def test_media_puxa_pra_baixo_mas_novato_nao_zera_a_guilda():
    """O motivo de média e não mínimo: veteranos 8 e 10 com um novato no 2
    (TOMBAR no banco de 04/09) ficam no tier 1, não no 0."""
    g = _guilda_com_andares("Mista", [8, 2, 10])
    tier, media = guildas.tier_da_guilda(g)
    assert round(media, 2) == 6.67
    assert tier["tier"] == 1


def test_veterano_sozinho_nao_carrega_a_guilda():
    """O motivo de média e não máximo: um no 10 e dois no 1 = média 4."""
    g = _guilda_com_andares("Carregada", [10, 1, 1])
    assert guildas.tier_da_guilda(g)[0]["tier"] == 1


def test_menos_de_3_membros_fica_no_tier_0_mesmo_com_media_alta():
    g = _guilda_com_andares("Dupla", [10, 10])
    tier, media = guildas.tier_da_guilda(g)
    assert media == 10
    assert tier["tier"] == 0


def test_home_liberada_pela_media():
    g = _guilda_com_andares("Subindo", [10, 7, 7])  # média 8 -> tier 2, home até 8
    ctx = FakeCtx(1)

    asyncio.run(guildas.acao_home(ctx, db.get_jogador(1), "8"))

    assert db.get_guilda(g)["andar_home"] == 8


def test_home_acima_do_tier_e_recusada_e_diz_a_media():
    g = _guilda_com_andares("Baixa", [10, 1, 1])  # média 4 -> tier 1, home até 5
    ctx = FakeCtx(1)

    asyncio.run(guildas.acao_home(ctx, db.get_jogador(1), "8"))

    assert db.get_guilda(g)["andar_home"] == 1
    texto = ctx.send.await_args.args[0]
    assert "4.0" in texto and "média 7" in texto


def test_guilda_com_home_acima_do_criterio_novo_nao_e_rebaixada():
    """Mesmo precedente da migração do Salão: o gate novo vale na próxima
    troca de home, não retroage -- nem na subida do bot (init_db), nem
    numa troca recusada."""
    g = _guilda_com_andares("Antiga", [10, 1, 1], andar_home=9)  # média 4 -> tier 1 só libera até 5

    db.init_db()
    assert db.get_guilda(g)["andar_home"] == 9

    ctx = FakeCtx(1)
    asyncio.run(guildas.acao_home(ctx, db.get_jogador(1), "10"))
    assert db.get_guilda(g)["andar_home"] == 9  # recusada, e segue 9


def _cooldown_gravado_pela_raide(andares):
    import raide
    import travas

    g = _guilda_com_andares(f"Raide {andares}", andares)
    ids = list(range(1, len(andares) + 1))
    ctx = FakeCtx(1)
    ctx.send = AsyncMock(return_value=SimpleNamespace())
    try:
        asyncio.run(raide.iniciar_raide(ctx, ids, g, 1))
    finally:
        travas.destravar_todos(ids)
    return db.checar_cooldown_raide(g)


def test_cooldown_de_raide_segue_a_media():
    assert 7200 - 5 < _cooldown_gravado_pela_raide([1, 1, 1]) <= 7200


def test_cooldown_de_raide_tier_2_e_1h30():
    assert 5400 - 5 < _cooldown_gravado_pela_raide([7, 7, 7]) <= 5400


def test_cooldown_de_raide_tier_3_e_1h():
    assert 3600 - 5 < _cooldown_gravado_pela_raide([10, 10, 10]) <= 3600
