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
    "arma_instancia_id", "armadura_instancia_id",
    "anel_instancia_id", "colar_instancia_id",
    "avatar_msg_id", "avatar_url",
    "mortalha", "mortalha_instancia_id",
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


# ---- migração 12: upgrades -> instâncias (ver decisoes.md § Instâncias de item) ----
# `db._migrar_upgrades_para_instancias` é chamada direto (função privada, mesmo
# padrão de tests/test_trocas.py chamando trocas._commitar_troca) porque a
# fixture já rodou init_db() com o schema final -- forjar um banco "antigo"
# sem as colunas de instância pra exercitar o bloco `if novas_instancias`
# não vale o esforço; testar a função extraída cobre a mesma lógica.

def _upgrade_bruto(user_id, item, nivel):
    with db.conectar() as conn:
        conn.execute(
            "INSERT INTO upgrades (user_id, item, nivel) VALUES (?, ?, ?)", (user_id, item, nivel)
        )


def test_migracao_instancias_peca_equipada_vira_instancia_equipada():
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, arma="espada_ferro")
    _upgrade_bruto(1, "espada_ferro", 2)

    with db.conectar() as conn:
        resultado = db._migrar_upgrades_para_instancias(conn)
    assert resultado == (1, 0, 0)   # 1 equipada, 0 mochila, 0 órfã

    j = db.get_jogador(1)
    assert j["arma_instancia_id"]
    instancia = db.get_instancia(j["arma_instancia_id"])
    assert instancia["item"] == "espada_ferro" and instancia["nivel_melhoria"] == 2
    assert db.instancias_na_mochila(1) == []   # equipada, não está "na mochila"


def test_migracao_instancias_pega_uma_copia_da_mochila_quando_nao_equipado():
    db.criar_jogador(1, "Alice")
    db.add_item(1, "espada_ferro", 3)   # três cópias comuns, nenhuma equipada
    _upgrade_bruto(1, "espada_ferro", 1)

    with db.conectar() as conn:
        resultado = db._migrar_upgrades_para_instancias(conn)
    assert resultado == (0, 1, 0)

    assert db.tem_item(1, "espada_ferro", 2)   # sobraram 2 comuns
    assert not db.tem_item(1, "espada_ferro", 3)
    mochila = db.instancias_na_mochila(1)
    assert len(mochila) == 1 and mochila[0]["nivel_melhoria"] == 1


def test_migracao_instancias_descarta_linha_orfa_sem_peca_fisica():
    db.criar_jogador(1, "Alice")
    _upgrade_bruto(1, "espada_ferro", 1)   # nem equipada, nem na mochila

    with db.conectar() as conn:
        resultado = db._migrar_upgrades_para_instancias(conn)
    assert resultado == (0, 0, 1)
    assert db.instancias_na_mochila(1) == []


def _contar_instancias():
    with db.conectar() as conn:
        return conn.execute("SELECT COUNT(*) FROM instancias").fetchone()[0]


def test_migracao_13_anel_colar_nao_reexecuta_a_migracao_12():
    """Regressão do bug real: acrescentar coluna nova a COLUNAS_INSTANCIAS
    fazia `novas_instancias` voltar a ser verdadeiro e `init_db()`
    reprocessava `upgrades` inteiro, duplicando instância. anel/colar têm
    dict e migração (13) PRÓPRIOS agora -- este teste simula rodar a
    migração 13 num banco que já tinha passado pela 12, sem tocar
    `COLUNAS_INSTANCIAS` (migração 12) pra não reabrir o mesmo buraco."""
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, arma="espada_ferro")
    _upgrade_bruto(1, "espada_ferro", 1)
    with db.conectar() as conn:
        db._migrar_upgrades_para_instancias(conn)   # simula a migração 12 já ter rodado
    assert _contar_instancias() == 1

    # simula um banco que já passou pela migração 12 mas ainda não pela 13
    # (anel/colar não existiam ainda quando essas duas colunas nasceram)
    with db.conectar() as conn:
        conn.execute("ALTER TABLE jogadores DROP COLUMN anel_instancia_id")
        conn.execute("ALTER TABLE jogadores DROP COLUMN colar_instancia_id")

    db.init_db()   # só a migração 13 deveria rodar agora

    colunas = _colunas_jogadores()
    assert "anel_instancia_id" in colunas and "colar_instancia_id" in colunas
    assert _contar_instancias() == 1   # não duplicou -- continua 1, não 2


# ---- migração 14: joia_atributo/joia_valor em `instancias` (Joalheiro) ----
def _colunas_instancias():
    with db.conectar() as conn:
        return {r["name"] for r in conn.execute("PRAGMA table_info(instancias)")}


def test_migracao_14_cria_colunas_de_joia_em_instancias():
    colunas = _colunas_instancias()
    assert {"joia_atributo", "joia_valor", "encantamento_atributo", "encantamento_valor"} <= colunas


def test_migracao_14_e_idempotente():
    antes = _colunas_instancias()
    db.init_db()
    assert _colunas_instancias() == antes


def test_migracao_14_nao_reprocessa_upgrades_quando_falta_so_a_coluna_de_joia():
    """Mesmo espírito do teste da migração 13: uma coluna nova em outra
    tabela não pode disparar `_migrar_upgrades_para_instancias` de novo."""
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, arma="espada_ferro")
    _upgrade_bruto(1, "espada_ferro", 1)
    with db.conectar() as conn:
        db._migrar_upgrades_para_instancias(conn)
    assert _contar_instancias() == 1

    with db.conectar() as conn:
        conn.execute("ALTER TABLE instancias DROP COLUMN joia_atributo")
        conn.execute("ALTER TABLE instancias DROP COLUMN joia_valor")

    db.init_db()
    assert "joia_atributo" in _colunas_instancias()
    assert _contar_instancias() == 1
