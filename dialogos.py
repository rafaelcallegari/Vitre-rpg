# dialogos.py
# Falas de todo NPC com diálogo -- os 9 de tipo "conversa", e desde o cartão
# "ações de diálogo de todos os NPCs" também mercador, ferreiro, taverneiro e
# carroceiro. Só DADO, nenhuma lógica aqui (a lógica de resolver estado de
# quest mora em npcs.opcoes_do_dialogo; a concordância de gênero em
# pronomes.concordar). Cada NPC referencia sua chave aqui a partir do campo
# "dialogo" em npcs.NPCS. A Guia (andares 11-15) fica de fora -- carta
# própria, ela ainda teleporta direto no comando `falar`.
#
# `abertura` e' a fala que o NPC diz ao abrir a conversa -- o mesmo texto do
# campo "fala" em npcs.py, so' reaproveitado aqui.
# `opcoes` aparece sempre, nos tres estados de qualquer sidequest do NPC.
# Pra mercador/ferreiro/taverneiro/carroceiro são só as perguntas da Lore —
# "Comprar"/"Vender"/"Descansar"/a viagem NÃO entram aqui, são os botões de
# mecânica que comercio.py já desenha ao lado dessas opções (ver
# PainelComercioBase em comercio.py). NPC sem pergunta na Lore (ex.: Bramm)
# não tem chave "opcoes" nenhuma -- `opcoes_do_dialogo` trata ausência igual
# a lista vazia.
# `opcoes_por_estado` (ausente em todos os NPCs deste corte -- nenhuma quest
# existe ainda) somaria opcoes conforme 'antes'/'durante'/'depois'; quando
# um NPC ganhar isso, precisa tambem de "quest_id" pra database.estado_sidequest
# saber qual linha da tabela `sidequests` consultar.
# `saida` e' a linha que o NPC diz quando o jogador clica em Sair -- o botao
# de Sair NAO e' um item de `opcoes`, a DialogoView/PainelComercioBase
# acrescenta ele sozinha. NPC sem `saida` própria cai no SAIDA_PADRAO.
#
# Texto marcado com {opcao_ele_elu|opcao_ela} concorda com o pronome de quem
# está jogando -- ver pronomes.concordar().
SAIDA_PADRAO = "Você se despede e segue em frente."

