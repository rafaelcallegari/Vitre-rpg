# database.py
import sqlite3
import time
from contextlib import contextmanager

import atributos as at

DB_PATH = "aincrad.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jogadores (
    user_id      INTEGER PRIMARY KEY,
    nome         TEXT,
    nivel        INTEGER DEFAULT 1,
    xp           INTEGER DEFAULT 0,
    hp           INTEGER DEFAULT 100,
    mana         INTEGER DEFAULT 0,
    moedas       INTEGER DEFAULT 0,
    andar        INTEGER DEFAULT 1,
    andar_max    INTEGER DEFAULT 1,
    arma         TEXT,
    armadura     TEXT,
    forca        INTEGER DEFAULT 5,
    destreza     INTEGER DEFAULT 5,
    constituicao INTEGER DEFAULT 5,
    inteligencia INTEGER DEFAULT 5,
    pontos       INTEGER DEFAULT 0,
    mortes       INTEGER DEFAULT 0,
    profissao    TEXT,
    prof_nivel   INTEGER DEFAULT 1,
    prof_xp      INTEGER DEFAULT 0,
    hp_em        REAL DEFAULT 0,
    combate_em   REAL DEFAULT 0,
    criado_em    REAL
);
CREATE TABLE IF NOT EXISTS inventario (
    user_id INTEGER,
    item    TEXT,
    qtd     INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, item)
);
CREATE TABLE IF NOT EXISTS cooldowns (
    user_id   INTEGER,
    comando   TEXT,
    expira_em REAL,
    PRIMARY KEY (user_id, comando)
);
"""

COLUNAS_ATRIBUTO = {
    "mana": "INTEGER DEFAULT 0",
    "forca": f"INTEGER DEFAULT {at.BASE}",
    "destreza": f"INTEGER DEFAULT {at.BASE}",
    "constituicao": f"INTEGER DEFAULT {at.BASE}",
    "inteligencia": f"INTEGER DEFAULT {at.BASE}",
    "pontos": "INTEGER DEFAULT 0",
}

COLUNAS_TEMPO = {
    "hp_em": "REAL DEFAULT 0",
    "combate_em": "REAL DEFAULT 0",
}

COLUNAS_PROFISSAO = {
    "profissao": "TEXT",
    "prof_nivel": "INTEGER DEFAULT 1",
    "prof_xp": "INTEGER DEFAULT 0",
}

COLUNAS_RESPEC = {
    "respec_gratis": "INTEGER DEFAULT 0",
}

COLUNAS_TITULO = {
    "titulo": "TEXT",
    "titulos_possuidos": "TEXT DEFAULT ''",
}

COLUNAS_HABILIDADES = {
    "classe": "TEXT",                        # None = sem classe, escolhe com rpg classe
    "habilidades_extras": "TEXT DEFAULT ''",  # skills destravadas por sidequest, não por atributo
    "mana_em": "REAL DEFAULT 0",              # último instante em que a mana mudou
}

# grant histórico e único — não é reconcedido em migrações futuras
HANZO_USER_ID = 330816605963681792


@contextmanager
def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with conectar() as conn:
        conn.executescript(SCHEMA)
        colunas = [r["name"] for r in conn.execute("PRAGMA table_info(jogadores)")]

        # migração 1: bancos criados antes da viagem entre andares
        if "andar_max" not in colunas:
            conn.execute("ALTER TABLE jogadores ADD COLUMN andar_max INTEGER DEFAULT 1")
            conn.execute("UPDATE jogadores SET andar_max = andar")
            print("Banco migrado: coluna andar_max criada.")

        # migração 2: sistema de atributos
        novas = [c for c in COLUNAS_ATRIBUTO if c not in colunas]
        if novas:
            for coluna in novas:
                conn.execute(
                    f"ALTER TABLE jogadores ADD COLUMN {coluna} {COLUNAS_ATRIBUTO[coluna]}"
                )
            conn.execute(
                """UPDATE jogadores SET
                       forca = ?, destreza = ?, constituicao = ?, inteligencia = ?,
                       pontos = ? * (nivel - 1)""",
                (at.BASE, at.BASE, at.BASE, at.BASE, at.PONTOS_POR_NIVEL),
            )
            for row in conn.execute("SELECT user_id, nivel FROM jogadores").fetchall():
                hp_max = at.hp_maximo(row["nivel"], at.BASE)
                mana_max = at.mana_maxima(row["nivel"], at.BASE)
                conn.execute(
                    "UPDATE jogadores SET hp = MIN(hp, ?), mana = ? WHERE user_id = ?",
                    (hp_max, mana_max, row["user_id"]),
                )
            print("Banco migrado: atributos criados. Todo mundo tem pontos para distribuir.")

        # migração 3: relógios da regeneração
        novas_tempo = [c for c in COLUNAS_TEMPO if c not in colunas]
        if novas_tempo:
            agora = time.time()
            for coluna in novas_tempo:
                conn.execute(
                    f"ALTER TABLE jogadores ADD COLUMN {coluna} {COLUNAS_TEMPO[coluna]}"
                )
            conn.execute("UPDATE jogadores SET hp_em = ?, combate_em = ?", (agora, agora))
            print("Banco migrado: regeneração ligada (começa a contar de agora).")

        # migração 4: profissões
        novas_prof = [c for c in COLUNAS_PROFISSAO if c not in colunas]
        if novas_prof:
            for coluna in novas_prof:
                conn.execute(
                    f"ALTER TABLE jogadores ADD COLUMN {coluna} {COLUNAS_PROFISSAO[coluna]}"
                )
            conn.execute("UPDATE jogadores SET prof_nivel = 1, prof_xp = 0")
            print("Banco migrado: profissões criadas (ninguém escolheu ainda).")

        # migração 5: respec grátis por causa do rebalanceamento de defesa
        # (CON parou de dar defesa — quem já tinha pontos em CON por isso
        # merece redistribuir sem pagar)
        if "respec_gratis" not in colunas:
            conn.execute(
                f"ALTER TABLE jogadores ADD COLUMN respec_gratis {COLUNAS_RESPEC['respec_gratis']}"
            )
            conn.execute("UPDATE jogadores SET respec_gratis = 1")
            print("Banco migrado: respec grátis liberado para quem já jogava.")

        # migração 6: títulos
        novas_titulo = [c for c in COLUNAS_TITULO if c not in colunas]
        if novas_titulo:
            for coluna in novas_titulo:
                conn.execute(
                    f"ALTER TABLE jogadores ADD COLUMN {coluna} {COLUNAS_TITULO[coluna]}"
                )
            conn.execute("UPDATE jogadores SET titulos_possuidos = 'beta_tester'")
            conn.execute(
                """UPDATE jogadores SET titulos_possuidos = titulos_possuidos || ',primeiro_andar_10'
                   WHERE user_id = ?""",
                (HANZO_USER_ID,),
            )
            print("Banco migrado: títulos criados — Beta Tester para todo mundo, "
                  "Primeiro do Décimo Andar para o Hanzo.")

        # migração 7: infraestrutura de classes e habilidades (sem skills ainda)
        novas_hab = [c for c in COLUNAS_HABILIDADES if c not in colunas]
        if novas_hab:
            for coluna in novas_hab:
                conn.execute(
                    f"ALTER TABLE jogadores ADD COLUMN {coluna} {COLUNAS_HABILIDADES[coluna]}"
                )
            print("Banco migrado: classes criadas — ninguém escolheu ainda, "
                  "`rpg classe` para os jogadores existentes.")


# ---------------- jogadores ----------------
def get_jogador(user_id):
    with conectar() as conn:
        row = conn.execute("SELECT * FROM jogadores WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def criar_jogador(user_id, nome):
    atribs = at.distribuicao_inicial()
    hp = at.hp_maximo(1, atribs["constituicao"])
    mana = at.mana_maxima(1, atribs["inteligencia"])
    agora = time.time()
    with conectar() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO jogadores
               (user_id, nome, hp, mana, forca, destreza, constituicao, inteligencia,
                pontos, hp_em, combate_em, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)""",
            (
                user_id, nome, hp, mana,
                atribs["forca"], atribs["destreza"],
                atribs["constituicao"], atribs["inteligencia"],
                agora, agora, agora,
            ),
        )


