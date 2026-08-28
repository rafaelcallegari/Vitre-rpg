# andares_altos.py
# Conteúdo e regras específicas dos andares 11-15 (acima do Selo): a fronteira
# entre a torre "antiga" e a nova, o menu da Guia (falas fixas por andar +
# revelação por mortes) e a corrente de pedidos que entrega as peças do manto.
# O resto do pacote (telegraph de condição elemental, fase 2 do andar 15,
# material de chefe via chefes_derrotados) vive em combate.py e database.py —
# depende demais do estado interno da Luta pra valer a pena isolar aqui. Sem
# instalar(bot, ...): não registra comando nenhum, bot.py chama as funções
# daqui direto, como faz com npcs.py.
#
# `database` é importado DENTRO de cada função que precisa dele (não no topo
# do módulo) de propósito: database.py já importa ANDAR_ACIMA_DO_SELO daqui
# (`from andares_altos import ANDAR_ACIMA_DO_SELO`), e bot.py importa
# andares_altos antes de database — um `import database as db` no topo deste
# arquivo criaria um ciclo real (database.py pausado no meio do próprio
# import, tentando ler um nome que este módulo ainda não definiu). Import
# lazy dentro da função resolve sem precisar reordenar nada em bot.py nem
# duplicar a constante.

ANDAR_ACIMA_DO_SELO = 10   # sem loja/ferreiro/carroça acima disso — ver decisoes.md

# `rpg viajar` nunca alcança acima disso, mesmo com andar_max maior — andar
# 12+ só se chega lutando pra cima a partir do 11, nunca de teleporte. Mora
# aqui (não em bot.py) porque combate.py também precisa dela pra montar a
# mensagem de recusa da sala de chefe, e combate.py não pode importar bot.py
# (ciclo) — ver decisoes.md § Teto de viajar acima do Selo.
LIMITE_VIAJAR = ANDAR_ACIMA_DO_SELO + 1

# ---------------- "O que me espera" — fixa por andar, não varia com mortes ----------------
# Texto aprovado pelo Rafael em 25/08, palavra por palavra — não reescrever.
FALA_O_QUE_ESPERA = {
    11: (
        "Vento, e mais vento. Aqui em cima a torre desiste de ter parede, e "
        "você vai achar isso bonito por uns dez minutos. Depois vai reparar "
        "que não tem chão nenhum embaixo do terraço, só mais céu. Todo mundo "
        "acha bonito no começo."
    ),
    12: (
        "O trovão daqui não vem de nuvem nenhuma. Ele mora no pátio, e bate "
        "quando quer. Conheci um homem que ria dele. Ele dizia que barulho é "
        "só barulho, e que o que mata é o silêncio depois. Ele estava certo "
        "nas duas coisas, e isso não o ajudou em nada."
    ),
    13: (
        "Branco em toda direção, inclusive para baixo. Você vai dar três "
        "passos e os primeiros já não estarão mais lá. Foi aqui que ele "
        "parou pela primeira vez. Ficou olhando os próprios passos "
        "sumirem, e eu achei que ele fosse voltar. Não voltou. Só ficou "
        "mais quieto daí em diante."
    ),
    14: (
        "A luz aqui não aquece, ela cozinha. Você vai querer tirar a "
        "armadura, e não pode. Este é o último andar em que eu o vi "
        "inteiro. Ele subiu daqui com o passo firme e o rosto de quem já "
        "tinha decidido uma coisa que não me contou."
    ),
    15: (
        "Não vou te pedir de novo. Você chegou até aqui e eu já disse tudo "
        "que tinha pra dizer, cinco vezes, de cinco jeitos. A porta está "
        "ali. Só uma coisa: o trono está vazio, e ele já estava vazio "
        "quando ele chegou. Seja lá o que você veio buscar, não está "
        "sentado lá dentro."
    ),
}


def o_que_espera(andar):
    """None se não há Guia nesse andar."""
    return FALA_O_QUE_ESPERA.get(andar)


