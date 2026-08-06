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
MANA_POR_MINUTO_REGEN = 1   # fixo, nao percentual — mais lento que o cooldown de chefe (15 min)

CRITICO_BASE = 0.10       # critico de quem esta desarmado ou com arma de forca
MULTIPLICADOR_CRITICO = 1.8
K_DEFESA = 50             # constante da curva de reducao de dano
TETO_REDUCAO = 0.60       # reducao maxima que a defesa pode dar
TETO_ESQUIVA = 0.25

# regeneracao fora de combate — HP e mana usam a mesma pausa pos-combate
REGEN_POR_MINUTO = 0.05   # fracao do HP maximo recuperada por minuto parado
REGEN_TETO = 0.70         # ela nunca passa disso — o resto e' pocao
REGEN_PAUSA_SEG = 180     # tempo sem lutar antes de comecar a regenerar

ATRIBUTO_PADRAO_ARMA = "destreza"   # maos vazias e arma sem atributo declarado
ESCALONAMENTO_DESARMADO_ORADOR = 0.5   # Orador base briga puxado; cheio vem so' na ascensao pra Monge

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
        "desc": "Mana maxima — quantos lancamentos cabem numa luta de chefe.",
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


def ataque(valor_atributo, bonus_arma=0, escala=1.0):
    return 5 + int(2 * valor_atributo * escala) + bonus_arma


def defesa(bonus_armadura=0):
    """Defesa vem só de equipamento — CON não participa mais (só dá HP)."""
    return 2 + bonus_armadura


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

def _regenerado(atual, teto, valor_em, combate_em, agora, ganho_por_minuto):
    """Nucleo comum da regeneracao fora de combate — usado por HP e mana.

    valor_em: quando o recurso mudou pela ultima vez.
    combate_em: quando o jogador lutou pela ultima vez (pausa a regen por
    REGEN_PAUSA_SEG depois disso).
    """
    atual = max(0, atual)
    if atual >= teto:
        return atual
    inicio = max(valor_em or 0, (combate_em or 0) + REGEN_PAUSA_SEG)
    minutos = (agora - inicio) / 60
    if minutos <= 0:
        return atual
    return min(teto, atual + int(ganho_por_minuto * minutos))


def _segundos_para_regenerar(atual, teto, valor_em, combate_em, agora):
    if max(0, atual) >= teto:
        return 0
    inicio = max(valor_em or 0, (combate_em or 0) + REGEN_PAUSA_SEG)
    return max(0, int(inicio - agora))


def hp_regenerado(hp_atual, hp_max, hp_em, combate_em, agora):
    """HP depois de ficar parado. So conta tempo sem lutar, e para em 70% — o
    resto e' pocao."""
    return _regenerado(
        hp_atual, int(hp_max * REGEN_TETO), hp_em, combate_em, agora,
        hp_max * REGEN_POR_MINUTO,
    )


def segundos_para_regenerar(hp_atual, hp_max, hp_em, combate_em, agora):
    """Quanto falta para a regeneracao de HP comecar. 0 = ja esta regenerando."""
    return _segundos_para_regenerar(hp_atual, int(hp_max * REGEN_TETO), hp_em, combate_em, agora)


def mana_regenerada(mana_atual, mana_max, mana_em, combate_em, agora):
    """Mana depois de ficar parado. 1 por minuto, sem teto reduzido — vai ate' o maximo."""
    return _regenerado(mana_atual, mana_max, mana_em, combate_em, agora, MANA_POR_MINUTO_REGEN)


def segundos_para_regenerar_mana(mana_atual, mana_max, mana_em, combate_em, agora):
    return _segundos_para_regenerar(mana_atual, mana_max, mana_em, combate_em, agora)


# ------------------------------------------------------------------- resumo

def ficha(nivel, atribs, arma=None, armadura=None, classe=None):
    """Todos os derivados de uma vez — usado nos embeds de perfil e status."""
    arma = arma or {}
    armadura = armadura or {}
    con = atribs["constituicao"]
    des = atribs["destreza"]
    chave = atributo_da_arma(arma)
    escala = ESCALONAMENTO_DESARMADO_ORADOR if (not arma and classe == "orador") else 1.0
    val_def = defesa(armadura.get("def", 0))
    return {
        "hp_max": hp_maximo(nivel, con),
        "mana_max": mana_maxima(nivel, atribs["inteligencia"]),
        "atk": ataque(atribs[chave], arma.get("atk", 0), escala),
        "def": val_def,
        "reducao": reducao_dano(val_def),
        "esquiva": chance_esquiva(des, des),
        "critico": critico_da_arma(arma),
        "atributo_arma": chave,
    }


# ------------------------------------------------------------- consumiveis

def restauracao_do_item(dado, hp_max, mana_max):
    """('hp', valor) ou ('mana', valor) — quanto o consumivel recupera.

    Cura fixa ("cura") ou por porcentagem ("cura_pct") mexe em HP; "mana" ou
    "mana_pct" mexe em mana. Cada item so' declara um dos quatro campos.
    """
    if "cura_pct" in dado:
        return "hp", max(1, int(hp_max * dado["cura_pct"]))
    if "cura" in dado:
        return "hp", dado["cura"]
    if "mana_pct" in dado:
        return "mana", max(1, int(mana_max * dado["mana_pct"]))
    return "mana", dado.get("mana", 0)