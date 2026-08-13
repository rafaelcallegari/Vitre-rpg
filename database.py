# database.py
import asyncio
import os
import sqlite3
import threading
import time
from contextlib import contextmanager

import atributos as at
from andares_altos import ANDAR_ACIMA_DO_SELO

DB_PATH = "aincrad.db"
BACKUP_DIR = "backups"

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
CREATE TABLE IF NOT EXISTS upgrades (
    user_id INTEGER,
    item    TEXT,
    nivel   INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, item)
);
CREATE TABLE IF NOT EXISTS instancias (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    dono                  INTEGER,
    item                  TEXT,
    nivel_melhoria        INTEGER DEFAULT 0,
    encantamento_atributo TEXT,
    encantamento_valor    INTEGER
);
CREATE TABLE IF NOT EXISTS guildas (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT UNIQUE,
    lider_id   INTEGER,
    andar_home INTEGER DEFAULT 1,
    cargo_id   INTEGER,
    canal_id   INTEGER,
    moedas     INTEGER DEFAULT 0,
    criada_em  REAL
);
CREATE TABLE IF NOT EXISTS guilda_membros (
    user_id   INTEGER PRIMARY KEY,
    guilda_id INTEGER,
    entrou_em REAL,
    papel     TEXT DEFAULT 'membro'
);
CREATE TABLE IF NOT EXISTS guilda_bau (
    guilda_id INTEGER,
    item      TEXT,
    qtd       INTEGER DEFAULT 0,
    PRIMARY KEY (guilda_id, item)
);
CREATE TABLE IF NOT EXISTS guilda_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    guilda_id INTEGER,
    user_id   INTEGER,
    acao      TEXT,
    item      TEXT,
    qtd       INTEGER,
    quando    REAL
);
CREATE TABLE IF NOT EXISTS guilda_raide (
    guilda_id INTEGER PRIMARY KEY,
    expira_em REAL
);
CREATE TABLE IF NOT EXISTS guilda_home_cooldown (
    guilda_id INTEGER PRIMARY KEY,
    expira_em REAL
);
CREATE TABLE IF NOT EXISTS chefes_derrotados (
    user_id INTEGER,
    andar   INTEGER,
    vezes   INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, andar)
);
CREATE TABLE IF NOT EXISTS guilda_convites (
    guilda_id     INTEGER,
    user_id       INTEGER,
    convidado_por INTEGER,
    expira_em     REAL,
    PRIMARY KEY (guilda_id, user_id)
);
CREATE TABLE IF NOT EXISTS sidequests (
    user_id  INTEGER NOT NULL,
    quest_id TEXT    NOT NULL,
    estado   TEXT    NOT NULL,          -- 'ativa' | 'concluida'
    UNIQUE (user_id, quest_id)
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

COLUNAS_ACESSORIOS = {
    "anel": "TEXT",
    "colar": "TEXT",
}

COLUNAS_GUIA = {
    # conta ações fora de luta de chefe enquanto acima do Selo — a cada 3,
    # a Guia comenta e o contador zera (ver andares_altos.fala_da_guia)
    "acoes_andar_alto": "INTEGER DEFAULT 0",
}

COLUNAS_PRONOME = {
    # default 'elu' de propósito -- não atribui gênero a ninguém que já
    # jogava antes da coluna existir (ver decisoes.md § pronomes do jogador)
    "pronome": "TEXT NOT NULL DEFAULT 'elu'",
}

COLUNAS_INSTANCIAS = {
    # arma/armadura continuam guardando a CHAVE do item, sempre -- essas
    # colunas só dizem SE a peça equipada é uma instância modificada e
    # QUAL linha de `instancias` é ela. NULL = peça comum, sem identidade
    # própria. Ver decisoes.md § Instâncias de item.
    #
    # CONGELADO -- não acrescente coluna nova aqui. Este dict é o gatilho
    # de `_migrar_upgrades_para_instancias` (migração 12): qualquer coluna
    # que falte dispara a migração de dados inteira de novo, reprocessando
    # `upgrades` e duplicando instância (ver decisoes.md § Instâncias de
    # item -- anel e colar também carregam instância). Slot de instância
    # novo entra num dict/migração PRÓPRIA, só com ALTER TABLE, sem chamar
    # a função de migração de dados.
    "arma_instancia_id": "INTEGER",
    "armadura_instancia_id": "INTEGER",
}

COLUNAS_INSTANCIA_ACESSORIOS = {
    # mesma ideia de COLUNAS_INSTANCIAS, mas pra anel/colar -- migração 13,
    # com guarda própria. `rpg melhorar` continua só em arma/armadura (isso
    # não muda); estas colunas existem pra o Arcano (encantamento) ter onde
    # guardar a instância de um acessório encantado. Nenhuma instância de
    # acessório é criada nesta carta -- ninguém escreve nestas colunas
    # ainda, então não há dado histórico pra migrar aqui.
    "anel_instancia_id": "INTEGER",
    "colar_instancia_id": "INTEGER",
}

# grant histórico e único — não é reconcedido em migrações futuras
HANZO_USER_ID = 330816605963681792


# Conexão única de módulo, reaberta nunca — abrir/fechar uma conexão por
# chamada (48x por fluxo) fazia o SQLite rodar checkpoint completo do WAL
# toda vez que "a última conexão" fechava, e com uma conexão de cada vez
# isso era sempre. Pagávamos o custo do WAL sem ganhar a concorrência que
# ele promete. Ver decisoes.md § Conexão longa.
_conn = None
_lock = threading.RLock()


def _conexao():
    global _conn
    if _conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        # PRAGMAs são por conexão — agora só rodam uma vez, na criação,
        # porque só existe uma conexão pra rodar neles.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        _conn = conn
    return _conn


@contextmanager
def conectar():
    """RLock (não Lock) segurado durante todo o corpo do `with` — hoje não
    existe `conectar()` aninhado (as chamadas internas de convite recebem
    `conn` por parâmetro em vez de reabrir), mas um aninhamento acidental
    futuro vira deadlock silencioso com Lock comum: o bot trava inteiro,
    sem erro, sem log. RLock deixa a mesma thread reentrar sem travar — o
    custo de usar RLock em vez de Lock é zero.

    `rollback()` explícito na exceção é o ponto que importa de verdade: com
    conexão por chamada, um erro no meio de um `with` era descartado de
    graça pelo `close()` no `finally` — cada chamada tinha conexão própria,
    então a próxima já começava limpa. Com conexão compartilhada isso deixa
    de valer: sem o rollback aqui, a transação suja de uma operação que
    falhou ficaria pendente na conexão e a PRÓXIMA chamada — de outro
    comando, outro jogador — herdaria e poderia commitar escrita parcial
    junto da dela. Numa economia com troca entre jogadores isso é o pior
    bug possível."""
    with _lock:
        conn = _conexao()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def fechar_conexao():
    """Desligamento limpo — chamada no encerramento do bot, nunca durante
    uso normal (`conectar()` não fecha a conexão em nenhum caminho)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


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

        # migração 8: slots de anel e colar
        novas_acessorios = [c for c in COLUNAS_ACESSORIOS if c not in colunas]
        if novas_acessorios:
            for coluna in novas_acessorios:
                conn.execute(
                    f"ALTER TABLE jogadores ADD COLUMN {coluna} {COLUNAS_ACESSORIOS[coluna]}"
                )
            print("Banco migrado: slots de anel e colar criados — ninguém equipado ainda.")

        # migração 9: contador da fala da Guia acima do Selo
        novas_guia = [c for c in COLUNAS_GUIA if c not in colunas]
        if novas_guia:
            for coluna in novas_guia:
                conn.execute(
                    f"ALTER TABLE jogadores ADD COLUMN {coluna} {COLUNAS_GUIA[coluna]}"
                )
            print("Banco migrado: contador da Guia criado.")

        # migração 10: home de guilda acima do Selo nunca devia ter sido
        # permitida — acima do andar 10 não tem loja/ferreiro/carroça, uma
        # guilda "morando" lá não fazia sentido (ver decisoes.md § Andares 11-15)
        presas = conn.execute(
            "SELECT COUNT(*) AS n FROM guildas WHERE andar_home > ?", (ANDAR_ACIMA_DO_SELO,)
        ).fetchone()["n"]
        if presas:
            conn.execute(
                "UPDATE guildas SET andar_home = 1 WHERE andar_home > ?", (ANDAR_ACIMA_DO_SELO,)
            )
            print(f"Banco migrado: {presas} guilda(s) com home acima do Selo voltaram pro andar 1.")

        # migração 11: pronome do jogador -- default 'elu' pra quem já jogava
        novas_pronome = [c for c in COLUNAS_PRONOME if c not in colunas]
        if novas_pronome:
            for coluna in novas_pronome:
                conn.execute(
                    f"ALTER TABLE jogadores ADD COLUMN {coluna} {COLUNAS_PRONOME[coluna]}"
                )
            print("Banco migrado: pronome adicionado (default 'elu' pra quem já jogava).")

        # migração 12: instâncias de item -- a melhoria (+1/+2) passa a
        # ficar presa à PEÇA (id próprio em `instancias`), não mais ao par
        # (jogador, item) em `upgrades`. Motivo: duas cópias do mesmo item
        # eram indistinguíveis, e o encantamento (Arcano, card futuro)
        # precisa viajar com a peça numa troca -- `upgrades` não viajava.
        # `upgrades` continua no schema (nunca se dropa tabela com dado
        # real), só para de ser escrita a partir daqui. Roda uma vez só,
        # no mesmo bloco que cria as colunas -- ver decisoes.md § Instâncias
        # de item pras regras de cada caso (equipada / na mochila / órfã).
        novas_instancias = [c for c in COLUNAS_INSTANCIAS if c not in colunas]
        if novas_instancias:
            for coluna in novas_instancias:
                conn.execute(
                    f"ALTER TABLE jogadores ADD COLUMN {coluna} {COLUNAS_INSTANCIAS[coluna]}"
                )
            equipadas, mochila, orfas = _migrar_upgrades_para_instancias(conn)
            print(
                f"Banco migrado: instâncias de item criadas -- {equipadas} equipada(s), "
                f"{mochila} na mochila, {orfas} órfã(s) descartada(s) (upgrade sem peça física)."
            )

        # migração 13: anel e colar também ganham coluna de instância --
        # só estrutura, pro Arcano (encantamento) ter onde guardar. `rpg
        # melhorar` continua não aceitando acessório, então não existe
        # `upgrades` de anel/colar pra migrar: só ALTER TABLE, sem chamar
        # `_migrar_upgrades_para_instancias` (guarda própria, deliberadamente
        # separada da migração 12 -- ver o comentário "CONGELADO" em
        # COLUNAS_INSTANCIAS e decisoes.md § Instâncias de item -- anel e
        # colar também carregam instância).
        novas_acessorios_instancia = [c for c in COLUNAS_INSTANCIA_ACESSORIOS if c not in colunas]
        if novas_acessorios_instancia:
            for coluna in novas_acessorios_instancia:
                conn.execute(
                    f"ALTER TABLE jogadores ADD COLUMN {coluna} {COLUNAS_INSTANCIA_ACESSORIOS[coluna]}"
                )
            print("Banco migrado: colunas de instância criadas pra anel e colar (sem melhoria neles ainda).")


def _migrar_upgrades_para_instancias(conn):
    """Migração 12, uma linha de `upgrades` por vez -> `instancias`. Extraída
    do corpo de init_db() pra dar pra testar os três casos isoladamente
    (equipada / uma cópia na mochila / órfã) sem precisar fingir schema
    antigo -- ver tests/test_database_migracao.py e decisoes.md § Instâncias
    de item. Só chamada de dentro do bloco `if novas_instancias` acima
    (roda uma vez, quando as colunas de instância ainda não existiam)."""
    equipadas = mochila = orfas = 0
    for row in conn.execute("SELECT user_id, item, nivel FROM upgrades WHERE nivel > 0").fetchall():
        user_id, item, nivel = row["user_id"], row["item"], row["nivel"]
        jog = conn.execute(
            "SELECT arma, armadura FROM jogadores WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not jog:
            orfas += 1
            continue

        if jog["arma"] == item:
            slot = "arma"
        elif jog["armadura"] == item:
            slot = "armadura"
        else:
            slot = None

        if slot:
            cur = conn.execute(
                "INSERT INTO instancias (dono, item, nivel_melhoria) VALUES (?, ?, ?)",
                (user_id, item, nivel),
            )
            conn.execute(
                f"UPDATE jogadores SET {slot}_instancia_id = ? WHERE user_id = ?",
                (cur.lastrowid, user_id),
            )
            equipadas += 1
            continue

        inv = conn.execute(
            "SELECT qtd FROM inventario WHERE user_id = ? AND item = ?", (user_id, item)
        ).fetchone()
        if inv and inv["qtd"] > 0:
            # várias cópias comuns + uma linha de upgrade: só UMA cópia
            # vira a instância melhorada, o resto continua comum -- o jogo
            # nunca soube diferenciar cópias além dessa única linha salva,
            # não tem como saber qual era "a" cópia melhorada além de
            # tirar uma da pilha.
            conn.execute(
                "INSERT INTO instancias (dono, item, nivel_melhoria) VALUES (?, ?, ?)",
                (user_id, item, nivel),
            )
            conn.execute(
                "UPDATE inventario SET qtd = qtd - 1 WHERE user_id = ? AND item = ?",
                (user_id, item),
            )
            conn.execute(
                "DELETE FROM inventario WHERE user_id = ? AND item = ? AND qtd <= 0",
                (user_id, item),
            )
            mochila += 1
        else:
            # linha órfã: upgrade salvo pra um item que o jogador não tem
            # mais nem equipado nem na mochila -- não existe peça física
            # pra prender a instância, descarta.
            orfas += 1

    return equipadas, mochila, orfas


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


def contar_jogadores():
    with conectar() as conn:
        return conn.execute("SELECT COUNT(*) FROM jogadores").fetchone()[0]


# ---------------- backup e reset de temporada ----------------
def backup_banco_para(destino):
    """Copia o banco pro caminho `destino` usando a API de backup do próprio
    SQLite (`Connection.backup`) — atômica e consistente, funciona mesmo com
    outras conexões escrevendo ao mesmo tempo. Com WAL ligado, `shutil.copy2`
    deixou de ser seguro: dado já commitado pode estar só no `.db-wal`, então
    copiar só o `.db` pode faltar transação recente ou pegar o arquivo em
    estado inconsistente se houver escrita em andamento durante a cópia.
    Deixa a exceção subir se falhar — quem chama decide o que fazer."""
    origem = sqlite3.connect(DB_PATH)
    try:
        destino_conn = sqlite3.connect(destino)
        try:
            with destino_conn:
                origem.backup(destino_conn)
        finally:
            destino_conn.close()
    finally:
        origem.close()


def backup_banco():
    """Copia o .db pra backups/ com timestamp no nome. Deixa a exceção
    subir se falhar — quem chama decide se aborta o reset por causa disso."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    carimbo = time.strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(BACKUP_DIR, f"aincrad_{carimbo}.db")
    backup_banco_para(destino)
    return destino


def resetar_temporada():
    """Reset completo de progresso — reutilizável, roda de novo em toda
    temporada futura. Mantém a linha do jogador (ninguém refaz `rpg
    comecar`), título equipado, títulos possuídos, `criado_em` e mortes.
    Zera nível/XP/moedas/HP/mana/atributos/equipamento/classe/ofício e
    apaga inventário, cooldowns e upgrades por inteiro.

    Tudo dentro do `with conectar()` de baixo: se qualquer execute() aqui
    lançar, o commit no fim do context manager nunca roda e o SQLite
    descarta a transação inteira ao fechar a conexão sem commit — ou reseta
    todo mundo, ou nada muda.
    """
    hp = at.hp_maximo(1, at.BASE)
    mana = at.mana_maxima(1, at.BASE)
    agora = time.time()
    with conectar() as conn:
        afetados = conn.execute("SELECT COUNT(*) FROM jogadores").fetchone()[0]
        conn.execute(
            """UPDATE jogadores SET
                   nivel = 1, xp = 0, moedas = 0,
                   hp = ?, mana = ?,
                   forca = ?, destreza = ?, constituicao = ?, inteligencia = ?, pontos = 0,
                   arma = NULL, armadura = NULL, anel = NULL, colar = NULL,
                   arma_instancia_id = NULL, armadura_instancia_id = NULL,
                   anel_instancia_id = NULL, colar_instancia_id = NULL,
                   classe = NULL,
                   profissao = NULL, prof_nivel = 1, prof_xp = 0,
                   andar = 1, andar_max = 1,
                   hp_em = ?, combate_em = ?, mana_em = ?""",
            (hp, mana, at.BASE, at.BASE, at.BASE, at.BASE, agora, agora, agora),
        )
        conn.execute("DELETE FROM inventario")
        conn.execute("DELETE FROM cooldowns")
        conn.execute("DELETE FROM upgrades")
        conn.execute("DELETE FROM instancias")
        conn.execute("DELETE FROM chefes_derrotados")
    return afetados


def resetar_classe_profissao(user_id):
    """Zera classe e profissão (+ nível/XP de ofício) de UM jogador — não
    mexe em nível, atributos, equipamento ou andar. Usado pra corrigir uma
    escolha individual, não pra reset de temporada (ver resetar_temporada)."""
    with conectar() as conn:
        cur = conn.execute(
            """UPDATE jogadores SET
                   classe = NULL, profissao = NULL, prof_nivel = 1, prof_xp = 0
               WHERE user_id = ?""",
            (user_id,),
        )
    return cur.rowcount


# ---------------- guildas ----------------
def criar_guilda(nome, lider_id, andar_home, cargo_id, canal_id):
    agora = time.time()
    with conectar() as conn:
        cur = conn.execute(
            """INSERT INTO guildas (nome, lider_id, andar_home, cargo_id, canal_id, moedas, criada_em)
               VALUES (?, ?, ?, ?, ?, 0, ?)""",
            (nome, lider_id, andar_home, cargo_id, canal_id, agora),
        )
        guilda_id = cur.lastrowid
        conn.execute(
            "INSERT INTO guilda_membros (user_id, guilda_id, entrou_em, papel) VALUES (?, ?, ?, 'lider')",
            (lider_id, guilda_id, agora),
        )
    return guilda_id


def get_guilda(guilda_id):
    with conectar() as conn:
        row = conn.execute("SELECT * FROM guildas WHERE id = ?", (guilda_id,)).fetchone()
    return dict(row) if row else None


def get_guilda_por_nome(nome):
    with conectar() as conn:
        row = conn.execute(
            "SELECT * FROM guildas WHERE nome = ? COLLATE NOCASE", (nome,)
        ).fetchone()
    return dict(row) if row else None


def guilda_do_membro(user_id):
    """A guilda de um jogador, com o papel e a data de entrada dele juntos —
    None se ele não está em nenhuma."""
    with conectar() as conn:
        row = conn.execute(
            """SELECT guildas.*, guilda_membros.papel, guilda_membros.entrou_em
               FROM guilda_membros JOIN guildas ON guildas.id = guilda_membros.guilda_id
               WHERE guilda_membros.user_id = ?""",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def viagem_gratis_guilda(user_id, andar_max, destino):
    """Só é de graça se o destino é a home da guilda do jogador E ele já
    destrancou até lá — checado por membro, não por guilda."""
    guilda = guilda_do_membro(user_id)
    return bool(guilda) and guilda["andar_home"] == destino and andar_max >= destino


def membros_da_guilda(guilda_id):
    with conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM guilda_membros WHERE guilda_id = ? ORDER BY entrou_em", (guilda_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def contar_membros_guilda(guilda_id):
    with conectar() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM guilda_membros WHERE guilda_id = ?", (guilda_id,)
        ).fetchone()[0]


def adicionar_membro_guilda(user_id, guilda_id):
    with conectar() as conn:
        conn.execute(
            "INSERT INTO guilda_membros (user_id, guilda_id, entrou_em, papel) VALUES (?, ?, ?, 'membro')",
            (user_id, guilda_id, time.time()),
        )


def remover_membro_guilda(user_id):
    with conectar() as conn:
        conn.execute("DELETE FROM guilda_membros WHERE user_id = ?", (user_id,))


def transferir_lideranca_guilda(guilda_id, novo_lider_id):
    with conectar() as conn:
        conn.execute("UPDATE guildas SET lider_id = ? WHERE id = ?", (novo_lider_id, guilda_id))
        conn.execute(
            "UPDATE guilda_membros SET papel = 'membro' WHERE guilda_id = ? AND papel = 'lider'",
            (guilda_id,),
        )
        conn.execute(
            "UPDATE guilda_membros SET papel = 'lider' WHERE guilda_id = ? AND user_id = ?",
            (guilda_id, novo_lider_id),
        )


def definir_home_guilda(guilda_id, andar):
    with conectar() as conn:
        conn.execute("UPDATE guildas SET andar_home = ? WHERE id = ?", (andar, guilda_id))


def apagar_guilda(guilda_id):
    with conectar() as conn:
        conn.execute("DELETE FROM guildas WHERE id = ?", (guilda_id,))
        conn.execute("DELETE FROM guilda_membros WHERE guilda_id = ?", (guilda_id,))
        conn.execute("DELETE FROM guilda_bau WHERE guilda_id = ?", (guilda_id,))
        conn.execute("DELETE FROM guilda_log WHERE guilda_id = ?", (guilda_id,))
        conn.execute("DELETE FROM guilda_raide WHERE guilda_id = ?", (guilda_id,))
        conn.execute("DELETE FROM guilda_convites WHERE guilda_id = ?", (guilda_id,))


def guilda_add_moedas(guilda_id, valor):
    with conectar() as conn:
        conn.execute("UPDATE guildas SET moedas = moedas + ? WHERE id = ?", (valor, guilda_id))


# ---------------- baú da guilda ----------------
def bau_add_item(guilda_id, item, qtd):
    with conectar() as conn:
        conn.execute(
            """INSERT INTO guilda_bau (guilda_id, item, qtd) VALUES (?, ?, ?)
               ON CONFLICT(guilda_id, item) DO UPDATE SET qtd = qtd + excluded.qtd""",
            (guilda_id, item, qtd),
        )


def bau_remove_item(guilda_id, item, qtd):
    with conectar() as conn:
        row = conn.execute(
            "SELECT qtd FROM guilda_bau WHERE guilda_id = ? AND item = ?", (guilda_id, item)
        ).fetchone()
        if not row or row["qtd"] < qtd:
            return False
        conn.execute(
            "UPDATE guilda_bau SET qtd = qtd - ? WHERE guilda_id = ? AND item = ?",
            (qtd, guilda_id, item),
        )
        conn.execute(
            "DELETE FROM guilda_bau WHERE guilda_id = ? AND item = ? AND qtd <= 0", (guilda_id, item)
        )
    return True


def get_bau(guilda_id):
    with conectar() as conn:
        rows = conn.execute(
            "SELECT item, qtd FROM guilda_bau WHERE guilda_id = ? AND qtd > 0 ORDER BY item",
            (guilda_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def guilda_log(guilda_id, user_id, acao, item=None, qtd=None):
    with conectar() as conn:
        conn.execute(
            """INSERT INTO guilda_log (guilda_id, user_id, acao, item, qtd, quando)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (guilda_id, user_id, acao, item, qtd, time.time()),
        )


def get_guilda_log(guilda_id, limite=10):
    with conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM guilda_log WHERE guilda_id = ? ORDER BY quando DESC LIMIT ?",
            (guilda_id, limite),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------- convites de guilda ----------------
# Sem agendador: convite vencido é limpo na leitura, não por task de fundo
# (ver decisoes.md § Convite de guilda). Toda função abaixo apaga o que já
# venceu antes de olhar o resto da tabela.
def _limpar_convites_vencidos(conn):
    conn.execute("DELETE FROM guilda_convites WHERE expira_em <= ?", (time.time(),))


def criar_ou_renovar_convite(guilda_id, user_id, convidado_por, segundos):
    with conectar() as conn:
        _limpar_convites_vencidos(conn)
        conn.execute(
            """INSERT INTO guilda_convites (guilda_id, user_id, convidado_por, expira_em)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(guilda_id, user_id) DO UPDATE SET
                   convidado_por = excluded.convidado_por, expira_em = excluded.expira_em""",
            (guilda_id, user_id, convidado_por, time.time() + segundos),
        )


def get_convite(guilda_id, user_id):
    with conectar() as conn:
        _limpar_convites_vencidos(conn)
        row = conn.execute(
            "SELECT * FROM guilda_convites WHERE guilda_id = ? AND user_id = ?",
            (guilda_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def contar_convites_pendentes_guilda(guilda_id):
    with conectar() as conn:
        _limpar_convites_vencidos(conn)
        return conn.execute(
            "SELECT COUNT(*) FROM guilda_convites WHERE guilda_id = ?", (guilda_id,)
        ).fetchone()[0]


def convites_do_jogador(user_id):
    """Convites pendentes de um jogador, com o nome da guilda já junto —
    quem convidou pode ter saído da guilda nesse meio tempo, então o
    convite mostra o id salvo mesmo que não seja mais membro."""
    with conectar() as conn:
        _limpar_convites_vencidos(conn)
        rows = conn.execute(
            """SELECT guilda_convites.*, guildas.nome AS guilda_nome
               FROM guilda_convites JOIN guildas ON guildas.id = guilda_convites.guilda_id
               WHERE guilda_convites.user_id = ?
               ORDER BY guilda_convites.expira_em""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def apagar_convite(guilda_id, user_id):
    with conectar() as conn:
        conn.execute(
            "DELETE FROM guilda_convites WHERE guilda_id = ? AND user_id = ?", (guilda_id, user_id)
        )


def apagar_convites_do_jogador(user_id):
    with conectar() as conn:
        conn.execute("DELETE FROM guilda_convites WHERE user_id = ?", (user_id,))


# ---------------- cooldown de raide (por guilda, não por jogador) ----------------
def checar_cooldown_raide(guilda_id):
    with conectar() as conn:
        row = conn.execute(
            "SELECT expira_em FROM guilda_raide WHERE guilda_id = ?", (guilda_id,)
        ).fetchone()
    if row and row["expira_em"] > time.time():
        return row["expira_em"] - time.time()
    return 0.0


def set_cooldown_raide(guilda_id, segundos):
    with conectar() as conn:
        conn.execute(
            """INSERT INTO guilda_raide (guilda_id, expira_em) VALUES (?, ?)
               ON CONFLICT(guilda_id) DO UPDATE SET expira_em = excluded.expira_em""",
            (guilda_id, time.time() + segundos),
        )


# ---------------- cooldown de troca de home (por guilda) ----------------
def checar_cooldown_home(guilda_id):
    with conectar() as conn:
        row = conn.execute(
            "SELECT expira_em FROM guilda_home_cooldown WHERE guilda_id = ?", (guilda_id,)
        ).fetchone()
    if row and row["expira_em"] > time.time():
        return row["expira_em"] - time.time()
    return 0.0


def set_cooldown_home(guilda_id, segundos):
    with conectar() as conn:
        conn.execute(
            """INSERT INTO guilda_home_cooldown (guilda_id, expira_em) VALUES (?, ?)
               ON CONFLICT(guilda_id) DO UPDATE SET expira_em = excluded.expira_em""",
            (guilda_id, time.time() + segundos),
        )


# ---------------- chefes derrotados (andares 11+) ----------------
# Material de chefe acima do andar 10 não usa a chance fixa do dict: a
# primeira vitória garante o material (100%), da segunda em diante cai pra
# 15% — ver combate.recompensar() e decisoes.md § Morte e reconquista.
def vezes_derrotado_chefe(user_id, andar):
    with conectar() as conn:
        row = conn.execute(
            "SELECT vezes FROM chefes_derrotados WHERE user_id = ? AND andar = ?",
            (user_id, andar),
        ).fetchone()
    return row["vezes"] if row else 0


def registrar_vitoria_chefe(user_id, andar):
    with conectar() as conn:
        conn.execute(
            """INSERT INTO chefes_derrotados (user_id, andar, vezes) VALUES (?, ?, 1)
               ON CONFLICT(user_id, andar) DO UPDATE SET vezes = vezes + 1""",
            (user_id, andar),
        )


# ---------------- sidequests ----------------
# Nenhuma quest existe ainda -- esta funcao e' o alicerce que o diálogo com
# NPC consulta pra decidir qual bloco de opcoes mostrar (ver dialogos.py e
# npcs.opcoes_do_dialogo). Tabela vazia = todo mundo em 'antes'.
def estado_sidequest(user_id, quest_id):
    """'antes' sem linha na tabela, senao traduz o estado salvo ('ativa'/
    'concluida') pro vocabulario do dialogo ('durante'/'depois')."""
    with conectar() as conn:
        row = conn.execute(
            "SELECT estado FROM sidequests WHERE user_id = ? AND quest_id = ?",
            (user_id, quest_id),
        ).fetchone()
    if not row:
        return "antes"
    return {"ativa": "durante", "concluida": "depois"}[row["estado"]]


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


# ---------------- instâncias de item ----------------
# Peça comum é só quantidade em `inventario`, sem identidade -- vira
# instância (linha própria, com dono e id) só quando recebe melhoria ou
# encantamento (encantamento ainda não existe, ver decisoes.md). Equipada:
# o dono aponta pra ela via jogadores.<slot>_instancia_id (jogadores.<slot>
# continua guardando a CHAVE do item, sempre -- a coluna de instância só
# diz SE e QUAL cópia daquela chave é a modificada). Desequipada: a
# instância "mora" na mochila -- não existe linha própria pra isso, o
# estado é derivado (pertence ao dono e nenhum slot dele aponta pro id
# dela). Substitui a tabela `upgrades` (que fica no schema, sem uso, por
# nunca se dropar tabela com dado real -- ver decisoes.md § Instâncias).
def criar_instancia(dono, item, nivel_melhoria=0):
    with conectar() as conn:
        cur = conn.execute(
            "INSERT INTO instancias (dono, item, nivel_melhoria) VALUES (?, ?, ?)",
            (dono, item, nivel_melhoria),
        )
    return cur.lastrowid


def get_instancia(instancia_id):
    if not instancia_id:
        return None
    with conectar() as conn:
        row = conn.execute("SELECT * FROM instancias WHERE id = ?", (instancia_id,)).fetchone()
    return dict(row) if row else None


def set_nivel_melhoria(instancia_id, nivel):
    with conectar() as conn:
        conn.execute("UPDATE instancias SET nivel_melhoria = ? WHERE id = ?", (nivel, instancia_id))


def excluir_instancia(instancia_id):
    with conectar() as conn:
        conn.execute("DELETE FROM instancias WHERE id = ?", (instancia_id,))


def instancias_na_mochila(user_id):
    """Instâncias do jogador que não estão equipadas em slot nenhum agora
    -- 'na mochila' é estado derivado, não uma coluna própria: compara
    contra os ponteiros de jogadores pra descobrir quais ids estão
    equipados."""
    with conectar() as conn:
        jog = conn.execute(
            """SELECT arma_instancia_id, armadura_instancia_id,
                      anel_instancia_id, colar_instancia_id
               FROM jogadores WHERE user_id = ?""",
            (user_id,),
        ).fetchone()
        equipadas = set(jog) if jog else set()
        rows = conn.execute("SELECT * FROM instancias WHERE dono = ?", (user_id,)).fetchall()
    return [dict(r) for r in rows if r["id"] not in equipadas]


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


# ---------------- wrappers assincronos ----------------
# `asyncio.to_thread` em volta das funcoes sincronas de sempre, so' pras
# chamadas que ja rodam dentro de `async def` no caminho quente do combate.
# Nao existe versao async das 47 funcoes do arquivo -- so' cria wrapper quem
# migra de verdade, e a funcao sincrona continua sendo a fonte da verdade
# (e' o que os 20 testes chamam direto). Com a conexao unica + RLock da
# parte A, isso NAO paraleliza consulta -- o ganho e' o event loop ficar
# livre enquanto a thread espera o lock. Ver decisoes.md § Cartao 3 - parte B.
async def a_get_jogador(*args, **kwargs):
    return await asyncio.to_thread(get_jogador, *args, **kwargs)


async def a_atualizar_jogador(*args, **kwargs):
    return await asyncio.to_thread(atualizar_jogador, *args, **kwargs)


async def a_marcar_combate(*args, **kwargs):
    return await asyncio.to_thread(marcar_combate, *args, **kwargs)


async def a_vezes_derrotado_chefe(*args, **kwargs):
    return await asyncio.to_thread(vezes_derrotado_chefe, *args, **kwargs)


async def a_registrar_vitoria_chefe(*args, **kwargs):
    return await asyncio.to_thread(registrar_vitoria_chefe, *args, **kwargs)


async def a_add_item(*args, **kwargs):
    return await asyncio.to_thread(add_item, *args, **kwargs)


async def a_remove_item(*args, **kwargs):
    return await asyncio.to_thread(remove_item, *args, **kwargs)


async def a_checar_cooldown(*args, **kwargs):
    return await asyncio.to_thread(checar_cooldown, *args, **kwargs)


async def a_set_cooldown(*args, **kwargs):
    return await asyncio.to_thread(set_cooldown, *args, **kwargs)