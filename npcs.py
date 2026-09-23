# npcs.py
# NPCs, lojas por andar e sistema de viagem.
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import database as db
import entidade_sombria
import mundo
from dialogos import DIALOGOS
from game_data import ITENS

FUSO = ZoneInfo("America/Sao_Paulo")

# ---------------- carroça do Bramm ----------------
HORARIOS_CARROCA = ((9, 0), (12, 40), (15, 0), (21, 0))   # (hora, minuto), horário de Brasília
JANELA_CARROCA_MIN = 30               # quanto tempo ele fica parado, em todos os horários
ANDAR_DESBLOQUEIA_CARROCA = 3         # onde você o encontra pela primeira vez

# ---------------- custo de viagem paga ----------------
CUSTO_BASE_VIAGEM = 80
CUSTO_POR_ANDAR = 40


def agora():
    return datetime.now(FUSO)


def custo_viagem(origem, destino):
    if origem == destino:
        return 0
    distancia = abs(destino - origem)
    return distancia * (CUSTO_BASE_VIAGEM + CUSTO_POR_ANDAR * max(origem, destino))


def carroca_ativa(momento=None):
    """Retorna (esta_ativa, horario_em_que_parte)."""
    m = momento or agora()
    for h, minuto in HORARIOS_CARROCA:
        inicio = m.replace(hour=h, minute=minuto, second=0, microsecond=0)
        fim = inicio + timedelta(minutes=JANELA_CARROCA_MIN)
        if inicio <= m < fim:
            return True, fim
    return False, None


def flor_ativa(momento=None):
    """A flor do andar 1 (pedido da Guia no andar 11, ver andares_altos.py)
    nasce na mesma janela da carroça do Bramm -- mesmos horários, mesma
    duração, sem aviso no #torre. Reaproveita carroca_ativa() em vez de
    duplicar a lógica de janela; o "esta_ativa" que ela devolve é sobre o
    RELÓGIO, não sobre quem pode colher -- isso é elegibilidade da quest
    (andares_altos.pode_colher_flor), checada à parte."""
    return carroca_ativa(momento)


def proxima_carroca(momento=None):
    m = momento or agora()
    candidatos = []
    for dia in (0, 1):
        base = (m + timedelta(days=dia)).replace(second=0, microsecond=0)
        for h, minuto in HORARIOS_CARROCA:
            candidatos.append(base.replace(hour=h, minute=minuto))
    for c in sorted(candidatos):
        if c > m:
            return c
    return None


# ---------------- lojas ----------------
def consumiveis_disponiveis(andar_max):
    """Poções são vendidas em qualquer andar; o que libera o tier é o progresso."""
    return {
        k: v for k, v in ITENS.items()
        if v["tipo"] == "consumivel" and v.get("andar_min", 1) <= andar_max
    }


def equipamentos_do_andar(andar):
    """Cada ferreiro só vende o equipamento do próprio andar."""
    return {
        k: v for k, v in ITENS.items()
        if v["tipo"] in ("arma", "armadura") and v.get("andar_min") == andar
    }


