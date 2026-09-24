# repouso.py
# Step F: Renzo (Costa Verde) oferece parar a busca -- não é desistir do
# personagem, não é apagar nada: é declarar que a perseguição incessante não
# vale a pena por enquanto, e ficar em repouso. NADA é travado -- nenhum
# comando bloqueado, nenhum cooldown pausado, nenhuma recompensa tirada. O
# peso inteiro da escolha está no texto (Renzo, e o reconhecimento de
# Nara/Eira/Bento), não em mecânica nenhuma. Ver decisoes.md § Step F.
import database as db

# Duas colunas, duas perguntas diferentes (migração 26, database.py):
# `em_repouso` liga/desliga a cada clique no par de botões de Renzo;
# `ja_parou` só liga, nunca desliga -- registro permanente pro que vier
# depois (ainda não consultado por ninguém além de si mesmo).


def em_repouso(jogador):
    return bool(jogador["em_repouso"])


def ja_parou_alguma_vez(jogador):
    return bool(jogador["ja_parou"])


def definir(user_id, jogador, ligar):
    """Seta o estado ALVO direto -- não alterna relativo ao atual. Os dois
    botões do par (bot.py, BotaoAlternarRepouso) já sabem qual estado cada
    um produz, então não tem ambiguidade de "alternar" aqui. `ja_parou` só
    liga quando `ligar` é True e ainda estava 0 -- nunca reseta ao
    desligar."""
    campos = {"em_repouso": 1 if ligar else 0}
    if ligar and not jogador["ja_parou"]:
        campos["ja_parou"] = 1
    db.atualizar_jogador(user_id, **campos)


# ---------------- linhas de reconhecimento ----------------
# Aparecem ANTES da abertura normal de cada NPC, só pra quem está em
# repouso NAQUELE MOMENTO (usa só `em_repouso`, nunca `ja_parou` -- ver
# bot.falar()). Chave é a mesma chave de `dialogos.DIALOGOS` do NPC.
# NENHUMA elogia a escolha -- "se alguma virar parabéns na implementação,
# parar vira recompensa, e o recurso inteiro perde o sentido" (o cartão foi
# explícito).
RECONHECIMENTO = {
    "nara_vilarejo": [
        "Você parou.",
        "Olha só.",
        "Não vou dizer que entendi, porque eu nunca precisei parar.",
        "Nunca comecei.",
        "Mas parar é mais difícil que nunca ter começado.",
        "Isso eu reconheço.",
    ],
    "eira": [
        "Você parou.",
        "Ele não parou.",
        "Passou por aqui sem descansar nem uma noite.",
        "Talvez você tenha ouvido alguma coisa que ele não ouviu.",
        "Ou talvez só tenha ouvido a tempo.",
    ],
    "bento": [
        "Você parou de procurar.",
        "Então talvez a gente possa tomar chá sem pressa.",
        "Meu avô ia gostar de você.",
        "Ele dizia que gente apressada não repara no gosto.",
        "Fica. O primeiro bule já está pronto.",
    ],
}
