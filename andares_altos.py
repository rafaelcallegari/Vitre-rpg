# andares_altos.py
# Conteúdo e regras específicas dos andares 11-15 (acima do Selo): a fronteira
# entre a torre "antiga" e a nova, e a fala da Guia, que muda com a contagem
# de mortes. O resto do pacote (telegraph de condição elemental, fase 2 do
# andar 15, material de chefe via chefes_derrotados) vive em combate.py e
# database.py — depende demais do estado interno da Luta pra valer a pena
# isolar aqui. Sem instalar(bot, ...): não registra comando nenhum, bot.py
# chama fala_da_guia() e ANDAR_ACIMA_DO_SELO direto, como faz com npcs.py.

ANDAR_ACIMA_DO_SELO = 10   # sem loja/ferreiro/carroça acima disso — ver decisoes.md

# (andar: ((limiar_de_mortes, fala), ...)) em ordem crescente de limiar.
# fala_da_guia() pega a última cujo limiar cabe na contagem atual.
FALAS_GUIA = {
    11: (
        (0, "Ainda dá pra descer. Ninguém vai lembrar que você chegou até aqui."),
        (3, "Você já bateu aqui antes e voltou puxando a respiração. Da próxima o vento pode não devolver o fôlego."),
        (7, "Eu não vou implorar. Só vou ficar aqui, com a mão estendida, até você entender que descer também é uma forma de vencer."),
    ),
    12: (
        (0, "O trovão aqui não faz barulho. Você também vai parar de fazer, com o tempo."),
        (3, "Contei suas quedas. Não em voz alta — o silêncio daqui não deixa. Mas contei."),
        (7, "Desce comigo. Não custa nada além do orgulho, e o orgulho não cura o que esse andar quebra."),
    ),
    13: (
        (0, "Branco é só a cor que sobra quando não tem mais nada pra ver. Volta antes de aprender isso."),
        (3, "Da última vez você voltou mais devagar. Isso não é fraqueza — é o corpo sendo mais honesto que você."),
        (7, "Eu seguro sua mão até a escada. Ninguém vai saber que precisou. Só eu, e eu não conto."),
    ),
    14: (
        (0, "Calor sem fogo é o corpo avisando. Eu só estou repetindo o aviso."),
        (3, "Você já queimou aqui mais de uma vez sem ver a chama. Da próxima, talvez nem isso sobre."),
        (7, "Desce. Não porque eu mandei — porque eu já vi esse andar vencer gente melhor do que você acha que é."),
    ),
    15: (
        (0, "Essa cadeira não é sua. Não é de ninguém. Senta lá embaixo, onde as coisas ainda cabem."),
        (3, "Você já ajoelhou aqui antes sem perceber. Isso é o andar decidindo por você."),
        (7, "Eu não peço mais que você desista. Só peço que desça vivo o bastante pra decidir de novo amanhã."),
    ),
}


def fala_da_guia(andar, mortes):
    """A fala muda com a contagem de mortes — quanto mais o jogador morre,
    mais gentil e mais convincente ela fica. None se não há Guia nesse andar."""
    tiers = FALAS_GUIA.get(andar)
    if not tiers:
        return None
    escolhida = tiers[0][1]
    for limiar, fala in tiers:
        if mortes >= limiar:
            escolhida = fala
    return escolhida
