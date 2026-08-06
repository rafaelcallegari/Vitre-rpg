# npcs.py
# NPCs, lojas por andar e sistema de viagem.
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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
        {"nome": "Elna", "titulo": "da Barraca Torta", "tipo": "mercador",
         "fala": "Poção é poção. Bebe rápido que o gosto passa."},
        {"nome": "Torv", "titulo": "o Ferreiro Aposentado", "tipo": "ferreiro",
         "fala": "Aposentado uma ova. Ninguém mais desce pra me render."},
        {"nome": "Pip", "titulo": "o Menino que Conta", "tipo": "conversa",
         "fala": "Já contei os degraus até em cima. Deu um número que não cabe na boca."},
    ],
    2: [
        {"nome": "Irmã Vell", "titulo": "da Tenda de Musgo", "tipo": "mercador",
         "fala": "Se a árvore repetir o que você falou, não responde. Elas aprendem."},
        {"nome": "O Lenhador", "titulo": "que não corta", "tipo": "conversa",
         "fala": "Machado é bom pra apontar. Cortar, aí já é briga."},
    ],
    3: [
        {"nome": "Doran", "titulo": "do Bote Furado", "tipo": "mercador",
         "fala": "Vendo por aqui porque o resto da minha loja tá dois metros abaixo."},
        {"nome": "Kesh", "titulo": "da Forja Submersa", "tipo": "ferreiro",
         "fala": "Aço que já afundou uma vez não afunda de novo. É superstição, mas funciona."},
        {"nome": "Bramm", "titulo": "o Carroceiro", "tipo": "carroceiro",
         "fala": "Passo três vezes por dia. Se você estiver aqui, sobe. Se não estiver, paciência."},
    ],
    4: [
        {"nome": "Ysra", "titulo": "da Caravana", "tipo": "mercador",
         "fala": "Água eu não vendo. Água aqui é o que separa vivo de estátua."},
        {"nome": "O Homem de Sal", "titulo": "", "tipo": "conversa",
         "fala": "..."},
    ],
    5: [
        {"nome": "Tikk", "titulo": "do Trenó", "tipo": "mercador",
         "fala": "Compra a poção grande. Não é venda, é conselho."},
        {"nome": "Hjalmar", "titulo": "o Sopro Frio", "tipo": "ferreiro",
         "fala": "Têmpera no lago. A lâmina grita e depois nunca mais reclama."},
        {"nome": "A Pescadora", "titulo": "silenciosa", "tipo": "conversa",
         "fala": "(Ela aponta pro buraco no gelo. Tem algo olhando de volta.)"},
    ],
    6: [
        {"nome": "Bico", "titulo": "do Vagão 7", "tipo": "mercador",
         "fala": "Lamparina acesa não quer dizer que tem gente. Quer dizer que teve."},
        {"nome": "Recado do Capataz", "titulo": "", "tipo": "conversa",
         "fala": "«Turno cancelado. Não descer. Assinado: ninguém.»"},
    ],
    7: [
        {"nome": "Vane", "titulo": "da Tenda de Cinza", "tipo": "mercador",
         "fala": "Sacode a roupa antes de entrar. A cinza aqui pega carona."},
        {"nome": "Ignatia", "titulo": "a Bigorna Viva", "tipo": "ferreiro",
         "fala": "Não forjo com fogo. Forjo com o que sobrou dele."},
        {"nome": "O Cavaleiro", "titulo": "que espera", "tipo": "conversa",
         "fala": "Vou subir amanhã. Falo isso há bastante tempo."},
    ],
    8: [
        {"nome": "Irmão Cael", "titulo": "", "tipo": "mercador",
         "fala": "Reze se quiser. Mas paga a poção primeiro."},
        {"nome": "A Corista", "titulo": "sem voz", "tipo": "conversa",
         "fala": "(Ela move os lábios. O som chega três segundos depois, de outro lugar.)"},
    ],
    9: [
        {"nome": "Ori", "titulo": "do Balão", "tipo": "mercador",
         "fala": "Não olha pra baixo. Não por medo — é que não tem baixo."},
        {"nome": "Selen", "titulo": "a Última Forja", "tipo": "ferreiro",
         "fala": "O que eu faço aqui, ninguém faz mais acima. Escolhe com calma."},
        {"nome": "O Cartógrafo", "titulo": "do Vazio", "tipo": "conversa",
         "fala": "Mapeei os dez. O décimo primeiro se recusa a ficar no papel."},
    ],
    10: [
        {"nome": "Eco de um Mercador", "titulo": "", "tipo": "mercador",
         "fala": "Eu já te vendi isso. Você já me pagou. Nós dois já esquecemos."},
        {"nome": "A Porta", "titulo": "", "tipo": "conversa",
         "fala": "(Não é um NPC. Mas responde quando você fala com ela.)"},
    ],
}


def npcs_do_andar(andar):
    return NPCS.get(andar, [])


def ferreiro_do_andar(andar):
    for n in npcs_do_andar(andar):
        if n["tipo"] == "ferreiro":
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