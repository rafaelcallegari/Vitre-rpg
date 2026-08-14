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

    # ---------------- acessórios (só cai da raide de guilda, ver decisoes.md) ----------------
    # "atributo" + "bonus" somam direto no atributo base na hora de montar os
    # stats (bot.stats()) — NÃO no requisito de skill, que lê a coluna crua.
    # INT fica deliberadamente mais baixo que FOR/DES/CON: INT alimenta mana,
    # mana alimenta lançamento de skill, e +6 INT de equipamento daria mais de
    # um lançamento extra da skill mais barata (12 mana) se escalasse igual
    # às outras. Com anel+colar de INT (2+2=4) e MANA_POR_INT=5, o teto são
    # +20 de mana — no máximo +1 lançamento da skill de 12, nunca +2.
    "anel_forca": {"loja": False, "nome": "«Anel do Punho Firme»", "emoji": "💍", "tipo": "anel", "atributo": "forca", "bonus": 4, "andar_min": 7},
    "anel_destreza": {"loja": False, "nome": "«Anel do Passo Leve»", "emoji": "💍", "tipo": "anel", "atributo": "destreza", "bonus": 4, "andar_min": 7},
    "anel_constituicao": {"loja": False, "nome": "«Anel do Coração de Pedra»", "emoji": "💍", "tipo": "anel", "atributo": "constituicao", "bonus": 4, "andar_min": 7},
    "anel_inteligencia": {"loja": False, "nome": "«Anel da Centelha»", "emoji": "💍", "tipo": "anel", "atributo": "inteligencia", "bonus": 2, "andar_min": 7},
    "colar_forca": {"loja": False, "nome": "«Colar do Touro»", "emoji": "📿", "tipo": "colar", "atributo": "forca", "bonus": 4, "andar_min": 7},
    "colar_destreza": {"loja": False, "nome": "«Colar da Presa»", "emoji": "📿", "tipo": "colar", "atributo": "destreza", "bonus": 4, "andar_min": 7},
    "colar_constituicao": {"loja": False, "nome": "«Colar da Muralha»", "emoji": "📿", "tipo": "colar", "atributo": "constituicao", "bonus": 4, "andar_min": 7},
    "colar_inteligencia": {"loja": False, "nome": "«Colar do Eco Arcano»", "emoji": "📿", "tipo": "colar", "atributo": "inteligencia", "bonus": 2, "andar_min": 7},

    # ---------------- armas elementais (craft de Forja, material de chefe 11-15) ----------------
    # Mesmo padrão dos acessórios: "atributo" + "bonus" somam no atributo
    # efetivo (bot.stats()), por cima do que a arma já faz normalmente (atk
    # escalando em "atributo", crítico fixo pras de Destreza). Requisito de
    # skill continua lendo a coluna crua — ver decisoes.md.
    # Tipo de FOR/DES distribuído pra cada nome aparecer 2x nos 6 elementos:
    # espada (ar, fogo) machado (raio, sombrio) martelo (gelo, divino)
    # arco (ar, fogo) adaga (raio, sombrio) foice (gelo, divino)
    "espada_vento": {"loja": False, "nome": "«Espada do Vento Preso»", "emoji": "🗡️", "tipo": "arma", "atributo": "forca", "bonus": 6, "elemento": "ar", "preco": 18000, "atk": 95, "andar_min": 11},
    "arco_vento": {"loja": False, "nome": "«Arco da Corrente de Ar»", "emoji": "🏹", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "bonus": 6, "elemento": "ar", "preco": 18000, "atk": 95, "andar_min": 11},
    "cajado_vento": {"loja": False, "nome": "«Cajado do Sopro Contido»", "emoji": "🪄", "tipo": "arma", "atributo": "inteligencia", "bonus": 6, "elemento": "ar", "preco": 18000, "atk": 95, "andar_min": 11},
    "manopla_vento": {"loja": False, "nome": "«Manoplas do Terraço»", "emoji": "🥊", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "bonus": 6, "elemento": "ar", "preco": 18000, "atk": 95, "andar_min": 11},

    "machado_raio": {"loja": False, "nome": "«Machado da Tempestade Muda»", "emoji": "🪓", "tipo": "arma", "atributo": "forca", "bonus": 6, "elemento": "raio", "preco": 18000, "atk": 95, "andar_min": 12},
    "adaga_raio": {"loja": False, "nome": "«Adaga da Faísca Presa»", "emoji": "🔪", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "bonus": 6, "elemento": "raio", "preco": 18000, "atk": 95, "andar_min": 12},
    "cajado_raio": {"loja": False, "nome": "«Cajado do Trovão Engolido»", "emoji": "🪄", "tipo": "arma", "atributo": "inteligencia", "bonus": 6, "elemento": "raio", "preco": 18000, "atk": 95, "andar_min": 12},
    "manopla_raio": {"loja": False, "nome": "«Manoplas do Arco Elétrico»", "emoji": "🥊", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "bonus": 6, "elemento": "raio", "preco": 18000, "atk": 95, "andar_min": 12},

    "martelo_gelo": {"loja": False, "nome": "«Martelo da Ala Branca»", "emoji": "🔨", "tipo": "arma", "atributo": "forca", "bonus": 6, "elemento": "gelo", "preco": 18000, "atk": 95, "andar_min": 13},
    "foice_gelo": {"loja": False, "nome": "«Foice do Silêncio»", "emoji": "🌫️", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "bonus": 6, "elemento": "gelo", "preco": 18000, "atk": 95, "andar_min": 13},
    "cajado_gelo": {"loja": False, "nome": "«Cajado do Eco Congelado»", "emoji": "🪄", "tipo": "arma", "atributo": "inteligencia", "bonus": 6, "elemento": "gelo", "preco": 18000, "atk": 95, "andar_min": 13},
    "manopla_gelo": {"loja": False, "nome": "«Manoplas do Gelo Fino»", "emoji": "🥊", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "bonus": 6, "elemento": "gelo", "preco": 18000, "atk": 95, "andar_min": 13},

    "espada_solario": {"loja": False, "nome": "«Espada do Fogo Sem Chama»", "emoji": "🗡️", "tipo": "arma", "atributo": "forca", "bonus": 6, "elemento": "fogo", "preco": 18000, "atk": 95, "andar_min": 14},
    "arco_solario": {"loja": False, "nome": "«Arco da Brasa Contida»", "emoji": "🏹", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "bonus": 6, "elemento": "fogo", "preco": 18000, "atk": 95, "andar_min": 14},
    "cajado_solario": {"loja": False, "nome": "«Cajado do Calor Retido»", "emoji": "🪄", "tipo": "arma", "atributo": "inteligencia", "bonus": 6, "elemento": "fogo", "preco": 18000, "atk": 95, "andar_min": 14},
    "manopla_solario": {"loja": False, "nome": "«Manoplas do Vidro Fundido»", "emoji": "🥊", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "bonus": 6, "elemento": "fogo", "preco": 18000, "atk": 95, "andar_min": 14},

    "machado_sombrio": {"loja": False, "nome": "«Machado da Sombra Dobrada»", "emoji": "🪓", "tipo": "arma", "atributo": "forca", "bonus": 6, "elemento": "sombrio", "preco": 18000, "atk": 95, "andar_min": 15},
    "adaga_sombria": {"loja": False, "nome": "«Adaga do Trono Vazio»", "emoji": "🔪", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "bonus": 6, "elemento": "sombrio", "preco": 18000, "atk": 95, "andar_min": 15},
    "cajado_sombrio": {"loja": False, "nome": "«Cajado da Ferida Sombria»", "emoji": "🪄", "tipo": "arma", "atributo": "inteligencia", "bonus": 6, "elemento": "sombrio", "preco": 18000, "atk": 95, "andar_min": 15},
    "manopla_sombria": {"loja": False, "nome": "«Manoplas do Silêncio Ajoelhado»", "emoji": "🥊", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "bonus": 6, "elemento": "sombrio", "preco": 18000, "atk": 95, "andar_min": 15},

    "martelo_divino": {"loja": False, "nome": "«Martelo do Prego de Luz»", "emoji": "🔨", "tipo": "arma", "atributo": "forca", "bonus": 6, "elemento": "divino", "preco": 18000, "atk": 95, "andar_min": 15},
    "foice_divina": {"loja": False, "nome": "«Foice do Juízo Suspenso»", "emoji": "🌫️", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "bonus": 6, "elemento": "divino", "preco": 18000, "atk": 95, "andar_min": 15},
    "cajado_divino": {"loja": False, "nome": "«Cajado da Ruína»", "emoji": "🪄", "tipo": "arma", "atributo": "inteligencia", "bonus": 6, "elemento": "divino", "preco": 18000, "atk": 95, "andar_min": 15},
    "manopla_divina": {"loja": False, "nome": "«Manoplas da Marca»", "emoji": "🥊", "tipo": "arma", "atributo": "destreza", "critico": 0.18, "bonus": 6, "elemento": "divino", "preco": 18000, "atk": 95, "andar_min": 15},

    # ---------------- materiais dos andares 11-15 (monstro comum) ----------------
    "pluma_eterea": {"nome": "Pluma Etérea", "emoji": "🪶", "tipo": "material", "preco": 480},
    "farpa_eletrica": {"nome": "Farpa Elétrica", "emoji": "🔌", "tipo": "material", "preco": 560},
    "estilhaco_gelido": {"nome": "Estilhaço Gélido", "emoji": "🧊", "tipo": "material", "preco": 640},
    "cinza_quente": {"nome": "Cinza Quente", "emoji": "♨️", "tipo": "material", "preco": 720},
    "po_de_estrela": {"nome": "Pó de Estrela", "emoji": "🌠", "tipo": "material", "preco": 800},

    # ---------------- materiais de chefe dos andares 11-15 (craft de arma elemental) ----------------
    "sopro_contido": {"nome": "Sopro Contido", "emoji": "🌬️", "tipo": "material", "preco": 1600},
    "semente_de_trovao": {"nome": "Semente de Trovão", "emoji": "🌩️", "tipo": "material", "preco": 1900},
    "lasca_de_silencio": {"nome": "Lasca de Silêncio", "emoji": "🔇", "tipo": "material", "preco": 2200},
    "brasa_sem_fumaca": {"nome": "Brasa Sem Fumaça", "emoji": "🔥", "tipo": "material", "preco": 2500},
    "sombra_dobrada": {"nome": "Sombra Dobrada", "emoji": "🌑", "tipo": "material", "preco": 2800},
    "prego_de_luz": {"nome": "Prego de Luz", "emoji": "📌", "tipo": "material", "preco": 2800},

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

    # ---------------- materiais de Encantador (andares ímpares) e Joalheiro
    # (andares pares) -- mesma escada de preço dos materiais de chão do
    # andar correspondente (12 no 1 até 400 no 10). Ver decisoes.md § Encantador
    # e Joalheiro pra quantidade por receita (tier do bônus -> andar do material).
    "essencia_do_vento": {"nome": "Essência do Vento", "emoji": "🍃", "tipo": "material", "preco": 12},
    "ambar_de_seiva": {"nome": "Âmbar de Seiva", "emoji": "🟠", "tipo": "material", "preco": 30},
    "essencia_da_agua": {"nome": "Essência da Água", "emoji": "💧", "tipo": "material", "preco": 55},
    "lagrima_de_sal": {"nome": "Lágrima de Sal", "emoji": "🤍", "tipo": "material", "preco": 85},
    "essencia_do_gelo": {"nome": "Essência do Gelo", "emoji": "🧊", "tipo": "material", "preco": 120},
    "rubi_fosco": {"nome": "Rubi Fosco", "emoji": "🔴", "tipo": "material", "preco": 160},
    "essencia_de_fogo": {"nome": "Essência de Fogo", "emoji": "🔥", "tipo": "material", "preco": 210},
    "vitral_partido": {"nome": "Vitral Partido", "emoji": "🟣", "tipo": "material", "preco": 265},
    "essencia_estelar": {"nome": "Essência Estelar", "emoji": "🌟", "tipo": "material", "preco": 330},
    "perola_do_eco": {"nome": "Pérola do Eco", "emoji": "⚪", "tipo": "material", "preco": 400},

    # ---------------- Joalheiro (fabrica, jogador escolhe o atributo) ----------------
    # Ao contrário do resto do catálogo, estas duas chaves NÃO têm "atributo"
    # nem "bonus" fixos -- variam por instância (joia_atributo/joia_valor em
    # `instancias`, escalando com o nível do Joalheiro que fabricou). "preco"
    # aqui só serve de base pra `rpg vender` (não há custo de craft fixo --
    # ver decisoes.md, o custo em moedas segue a mesma tabela do Encantador).
    "anel_joia": {"loja": False, "nome": "Anel Lapidado", "emoji": "💍", "tipo": "anel", "preco": 3800, "andar_min": 1},
    "colar_joia": {"loja": False, "nome": "Colar Lapidado", "emoji": "📿", "tipo": "colar", "preco": 3800, "andar_min": 1},
}