# ---------------- NPCs ----------------
NPCS = {
    1: [
        {"nome": "Elna", "titulo": "da Barraca Torta", "tipo": "mercador", "dialogo": "elna",
         "fala": "Poção é poção. Bebe rápido que o gosto passa."},
        {"nome": "Torv", "titulo": "o Ferreiro Aposentado", "tipo": "ferreiro", "dialogo": "torv",
         "fala": "Vamos para mais um dia na forja, isso por enquanto vai servir pra você."},
        {"nome": "Pip", "titulo": "o Menino que Conta", "tipo": "conversa", "dialogo": "pip",
         "fala": "Já contei os degraus até em cima. Deu um número que não cabe na boca."},
        {"nome": "Sera", "titulo": "a Taverneira", "tipo": "taverneiro", "dialogo": "sera",
         "fala": "Aqui ninguém pergunta o motivo do cansaço. Só cobra por ele."},
        {"nome": "Baldo", "titulo": "do Cata-Vento", "tipo": "encantador", "dialogo": "baldo",
         "fala": "O vento não escolhe onde bate. Eu só aprendi a prender um pedaço dele na sua lâmina."},
    ],
    2: [
        {"nome": "Irmã Vell", "titulo": "da Tenda de Musgo", "tipo": "mercador", "dialogo": "irma_vell",
         "fala": "Se a árvore repetir o que você falou, não responde. Elas aprendem."},
        {"nome": "O Lenhador", "titulo": "que não corta", "tipo": "conversa", "dialogo": "lenhador",
         "fala": "Machado é bom pra apontar. Cortar, aí já é briga."},
        {"nome": "Orin", "titulo": "da Árvore Torta", "tipo": "joalheiro", "dialogo": "orin",
         "fala": "Toda pedra que acho aqui já nasceu torta, que nem a árvore. Eu só ajudo a torcer certo."},
    ],
    3: [
        {"nome": "Doran", "titulo": "do Bote Furado", "tipo": "mercador", "dialogo": "doran",
         "fala": "Vendo por aqui porque o resto da minha loja tá dois metros abaixo."},
        {"nome": "Kesh", "titulo": "da Forja Submersa", "tipo": "ferreiro", "dialogo": "kesh",
         "fala": "Aço que já afundou uma vez não afunda de novo. É superstição, mas funciona."},
        {"nome": "Bramm", "titulo": "o Carroceiro", "tipo": "carroceiro", "dialogo": "bramm",
         "fala": "Passo quatro vezes por dia. Se você estiver aqui, sobe. Se não estiver, paciência."},
        {"nome": "Lira", "titulo": "a Que Escuta a Maré", "tipo": "encantador", "dialogo": "lira",
         "fala": "A maré fala baixo, mas fala sempre a mesma coisa duas vezes. Eu só repito pra sua arma."},
    ],
    4: [
        {"nome": "Ysra", "titulo": "da Caravana", "tipo": "mercador", "dialogo": "ysra",
         "fala": "Água eu não vendo. Água aqui é o que separa vivo de estátua."},
        {"nome": "O Homem de Sal", "titulo": "", "tipo": "conversa", "dialogo": "homem_de_sal",
         "fala": "..."},
        {"nome": "Kef", "titulo": "do Poço Seco", "tipo": "joalheiro", "dialogo": "kef",
         "fala": "O poço secou, mas o que ele guardava no fundo não. Eu só desço buscar."},
    ],
    5: [
        {"nome": "Tikk", "titulo": "do Trenó", "tipo": "mercador", "dialogo": "tikk",
         "fala": "Compra a poção grande. Não é venda, é conselho."},
        {"nome": "Hjalmar", "titulo": "o Sopro Frio", "tipo": "ferreiro", "dialogo": "hjalmar",
         "fala": "Têmpera no lago. A lâmina grita e depois nunca mais reclama."},
        {"nome": "A Pescadora", "titulo": "silenciosa", "tipo": "conversa", "dialogo": "pescadora",
         "fala": "(Ela aponta pro buraco no gelo. Tem algo olhando de volta.)"},
        {"nome": "Corin", "titulo": "do Casaco Longo", "tipo": "encantador", "dialogo": "corin",
         "fala": "Uso o casaco comprido porque o frio daqui gruda no encantamento antes de grudar em mim."},
    ],
    6: [
        {"nome": "Bico", "titulo": "do Vagão 7", "tipo": "mercador", "dialogo": "bico",
         "fala": "Lamparina acesa não quer dizer que tem gente. Quer dizer que teve."},
        {"nome": "Recado do Capataz", "titulo": "", "tipo": "conversa", "dialogo": "capataz",
         "fala": "«Turno cancelado. Não descer. Assinado: ninguém.»"},
        {"nome": "Mira", "titulo": "do Trilho Morto", "tipo": "joalheiro", "dialogo": "mira",
         "fala": "O trilho não leva a lugar nenhum mais. Mas as pedras que acho ao lado dele levam."},
    ],
    7: [
        {"nome": "Vane", "titulo": "da Tenda de Cinza", "tipo": "mercador", "dialogo": "vane",
         "fala": "Sacode a roupa antes de entrar. A cinza aqui pega carona."},
        {"nome": "Ignatia", "titulo": "a Bigorna Viva", "tipo": "ferreiro", "dialogo": "ignatia",
         "fala": "Não forjo com fogo. Forjo com o que sobrou dele."},
        # Os quatro mestres da ascensão (Step 4) -- todos no mesmo andar de
        # propósito, pra ninguém ascender antes de ninguém (ver
        # game_data.ANDAR_MESTRES e decisoes.md § Step 4). O Cavaleiro já
        # existia como NPC de conversa comum desde antes -- ganhou
        # "mestre_de" aqui, não foi recriado.
        {"nome": "O Cavaleiro", "titulo": "que espera", "tipo": "conversa", "dialogo": "cavaleiro",
         "mestre_de": "guerreiro",
         "fala": "Vou subir amanhã. Falo isso há bastante tempo."},
        {"nome": "Santo Augustiel", "titulo": "o Paciente", "tipo": "conversa", "dialogo": "augustiel",
         "mestre_de": "orador",
         "fala": "Chega quando chega. Eu aprendi a não contar as horas."},
        {"nome": "Gregory Merlin", "titulo": "o Quinto", "tipo": "conversa", "dialogo": "merlin",
         "mestre_de": "mago",
         "fala": "Sou o quinto a carregar esse nome. Os outros quatro não terminaram o que começaram."},
        {"nome": "Arvin", "titulo": "Mãos Rápidas", "tipo": "conversa", "dialogo": "arvin",
         "mestre_de": "ladino",
         "fala": "Suas mãos são rápidas? As minhas também. Vamos ver."},
        {"nome": "Talla", "titulo": "da Última Brasa", "tipo": "encantador", "dialogo": "talla",
         "fala": "Guardo uma brasa só, a última que não virou cinza. É o suficiente pra encantar o resto."},
    ],
    8: [
        {"nome": "Irmão Cael", "titulo": "", "tipo": "mercador", "dialogo": "irmao_cael",
         "fala": "Reze se quiser. Mas paga a poção primeiro."},
        {"nome": "A Corista", "titulo": "sem voz", "tipo": "conversa", "dialogo": "corista",
         "fala": "(Ela move os lábios. O som chega três segundos depois, de outro lugar.)"},
        {"nome": "Vesna", "titulo": "do Altar Lateral", "tipo": "joalheiro", "dialogo": "vesna",
         "fala": "O altar principal é pra rezar. O lateral, onde eu fico, é pra lapidar. Os dois pedem silêncio."},
    ],
    9: [
        {"nome": "Ori", "titulo": "do Balão", "tipo": "mercador", "dialogo": "ori",
         "fala": "Não olha pra baixo. Não por medo — é que não tem baixo."},
        {"nome": "Selen", "titulo": "a Última Forja", "tipo": "ferreiro", "dialogo": "selen",
         "fala": "O que eu faço aqui, ninguém faz mais acima. Escolhe com calma."},
        {"nome": "O Cartógrafo", "titulo": "do Vazio", "tipo": "conversa", "dialogo": "cartografo",
         "fala": "Mapeei os dez. O décimo primeiro se recusa a ficar no papel."},
        {"nome": "Astrea", "titulo": "Contadora de Estrelas", "tipo": "encantador", "dialogo": "astrea",
         "fala": "Cada estrela que conto daqui já morreu há tempos. O brilho que sobra é o que eu uso pra encantar."},
    ],
    10: [
        {"nome": "Eco de um Mercador", "titulo": "", "tipo": "mercador", "dialogo": "eco_mercador",
         "fala": "Eu já te vendi isso. Você já me pagou. Nós dois já esquecemos."},
        {"nome": "Eco de uma Taverneira", "titulo": "", "tipo": "taverneiro", "dialogo": "eco_taverneira",
         "fala": "Descansa. Não vai ajudar, mas descansa."},
        {"nome": "A Porta", "titulo": "", "tipo": "conversa", "dialogo": "porta",
         "fala": "(Não é um NPC. Mas responde quando você fala com ela.)"},
        {"nome": "Eco de uma Joalheira", "titulo": "", "tipo": "joalheiro", "dialogo": "eco_joalheira",
         "fala": "Já lapidei isso. Você já usou. Nós duas já esquecemos — só a pedra lembra."},
    ],

    # ---- acima do selo: só A Guia. Sem loja, ferreiro nem carroça de propósito
    # (bot.py bloqueia comércio pra andar > 10). "fala" abaixo é a abertura
    # mostrada sempre que se fala com ela — o menu (O que me espera/Sobre
    # você) é quem varia por andar/mortes, ver andares_altos.py ----
    11: [
        {"nome": "A Guia", "titulo": "", "tipo": "guia",
         "fala": "Ainda dá pra descer. Ninguém vai lembrar que você chegou até aqui."},
    ],
    12: [
        {"nome": "A Guia", "titulo": "", "tipo": "guia",
         "fala": "O trovão aqui não faz barulho. Você também vai parar de fazer, com o tempo."},
    ],
    13: [
        {"nome": "A Guia", "titulo": "", "tipo": "guia",
         "fala": "Branco é só a cor que sobra quando não tem mais nada pra ver. Volta antes de aprender isso."},
    ],
    14: [
        {"nome": "A Guia", "titulo": "", "tipo": "guia",
         "fala": "Calor sem fogo é o corpo avisando. Eu só estou repetindo o aviso."},
    ],
    15: [
        {"nome": "A Guia", "titulo": "", "tipo": "guia",
         "fala": "Essa cadeira não é sua. Não é de ninguém. Senta lá embaixo, onde as coisas ainda cabem."},
        # A porta atrás do trono (Step B, commit 2) -- "porta": True é o
        # marcador que bot.falar() usa pra desviar do fluxo comum de
        # conversa. Só responde de verdade (abre a escolha Ficar/Sair)
        # pra quem já venceu o chefe do andar 15 alguma vez
        # (db.vezes_derrotado_chefe) -- pra todo o resto, é só a fala
        # abaixo, via DialogoView normal. Ver decisoes.md § Step B.
        {"nome": "A Porta", "titulo": "atrás do trono", "tipo": "conversa", "dialogo": "porta_do_trono",
         "porta": True,
         "fala": "Madeira escura, num vão que não devia existir atrás do trono. Ela não se abre, não importa o quanto você empurre."},
    ],
    # ---- vilarejo (Step C) ----
    # O alquimista é a ÚNICA exceção comercial do vilarejo -- sem ferreiro,
    # sem mercador de equipamento, sem encantador (isso fica pras cidades
    # do step F). "tipo": "alquimista" é um tipo novo (ver comercio.py,
    # AlquimistaView) porque o catálogo dele não é andar-based feito o do
    # mercador -- é sempre os quatro elixires, ponto.
    mundo.VILAREJO: [
        {"nome": "Ren", "titulo": "o Alquimista de Beira de Estrada", "tipo": "alquimista", "dialogo": "ren",
         "fala": "Elixir de verdade não se compra na torre. Compra aqui, onde tem sol pra secar a erva."},
        {"nome": "Ohanna", "titulo": "da Taverna do Poço", "tipo": "taverneiro", "dialogo": "ohanna",
         "cerveja": True,
         "fala": "Descansa, come, bebe. Nessa ordem se quiser acordar."},
        # Commit 3 -- "as pessoas". Ivo é o gancho (o Herói saiu e foi pro
        # norte -- o primeiro sinal de que o jogador não é o primeiro);
        # Mira é o contraponto que a lore pede (a torre é abrigo, e quem
        # está dentro não sabe -- ela sabe e escolheu não entrar). Nenhum
        # dos dois entrega o inimigo maior -- isso ainda não foi decidido.
        {"nome": "Ivo", "titulo": "o Que Aponta pro Norte", "tipo": "conversa", "dialogo": "ivo",
         "fala": "Um saiu daqui, faz tempo. Foi pro norte. Nunca mais soube dele — mas também nunca soube de ninguém que tenha ido atrás."},
        {"nome": "Nara", "titulo": "a Que Não Entrou", "tipo": "conversa", "dialogo": "nara_vilarejo",
         "fala": "Vocês entram lá pensando que é desafio. Eu cresci vendo ela de fora. Sei pra que ela serve — e não é pra isso."},
    ],
    # ---- Costa Verde (Step F, commit 2) ----
    # Cidade de lore, decisão de desenho: NÃO VENDE NADA -- nenhum NPC daqui
    # tem "tipo" comercial (bot.comprar já recusa tudo fora de torre/vilarejo
    # sozinho, ver o `else` em bot.comprar; nada precisou mudar lá pra isso
    # valer). Suzu é o segundo elo da corrente que o Ivo (vilarejo, Step C)
    # começou -- ele disse que "alguém saiu e foi pro norte", ela VIU esse
    # alguém passar por aqui. Osamu é o contraponto que dá o tom da cidade:
    # gente que fala dos próprios mortos como quem fala do tempo, sem achar
    # estranho -- o oposto exato da torre, onde ninguém sabe que é abrigo.
    mundo.COSTA_VERDE: [
        {"nome": "Suzu", "titulo": "Guardiã do Sino Parado", "tipo": "conversa", "dialogo": "suzu",
         "fala": "Ele parou bem ali, onde a névoa não sobe. Não disse o nome — só perguntou se alguém aqui já tinha visto o que dorme atrás das montanhas."},
        {"nome": "Osamu", "titulo": "Que Serve Chá pro Avô", "tipo": "conversa", "dialogo": "osamu",
         "fala": "Meu avô gosta do chá mais forte de manhã. Ele não bebe mais, claro. Mas eu sirvo, do jeito que ele sempre gostou."},
    ],
}


