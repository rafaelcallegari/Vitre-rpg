# tests/test_database_migracao.py
# init_db() num banco zerado precisa produzir o schema final das nove
# migrações encadeadas, e rodar de novo sobre a mesma base sem estourar
# (as migrações só são seguras porque cada uma checa PRAGMA table_info
# antes de alterar).
import database as db

COLUNAS_ESPERADAS = {
    "user_id", "nome", "nivel", "xp", "hp", "mana", "moedas", "andar", "andar_max",
    "arma", "armadura", "forca", "destreza", "constituicao", "inteligencia", "pontos",
    "mortes", "profissao", "prof_nivel", "prof_xp", "hp_em", "combate_em", "criado_em",
    "respec_gratis", "titulo", "titulos_possuidos", "classe", "habilidades_extras",
    "mana_em", "anel", "colar", "acoes_andar_alto", "pronome",
}


def _colunas_jogadores():
    with db.conectar() as conn:
        return {r["name"] for r in conn.execute("PRAGMA table_info(jogadores)")}


def test_migracao_cria_todas_as_colunas_esperadas():
    # fixture já rodou init_db() uma vez, num banco em memória vazio
    faltando = COLUNAS_ESPERADAS - _colunas_jogadores()
    assert not faltando, f"colunas faltando após init_db(): {faltando}"


def test_migracao_e_idempotente_rodando_de_novo_na_mesma_base():
    antes = _colunas_jogadores()
    db.init_db()   # segunda vez, mesma base — não pode estourar nem duplicar coluna
    depois = _colunas_jogadores()
    assert antes == depois == COLUNAS_ESPERADAS