# atk do boss = 13 + 13 * (andar - 1)
ANDARES = {
    1: {
        "nome": "Planície dos Iniciantes",
        "cor": 0x7FB069,
        "descricao": "Grama alta até o joelho e o céu de pedra do andar de cima. Todo mundo começa aqui.",
        "monstros": [
            {"nome": "Javali das Planícies", "hp": 42, "atk": 8, "def": 1, "xp": 18, "moedas": 26, "drops": [("presa_javali", 0.55), ("essencia_do_vento", 0.55)]},
            {"nome": "Lobo da Névoa", "hp": 38, "atk": 9, "def": 1, "xp": 19, "moedas": 24, "drops": [("presa_javali", 0.45), ("essencia_do_vento", 0.45)]},
            {"nome": "Slime Azulado", "hp": 52, "atk": 6, "def": 2, "xp": 17, "moedas": 28, "drops": [("presa_javali", 0.60), ("essencia_do_vento", 0.50)]},
        ],
        "boss": {"nome": "«Vargash, o Kobold Coroado»", "hp": 165, "atk": 13, "def": 2, "xp": 150, "moedas": 260, "drops": [("fragmento_selo", 1.0)]},
    },
    2: {
        "nome": "Bosque Sussurrante",
        "cor": 0x3E7C59,
        "descricao": "As árvores repetem, com meio segundo de atraso, tudo o que você fala.",
        "monstros": [
            {"nome": "Aranha Tecelã", "hp": 72, "atk": 13, "def": 3, "xp": 32, "moedas": 45, "drops": [("seda_sussurrante", 0.55), ("ambar_de_seiva", 0.55)]},
            {"nome": "Cogumelo Andante", "hp": 82, "atk": 11, "def": 4, "xp": 30, "moedas": 48, "drops": [("seda_sussurrante", 0.50), ("ambar_de_seiva", 0.50)]},
            {"nome": "Corvo de Ferro", "hp": 62, "atk": 15, "def": 2, "xp": 34, "moedas": 42, "drops": [("seda_sussurrante", 0.45), ("ambar_de_seiva", 0.45)]},
        ],
        "boss": {"nome": "«Aracnia, a Rainha dos Fios»", "hp": 285, "atk": 26, "def": 5, "xp": 260, "moedas": 450, "drops": [("fragmento_selo", 1.0)]},
    },
    3: {
        "nome": "Ruínas Afundadas",
        "cor": 0x5C6B73,
        "descricao": "Uma cidade inteira submersa até a metade. Alguma coisa ainda anda lá embaixo.",
        "monstros": [
            {"nome": "Esqueleto Enferrujado", "hp": 102, "atk": 18, "def": 5, "xp": 46, "moedas": 65, "drops": [("osso_enferrujado", 0.55), ("essencia_da_agua", 0.55)]},
            {"nome": "Rato Colossal", "hp": 92, "atk": 20, "def": 4, "xp": 48, "moedas": 62, "drops": [("osso_enferrujado", 0.50), ("essencia_da_agua", 0.50)]},
            {"nome": "Lodo Ácido", "hp": 115, "atk": 16, "def": 6, "xp": 44, "moedas": 68, "drops": [("osso_enferrujado", 0.45), ("essencia_da_agua", 0.45)]},
        ],
        "boss": {"nome": "«Guardião de Pedra Rachada»", "hp": 410, "atk": 39, "def": 8, "xp": 380, "moedas": 650, "drops": [("fragmento_selo", 1.0)]},
    },
    4: {
        "nome": "Deserto de Sal",
        "cor": 0xD9C5A0,
        "descricao": "Branco até onde a vista alcança. O chão range quando você pisa.",
        "monstros": [
            {"nome": "Escorpião de Cristal", "hp": 132, "atk": 23, "def": 7, "xp": 60, "moedas": 85, "drops": [("cristal_de_sal", 0.55), ("lagrima_de_sal", 0.55)]},
            {"nome": "Bandido Errante", "hp": 122, "atk": 26, "def": 6, "xp": 62, "moedas": 90, "drops": [("cristal_de_sal", 0.45), ("lagrima_de_sal", 0.45)]},
            {"nome": "Verme das Dunas", "hp": 145, "atk": 21, "def": 8, "xp": 58, "moedas": 82, "drops": [("cristal_de_sal", 0.50), ("lagrima_de_sal", 0.50)]},
        ],
        "boss": {"nome": "«Zarhak, o Verme Ancião»", "hp": 530, "atk": 52, "def": 11, "xp": 500, "moedas": 850, "drops": [("fragmento_selo", 1.0)]},
    },
    5: {
        "nome": "Lago Congelado",
        "cor": 0x8ECAE6,
        "descricao": "O gelo é grosso o bastante pra andar e fino o bastante pra ouvir.",
        "monstros": [
            {"nome": "Lobo de Gelo", "hp": 162, "atk": 28, "def": 9, "xp": 74, "moedas": 105, "drops": [("nucleo_gelado", 0.55), ("essencia_do_gelo", 0.55)]},
            {"nome": "Espírito da Neblina", "hp": 148, "atk": 32, "def": 7, "xp": 78, "moedas": 100, "drops": [("nucleo_gelado", 0.45), ("essencia_do_gelo", 0.45)]},
            {"nome": "Urso Corrompido", "hp": 180, "atk": 26, "def": 11, "xp": 72, "moedas": 110, "drops": [("nucleo_gelado", 0.50), ("essencia_do_gelo", 0.50)]},
        ],
        "boss": {"nome": "«Nivalgar, o Uivo Branco»", "hp": 650, "atk": 65, "def": 14, "xp": 620, "moedas": 1050, "drops": [("fragmento_selo", 1.0)]},
    },
    6: {
        "nome": "Mina Abandonada",
        "cor": 0x6B4E31,
        "descricao": "As lamparinas ainda estão acesas. Ninguém apagou porque ninguém saiu.",
        "monstros": [
            {"nome": "Golem de Minério", "hp": 205, "atk": 31, "def": 13, "xp": 88, "moedas": 125, "drops": [("minerio_negro", 0.55), ("rubi_fosco", 0.55)]},
            {"nome": "Morcego Sanguinário", "hp": 175, "atk": 36, "def": 9, "xp": 92, "moedas": 120, "drops": [("minerio_negro", 0.45), ("rubi_fosco", 0.45)]},
            {"nome": "Mineiro Enlouquecido", "hp": 190, "atk": 34, "def": 11, "xp": 90, "moedas": 130, "drops": [("minerio_negro", 0.50), ("rubi_fosco", 0.50)]},
        ],
        "boss": {"nome": "«Núcleo Vivo da Mina»", "hp": 770, "atk": 78, "def": 17, "xp": 740, "moedas": 1250, "drops": [("fragmento_selo", 1.0)]},
    },
    7: {
        "nome": "Campos de Cinzas",
        "cor": 0xB5651D,
        "descricao": "Não chove aqui. Cai cinza, e ela é quente.",
        "monstros": [
            {"nome": "Cavaleiro Queimado", "hp": 232, "atk": 38, "def": 14, "xp": 102, "moedas": 145, "drops": [("brasa_eterna", 0.55), ("essencia_de_fogo", 0.55)]},
            {"nome": "Elemental de Brasa", "hp": 210, "atk": 43, "def": 11, "xp": 106, "moedas": 140, "drops": [("brasa_eterna", 0.45), ("essencia_de_fogo", 0.45)]},
            {"nome": "Abutre de Ferro", "hp": 220, "atk": 40, "def": 13, "xp": 104, "moedas": 150, "drops": [("brasa_eterna", 0.50), ("essencia_de_fogo", 0.50)]},
        ],
        "boss": {"nome": "«Ignar, o Cavaleiro de Brasas»", "hp": 890, "atk": 91, "def": 20, "xp": 860, "moedas": 1450, "drops": [("fragmento_selo", 1.0)]},
    },
    8: {
        "nome": "Catedral Quebrada",
        "cor": 0x9A8C98,
        "descricao": "O teto sumiu, os bancos continuam ocupados.",
        "monstros": [
            {"nome": "Estátua Animada", "hp": 265, "atk": 42, "def": 17, "xp": 116, "moedas": 165, "drops": [("fragmento_sino", 0.55), ("vitral_partido", 0.55)]},
            {"nome": "Monge Silente", "hp": 240, "atk": 47, "def": 14, "xp": 120, "moedas": 160, "drops": [("fragmento_sino", 0.45), ("vitral_partido", 0.45)]},
            {"nome": "Sino Amaldiçoado", "hp": 280, "atk": 40, "def": 18, "xp": 114, "moedas": 172, "drops": [("fragmento_sino", 0.50), ("vitral_partido", 0.50)]},
        ],
        "boss": {"nome": "«Coro dos Sem Rosto»", "hp": 1010, "atk": 104, "def": 23, "xp": 980, "moedas": 1650, "drops": [("fragmento_selo", 1.0)]},
    },
    9: {
        "nome": "Céu Partido",
        "cor": 0x4361EE,
        "descricao": "O andar acabou e vira ponte. Não olhe pra baixo — não tem baixo.",
        "monstros": [
            {"nome": "Harpia Tempestade", "hp": 292, "atk": 48, "def": 18, "xp": 130, "moedas": 185, "drops": [("pena_do_trovao", 0.55), ("essencia_estelar", 0.55)]},
            {"nome": "Dragão Jovem", "hp": 320, "atk": 45, "def": 21, "xp": 128, "moedas": 195, "drops": [("pena_do_trovao", 0.45), ("essencia_estelar", 0.45)]},
            {"nome": "Sentinela Alada", "hp": 275, "atk": 52, "def": 16, "xp": 134, "moedas": 180, "drops": [("pena_do_trovao", 0.50), ("essencia_estelar", 0.50)]},
        ],
        "boss": {"nome": "«Vyrra, a Serpente do Trovão»", "hp": 1130, "atk": 117, "def": 26, "xp": 1100, "moedas": 1850, "drops": [("fragmento_selo", 1.0)]},
    },
    10: {
        "nome": "Salão do Selo",
        "cor": 0x2B2D42,
        "descricao": "Dez portas atrás de você. Uma na frente. Nenhuma janela.",
        "monstros": [
            {"nome": "Cavaleiro Espelhado", "hp": 325, "atk": 53, "def": 20, "xp": 144, "moedas": 205, "drops": [("eco_cristalizado", 0.55), ("perola_do_eco", 0.55)]},
            {"nome": "Eco do Jogador", "hp": 300, "atk": 58, "def": 18, "xp": 148, "moedas": 200, "drops": [("eco_cristalizado", 0.45), ("perola_do_eco", 0.45)]},
            {"nome": "Guardião do Selo", "hp": 350, "atk": 50, "def": 23, "xp": 142, "moedas": 215, "drops": [("eco_cristalizado", 0.50), ("perola_do_eco", 0.50)]},
        ],
        "boss": {"nome": "«O Arquiteto do Décimo Selo»", "hp": 1260, "atk": 130, "def": 29, "xp": 1220, "moedas": 2050, "drops": [("fragmento_selo", 1.0)]},
    },

    # ---- acima do selo: sem paredes, sem loja, sem ferreiro, sem carroça ----
    # (bot.py bloqueia comércio pra andar > 10; ver decisoes.md § Andares 11-15)
    # "elemento" no chefe liga o telegraph de condição em combate.py — só
    # chefes com essa chave rolam pra amarrar Queimadura/Congelamento/etc.
    11: {
        "nome": "Terraço Estrelado",
        "cor": 0x8ECAE6,
        "descricao": "O teto sumiu. A torre continua, mas agora é só as bordas de uma sala que o céu invadiu.",
        "monstros": [
            {"nome": "Grifo de Vidro", "hp": 330, "atk": 58, "def": 21, "xp": 156, "moedas": 222, "drops": [("pluma_eterea", 0.55)]},
            {"nome": "Sentinela Suspensa", "hp": 355, "atk": 56, "def": 24, "xp": 158, "moedas": 226, "drops": [("pluma_eterea", 0.50)]},
            {"nome": "Corrente de Vento", "hp": 375, "atk": 60, "def": 20, "xp": 154, "moedas": 220, "drops": [("pluma_eterea", 0.45)]},
        ],
        "boss": {
            "nome": "«Guardiã do Terraço»", "hp": 4140, "atk": 231, "def": 35,
            "xp": 1460, "moedas": 2450, "elemento": "ar",
            "drops": [("sopro_contido", 1.0)],
        },
    },
    12: {
        "nome": "Pátio da Tempestade",
        "cor": 0x6247AA,
        "descricao": "Relâmpago sem trovão — a luz chega, o som não vem. Alguma coisa aqui em cima engole barulho.",
        "monstros": [
            {"nome": "Coluna Carregada", "hp": 365, "atk": 64, "def": 23, "xp": 168, "moedas": 237, "drops": [("farpa_eletrica", 0.55)]},
            {"nome": "Arco Que Ainda Zune", "hp": 385, "atk": 66, "def": 25, "xp": 170, "moedas": 240, "drops": [("farpa_eletrica", 0.50)]},
            {"nome": "Servo de Cobre", "hp": 400, "atk": 62, "def": 27, "xp": 166, "moedas": 235, "drops": [("farpa_eletrica", 0.45)]},
        ],
        "boss": {
            "nome": "«Arauto do Pátio»", "hp": 4500, "atk": 257, "def": 41,
            "xp": 1700, "moedas": 2850, "elemento": "raio",
            "drops": [("semente_de_trovao", 1.0)],
        },
    },
    13: {
        "nome": "Ala Branca",
        "cor": 0xCAF0F8,
        "descricao": "Branco em toda direção, inclusive pra baixo. Os próprios passos somem depois do terceiro.",
        "monstros": [
            {"nome": "Estátua de Gelo Fino", "hp": 390, "atk": 70, "def": 26, "xp": 180, "moedas": 252, "drops": [("estilhaco_gelido", 0.55)]},
            {"nome": "Eco Congelado", "hp": 410, "atk": 68, "def": 28, "xp": 182, "moedas": 255, "drops": [("estilhaco_gelido", 0.50)]},
            {"nome": "Vigia Sem Rosto", "hp": 425, "atk": 74, "def": 24, "xp": 178, "moedas": 250, "drops": [("estilhaco_gelido", 0.45)]},
        ],
        "boss": {
            "nome": "«Curadora da Ala Branca»", "hp": 4860, "atk": 283, "def": 47,
            "xp": 1940, "moedas": 3250, "elemento": "gelo",
            "drops": [("lasca_de_silencio", 1.0)],
        },
    },
    14: {
        "nome": "O Solário",
        "cor": 0xF3722C,
        "descricao": "Calor sem chama à vista. Se tem fogo aqui, ele decidiu não aparecer pra ninguém ver.",
        "monstros": [
            {"nome": "Vidro Fundido", "hp": 415, "atk": 78, "def": 28, "xp": 192, "moedas": 267, "drops": [("cinza_quente", 0.55)]},
            {"nome": "Fôlego Retido", "hp": 435, "atk": 76, "def": 30, "xp": 194, "moedas": 270, "drops": [("cinza_quente", 0.50)]},
            {"nome": "Estátua de Sal Requentado", "hp": 450, "atk": 82, "def": 26, "xp": 190, "moedas": 265, "drops": [("cinza_quente", 0.45)]},
        ],
        "boss": {
            "nome": "«Guardião do Solário»", "hp": 5220, "atk": 309, "def": 53,
            "xp": 2180, "moedas": 3650, "elemento": "fogo",
            "drops": [("brasa_sem_fumaca", 1.0)],
        },
    },
    15: {
        "nome": "Trono Vazio",
        "cor": 0x22223B,
        "descricao": "Uma cadeira grande demais pra qualquer um. Ninguém se sentou nela ainda — e talvez seja melhor assim.",
        "monstros": [
            {"nome": "Guarda Sem Nome", "hp": 440, "atk": 84, "def": 30, "xp": 204, "moedas": 282, "drops": [("po_de_estrela", 0.55)]},
            {"nome": "Sombra Que Ajoelha", "hp": 460, "atk": 82, "def": 32, "xp": 206, "moedas": 285, "drops": [("po_de_estrela", 0.50)]},
            {"nome": "Retrato Vivo", "hp": 475, "atk": 88, "def": 28, "xp": 202, "moedas": 280, "drops": [("po_de_estrela", 0.45)]},
        ],
        # duas fases, ver decisoes.md § Andar 15 — combate.py troca pra
        # "fase2" sozinho quando o hp cruza 50%, sem resetar nada da luta.
        "boss": {
            "nome": "«Espectro do rei»", "hp": 5580, "atk": 335, "def": 59,
            "xp": 2420, "moedas": 4050, "elemento": "sombrio",
            "drops": [("sombra_dobrada", 1.0)],
            "fase2": {
                "nome": "«A Ruína do Rei»", "atk": 375, "def": 65,
                "elemento": "divino", "drops": [("prego_de_luz", 1.0)],
                "fala_derrota": "De novo não, como você está aqui, se já subiu essa torre",
            },
        },
    },
}

