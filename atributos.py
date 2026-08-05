# atributos.py
# Sistema de atributos do Vitre bot.
# Concentra todas as formulas derivadas de nivel, atributos e equipamento.
# Nao toca no banco nem no discord — e' so' matematica.

import unicodedata

# ---------------------------------------------------------------- constantes

BASE = 5                  # valor inicial de cada atributo
PONTOS_POR_NIVEL = 3      # pontos livres ganhos a cada nivel
CURA_LEVEL_UP = 0.50      # fracao do HP maximo restaurada ao subir de nivel

HP_BASE = 60              # HP de um personagem com 0 de CON no nivel 1
HP_POR_CON = 10           # HP ganho por ponto de constituicao
HP_POR_NIVEL = 10         # HP ganho automaticamente a cada nivel

MANA_BASE = 20
MANA_POR_INT = 5

CRITICO_BASE = 0.10       # critico de quem esta desarmado ou com arma de forca
MULTIPLICADOR_CRITICO = 1.8
K_DEFESA = 50             # constante da curva de reducao de dano
TETO_REDUCAO = 0.60       # reducao maxima que a defesa pode dar
TETO_ESQUIVA = 0.25

# regeneracao fora de combate
REGEN_POR_MINUTO = 0.05   # fracao do HP maximo recuperada por minuto parado
REGEN_TETO = 0.70         # ela nunca passa disso — o resto e' pocao
REGEN_PAUSA_SEG = 180     # tempo sem lutar antes de comecar a regenerar

ATRIBUTO_PADRAO_ARMA = "forca"   # arma sem atributo declarado (e maos vazias)

ATRIBUTOS = {
    "forca": {
        "nome": "Forca", "sigla": "FOR", "emoji": "💪",
        "desc": "Dano de espadas, machados e martelos.",
    },
    "destreza": {
        "nome": "Destreza", "sigla": "DES", "emoji": "🎯",
        "desc": "Dano de adagas, arcos e foices. Iniciativa, esquiva e fuga.",
    },
    "constituicao": {
        "nome": "Constituicao", "sigla": "CON", "emoji": "🛡️",
        "desc": f"+{HP_POR_CON} de HP maximo e mais defesa.",
    },
    "inteligencia": {
        "nome": "Inteligencia", "sigla": "INT", "emoji": "🔮",
        "desc": "Mana maxima e dano de habilidade (habilidades ainda nao existem).",
    },
}

APELIDOS = {
    "for": "forca", "forca": "forca", "força": "forca", "str": "forca", "f": "forca",
    "des": "destreza", "destreza": "destreza", "dex": "destreza",
    "agi": "destreza", "d": "destreza",
    "con": "constituicao", "constituicao": "constituicao", "constituição": "constituicao",
    "vit": "constituicao", "c": "constituicao",
    "int": "inteligencia", "inteligencia": "inteligencia", "inteligência": "inteligencia",
    "mag": "inteligencia", "i": "inteligencia",
}


# ------------------------------------------------------------------ helpers

def _normalizar(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower().strip())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def encontrar_atributo(texto):
    """Aceita 'FOR', 'forca', 'força', 'str', 'des'. Retorna a chave ou None."""
    chave = _normalizar(texto)
    if not chave:
        return None
    if chave in APELIDOS:
        return APELIDOS[chave]
    for nome in ATRIBUTOS:
        if _normalizar(nome).startswith(chave):
            return nome
    return None


def extrair(j):
    """Le os quatro atributos de uma linha do banco e devolve um dict."""
    return {nome: int(j[nome] or 0) for nome in ATRIBUTOS}


def distribuicao_inicial():
    return {nome: BASE for nome in ATRIBUTOS}


def pontos_ganhos(nivel):
    """Total de pontos livres que um personagem daquele nivel ja recebeu."""
    return PONTOS_POR_NIVEL * max(0, nivel - 1)


def custo_respec(nivel):
    return 50 * nivel


# -------------------------------------------------------------------- armas

def atributo_da_arma(arma):
    """Qual atributo escala o dano desta arma. Maos vazias = forca."""
    return (arma or {}).get("atributo", ATRIBUTO_PADRAO_ARMA)