# ---------------- "Sobre você" — muda com jogadores.mortes, igual em todos os andares ----------------
# (limiar_de_mortes, fala) em ordem crescente — mesmo aprovado em 25/08. A
# revelação (escudeira do Herói) só sai na faixa 7+, de propósito: quem nunca
# morreu nunca descobre. Não destravar por conclusão de quest nem atalho.
FALA_SOBRE_VOCE = (
    (0, (
        "Não é da sua conta. Você subiu rápido, não perdeu nada ainda, e "
        "gente que não perdeu nada faz pergunta como quem coleciona. Volta "
        "quando a torre tiver cobrado alguma coisa de você."
    )),
    (3, (
        "Já subi essa escada antes. Não sozinha — atrás de alguém, "
        "carregando o que ele não queria carregar. Era o meu trabalho e eu "
        "era boa nisso. Cheguei até o andar de baixo do último e ele me "
        "mandou esperar. Esperei. É a única ordem dele que eu cumpri até o "
        "fim."
    )),
    (7, (
        "Eu era escudeira dele. Do Herói, se é assim que ainda chamam. Eu "
        "afiava, eu remendava, eu andava meio passo atrás. E quando ele "
        "passou por aquela porta eu fiquei do lado de fora, porque foi o "
        "que ele pediu, e eu nunca soube se ele morreu lá dentro ou se "
        "simplesmente não quis voltar.\n\n"
        "Não fico aqui por causa dele. Fico porque vocês continuam subindo "
        "com a mesma cara que ele fazia, e alguém tem que pelo menos "
        "perguntar se vocês têm certeza."
    )),
)


def sobre_voce(mortes):
    """A fala escala com a contagem de mortes — quanto mais o jogador
    morreu, mais ela abre sobre si mesma."""
    escolhida = FALA_SOBRE_VOCE[0][1]
    for limiar, fala in FALA_SOBRE_VOCE:
        if mortes >= limiar:
            escolhida = fala
    return escolhida


# ---------------- a corrente de pedidos (manto) ----------------
# Uma entrada por andar 11-14 (o 15 não pede nem entrega nada — só fala,
# ver decisoes.md). `quest_id` é por ANDAR, não uma quest única com estado
# de etapa: a tabela `sidequests` já traduz 'ativa'/'concluida' em
# 'durante'/'depois', e cada estágio da corrente cabe exatamente nesse
# vocabulário sem precisar inventar um terceiro campo pra "qual etapa".
PEDIDOS = (
    {"andar": 11, "quest_id": "guia_flor", "pede": "flor_do_andar_1", "qtd": 1, "da": "molde_do_manto"},
    {"andar": 12, "quest_id": "guia_farpas", "pede": "farpa_eletrica", "qtd": 6, "da": "fio_do_manto"},
    {"andar": 13, "quest_id": "guia_estilhacos", "pede": "estilhaco_gelido", "qtd": 8, "da": "forro_do_manto"},
    {"andar": 14, "quest_id": "guia_cinzas", "pede": "cinza_quente", "qtd": 10, "da": "fecho_do_manto"},
)

# Fala do botão "Sobre o pedido" — uma por quest_id, aprovada palavra por
# palavra, não reescrever. Separada de FALA_O_QUE_ESPERA/FALA_SOBRE_VOCE
# porque varia por PEDIDO, não por andar nem por mortes.
FALA_PEDIDO = {
    "guia_flor": (
        "No primeiro andar, no meio daquele mato todo, nasce uma flor "
        "branca que só abre em certas horas. Ele colhia uma toda vez que "
        "passávamos por lá e nunca me disse pra quê. Traz uma. É tudo que "
        "eu peço."
    ),
    "guia_farpas": (
        "Seis farpas, das que ficam presas na pedra depois que o trovão "
        "passa. Não me pergunte pra quê ainda. Você vai entender quando eu "
        "tiver as quatro coisas na mão."
    ),
    "guia_estilhacos": (
        "Oito estilhaços. Sei que é muito. Este andar cobra caro por tudo, "
        "inclusive por gelo, e eu não tenho como descer pra buscar sozinha."
    ),
    "guia_cinzas": (
        "Dez punhados de cinza, ainda quentes. É o último. Depois disso eu "
        "te devolvo uma coisa e a gente não se deve mais nada."
    ),
}


