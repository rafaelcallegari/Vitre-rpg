# mundo.py
# Onde o jogador está, além do andar -- Step B: o mundo deixa de ser só a
# torre. `jogadores.mundo` (migração 21, database.py) diz em que mundo o
# jogador está agora. Dentro da torre (TORRE, valor padrão -- ninguém dos
# jogadores existentes sente nada), `andar` continua mandando sozinho, sem
# mudança nenhuma. Fora, `andar` fica CONGELADO no que era quando saiu (o
# único jeito de sair é a porta do andar 15) -- deixa de significar "onde o
# jogador está" e vira só "pra onde a escada devolve" (ver decisoes.md §
# Step B); `mundo` é quem diz onde o jogador está de verdade lá fora.
#
# Step C: "fora" deixou de ser um balde só (o Mirante era o único lugar) --
# agora `mundo` guarda o NOME do lugar (torre/mirante/vilarejo, cidades no
# step F). "A estrutura de lugares nomeados nasceu no step B... aqui ela
# ganha o segundo" -- é por isso que existe `LOCAIS_FORA` abaixo, em vez de
# cada lugar novo ganhar seu próprio módulo de constantes soltas.
#
# Função pura, sem discord no topo -- qualquer módulo (bot.py, combate.py,
# dungeon.py) importa sem risco de ciclo.
import database as db
import game_data
from andares_altos import ANDAR_ACIMA_DO_SELO

TORRE = "torre"
MIRANTE = "mirante"     # o alto da torre, do lado de fora da porta
VILAREJO = "vilarejo"   # ao pé da escada que desce do Mirante -- Step C


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
    lá) -- é pra onde a escada devolve. A porta sempre dá no Mirante --
    é o único lugar que fica direto atrás dela."""
    db.atualizar_jogador(user_id, mundo=MIRANTE)


def subir_a_escada(user_id):
    """A escada do Mirante sobe de volta pro andar 15, sempre de graça --
    sem ela o jogador fica preso do lado de fora pra sempre. `andar`/
    `andar_max` já são 15 (congelados desde que saiu), só `mundo` volta
    pra TORRE."""
    db.atualizar_jogador(user_id, mundo=TORRE)


def descer_para_o_vilarejo(user_id):
    """A mesma escada do Mirante desce pro vilarejo (Step C) -- outra
    perna da mesma estrutura que leva de volta pro andar 15."""
    db.atualizar_jogador(user_id, mundo=VILAREJO)


def subir_para_o_mirante(user_id):
    """Do vilarejo, a escada só sobe de volta pro Mirante -- pra chegar
    na torre a partir daqui, primeiro sobe aqui, depois usa a porta."""
    db.atualizar_jogador(user_id, mundo=MIRANTE)


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


# ---------------- os lugares fora da torre ----------------
# Nasceu no Step B com o Mirante sozinho; o Step C acrescenta o vilarejo e
# é aqui que a estrutura precisa aguentar o segundo lugar antes das duas
# cidades do step F (ver decisoes.md § Step C). Cada entrada é só dado --
# nome, cor, descrição -- sem discord.Embed nenhum aqui; quem chama (bot.py,
# combate.py) monta o embed com o que fizer sentido pro próprio contexto.
# `npcs.NPCS` usa a MESMA chave (string) pra guardar quem mora em cada
# lugar -- não precisa de estrutura paralela nenhuma pra isso.
LOCAIS_FORA = {
    MIRANTE: {
        "nome": "O Mirante",
        "cor": 0x87CEEB,
        "descricao": (
            "Sol, nuvens, montanhas verdejantes até onde a vista alcança. Ao longe, três "
            "cidades — perto demais pra ignorar, longe demais pra chegar a pé. Uma escada "
            "desce logo atrás de você."
        ),
    },
    VILAREJO: {
        "nome": "Vilarejo ao Pé da Escada",
        "cor": 0x8FBC5A,
        "descricao": (
            "Pequeno, gente vivendo — depois da torre inteira, é a diferença de respiro que "
            "chama atenção primeiro. Aqui tem sol de verdade, não o que passa pelas frestas de "
            "andar nenhum. Uma escada sobe de volta pro Mirante."
        ),
    },
}

# título/descrição de compatibilidade -- Step B chamava só de "o Mirante";
# mantidos porque _viajar_fora (bot.py) e a escolha "Sair" da porta
# (combate.py) ainda leem direto daqui.
TITULO_MIRANTE = LOCAIS_FORA[MIRANTE]["nome"]
DESCRICAO_MIRANTE = LOCAIS_FORA[MIRANTE]["descricao"]


def chave_do_lugar(jogador):
    """A chave que `npcs.NPCS` usa pra achar quem mora onde o jogador
    está -- o número do andar dentro da torre, o nome do lugar fora
    dela. Mesma chave pros dois mundos, pra `npcs.npcs_do_andar` (e
    companhia) não precisar saber a diferença."""
    return jogador["andar"] if na_torre(jogador) else jogador["mundo"]


def info_do_lugar(jogador):
    """(chave, nome, cor) do lugar atual -- uniforme pra torre e fora,
    pra quem monta embed (bot.py, comercio.py) não precisar de um `if
    na_torre` próprio toda vez."""
    chave = chave_do_lugar(jogador)
    if na_torre(jogador):
        dados = game_data.ANDARES[chave]
    else:
        dados = LOCAIS_FORA[chave]
    return chave, dados["nome"], dados["cor"]