def atualizar_jogador(user_id, **campos):
    """Sempre que o HP muda, carimba hp_em — a regeneração depende disso."""
    if not campos:
        return
    if "hp" in campos and "hp_em" not in campos:
        campos["hp_em"] = time.time()
    if "mana" in campos and "mana_em" not in campos:
        campos["mana_em"] = time.time()
    sets = ", ".join(f"{k} = ?" for k in campos)
    valores = list(campos.values()) + [user_id]
    with conectar() as conn:
        conn.execute(f"UPDATE jogadores SET {sets} WHERE user_id = ?", valores)


def marcar_combate(user_id):
    """Zera o relógio da regeneração: acabou de lutar, tem que esperar de novo."""
    with conectar() as conn:
        conn.execute("UPDATE jogadores SET combate_em = ? WHERE user_id = ?",
                     (time.time(), user_id))


def ranking(limite=10):
    with conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM jogadores ORDER BY andar_max DESC, nivel DESC, xp DESC LIMIT ?", (limite,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------- inventário ----------------
def add_item(user_id, item, qtd=1):
    with conectar() as conn:
        conn.execute(
            """INSERT INTO inventario (user_id, item, qtd) VALUES (?, ?, ?)
               ON CONFLICT(user_id, item) DO UPDATE SET qtd = qtd + excluded.qtd""",
            (user_id, item, qtd),
        )


def tem_item(user_id, item, qtd=1):
    with conectar() as conn:
        row = conn.execute(
            "SELECT qtd FROM inventario WHERE user_id = ? AND item = ?", (user_id, item)
        ).fetchone()
    return bool(row) and row["qtd"] >= qtd


def remove_item(user_id, item, qtd=1):
    if not tem_item(user_id, item, qtd):
        return False
    with conectar() as conn:
        conn.execute(
            "UPDATE inventario SET qtd = qtd - ? WHERE user_id = ? AND item = ?", (qtd, user_id, item)
        )
        conn.execute("DELETE FROM inventario WHERE user_id = ? AND item = ? AND qtd <= 0", (user_id, item))
    return True


def get_inventario(user_id):
    with conectar() as conn:
        rows = conn.execute(
            "SELECT item, qtd FROM inventario WHERE user_id = ? AND qtd > 0 ORDER BY item", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------- cooldowns ----------------
def checar_cooldown(user_id, comando):
    with conectar() as conn:
        row = conn.execute(
            "SELECT expira_em FROM cooldowns WHERE user_id = ? AND comando = ?", (user_id, comando)
        ).fetchone()
    if row and row["expira_em"] > time.time():
        return row["expira_em"] - time.time()
    return 0.0


def set_cooldown(user_id, comando, segundos):
    with conectar() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cooldowns (user_id, comando, expira_em) VALUES (?, ?, ?)",
            (user_id, comando, time.time() + segundos),
        )