DIALOGOS = {
    "pip": {
        "abertura": "Já contei os degraus até em cima. Deu um número que não cabe na boca.",
        "opcoes": [
            {"label": "Em qual número você parou?",
             "resposta": "Não vou repetir. Você vai ter que subir e contar sozinh{o|a}, aí a gente compara."},
            {"label": "Por que você conta tanto?",
             "resposta": "Porque enquanto eu conto, eu não penso em descer. É mais fácil contar do que decidir."},
        ],
        "saida": "Vai. Eu fico aqui, contando de novo.",
    },
    "lenhador": {
        "abertura": "Machado é bom pra apontar. Cortar, aí já é briga.",
        "opcoes": [
            {"label": "Pedir um pouco de lenha",
             "resposta": "Pega. Não vai fazer falta — eu não uso mesmo, só carrego."},
        ],
        "saida": "Ele aponta o machado pra floresta, sem dizer mais nada.",
    },
    "homem_de_sal": {
        "abertura": "...",
        "opcoes": [
            {"label": "Ficar em silêncio",
             "resposta": "(Ele também fica. O silêncio dos dois dura mais do que devia.)"},
            {"label": "Insistir para ele falar",
             "resposta": "(Ele vira o rosto de sal na sua direção. Nada sai — só um som seco, de pedra raspando em pedra.)"},
        ],
        "saida": "(Ele não se move quando você vai embora. Também não se moveu quando você chegou.)",
    },
    "pescadora": {
        "abertura": "(Ela aponta pro buraco no gelo. Tem algo olhando de volta.)",
        "opcoes": [
            {"label": "Olhar para o buraco",
             "resposta": "(Você se aproxima. A coisa lá embaixo não desvia o olhar. Ela também não.)"},
            {"label": "Dizer que quer pescar",
             "resposta": "(Ela balança a cabeça, devagar. Não é um convite. Ainda não.)"},
        ],
        "saida": "(Ela volta a olhar pro gelo antes mesmo de você terminar de se afastar.)",
    },
    "capataz": {
        "abertura": "«Turno cancelado. Não descer. Assinado: ninguém.»",
        "opcoes": [
            {"label": "Ler de novo",
             "resposta": "As mesmas palavras. «Turno cancelado. Não descer. Assinado: ninguém.» A tinta não mudou desde a última vez."},
            {"label": "Procurar mais bilhetes por perto",
             "resposta": "Nada. Só o vagão vazio, e a lamparina que ninguém apagou."},
        ],
        "saida": "Você dobra o bilhete e deixa onde estava. Ele não vai a lugar nenhum.",
    },
    "cavaleiro": {
        "abertura": "Vou subir amanhã. Falo isso há bastante tempo.",
        "opcoes": [
            {"label": "Perguntar por que ele espera",
             "resposta": "Porque amanhã ainda não chegou de um jeito que me convença. Um dia chega, ainda não estou pronto para voltar lá."},
            {"label": "Perguntar sobre a armadura dele",
             "resposta": "Isso aqui já viu andar mais alto que este. hoje é apenas um metal batido."},
        ],
        "saida": "Ele acena, sem se levantar. \"Amanhã\", ele repete, pra si mesmo.",
    },
    "corista": {
        "abertura": "(Ela move os lábios. O som chega três segundos depois, de outro lugar.)",
        "opcoes": [
            {"label": "Tentar falar com ela",
             "resposta": "(Os lábios se movem nas mesmas palavras de antes. O som, quando chega, vem de trás do altar — não da boca dela.)"},
        ],
        "saida": "(Ela continua movendo os lábios muito depois de você ir embora.)",
    },
    "cartografo": {
        "abertura": "Mapeei os dez. O décimo primeiro se recusa a ficar no papel.",
        "opcoes": [
            {"label": "Perguntar sobre o andar 11",
             "resposta": "Toda vez que desenho a linha, ela muda de lugar quando eu não olho. Não é o meu pulso que treme, é o andar."},
            {"label": "Perguntar se ele já subiu",
             "resposta": "Só até onde o mapa aguenta. Depois disso é fé, não cartografia."},
        ],
        "saida": "Ele nem levanta os olhos do mapa. \"Volta quando quiser ver o que eu já entendi.\"",
    },
    "porta": {
        "abertura": "(Não é um NPC. Mas responde quando você fala com ela.)",
        "opcoes": [
            {"label": "Bater na porta",
             "resposta": "(Ela responde com uma batida igual, do outro lado. Não há outro lado.)"},
            {"label": "Perguntar o que tem atrás dela",
             "resposta": "(Ela não abre. Mas por um instante, você jura ouvir passos se afastando.)"},
        ],
        "saida": "(A porta não se despede. Portas não se despedem.)",
    },

    # ---- andar 1
    "elna": {
        "abertura": "Poção é poção. Bebe rápido que o gosto passa.",
        "opcoes": [
            {"label": "Perguntar sobre a barraca torta",
             "resposta": "A barraca é torta porque eu monto ela torta. Ninguém rouba barraca que parece prestes a cair."},
        ],
        "saida": "Ela já está de olho no próximo cliente antes de você sair.",
    },
    "torv": {
        "abertura": "Vamos para mais um dia na forja, isso por enquanto vai servir pra você.",
        "opcoes": [
            {"label": "Perguntar por que está aposentado",
             "resposta": "Uma hora o martelo tem que repousar, nem sempre a melhor forja esta no topo."},
        ],
        "saida": "Ele volta pro fole sem se despedir — trabalho não espera despedida.",
    },
    "sera": {
        "abertura": "Aqui ninguém pergunta o motivo do cansaço. Só cobra por ele.",
        "opcoes": [
            {"label": "Comprar uma cerveja",
             "resposta": "Só não extrapola, o ultimo deixou a barraca da Elna torta."},
            {"label": "Perguntar da clientela",
             "resposta": "Gente cansada, gente machucada, e um ou outro que só quer conversa. Eu sirvo os três igual."},
        ],
        "saida": "Ela já está limpando o copo antes mesmo de você levantar da mesa.",
    },

    # ---- andar 2
    "irma_vell": {
        "abertura": "Se a árvore repetir o que você falou, não responde. Elas aprendem.",
        "opcoes": [
            {"label": "Por que existem tantas aranhas na floresta",
             "resposta": "Porque teia segura o que grita. Quanto mais barulho esse bosque faz, mais fio elas fiam."},
        ],
        "saida": "Ela te empurra de leve pra fora da tenda, olhando pras árvores atrás de você.",
    },

    # ---- andar 3
    "doran": {
        "abertura": "Vendo por aqui porque o resto da minha loja tá dois metros abaixo.",
        "opcoes": [
            {"label": "O que aconteceu para tudo estar afundado",
             "resposta": "Ninguém sabe direito. Um dia uma tempestade começou e eu só me mudei antes de descobrir o motivo."},
        ],
        "saida": "Ele volta a arrumar os potes que a maré já bagunçou de novo.",
    },
    "kesh": {
        "abertura": "Aço que já afundou uma vez não afunda de novo. É superstição, mas funciona.",
        "opcoes": [
            {"label": "Como ela forja debaixo d'água",
             "resposta": "Uso pedras vulcanicas que um rapaz trouxe para mim de andares mais altos, faz tempo que não o vejo para agradecer."},
            {"label": "Perguntar sobre Torv",
             "resposta": "Torv? Ele martelou minha primeira peça, faz muito tempo que ele não sobe para os andares superiores, existem boatos que tem haver com um dos seus aprendizes."},
        ],
        "saida": "Ela volta a bater o martelo, e o som atravessa a água como se não estivesse lá.",
    },
    "bramm": {
        "abertura": "Passo quatro vezes por dia. Se você estiver aqui, sobe. Se não estiver, paciência.",
        "saida": "Ele já está de olho na estrada, esperando o próximo horário.",
    },

    # ---- andar 4
    "ysra": {
        "abertura": "Água eu não vendo. Água aqui é o que separa vivo de estátua.",
        "opcoes": [
            {"label": "O que existe nas dunas de sal",
             "resposta": "Gente que achou que sabia o caminho. O sal guarda a forma de quem para de andar."},
        ],
        "saida": "Ela puxa o véu sobre o rosto antes que o vento levante mais poeira.",
    },

    # ---- andar 5
    "tikk": {
        "abertura": "Compra a poção grande. Não é venda, é conselho.",
        "opcoes": [
            {"label": "Pedir um chocolate quente",
             "resposta": "Não vendo isso, mas se você comprar a poção grande, eu finjo que foi chocolate. Combinado?"},
        ],
        "saida": "Ele já está de volta ao trenó, ajeitando os potes pro próximo cliente.",
    },
    "hjalmar": {
        "abertura": "Têmpera no lago. A lâmina grita e depois nunca mais reclama.",
        "opcoes": [
            {"label": "Perguntar sobre Torv",
             "resposta": "Todo ferreiro dessa torre segurou o martelo pela primeira vez com o Torv. existem boatos dizendo que um aventureiro pediu a Torv uma arma perigosa, Torv não queria fazer, mas quando a fez, o arrependimento foi tão grande que ele voltou para o andar 1."},
        ],
        "saida": "Ele mergulha a lâmina de novo, e o vapor sobe entre vocês dois.",
    },

    # ---- andar 6
    "bico": {
        "abertura": "Lamparina acesa não quer dizer que tem gente. Quer dizer que teve.",
        "opcoes": [
            {"label": "O que tem no vagão 13",
             "resposta": "Ninguém abre o vagão 13. Não porque é proibido, porque ninguém quis ser o primeiro a descobrir por quê."},
        ],
        "saida": "Ele baixa a voz antes de virar de costas, como se o vagão pudesse ouvir.",
    },

    # ---- andar 7
    "vane": {
        "abertura": "Sacode a roupa antes de entrar. A cinza aqui pega carona.",
        "opcoes": [
            {"label": "Por que aqui chove cinzas",
             "resposta": "Minha avó dizia que antes aqui era um lugar de luz, calor e sol, mas um dia alguém tentou ser maior que a luz e apagou o fogo destas terras."},
        ],
        "saida": "Ela sacode o próprio avental, e mais cinza sobe no ar entre vocês.",
    },
    "ignatia": {
        "abertura": "Não forjo com fogo. Forjo com o que sobrou dele.",
        "opcoes": [
            {"label": "Por que o fogo se apagou",
             "resposta": "Um aventureiro, decidiu que queria governar essas terras, o que você esta vendo é as consequências da decisão de um de vocês."},
        ],
        "saida": "Ela volta a bater a bigorna, e a brasa nela pisca como se respirasse.",
    },

    # ---- andar 8
    "irmao_cael": {
        "abertura": "Reze se quiser. Mas paga a poção primeiro.",
        "opcoes": [
            {"label": "Rezar",
             "resposta": "(Ele espera em silêncio enquanto você reza. No fim, só estende a mão — a fé não desconta o preço.)"},
        ],
        "saida": "Ele volta à contagem das moedas, murmurando algo que não chega a ser oração.",
    },

    # ---- andar 9
    "ori": {
        "abertura": "Não olha pra baixo. Não por medo — é que não tem baixo.",
        "opcoes": [
            {"label": "O que existe além do céu",
             "resposta": "Mais céu. E depois disso, o Selo. Eu já subi o balão até onde dava, não me atrevo a subir mais que isso, deixo essa aventura para vocês."},
        ],
        "saida": "Ele ajusta as cordas do balão, sem tirar os olhos do horizonte.",
    },
    "selen": {
        "abertura": "O que eu faço aqui, ninguém faz mais acima. Escolhe com calma.",
        "opcoes": [
            {"label": "Perguntar sobre Torv",
             "resposta": "O Torv foi o primeiro nome que ouvi quando escolhi esse ofício, mesmo aqui em cima, tão longe do andar dele. Ele continua lá embaixo? Claro que sim, nunca se perdoou pela arma que forjou, mas não o culpo, qualquer um confiaria em seu aprendiz."},
            {"label": "Perguntar sobre o Selo",
             "resposta": "O Selo foi criado para proteger os 10 andares do que há de pior lá em cima. Foi criado por um heroí, em uma missão quase impossivel, ele e sua escudeira subiram e se trancaram lá pra cima, nunca mais tivemos noticias."},
        ],
        "saida": "Ela volta pra bancada sem dizer mais nada — aqui, o trabalho fala por ela.",
    },

    # ---- encantadores (ímpares) e joalheiros (pares) -- falas e ações de
    # diálogo destes 10 NÃO são do Rafael, escritas no tom estabelecido pra
    # ele revisar depois (mesmo acordo dos 9 NPCs de conversa). Ver decisoes.md.
    "baldo": {
        "abertura": "O vento não escolhe onde bate. Eu só aprendi a prender um pedaço dele na sua lâmina.",
        "opcoes": [
            {"label": "Como se encanta uma arma",
             "resposta": "Não é magia grande, é teimosia pequena. Repito o mesmo símbolo até ele parar de escorregar da peça."},
            {"label": "Por que só nos andares ímpares",
             "resposta": "Porque nos pares a Torv que vem antes de mim já disse: quem forja e quem encanta não deviam dividir bancada. Eu concordo, hoje em dia."},
        ],
        "saida": "Ele sopra de leve na palma da mão, como se testasse o vento antes de você ir.",
    },
    "orin": {
        "abertura": "Toda pedra que acho aqui já nasceu torta, que nem a árvore. Eu só ajudo a torcer certo.",
        "opcoes": [
            {"label": "Por que escolher o atributo da peça",
             "resposta": "Porque uma joia sem dono ainda não decidiu o que quer ser. Você decide por ela, eu só lapido a decisão."},
            {"label": "Já viu uma joia encantada por cima",
             "resposta": "Já. Some o que eu boto com o que o encantador bota depois, e não briga — cada um fica no seu canto da pedra."},
        ],
        "saida": "Ela sopra a poeira da bancada e ergue a próxima pedra contra a luz.",
    },
    "lira": {
        "abertura": "A maré fala baixo, mas fala sempre a mesma coisa duas vezes. Eu só repito pra sua arma.",
        "opcoes": [
            {"label": "O que a maré repete",
             "resposta": "Repete o nome de quem afundou aqui antes de a cidade virar ruína. Eu não entendo a língua, só o ritmo — e o ritmo é o que vira encantamento."},
            {"label": "Dá pra remover o que você encanta",
             "resposta": "Dá. Custa metade do que custou prender. A maré leva embora o que a maré ainda não esqueceu."},
        ],
        "saida": "Ela volta a olhar pra água, esperando a próxima repetição.",
    },
    "kef": {
        "abertura": "O poço secou, mas o que ele guardava no fundo não. Eu só desço buscar.",
        "opcoes": [
            {"label": "O que tem no fundo do poço",
             "resposta": "Pedra que nunca viu sol. É por isso que ela segura tão bem um atributo — nunca teve outra cor pra perder."},
            {"label": "Já fabricou um colar tão bom quanto anel",
             "resposta": "Os dois saem da mesma pedra, só muda o corte. Ninguém nunca me disse qual serve mais — escolho pelo peso na mão."},
        ],
        "saida": "Ele desce mais uma corda no poço, sem olhar pra trás.",
    },
    "corin": {
        "abertura": "Uso o casaco comprido porque o frio daqui gruda no encantamento antes de grudar em mim.",
        "opcoes": [
            {"label": "Por que o frio ajuda a encantar",
             "resposta": "Não ajuda. Só desacelera o bastante pra eu enxergar o símbolo formando antes dele fixar errado."},
            {"label": "Perguntar sobre Hjalmar",
             "resposta": "Ele tempera o aço no mesmo lago que eu uso pra esfriar o encantamento. Nunca conversamos sobre isso — nem precisa, o lago já divide o trabalho."},
        ],
        "saida": "Ele puxa a gola do casaco e volta a olhar pro gelo, como se procurasse o próximo símbolo nele.",
    },
    "mira": {
        "abertura": "O trilho não leva a lugar nenhum mais. Mas as pedras que acho ao lado dele levam.",
        "opcoes": [
            {"label": "Pra onde as pedras levam",
             "resposta": "Pro atributo que você escolher. Eu só entrego a pedra pronta — a decisão de virar força, destreza, o que for, é sempre sua."},
            {"label": "O que aconteceu com o trilho",
             "resposta": "Parou de levar gente antes de eu chegar. Fico com o que sobrou dele: silêncio, ferrugem, e as pedras boas."},
        ],
        "saida": "Ela guarda a lapidadeira no bolso do avental e volta a andar pelo trilho morto.",
    },
    "talla": {
        "abertura": "Guardo uma brasa só, a última que não virou cinza. É o suficiente pra encantar o resto.",
        "opcoes": [
            {"label": "Por que só uma brasa",
             "resposta": "Porque encantamento não gasta fogo, gasta símbolo. A brasa só me dá luz pra ver o que eu tô desenhando na peça."},
            {"label": "Encanta arma e armadura igual",
             "resposta": "Igual. O que muda é onde o atributo pega — na arma ele empurra, na armadura ele segura. O símbolo é o mesmo."},
        ],
        "saida": "Ela protege a brasa com a mão antes que o vento dos Campos de Cinzas a apague de vez.",
    },
    "vesna": {
        "abertura": "O altar principal é pra rezar. O lateral, onde eu fico, é pra lapidar. Os dois pedem silêncio.",
        "opcoes": [
            {"label": "Por que lapidar exige silêncio",
             "resposta": "Porque a pedra racha no barulho errado. Aprendi isso perdendo mais joia do que gostaria de admitir pro Irmão Cael."},
            {"label": "Alguém já pediu uma joia estranha",
             "resposta": "Todo dia. Ninguém concorda em qual atributo é o certo pra um anel. Eu só fico feliz que a escolha não seja minha."},
        ],
        "saida": "Ela volta a lapidar em silêncio, sem levantar os olhos do altar lateral.",
    },
    "astrea": {
        "abertura": "Cada estrela que conto daqui já morreu há tempos. O brilho que sobra é o que eu uso pra encantar.",
        "opcoes": [
            {"label": "Como se encanta com luz morta",
             "resposta": "A luz não sabe que a estrela já morreu — ela ainda tá viajando. Eu só interrompo a viagem um pouco antes de chegar."},
            {"label": "Perguntar sobre Selen",
             "resposta": "Ela forja o que eu não consigo encantar sozinha: o Selo em si. Nunca subimos juntas pra ver o que tem depois dele."},
        ],
        "saida": "Ela volta a contar as estrelas, murmurando um número que você não consegue acompanhar.",
    },
    "eco_joalheira": {
        "abertura": "Já lapidei isso. Você já usou. Nós duas já esquecemos — só a pedra lembra.",
        "opcoes": [
            {"label": "Quem foi você antes deste andar",
             "resposta": "Uma joalheira, imagino. É a única coisa que meu corpo ainda sabe fazer sem eu lembrar por quê."},
            {"label": "Qual pedra você mais lembra",
             "resposta": "Nenhuma. Mas minhas mãos param exatamente no lugar onde uma pedra melhor ficaria — isso deve contar como lembrança."},
        ],
        "saida": "Ela já está com outra pedra na mão, como se você nunca tivesse chegado.",
    },

    # ---- andar 10
    "eco_mercador": {
        "abertura": "Eu já te vendi isso. Você já me pagou. Nós dois já esquecemos.",
        "opcoes": [
            {"label": "Quem é você?",
             "resposta": "A mesma pergunta que você fez da última vez. E a resposta continua a mesma: não sei. Só sei vender."},
            {"label": "O que eu comprei de você?",
             "resposta": "Não lembro, e você também não vai lembrar depois de sair daqui. É só assim que esse andar funciona."},
        ],
        "saida": "Ele já estica a mão pra outro cliente que ainda não chegou.",
    },
    "eco_taverneira": {
        "abertura": "Descansa. Não vai ajudar, mas descansa.",
        "opcoes": [
            {"label": "Por que só uma taverna",
             "resposta": "Porque só sobrou memória pra uma. Lá embaixo tinha outra, mas ninguém mais lembra o nome dela."},
        ],
        "saida": "Ela já está arrumando um lugar vazio, como se mais alguém fosse chegar.",
    },
}