# Condição que cada elemento amarra quando um chefe de andar 11+ telegrafa
# (chefe precisa ter "elemento" no dict — bosses do andar 1-10 não têm essa
# chave, então nunca entram nesse sistema). "duracao" já inclui o "+1" de
# ajuste onde a consulta acontece depois do tick() da própria rodada — ver
# decisoes.md § Condições no jogador pra qual valor pede ajuste e qual não.
CONDICOES_ELEMENTO = {
    "ar": {"tipo": "chance_erro", "nome": "Vendaval", "emoji": "🌪️", "duracao": 3, "valor": 0.35},
    "raio": {"tipo": "bloqueia_skill", "nome": "Choque", "emoji": "⚡", "duracao": 2, "valor": 0},
    "gelo": {"tipo": "pula_turno", "nome": "Congelamento", "emoji": "❄️", "duracao": 3, "valor": 0},
    "fogo": {"tipo": "dano_por_rodada", "nome": "Queimadura", "emoji": "🔥", "duracao": 3, "valor": 0.06},
    "sombrio": {"tipo": "reduz_cura", "nome": "Ferida Sombria", "emoji": "🌑", "duracao": 2, "valor": 0.50},
    "divino": {"tipo": "vulneravel", "nome": "Marca", "emoji": "✨", "duracao": 4, "valor": 0.30},
}

