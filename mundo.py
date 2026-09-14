# mundo.py
# Onde o jogador está, além do andar -- Step B: o mundo deixa de ser só a
# torre. `jogadores.mundo` (migração 21, database.py) diz em que mundo o
# jogador está agora. Dentro da torre (TORRE, valor padrão -- ninguém dos
# jogadores existentes sente nada), `andar` continua mandando sozinho, sem
# mudança nenhuma. Fora (FORA), `andar` fica CONGELADO no que era quando
# saiu -- deixa de significar "onde o jogador está" e vira só "pra onde a
# escada devolve" (ver decisoes.md § Step B).
#
# Função pura, sem discord/database no topo -- mesmo padrão de
# andares_altos.py -- qualquer módulo (bot.py, combate.py, dungeon.py)
# importa sem risco de ciclo.

TORRE = "torre"
FORA = "fora"   # o alto da torre, do lado de fora da porta -- step C acrescenta o vilarejo


def na_torre(jogador):
    return jogador["mundo"] == TORRE


MENSAGEM_FORA_DA_TORRE = (
    "Você não está na torre agora — ficou pra trás, do outro lado da porta. "
    "Não tem caçada, chefe, dungeon nem ninguém de lá daqui. A escada desce de volta quando quiser."
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
