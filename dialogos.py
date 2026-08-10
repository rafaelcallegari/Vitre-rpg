# dialogos.py
# Falas dos NPCs de tipo "conversa" -- so' DADO, nenhuma logica aqui (a
# logica de resolver estado de quest mora em npcs.opcoes_do_dialogo; a
# concordancia de genero em pronomes.concordar). Cada NPC referencia sua
# chave aqui a partir do campo "dialogo" em npcs.NPCS.
#
# `abertura` e' a fala que o NPC diz ao abrir a conversa -- o mesmo texto do
# campo "fala" em npcs.py, so' reaproveitado aqui.
# `opcoes` aparece sempre, nos tres estados de qualquer sidequest do NPC.
# `opcoes_por_estado` (ausente em todos os NPCs deste corte -- nenhuma quest
# existe ainda) somaria opcoes conforme 'antes'/'durante'/'depois'; quando
# um NPC ganhar isso, precisa tambem de "quest_id" pra database.estado_sidequest
# saber qual linha da tabela `sidequests` consultar.
# `saida` e' a linha que o NPC diz quando o jogador clica em Sair -- o botao
# de Sair NAO e' um item de `opcoes`, a DialogoView acrescenta ele sozinha
# (ver bot.py). NPC sem `saida` própria cai no SAIDA_PADRAO.
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
             "resposta": "Porque amanhã ainda não chegou de um jeito que me convença. Um dia chega."},
            {"label": "Perguntar sobre a armadura dele",
             "resposta": "Isso aqui já viu andar mais alto que este. Não pergunta o que ela viu lá."},
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
             "resposta": "Toda vez que desenho a linha, ela muda de lugar quando eu não olho. Não é o meu pulso que treme — é o andar."},
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
}