# Fase 2: as 4 bases. Os 12 ramos (ascensões) entram depois.
CLASSES = {
    "mago": {
        "nome": "Mago", "emoji": "🔮",
        "atributo_habilidade": "inteligencia",   # dano de habilidade escala com isso
        "afinidade_arma": "inteligencia",        # rende cheio com cajado
        "recurso": "mana",
        "desc": "Dano de habilidade em INT. Rende cheio com cajado na mão.",
    },
    "guerreiro": {
        "nome": "Guerreiro", "emoji": "🗡️",
        "atributo_habilidade": "forca",
        "afinidade_arma": "forca",
        "recurso": "furia",
        "desc": "Dano de habilidade em FOR. Rende cheio com espada, machado ou martelo.",
    },
    "ladino": {
        "nome": "Ladino", "emoji": "🏹",
        "atributo_habilidade": "destreza",
        "afinidade_arma": "destreza",
        "recurso": "energia",
        "desc": "Dano de habilidade em DES. Rende cheio com adaga, arco ou foice.",
    },
    "orador": {
        "nome": "Orador", "emoji": "🙏",
        "atributo_habilidade": "inteligencia",   # dano de habilidade em INT, apesar da arma ser de DES
        "afinidade_arma": "destreza",            # rende cheio desarmado ou de manopla/faixa
        "recurso": "mana",
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

# Catálogo de habilidades. Cada chave segue este formato:
#   "chave": {
#       "nome": str, "emoji": str, "classe": uma chave de CLASSES,
#       "recurso": "mana" | "furia" | "energia" — bate com CLASSES[classe]["recurso"],
#       "custo": int — quanto do recurso a habilidade consome,
#       "desc": str,
#       "requisito": (atributo, valor_minimo) ou omitido — sem requisito = vem
#           com a classe, disponível desde o nível 1,
#       "sidequest": True ou omitido — destravada por NPC, não por atributo,
#       "alvo": "aliado_escolhido" ou omitido — omitido = afeta quem lança,
#           o chefe, ou a party inteira (a função de efeito em combate.py sabe
#           qual); "aliado_escolhido" abre um seletor de alvo antes de lançar.
#   }
# Fúria e Energia são recursos por luta — zeram/enchem toda vez que uma luta
# de chefe começa, não persistem no banco. Ver decisoes.md § Primeira leva
# de skills.
HABILIDADES = {
    "dardo_arcano": {
        "nome": "Dardo Arcano", "emoji": "🔹", "classe": "mago",
        "recurso": "mana", "custo": 12,
        "desc": "Dano em INT que ignora a defesa do chefe.",
    },
    "ruptura": {
        "nome": "Ruptura", "emoji": "💠", "classe": "mago",
        "recurso": "mana", "custo": 18, "requisito": ("inteligencia", 15),
        "desc": "O chefe recebe +20% de dano por 3 rodadas — vale pra party inteira.",
    },
    "golpe_aberto": {
        "nome": "Golpe Aberto", "emoji": "🩸", "classe": "guerreiro",
        "recurso": "furia", "custo": 40,
        "desc": "Dano em FOR + sangramento por rodada, empilha até 3 vezes.",
    },
    "pancada_atordoante": {
        "nome": "Pancada Atordoante", "emoji": "💥", "classe": "guerreiro",
        "recurso": "furia", "custo": 65, "requisito": ("forca", 15),
        "desc": "Chance de o chefe perder a próxima ação — escala com FOR, teto 25%.",
    },
    "corte_rapido": {
        "nome": "Corte Rápido", "emoji": "🗡️", "classe": "ladino",
        "recurso": "energia", "custo": 30,
        "desc": "Dois golpes em DES com chance de crítico maior.",
    },
    "ponto_cego": {
        "nome": "Ponto Cego", "emoji": "🎯", "classe": "ladino",
        "recurso": "energia", "custo": 50, "requisito": ("destreza", 15),
        "desc": "3 rodadas com chance de crítico muito alta.",
    },
    "palavra_de_alento": {
        "nome": "Palavra de Alento", "emoji": "🕊️", "classe": "orador",
        "recurso": "mana", "custo": 12, "alvo": "aliado_escolhido",
        "desc": "Regeneração num aliado escolhido ao longo de 2 rodadas — não é cura instantânea.",
    },
    "voto_de_ferro": {
        "nome": "Voto de Ferro", "emoji": "🛡️", "classe": "orador",
        "recurso": "mana", "custo": 18, "requisito": ("inteligencia", 15),
        "desc": "Reduz o dano recebido por toda a party por 2 rodadas.",
    },
}

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

# só o que "Sua Majestade do Andar Nenhum" derruba — ver raide.py. Lista
# EXPLÍCITA de propósito (não mais `tuple(k for k,v in ITENS.items() if
# v.get("tipo") in ("anel","colar"))`): a versão derivada por tipo juntava
# QUALQUER anel/colar novo à mesa de loot da raide sem ninguém pedir --
# armadilha que pegaria em cheio os dois itens do Joalheiro (anel_joia,
# colar_joia) assim que existissem. Estes 8 são os únicos acessórios da
# raide e não mudam nesta carta nem em nenhuma futura sem decisão explícita
# -- ver decisoes.md § Encantador e Joalheiro.
ACESSORIOS_RAIDE = (
    "anel_forca", "anel_destreza", "anel_constituicao", "anel_inteligencia",
    "colar_forca", "colar_destreza", "colar_constituicao", "colar_inteligencia",
)

# ---------------- raide de guilda ----------------
# Fixa, fora da progressão da torre — não fica em ANDARES porque não
# destranca andar nenhum. HP/ATK/DEF calibrados um pouco abaixo do chefe do
# andar 7 (hp 890/atk 91/def 20) de propósito: com HP × participantes
# (Luta já faz isso sozinha) e recompensa modesta, o risco tem que ficar
# baixo pra um grupo de late game — ver decisoes.md § Raide.
RAIDE_CHEFE = {
    "nome": "«Sua Majestade do Andar Nenhum»",
    "hp": 850, "atk": 82, "def": 18,
}
ANDAR_MINIMO_RAIDE = 7
ANDAR_REFERENCIA_RAIDE = 7   # só pra fórmulas de penetração/destreza — não desbloqueia nada
RECOMPENSA_MOEDAS_RAIDE = 800   # modesta de propósito: chefe fixo, sem risco pra late game
QTD_ACESSORIOS_RAIDE = 2
COOLDOWN_RAIDE_SEGUNDOS = 2 * 3600   # por guilda (não por jogador)


def itens_da_loja(andar: int):
    return {k: v for k, v in ITENS.items()
            if v["tipo"] != "material" and v.get("loja", True)
            and v.get("andar_min", 1) <= andar}