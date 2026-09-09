# mestres.py
# Os quatro mestres do andar 7 (Step 4) -- lógica pura, sem discord. Segue o
# mesmo padrão de andares_altos.py: sem instalar(bot, ...), bot.py chama as
# funções daqui direto de dentro de `falar()`. A UI (embed/view da conversa e
# do fluxo de escolha de ramo) mora em bot.py, igual a como GuiaDialogoView
# já faz pra andares_altos. Ver decisoes.md § Step 4.
import database as db
import game_data

# chave do NPC (campo "dialogo" em npcs.NPCS) por classe base -- usado tanto
# por npcs.mestre_do_andar quanto pelos textos de recusa abaixo.
MESTRES = {
    "guerreiro": "cavaleiro",
    "orador": "augustiel",
    "mago": "merlin",
    "ladino": "arvin",
}

# Fração roubada na primeira conversa com o Arvin -- constante nomeada, ponto
# de partida pra playtest (ver Regras do projeto em decisoes.md).
VALOR_ROUBO_ARVIN = 0.20

RECUSA_CLASSE_ERRADA = {
    "cavaleiro": "Isso aqui não é pra você. Minha espada só ensina quem já carrega uma parecida.",
    "augustiel": "Minha paciência é grande, mas o que eu guardo não serve pro seu caminho.",
    "merlin": "Minha linhagem não aceita quem nasceu fora dela. O seu mestre você já cruzou, lá embaixo.",
    "arvin": "Rouba de mim outra hora. Isso aqui só interessa quem anda na sombra que eu ando.",
}

TEXTO_NIVEL_BAIXO = 'Ele mede você com o olhar e balança a cabeça. "Ainda não. Volta quando pesar mais."'
TEXTO_SEM_ORBE = '"Você não trouxe nada." Ele espera algo que ainda não está com você.'
TEXTO_JA_ASCENDEU = "Ele olha pra você como quem já viu essa conversa acontecer. \"Você já escolheu. Não tem duas vezes.\""


def npc_mestre_de(classe):
    """Chave do NPC (campo "dialogo") que é o mestre daquela classe base."""
    return MESTRES.get(classe)


def pode_ascender(jogador):
    """(ok: bool, motivo: str|None). motivo é None só quando ok=True --
    quem chama decide o texto a partir do motivo (recusa em personagem,
    não erro genérico). Ordem importa pouco aqui: os quatro requisitos são
    independentes, o primeiro que falhar já é a resposta certa."""
    if jogador["ascensao"]:
        return False, "ja_ascendeu"
    if jogador["nivel"] < game_data.NIVEL_ASCENSAO_PADRAO:
        return False, "nivel_baixo"
    if jogador["andar"] != game_data.ANDAR_MESTRES:
        return False, "andar_errado"
    if not db.tem_item(jogador["user_id"], "orbe_de_ascensao"):
        return False, "sem_orbe"
    return True, None


def ramos_da_base(classe):
    """Os 2 ou 3 ramos que aquela base abre -- sempre de ASCENSOES, nunca
    hardcoded (o Ladino tem 2, as outras 3 -- isso acontece sozinho)."""
    return {k: v for k, v in game_data.ASCENSOES.items() if v["base"] == classe}


def descricao_ramo(chave_ramo):
    """(dados_do_ramo, skill, [passiva, ...]) -- texto REAL de cada peça,
    não o nome. É o que faz a escolha ser decisão e não sorteio (ver
    decisoes.md § Step 4)."""
    dados = game_data.ASCENSOES[chave_ramo]
    skill = game_data.HABILIDADES[dados["skill"]]
    passivas_do_ramo = [game_data.PASSIVAS[p] for p in dados["passivas"]]
    return dados, skill, passivas_do_ramo


def executar_ascensao(user_id, ramo):
    """Só grava -- pressupõe pode_ascender(jogador) == (True, None) e o
    ramo pertencente à base do jogador; quem chama (bot.py) já validou os
    dois antes de deixar o jogador confirmar."""
    db.ascender_jogador(user_id, ramo)


def arvin_interagir(user_id):
    """Alterna sozinho entre roubar e devolver -- sem dívida pendente
    (divida == 0, tanto "nunca falou" quanto "já devolveu"), rouba
    VALOR_ROUBO_ARVIN do saldo ATUAL e grava o valor exato; com dívida
    pendente, devolve exatamente esse valor e zera. Retorna (resultado,
    valor) com resultado em "roubou"/"devolveu"."""
    jogador = db.get_jogador(user_id)
    divida = jogador["arvin_divida"]
    if divida > 0:
        db.arvin_devolver(user_id, divida)
        return "devolveu", divida
    valor = int(jogador["moedas"] * VALOR_ROUBO_ARVIN)
    db.arvin_roubar(user_id, valor)
    return "roubou", valor
