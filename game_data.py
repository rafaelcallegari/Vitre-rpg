# game_data.py
# Todo o conteúdo do jogo vive aqui. Mexer aqui = mudar o jogo, sem tocar na lógica.

def xp_necessario(nivel: int) -> int:
    return int(40 * (nivel ** 1.5))


ITENS = {
    # ---------------- consumíveis ----------------
    "pocao_p": {"nome": "Poção Pequena", "emoji": "🧪", "tipo": "consumivel", "preco": 60, "cura": 60, "andar_min": 1},
    "pocao_m": {"nome": "Poção Média", "emoji": "⚗️", "tipo": "consumivel", "preco": 220, "cura": 200, "andar_min": 3},
    "pocao_g": {"nome": "Poção Grande", "emoji": "🍶", "tipo": "consumivel", "preco": 700, "cura": 600, "andar_min": 6},
    "pocao_mana": {"nome": "Poção de Mana", "emoji": "🔵", "tipo": "consumivel", "preco": 150, "mana": 25, "andar_min": 1},

    # ---------------- armas de Força (dano alto, crítico de 10%) ----------------
    "espada_ferro": {"nome": "Espada de Ferro", "emoji": "🗡️", "tipo": "arma", "atributo": "forca", "preco": 280, "atk": 8, "andar_min": 1},
    "espada_aco": {"nome": "Espada de Aço", "emoji": "⚔️", "tipo": "arma", "atributo": "forca", "preco": 1100, "atk": 20, "andar_min": 3},
    "lamina_gelo": {"nome": "«Lâmina de Gelo»", "emoji": "❄️", "tipo": "arma", "atributo": "forca", "preco": 3200, "atk": 36, "andar_min": 5},
    "espada_brasa": {"nome": "«Espada de Brasas»", "emoji": "🔥", "tipo": "arma", "atributo": "forca", "preco": 7500, "atk": 55, "andar_min": 7},
    "lamina_selo": {"loja": False, "nome": "«Lâmina do Selo»", "emoji": "🌑", "tipo": "arma", "atributo": "forca", "preco": 16000, "atk": 82, "andar_min": 9},

    # ---------------- armas de Destreza (75% do dano, crítico de 18%) ----------------
    "adaga": {"nome": "Adaga", "emoji": "🔪", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "preco": 260, "atk": 6, "andar_min": 1},
    "arco_curto": {"nome": "Arco Curto", "emoji": "🏹", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "preco": 1000, "atk": 15, "andar_min": 3},
    "foice_bruma": {"nome": "«Foice de Bruma»", "emoji": "🌫️", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "preco": 2900, "atk": 27, "andar_min": 5},
    "arco_cinzas": {"nome": "«Arco de Cinzas»", "emoji": "🎯", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "preco": 6800, "atk": 41, "andar_min": 7},
    "adaga_selo": {"loja": False, "nome": "«Adaga do Selo»", "emoji": "🌒", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "preco": 14500, "atk": 61, "andar_min": 9},

    # ---------------- armas de Inteligência (cajados — Mago, crítico de 10%) ----------------
    "cajado_carvalho": {"nome": "Cajado de Carvalho", "emoji": "🪄", "tipo": "arma", "atributo": "inteligencia", "preco": 280, "atk": 8, "andar_min": 1},
    "cajado_cristal": {"nome": "Cajado de Cristal", "emoji": "🔮", "tipo": "arma", "atributo": "inteligencia", "preco": 1100, "atk": 20, "andar_min": 3},
    "cajado_aurora": {"nome": "«Cajado da Aurora»", "emoji": "✨", "tipo": "arma", "atributo": "inteligencia", "preco": 3200, "atk": 36, "andar_min": 5},
    "cajado_cinzas": {"nome": "«Cajado de Cinzas»", "emoji": "🔥", "tipo": "arma", "atributo": "inteligencia", "preco": 7500, "atk": 55, "andar_min": 7},
    "cajado_selo": {"loja": False, "nome": "«Cajado do Selo»", "emoji": "🌑", "tipo": "arma", "atributo": "inteligencia", "preco": 16000, "atk": 82, "andar_min": 9},

    # ---------------- manoplas e faixas (Orador — mesma escala de Destreza do desarmado, crítico de 18%) ----------------
    "manoplas_couro": {"nome": "Manoplas de Couro", "emoji": "🥊", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "preco": 260, "atk": 6, "andar_min": 1},
    "faixas_trancadas": {"nome": "Faixas Trançadas", "emoji": "🎗️", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "preco": 1000, "atk": 15, "andar_min": 3},
    "manoplas_geladas": {"nome": "«Manoplas Geladas»", "emoji": "❄️", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "preco": 2900, "atk": 27, "andar_min": 5},
    "faixas_brasa": {"nome": "«Faixas de Brasa»", "emoji": "🔥", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "preco": 6800, "atk": 41, "andar_min": 7},
    "manoplas_selo": {"loja": False, "nome": "«Manoplas do Selo»", "emoji": "🌒", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "preco": 14500, "atk": 61, "andar_min": 9},

    # ---------------- armaduras ----------------
    "couro": {"nome": "Armadura de Couro", "emoji": "🥋", "tipo": "armadura", "preco": 220, "def": 5, "andar_min": 1},
    "cota_malha": {"nome": "Cota de Malha", "emoji": "🛡️", "tipo": "armadura", "preco": 900, "def": 12, "andar_min": 3},
    "placas": {"nome": "Armadura de Placas", "emoji": "🪖", "tipo": "armadura", "preco": 2800, "def": 22, "andar_min": 5},
    "obsidiana": {"nome": "«Placa de Obsidiana»", "emoji": "🌋", "tipo": "armadura", "preco": 6800, "def": 36, "andar_min": 7},
    "manto_selo": {"loja": False, "nome": "«Manto do Selo»", "emoji": "🧿", "tipo": "armadura", "preco": 15000, "def": 54, "andar_min": 9},

    # ---------------- forjados (só craft, não aparecem em loja) ----------------
    "couro_batido": {"loja": False, "nome": "«Couro Batido»", "emoji": "🥾", "tipo": "armadura", "preco": 700, "def": 8, "andar_min": 1},
    "malha_reforcada": {"loja": False, "nome": "«Malha Reforçada»", "emoji": "⛓️", "tipo": "armadura", "preco": 2400, "def": 17, "andar_min": 3},
    "placas_polidas": {"loja": False, "nome": "«Placas Polidas»", "emoji": "🔩", "tipo": "armadura", "preco": 5200, "def": 29, "andar_min": 5},
    "couraca_cinzas": {"loja": False, "nome": "«Couraça de Cinzas»", "emoji": "🜃", "tipo": "armadura", "preco": 11000, "def": 45, "andar_min": 7},

    # ---------------- alquimia (só craft) ----------------
    "elixir_ervas": {"loja": False, "nome": "«Elixir de Ervas»", "emoji": "🌿", "tipo": "consumivel", "preco": 200, "cura_pct": 0.25, "andar_min": 1},
    "elixir_vermelho": {"loja": False, "nome": "«Elixir Vermelho»", "emoji": "🍷", "tipo": "consumivel", "preco": 900, "cura_pct": 0.50, "andar_min": 4},
    "nectar_torre": {"loja": False, "nome": "«Néctar da Torre»", "emoji": "🍯", "tipo": "consumivel", "preco": 2600, "cura_pct": 1.00, "andar_min": 7},
    "elixir_mana": {"loja": False, "nome": "«Elixir de Mana»", "emoji": "🟣", "tipo": "consumivel", "preco": 900, "mana_pct": 0.50, "andar_min": 4},

    # ---------------- materiais (só pra vender) ----------------
    "presa_javali": {"nome": "Presa de Javali", "emoji": "🦷", "tipo": "material", "preco": 12},
    "seda_sussurrante": {"nome": "Seda Sussurrante", "emoji": "🕸️", "tipo": "material", "preco": 30},
    "osso_enferrujado": {"nome": "Osso Enferrujado", "emoji": "🦴", "tipo": "material", "preco": 55},
    "cristal_de_sal": {"nome": "Cristal de Sal", "emoji": "🧂", "tipo": "material", "preco": 85},
    "nucleo_gelado": {"nome": "Núcleo Gelado", "emoji": "🧊", "tipo": "material", "preco": 120},
    "minerio_negro": {"nome": "Minério Negro", "emoji": "🪨", "tipo": "material", "preco": 160},
    "brasa_eterna": {"nome": "Brasa Eterna", "emoji": "🔥", "tipo": "material", "preco": 210},
    "fragmento_sino": {"nome": "Fragmento de Sino", "emoji": "🔔", "tipo": "material", "preco": 265},
    "pena_do_trovao": {"nome": "Pena do Trovão", "emoji": "⚡", "tipo": "material", "preco": 330},
    "eco_cristalizado": {"nome": "Eco Cristalizado", "emoji": "💠", "tipo": "material", "preco": 400},
    "fragmento_selo": {"vendavel": False, "nome": "Fragmento do Selo", "emoji": "🔷", "tipo": "material", "preco": 500},
}


