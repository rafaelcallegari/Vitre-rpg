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