# ---- despertar (patch 0.3 -- `rpg comecar`) --------------------------------
# Texto exato do Rafael pra sequência de início. Fora do dict DIALOGOS de
# propósito -- não é indexado por NPC, não é alcançável por `rpg falar`, só
# pela sequência de despertar.py. Não mexer numa vírgula deste texto.
#
# "{classe}"/"{oficio}" são placeholders de str.format(), preenchidos por
# despertar.py DEPOIS de pronomes.concordar() já ter resolvido os marcadores
# {opcao|opcao} -- nessa ordem sempre, senão sobra "{|a}" cru pro .format()
# tropeçar (ele não sabe o que fazer com um campo sem nome e com "|" dentro).
DESPERTAR = {
    "abertura": (
        "Você sente uma brisa forte e fresca em seu rosto, abaixo de você, "
        "você sente uma grama fofa e alta. Em meio a essa tranquilidade, "
        "você começa a lembrar de batalhas...guerras...e um propósito..."
    ),
    "pergunta_classe": "Qual era seu propósito em batalha?",
    "confirmacao_classe": (
        "Você ainda se lembra! Você era um{|a} {classe}! Mas, você nem "
        "sempre foi só isso, você era alguém fora do campo de batalha, você "
        "fazia algo fora do campo de batalha...aquilo que te movia em "
        "noites escuras, aquilo que te mantinha acordado."
    ),
    "pergunta_oficio": "Qual era o seu oficio?",
    "confirmacao_oficio": (
        "Sim, claro! Você era um{|a} {oficio}, o mais dedicad{o|a} em suas "
        "terras. Mas agora, tão longe de casa, quem é você?"
    ),
    "elna_acorda": (
        "Ei, Acorda! O que está fazendo no meio do mato? Esta tod{o|a} "
        "suj{o|a} de grama, apanhou para os javalis? Toma aqui, vai ajudar."
    ),
    "elna_agradecer": "Não tem de que aventureir{o|a}, sempre tem um de vocês caido no mato",
    "elna_onde_esta": (
        "Vai entender melhor com o tempo, mas saiba que a resposta para "
        "isso, esta lá em cima, e quanto mais alto, maior o perigo"
    ),
    "elna_olhar_envolta": (
        "Você vê uma planicie com grama alta, clima extremamente agradável. "
        "E você vê um aventureiro de fundo sendo derrubado por um javali"
    ),
}
