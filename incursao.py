# incursao.py
# Step D, commit 1: o andar corrompido. O Herói selou a torre de dentro pra
# proteger quem estava lá do que havia fora; a porta atrás do trono (Step B)
# ficou aberta. A incursão é a consequência -- coisas de fora entrando num
# abrigo, um andar por dia, sempre entre o 2 e o Selo (10). Nunca o 1 (onde
# todo mundo começa) nem acima do Selo (11-15, sem comércio, sem esse tipo de
# evento -- ver decisoes.md § Step D).
#
# Sem tabela nova no banco: o sorteio é uma função pura do dia (fuso
# America/Sao_Paulo), a mesma pra todo mundo, e reiniciar o bot no meio do
# dia não pode sortear de novo. `random.Random(semente_string)` resolve isso
# sozinho -- desde sempre o CPython converte uma seed string de forma
# determinística (sha512 por baixo, documentado), então a MESMA string
# sempre dá o MESMO resultado, em qualquer processo, sem precisar persistir
# nada. Ver decisoes.md § Step D.
import random
from datetime import datetime
from zoneinfo import ZoneInfo

import game_data
from andares_altos import ANDAR_ACIMA_DO_SELO

FUSO = ZoneInfo("America/Sao_Paulo")

ANDAR_MIN_INCURSAO = 2                    # nunca o andar 1
ANDAR_MAX_INCURSAO = ANDAR_ACIMA_DO_SELO  # nunca acima do Selo


def _dia(momento=None):
    m = momento or datetime.now(FUSO)
    return m.date().isoformat()


def andar_do_dia(momento=None):
    """O andar corrompido de hoje -- determinístico, sem estado. Mesma
    semente (a data em ISO) em qualquer processo dá o mesmo `randint`,
    então reiniciar o bot no meio do dia não sorteia de novo -- só
    recalcula o mesmo número."""
    semente = f"incursao-{_dia(momento)}"
    return random.Random(semente).randint(ANDAR_MIN_INCURSAO, ANDAR_MAX_INCURSAO)


def andar_esta_corrompido(andar, momento=None):
    return andar == andar_do_dia(momento)


def nome_sombrio(nome_original):
    """'Vira de sombra' é a mesma criatura, tomada -- não troca de espécie.
    Prefixo simples, reaproveitado tanto pro nome de exibição quanto (no
    commit 4) pra reconhecer que um mob é de incursão sem precisar de um
    campo à parte em todo call site."""
    return f"Sombra de {nome_original}"


# ---------------- commit 2: as criaturas escalam por inteiro ----------------
BONUS_XP_MOEDAS_INCURSAO = 2   # "XP e dinheiro dobram" -- decisão firme, não é ajuste fino


def andar_referencia(jogador):
    """O andar que representa o PRÓPRIO progresso do jogador (`andar_max`,
    travado em [1, ANDAR_MAXIMO]) -- nunca o andar corrompido em si
    (sempre baixo, 2-10). É esse andar que empresta hp/atk/def/xp/moedas
    pra criatura corrompida: "escalar pelo jogador que deu o comando"
    significa escalar por QUANTO ele já progrediu, não pelo número baixo
    do andar sorteado -- senão um jogador de andar_max 15 numa incursão
    no andar 2 enfrentaria a mesma criatura fraca que um jogador novo, e
    mataria em um golpe (ver decisoes.md § Step D -- o raciocínio
    completo, com o número de XP que isso destravaria)."""
    return max(1, min(jogador["andar_max"], game_data.ANDAR_MAXIMO))


def sortear_criatura(jogador, momento=None):
    """A criatura de uma incursão: nome/flavor vêm do andar corrompido (a
    "espécie" local que virou sombra -- ver nome_sombrio); hp/atk/def/xp/
    moedas/elemento/drops vêm do andar de REFERÊNCIA do jogador --
    pareados pelo mesmo índice na lista de 3 monstros de cada andar (as
    duas listas nunca têm tamanho diferente, ver game_data.ANDARES). XP e
    moedas dobram por cima do valor emprestado.

    Por que emprestar do andar de referência em vez de inventar uma
    fórmula de escala nova: os números por andar em game_data.ANDARES já
    SÃO a curva de balanceamento do jogo inteiro, andar a andar --
    reaproveitar é mais simples e não corre o risco de destoar dela.
    Efeito colateral aceito (o cartão foi explícito): pro MESMO jogador,
    andar 2 corrompido e andar 9 corrompido viram o mesmo desafio -- o
    sorteio decide onde ir, a referência decide o que enfrentar."""
    andar_corrompido = andar_do_dia(momento)
    locais = game_data.ANDARES[andar_corrompido]["monstros"]
    indice = random.randrange(len(locais))
    nome_local = locais[indice]["nome"]
    referencia = game_data.ANDARES[andar_referencia(jogador)]["monstros"][indice]
    mob = dict(referencia)
    mob["nome"] = nome_sombrio(nome_local)
    mob["xp"] = referencia["xp"] * BONUS_XP_MOEDAS_INCURSAO
    mob["moedas"] = referencia["moedas"] * BONUS_XP_MOEDAS_INCURSAO
    mob["corrompido"] = True
    return mob