# atk do boss = 13 + 13 * (andar - 1)
ANDARES = {
    1: {
        "nome": "Planície dos Iniciantes",
        "cor": 0x7FB069,
        "descricao": "Grama alta até o joelho e o céu de pedra do andar de cima. Todo mundo começa aqui.",
        "monstros": [
            {"nome": "Javali das Planícies", "hp": 42, "atk": 8, "def": 1, "xp": 18, "moedas": 26, "drops": [("presa_javali", 0.55)]},
            {"nome": "Lobo da Névoa", "hp": 38, "atk": 9, "def": 1, "xp": 19, "moedas": 24, "drops": [("presa_javali", 0.45)]},
            {"nome": "Slime Azulado", "hp": 52, "atk": 6, "def": 2, "xp": 17, "moedas": 28, "drops": [("presa_javali", 0.60)]},
        ],
        "boss": {"nome": "«Vargash, o Kobold Coroado»", "hp": 165, "atk": 13, "def": 2, "xp": 150, "moedas": 260, "drops": [("fragmento_selo", 1.0)]},
    },
    2: {
        "nome": "Bosque Sussurrante",
        "cor": 0x3E7C59,
        "descricao": "As árvores repetem, com meio segundo de atraso, tudo o que você fala.",
        "monstros": [
            {"nome": "Aranha Tecelã", "hp": 72, "atk": 13, "def": 3, "xp": 32, "moedas": 45, "drops": [("seda_sussurrante", 0.55)]},
            {"nome": "Cogumelo Andante", "hp": 82, "atk": 11, "def": 4, "xp": 30, "moedas": 48, "drops": [("seda_sussurrante", 0.50)]},
            {"nome": "Corvo de Ferro", "hp": 62, "atk": 15, "def": 2, "xp": 34, "moedas": 42, "drops": [("seda_sussurrante", 0.45)]},
        ],
        "boss": {"nome": "«Aracnia, a Rainha dos Fios»", "hp": 285, "atk": 26, "def": 5, "xp": 260, "moedas": 450, "drops": [("fragmento_selo", 1.0)]},
    },
    3: {
        "nome": "Ruínas Afundadas",
        "cor": 0x5C6B73,
        "descricao": "Uma cidade inteira submersa até a metade. Alguma coisa ainda anda lá embaixo.",
        "monstros": [
            {"nome": "Esqueleto Enferrujado", "hp": 102, "atk": 18, "def": 5, "xp": 46, "moedas": 65, "drops": [("osso_enferrujado", 0.55)]},
            {"nome": "Rato Colossal", "hp": 92, "atk": 20, "def": 4, "xp": 48, "moedas": 62, "drops": [("osso_enferrujado", 0.50)]},
            {"nome": "Lodo Ácido", "hp": 115, "atk": 16, "def": 6, "xp": 44, "moedas": 68, "drops": [("osso_enferrujado", 0.45)]},
        ],
        "boss": {"nome": "«Guardião de Pedra Rachada»", "hp": 410, "atk": 39, "def": 8, "xp": 380, "moedas": 650, "drops": [("fragmento_selo", 1.0)]},
    },
    4: {
        "nome": "Deserto de Sal",
        "cor": 0xD9C5A0,
        "descricao": "Branco até onde a vista alcança. O chão range quando você pisa.",
        "monstros": [
            {"nome": "Escorpião de Cristal", "hp": 132, "atk": 23, "def": 7, "xp": 60, "moedas": 85, "drops": [("cristal_de_sal", 0.55)]},
            {"nome": "Bandido Errante", "hp": 122, "atk": 26, "def": 6, "xp": 62, "moedas": 90, "drops": [("cristal_de_sal", 0.45)]},
            {"nome": "Verme das Dunas", "hp": 145, "atk": 21, "def": 8, "xp": 58, "moedas": 82, "drops": [("cristal_de_sal", 0.50)]},
        ],
        "boss": {"nome": "«Zarhak, o Verme Ancião»", "hp": 530, "atk": 52, "def": 11, "xp": 500, "moedas": 850, "drops": [("fragmento_selo", 1.0)]},
    },
    5: {
        "nome": "Lago Congelado",
        "cor": 0x8ECAE6,
        "descricao": "O gelo é grosso o bastante pra andar e fino o bastante pra ouvir.",
        "monstros": [
            {"nome": "Lobo de Gelo", "hp": 162, "atk": 28, "def": 9, "xp": 74, "moedas": 105, "drops": [("nucleo_gelado", 0.55)]},
            {"nome": "Espírito da Neblina", "hp": 148, "atk": 32, "def": 7, "xp": 78, "moedas": 100, "drops": [("nucleo_gelado", 0.45)]},
            {"nome": "Urso Corrompido", "hp": 180, "atk": 26, "def": 11, "xp": 72, "moedas": 110, "drops": [("nucleo_gelado", 0.50)]},
        ],
        "boss": {"nome": "«Nivalgar, o Uivo Branco»", "hp": 650, "atk": 65, "def": 14, "xp": 620, "moedas": 1050, "drops": [("fragmento_selo", 1.0)]},
    },
    6: {
        "nome": "Mina Abandonada",
        "cor": 0x6B4E31,
        "descricao": "As lamparinas ainda estão acesas. Ninguém apagou porque ninguém saiu.",
        "monstros": [
            {"nome": "Golem de Minério", "hp": 205, "atk": 31, "def": 13, "xp": 88, "moedas": 125, "drops": [("minerio_negro", 0.55)]},
            {"nome": "Morcego Sanguinário", "hp": 175, "atk": 36, "def": 9, "xp": 92, "moedas": 120, "drops": [("minerio_negro", 0.45)]},
            {"nome": "Mineiro Enlouquecido", "hp": 190, "atk": 34, "def": 11, "xp": 90, "moedas": 130, "drops": [("minerio_negro", 0.50)]},
        ],
        "boss": {"nome": "«Núcleo Vivo da Mina»", "hp": 770, "atk": 78, "def": 17, "xp": 740, "moedas": 1250, "drops": [("fragmento_selo", 1.0)]},
    },
    7: {
        "nome": "Campos de Cinzas",
        "cor": 0xB5651D,
        "descricao": "Não chove aqui. Cai cinza, e ela é quente.",
        "monstros": [
            {"nome": "Cavaleiro Queimado", "hp": 232, "atk": 38, "def": 14, "xp": 102, "moedas": 145, "drops": [("brasa_eterna", 0.55)]},
            {"nome": "Elemental de Brasa", "hp": 210, "atk": 43, "def": 11, "xp": 106, "moedas": 140, "drops": [("brasa_eterna", 0.45)]},
            {"nome": "Abutre de Ferro", "hp": 220, "atk": 40, "def": 13, "xp": 104, "moedas": 150, "drops": [("brasa_eterna", 0.50)]},
        ],
        "boss": {"nome": "«Ignar, o Cavaleiro de Brasas»", "hp": 890, "atk": 91, "def": 20, "xp": 860, "moedas": 1450, "drops": [("fragmento_selo", 1.0)]},
    },
    8: {
        "nome": "Catedral Quebrada",
        "cor": 0x9A8C98,
        "descricao": "O teto sumiu, os bancos continuam ocupados.",
        "monstros": [
            {"nome": "Estátua Animada", "hp": 265, "atk": 42, "def": 17, "xp": 116, "moedas": 165, "drops": [("fragmento_sino", 0.55)]},
            {"nome": "Monge Silente", "hp": 240, "atk": 47, "def": 14, "xp": 120, "moedas": 160, "drops": [("fragmento_sino", 0.45)]},
            {"nome": "Sino Amaldiçoado", "hp": 280, "atk": 40, "def": 18, "xp": 114, "moedas": 172, "drops": [("fragmento_sino", 0.50)]},
        ],
        "boss": {"nome": "«Coro dos Sem Rosto»", "hp": 1010, "atk": 104, "def": 23, "xp": 980, "moedas": 1650, "drops": [("fragmento_selo", 1.0)]},
    },
    9: {
        "nome": "Céu Partido",
        "cor": 0x4361EE,
        "descricao": "O andar acabou e vira ponte. Não olhe pra baixo — não tem baixo.",
        "monstros": [
            {"nome": "Harpia Tempestade", "hp": 292, "atk": 48, "def": 18, "xp": 130, "moedas": 185, "drops": [("pena_do_trovao", 0.55)]},
            {"nome": "Dragão Jovem", "hp": 320, "atk": 45, "def": 21, "xp": 128, "moedas": 195, "drops": [("pena_do_trovao", 0.45)]},
            {"nome": "Sentinela Alada", "hp": 275, "atk": 52, "def": 16, "xp": 134, "moedas": 180, "drops": [("pena_do_trovao", 0.50)]},
        ],
        "boss": {"nome": "«Vyrra, a Serpente do Trovão»", "hp": 1130, "atk": 117, "def": 26, "xp": 1100, "moedas": 1850, "drops": [("fragmento_selo", 1.0)]},
    },
    10: {
        "nome": "Salão do Selo",
        "cor": 0x2B2D42,
        "descricao": "Dez portas atrás de você. Uma na frente. Nenhuma janela.",
        "monstros": [
            {"nome": "Cavaleiro Espelhado", "hp": 325, "atk": 53, "def": 20, "xp": 144, "moedas": 205, "drops": [("eco_cristalizado", 0.55)]},
            {"nome": "Eco do Jogador", "hp": 300, "atk": 58, "def": 18, "xp": 148, "moedas": 200, "drops": [("eco_cristalizado", 0.45)]},
            {"nome": "Guardião do Selo", "hp": 350, "atk": 50, "def": 23, "xp": 142, "moedas": 215, "drops": [("eco_cristalizado", 0.50)]},
        ],
        "boss": {"nome": "«O Arquiteto do Décimo Selo»", "hp": 1260, "atk": 130, "def": 29, "xp": 1220, "moedas": 2050, "drops": [("fragmento_selo", 1.0)]},
    },
}

