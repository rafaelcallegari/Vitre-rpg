# passivas.py
# Motor de passivas de ascensão -- espelha condicoes.py na forma: uma
# função de consulta por efeito, cada uma recebendo o jogador (dict) e
# devolvendo um número ou bool. combate.py e os pontos de recompensa
# (cacar/explorar/chefe, ver bot.py/combate.py) NUNCA fazem
# `if jogador["ascensao"] == "assassino"` espalhado -- só chamam estas
# funções, que sabem ler ASCENSOES/PASSIVAS (game_data.py) por baixo.
# Nenhum número mora aqui: quem carrega o valor de cada passiva é
# game_data.PASSIVAS. Ver decisoes.md § Step 2a.
#
# Ao contrário de condicoes.py (estado por LUTA, em luta.condicoes), isto
# aqui é estado PERSISTENTE do jogador (coluna jogadores.ascensao) -- não
# tem tick(), não expira, não nasce nem morre dentro de uma luta.
#
# Todas as consultas devolvem o valor NEUTRO (o que não muda nada) quando
# `ascensao` é NULL (jogador não ascendeu), não é mais uma chave válida em
# ASCENSOES (ramo que existiu e foi removido do jogo -- ver decisoes.md §
# Step 2a, Batedor de Carteira), ou é um ramo válido que ainda não tem essa
# passiva específica. Nunca `ASCENSOES[jogador["ascensao"]]` direto --
# sempre confirma que a chave existe antes de indexar.
import atributos as at
from game_data import ASCENSOES, PASSIVAS


def _ramo(jogador):
    ascensao = (jogador or {}).get("ascensao")
    return ascensao if ascensao in ASCENSOES else None


def _tem_passiva(jogador, chave):
    ramo = _ramo(jogador)
    return ramo is not None and chave in ASCENSOES[ramo]["passivas"]


def critico_garantido(jogador, rodada):
    """Sangue Frio (assassino): o primeiro golpe da luta (rodada 1) é
    crítico garantido. Só isso -- combate.py ainda precisa garantir que não
    dispara de novo pra quem já usou o golpe garantido nesta luta (ex.: o
    segundo hit de Corte Rápido, no mesmo clique), e isso é estado por
    COMBATENTE, não cabe numa consulta stateless como esta."""
    return rodada == 1 and _tem_passiva(jogador, "sangue_frio")


def multiplicador_critico(jogador):
    """Fator extra sobre at.MULTIPLICADOR_CRITICO quando o golpe critica --
    1.0 = nenhuma passiva mexe nisso. Olho de Águia (arqueiro) soma um
    bônus fixo ao multiplicador base (PASSIVAS["olho_de_aguia"]["valor"]),
    reexpresso aqui como razão pra caber num motor sempre multiplicativo --
    é recalculado a cada chamada, então continua somando exatamente esse
    bônus mesmo se at.MULTIPLICADOR_CRITICO for rebalanceado depois."""
    if _tem_passiva(jogador, "olho_de_aguia"):
        bonus = PASSIVAS["olho_de_aguia"]["valor"]
        return (at.MULTIPLICADOR_CRITICO + bonus) / at.MULTIPLICADOR_CRITICO
    return 1.0


def bonus_moedas(jogador):
    """Fração ADICIONAL de moedas -- 0.0 = nenhuma passiva mexe nisso."""
    if _tem_passiva(jogador, "instinto_ladino"):
        return PASSIVAS["instinto_ladino"]["valor_moedas"]
    return 0.0


def bonus_material(jogador):
    """Fração ADICIONAL de CHANCE de material por item -- 0.0 = nenhuma
    passiva mexe nisso. Mexe na chance, não na quantidade -- ver
    decisoes.md § Step 2a (chance, não quantidade)."""
    if _tem_passiva(jogador, "instinto_ladino"):
        return PASSIVAS["instinto_ladino"]["valor_material"]
    return 0.0


def bonus_duracao_travamento(jogador):
    """Rodadas ADICIONAIS em todo Travamento (pula_turno) que o JOGADOR
    aplica no chefe -- Prisão de Cristal (skill) e o Travamento da arma
    elemental (gelo) os dois consultam isto. 0 = nenhuma passiva mexe
    nisso. É bônus de quem APLICA, não de quem sofre -- por isso o
    parâmetro é sempre o jogador que deu o golpe, nunca o alvo."""
    if _tem_passiva(jogador, "inverno_constante"):
        return PASSIVAS["inverno_constante"]["valor"]
    return 0
