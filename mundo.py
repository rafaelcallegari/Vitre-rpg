# mundo.py
# Onde o jogador está, além do andar -- Step B: o mundo deixa de ser só a
# torre. `jogadores.mundo` (migração 21, database.py) diz em que mundo o
# jogador está agora. Dentro da torre (TORRE, valor padrão -- ninguém dos
# jogadores existentes sente nada), `andar` continua mandando sozinho, sem
# mudança nenhuma. Fora (FORA), `andar` fica CONGELADO no que era quando
# saiu -- deixa de significar "onde o jogador está" e vira só "pra onde a
# escada devolve" (ver decisoes.md § Step B).
#
# Função pura, sem discord no topo -- qualquer módulo (bot.py, combate.py,
# dungeon.py) importa sem risco de ciclo.
import database as db
from andares_altos import ANDAR_ACIMA_DO_SELO

TORRE = "torre"
FORA = "fora"   # o alto da torre, do lado de fora da porta -- step C acrescenta o vilarejo


def na_torre(jogador):
    return jogador["mundo"] == TORRE


MENSAGEM_FORA_DA_TORRE = (
    "Você não está na torre agora — ficou pra trás, do outro lado da porta. "
    "Não tem caçada, chefe, dungeon nem ninguém de lá daqui. `rpg viajar 15` sobe a escada de volta."
)


async def exigir_torre(ctx, jogador):
    """Trava central pra todo comando que assume torre -- `rpg cacar`/
    `explorar`/`boss`/`party`/`dungeon`/`npcs`/`falar`. Recusa em
    personagem (a mesma frase ambiente pros seis, não erro de sistema);
    devolve True se pode seguir. Chame depois de `pegar_jogador`, igual
    a `travas.bloqueado`. Ver decisoes.md § Step B."""
    if na_torre(jogador):
        return True
    await ctx.send(MENSAGEM_FORA_DA_TORRE)
    return False


# ---------------- a porta atrás do trono (Step B, commit 2) ----------------
def ficar_na_torre(user_id):
    """Escolha "Ficar" -- exatamente o reset que a vitória do andar 15
    fazia sozinha antes deste cartão (ver combate.recompensar), só que
    agora é decisão do jogador, não automático."""
    db.atualizar_jogador(user_id, andar=ANDAR_ACIMA_DO_SELO, andar_max=ANDAR_ACIMA_DO_SELO)


def sair_pela_porta(user_id):
    """Escolha "Sair" -- `andar`/`andar_max` ficam exatamente como
    estavam (sempre 15, a vitória contra o chefe do topo já deixou eles
    lá) -- é pra onde a escada devolve (commit 3)."""
    db.atualizar_jogador(user_id, mundo=FORA)


def subir_a_escada(user_id):
    """A escada sobe de volta pro andar 15, sempre de graça -- sem ela o
    jogador fica preso do lado de fora pra sempre. `andar`/`andar_max` já
    são 15 (congelados desde que saiu), só `mundo` volta pra TORRE."""
    db.atualizar_jogador(user_id, mundo=TORRE)


# ---------------- a fala da Guia -- gatilho é VER, não VENCER (conserto) ----------------
# `vezes_derrotado_chefe` não serve de gatilho: pra quem já tinha zerado a
# torre antes deste pacote, esse número já estava gasto (>= 1 desde muito
# antes da porta existir) -- a mesa inteira, o público pra quem a cena foi
# escrita, nunca veria ela. Coluna própria (migração 22): "já viu a porta"
# é um evento novo, zerado pra TODO MUNDO no deploy, veterano ou não.
def ja_viu_a_porta(jogador):
    return bool(jogador["viu_porta_do_trono"])


def marcar_porta_vista(user_id):
    db.atualizar_jogador(user_id, viu_porta_do_trono=1)


# ---------------- o mirante (Step B, commit 3) ----------------
# Só isto existe do lado de fora por enquanto -- um único lugar, sem nome
# de destino nenhum pra viajar (as "três cidades" são só paisagem; step F
# é quem constrói elas de verdade). Texto puro aqui, sem discord.Embed --
# quem chama (bot.py, combate.py) monta o embed com a cor/rodapé que
# fizer sentido pro próprio contexto.
TITULO_MIRANTE = "O Mirante"
DESCRICAO_MIRANTE = (
    "Sol, nuvens, montanhas verdejantes até onde a vista alcança. Ao longe, três "
    "cidades — perto demais pra ignorar, longe demais pra chegar a pé. Uma escada "
    "desce logo atrás de você."
)