# Fase 2: as 4 bases. Os 12 ramos (ascensões) entram depois.
CLASSES = {
    "mago": {
        "nome": "Mago", "emoji": "🔮",
        "atributo_habilidade": "inteligencia",   # dano de habilidade escala com isso
        "afinidade_arma": "inteligencia",        # rende cheio com cajado
        "desc": "Dano de habilidade em INT. Rende cheio com cajado na mão.",
    },
    "guerreiro": {
        "nome": "Guerreiro", "emoji": "🗡️",
        "atributo_habilidade": "forca",
        "afinidade_arma": "forca",
        "desc": "Dano de habilidade em FOR. Rende cheio com espada, machado ou martelo.",
    },
    "ladino": {
        "nome": "Ladino", "emoji": "🏹",
        "atributo_habilidade": "destreza",
        "afinidade_arma": "destreza",
        "desc": "Dano de habilidade em DES. Rende cheio com adaga, arco ou foice.",
    },
    "orador": {
        "nome": "Orador", "emoji": "🙏",
        "atributo_habilidade": "inteligencia",   # dano de habilidade em INT, apesar da arma ser de DES
        "afinidade_arma": "destreza",            # rende cheio desarmado ou de manopla/faixa
        "desc": "Dano de habilidade em INT, mas briga desarmado ou de manopla — escala em DES.",
    },
}