def critico_da_arma(arma):
    """Armas de destreza batem menos e critam mais."""
    return (arma or {}).get("critico", CRITICO_BASE)


# -------------------------------------------------------- atributos -> stats

def hp_maximo(nivel, constituicao):
    return HP_BASE + HP_POR_CON * constituicao + HP_POR_NIVEL * (nivel - 1)


def mana_maxima(nivel, inteligencia):
    return MANA_BASE + MANA_POR_INT * inteligencia


def ataque(valor_atributo, bonus_arma=0):
    return 5 + 2 * valor_atributo + bonus_arma


def defesa(constituicao, bonus_armadura=0):
    return 2 + constituicao + bonus_armadura


# ------------------------------------------------------------ dano e chances

def reducao_dano(valor_defesa):
    """Fracao do dano que a defesa apara. Curva com teto — nunca zera o dano."""
    if valor_defesa <= 0:
        return 0.0
    return min(TETO_REDUCAO, valor_defesa / (valor_defesa + K_DEFESA))


def aplicar_defesa(dano_bruto, valor_defesa):
    """Dano final depois da defesa do alvo. Sempre pelo menos 1."""
    return max(1, int(dano_bruto * (1 - reducao_dano(valor_defesa))))


def destreza_monstro(andar):
    """Destreza implicita de um monstro do andar N (nao existe em game_data)."""
    return 4 + 2 * (andar - 1)


def _limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def chance_iniciativa(destreza, destreza_alvo):
    return _limitar(0.50 + 0.02 * (destreza - destreza_alvo), 0.20, 0.90)


def chance_esquiva(destreza, destreza_atacante):
    return _limitar(0.02 + 0.01 * (destreza - destreza_atacante), 0.0, TETO_ESQUIVA)


def chance_fuga(destreza, destreza_alvo, eh_chefe=False):
    base = 0.45 + 0.02 * (destreza - destreza_alvo)
    if eh_chefe:
        base -= 0.15
    return _limitar(base, 0.10, 0.85)


# ---------------------------------------------------------------- regeneracao

def hp_regenerado(hp_atual, hp_max, hp_em, combate_em, agora):
    """HP depois de ficar parado. So conta tempo sem lutar, e para no teto.

    hp_em: quando o HP mudou pela ultima vez.
    combate_em: quando o jogador lutou pela ultima vez.
    """
    hp_atual = max(0, hp_atual)
    teto = int(hp_max * REGEN_TETO)
    if hp_atual >= teto:
        return hp_atual
    inicio = max(hp_em or 0, (combate_em or 0) + REGEN_PAUSA_SEG)
    minutos = (agora - inicio) / 60
    if minutos <= 0:
        return hp_atual
    ganho = int(hp_max * REGEN_POR_MINUTO * minutos)
    return min(teto, hp_atual + ganho)


def segundos_para_regenerar(hp_atual, hp_max, hp_em, combate_em, agora):
    """Quanto falta para a regeneracao comecar. 0 = ja esta regenerando."""
    if max(0, hp_atual) >= int(hp_max * REGEN_TETO):
        return 0
    inicio = max(hp_em or 0, (combate_em or 0) + REGEN_PAUSA_SEG)
    return max(0, int(inicio - agora))


# ------------------------------------------------------------------- resumo

def ficha(nivel, atribs, arma=None, armadura=None):
    """Todos os derivados de uma vez — usado nos embeds de perfil e status."""
    arma = arma or {}
    armadura = armadura or {}
    con = atribs["constituicao"]
    des = atribs["destreza"]
    chave = atributo_da_arma(arma)
    val_def = defesa(con, armadura.get("def", 0))
    return {
        "hp_max": hp_maximo(nivel, con),
        "mana_max": mana_maxima(nivel, atribs["inteligencia"]),
        "atk": ataque(atribs[chave], arma.get("atk", 0)),
        "def": val_def,
        "reducao": reducao_dano(val_def),
        "esquiva": chance_esquiva(des, des),
        "critico": critico_da_arma(arma),
        "atributo_arma": chave,
    }