def npcs_do_andar(andar):
    """A Entidade Sombria (Step D, commit 4) não mora em NPCS -- ela não
    tem andar fixo, muda todo dia com a incursão. Soma dinamicamente em
    vez de ficar em 15 entradas estáticas, uma por andar possível."""
    pessoas = list(NPCS.get(andar, []))
    if entidade_sombria.npc_presente(andar):
        pessoas.append(entidade_sombria.ENTIDADE_SOMBRIA)
    return pessoas


def ferreiro_do_andar(andar):
    for n in npcs_do_andar(andar):
        if n["tipo"] == "ferreiro":
            return n
    return None


def taverneiro_do_andar(andar):
    """Só existe nos andares 1 e 10 — ver decisoes.md § Taverna."""
    for n in npcs_do_andar(andar):
        if n["tipo"] == "taverneiro":
            return n
    return None


def guia_do_andar(andar):
    """Só existe nos andares 11-15 — ver decisoes.md § A Guia."""
    for n in npcs_do_andar(andar):
        if n["tipo"] == "guia":
            return n
    return None


def mestre_do_andar(andar, classe):
    """O NPC "mestre_de" == classe naquele andar, ou None -- hoje só existe
    no andar 7 (ver game_data.ANDAR_MESTRES), mas não hardcoda o andar
    aqui: se um mestre novo nascer noutro andar no futuro, isso funciona
    sem mudança. Ver mestres.py e decisoes.md § Step 4."""
    for n in npcs_do_andar(andar):
        if n.get("mestre_de") == classe:
            return n
    return None


def encontrar_npc(andar, texto):
    alvo = texto.lower().strip()
    if not alvo:
        return None
    for n in npcs_do_andar(andar):
        if alvo in n["nome"].lower() or (n["titulo"] and alvo in n["titulo"].lower()):
            return n
    return None


# ---------------- diálogo ----------------
def opcoes_do_dialogo(chave_npc, user_id):
    """Opções soltas (`opcoes`) aparecem sempre. Se o NPC tiver
    `opcoes_por_estado`, soma o bloco do estado atual da quest dele —
    'antes' (padrão, nenhuma quest existe ainda), 'durante' ou 'depois'.
    NPC sem quest, a maioria hoje, nunca chama estado_sidequest."""
    dado = DIALOGOS[chave_npc]
    opcoes = list(dado.get("opcoes", []))
    por_estado = dado.get("opcoes_por_estado")
    if por_estado:
        estado = db.estado_sidequest(user_id, dado["quest_id"])
        opcoes += por_estado.get(estado, [])
    return opcoes