# Ramos liberados por nível dentro de cada base. Vêm depois da fase 2 —
# por enquanto só existem pra `rpg ascencao` explicar o caminho.
ASCENSOES = {
    "mago_gelo": {"nome": "Mago de Gelo", "base": "mago", "elemento": "gelo"},
    "mago_fogo": {"nome": "Mago de Fogo", "base": "mago", "elemento": "fogo"},
    "mago_raio": {"nome": "Mago de Raio", "base": "mago", "elemento": "raio"},
    "soldado": {"nome": "Soldado", "base": "guerreiro", "elemento": None},
    "mercenario": {"nome": "Mercenário", "base": "guerreiro", "elemento": None},
    "espadachim": {"nome": "Espadachim", "base": "guerreiro", "elemento": None},
    "assassino": {"nome": "Assassino", "base": "ladino", "elemento": None},
    "batedor_de_carteira": {"nome": "Batedor de Carteira", "base": "ladino", "elemento": None},
    "arqueiro": {"nome": "Arqueiro", "base": "ladino", "elemento": None},
    "monge": {"nome": "Monge", "base": "orador", "elemento": None},
    "clerigo": {"nome": "Clérigo", "base": "orador", "elemento": "divino"},
    "paladino": {"nome": "Paladino", "base": "orador", "elemento": "divino"},
}

# Catálogo de habilidades — vazio de propósito nesta fase. Só a infraestrutura
# (mana, botão de habilidade, requisito, condição, afinidade de arma) existe
# ainda. Quando a primeira skill entrar, a chave segue este formato:
#   "chave": {
#       "nome": str, "emoji": str, "classe": uma chave de CLASSES,
#       "custo_mana": int, "desc": str,
#       "requisito": (atributo, valor_minimo) ou omitido,
#       "sidequest": True ou omitido — destravada por NPC, não por atributo,
#   }
HABILIDADES = {}

TITULOS = {
    "beta_tester": {
        "nome": "Beta Tester", "emoji": "🧪",
        "desc": "Jogou a torre antes dela ficar de pé.",
    },
    "primeiro_andar_10": {
        "nome": "Primeiro do Décimo Andar", "emoji": "🏆",
        "desc": "O primeiro a abrir a porta do Salão do Selo.",
    },
}


ANDAR_MAXIMO = max(ANDARES)


def itens_da_loja(andar: int):
    return {k: v for k, v in ITENS.items()
            if v["tipo"] != "material" and v.get("loja", True)
            and v.get("andar_min", 1) <= andar}