def fala_do_pedido(quest_id):
    return FALA_PEDIDO.get(quest_id)


# Fala do MOMENTO da entrega — só a última (guia_cinzas, o fecho) tem uma.
# Aprovada 27/08, palavra por palavra. Sem ela a corrente terminava em
# silêncio: o jogador recebia o fecho e não tinha nenhuma pista de que
# existe uma forja no andar 9 esperando. As três entregas anteriores
# continuam só com o recibo mecânico ("✅ Entregue") — nenhuma fala nova
# pra elas, não foi pedido.
FALA_ENTREGA = {
    "guia_cinzas": (
        "Pronto. É a última.\n\n"
        "Leva as quatro pro andar nove. Tem uma ferreira lá, a Selen, a "
        "única que ainda acende a forja do Selo. Ela vai saber o que "
        "fazer com isso — eu já subi aquela escada uma vez com as mesmas "
        "quatro coisas na mão, e ela não me perguntou pra quem era.\n\n"
        "Escolhe bem o que você vai pedir pra ela. Luz ou sombra. Ele não "
        "teve escolha, e eu nunca soube se isso o ajudou ou o matou."
    ),
}


def fala_entrega(quest_id):
    """None pras três primeiras entregas — só o fecho (guia_cinzas) tem
    fala própria no momento em que é entregue."""
    return FALA_ENTREGA.get(quest_id)


def pedido_pendente(user_id):
    """O primeiro pedido da corrente (11 -> 12 -> 13 -> 14) que o jogador
    ainda não concluiu, e o estado dele ('antes'/'durante') -- (None, None)
    se os 4 já foram entregues. É isto que faz "ela cobra a anterior"
    funcionar: não importa em qual andar (11-15) o jogador fala com ela, o
    pedido em jogo é sempre o mais antigo ainda aberto da corrente, nunca o
    do andar em que ele está fisicamente parado."""
    import database as db
    for pedido in PEDIDOS:
        estado = db.estado_sidequest(user_id, pedido["quest_id"])
        if estado != "depois":
            return pedido, estado
    return None, None


def conceder_pedido_pendente(user_id):
    """Chamado toda vez que `rpg falar guia` abre, em qualquer andar 11-15.
    Se o pedido da vez ainda não foi dado ('antes'), dá agora e devolve o
    pedido recém-concedido -- None se não havia nada novo pra dar (pedido já
    em andamento, ou corrente inteira concluída)."""
    import database as db
    pedido, estado = pedido_pendente(user_id)
    if pedido and estado == "antes":
        db.iniciar_sidequest(user_id, pedido["quest_id"])
        return pedido
    return None


def entregar_pedido(user_id):
    """Tenta entregar o pedido pendente da vez. Recalcula a frente da fila
    sozinha (nunca recebe qual pedido entregar por fora) -- é isso que torna
    impossível entregar fora de ordem: mesmo com o material do andar 13 na
    mochila, se a corrente ainda está travada no 11, não há o que entregar.
    Devolve o pedido em caso de sucesso, None se não havia pedido em aberto
    ('antes' ou corrente concluída) ou se faltava material -- nesse último
    caso nada é consumido (db.remove_item já garante isso)."""
    import database as db
    pedido, estado = pedido_pendente(user_id)
    if not pedido or estado != "durante":
        return None
    if not db.remove_item(user_id, pedido["pede"], pedido["qtd"]):
        return None
    db.add_item(user_id, pedido["da"], 1)
    db.concluir_sidequest(user_id, pedido["quest_id"])
    return pedido


def pode_colher_flor(user_id):
    """A flor do andar 1 só nasce pra quem já recebeu o pedido dela no andar
    11 (quest 'durante') e ainda não entregou. Concluída, nunca mais nasce
    pra esse jogador -- e nunca nasceu pra quem ainda não falou com a Guia."""
    pedido, estado = pedido_pendente(user_id)
    return bool(pedido and pedido["andar"] == 11 and estado == "durante")
