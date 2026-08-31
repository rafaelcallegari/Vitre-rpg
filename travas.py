# travas.py
# Trava jogadores em luta de chefe pra impedir comando de texto durante o
# combate por turnos — a View controla os botões, mas o canal continuava
# aceitando `rpg comprar`/`rpg upar`/etc no meio da luta, o que anula o
# planejamento de recurso que é o ponto do turno. Não importa combate.py/
# bot.py (evita import circular): é só o registro e o check; combate.py e
# raide.py chamam travar_todos()/destravar()/destravar_todos() nos pontos
# certos do ciclo de vida da luta (ver decisoes.md).

import time

from discord.ext import commands

import dungeon

# registro em memória, de propósito: luta não sobrevive a restart do bot
# (View e estado da Luta são só RAM), então a trava também não deveria —
# uma trava sobrevivendo a restart soft-lockaria todo mundo que estava
# lutando quando o bot caiu.
_em_luta = {}   # user_id -> timestamp de quando entrou na luta

# rede de segurança: TIMEOUT_RODADA (combate.py) é 60s por rodada, e
# nenhuma luta realista passa perto de 20 rodadas. Bem acima disso pra só
# pegar o caso de uma View morrer por exceção sem passar pelo destravar()
# — não é o caminho normal de saída, é o último resort.
EXPIRACAO_SEGUNDOS = 20 * 60

MENSAGEM_BLOQUEIO = "⚔️ Você está numa luta de chefe agora — resolve isso primeiro (ou foge)."


class EmLutaDeChefe(commands.CheckFailure):
    """Levantado quando um comando travado é chamado durante luta de chefe."""


def travar_todos(user_ids):
    agora = time.time()
    for uid in user_ids:
        _em_luta[uid] = agora


def destravar(user_id):
    _em_luta.pop(user_id, None)


def destravar_todos(user_ids):
    for uid in user_ids:
        _em_luta.pop(uid, None)


def em_luta(user_id):
    """True se travado e a trava ainda não expirou. Expirada conta como
    livre e já limpa a entrada — cobre a View que morreu sem limpar."""
    inicio = _em_luta.get(user_id)
    if inicio is None:
        return False
    if time.time() - inicio > EXPIRACAO_SEGUNDOS:
        del _em_luta[user_id]
        return False
    return True


def fora_de_luta():
    """Check pra comandos inteiros (`@bot.command` + `@travas.fora_de_luta()`
    logo abaixo). Pra ações dentro de um comando com sub-ações (ex.: `rpg
    guilda depositar`, que divide o mesmo `@bot.command` com sub-ações
    somente-leitura que não precisam travar), use bloqueado() direto."""
    async def predicado(ctx):
        if em_luta(ctx.author.id):
            raise EmLutaDeChefe()
        return True
    return commands.check(predicado)


async def bloqueado(ctx):
    """Pra sub-ações dentro de um comando com dispatch manual (guildas.py).
    Manda a mensagem e devolve True (bloqueado) se o autor está em luta —
    quem chama só precisa dar `return` quando vier True."""
    if em_luta(ctx.author.id):
        await ctx.send(MENSAGEM_BLOQUEIO)
        return True
    return False


# ---------------------------------------------------------------- manutenção
# Janela do dono que bloqueia abrir luta NOVA (`rpg boss`/`rpg party`/`rpg
# raide`) sem interromper luta em andamento — mesmo raciocínio de estado em
# memória do resto do módulo: reiniciar o bot já destrava tudo sozinho, e é
# esse o comportamento certo depois de um restart (ver decisoes.md § Modo
# manutenção).
_manutencao_fim = None          # timestamp epoch de quando a janela acaba, ou None se desligada
_manutencao_owner_id = None     # quem ligou — pra onde manda o DM de "pode reiniciar"
_manutencao_notificada = False  # já mandou o DM desta janela?


class ManutencaoAtiva(commands.CheckFailure):
    """Levantado quando `rpg boss`/`rpg party`/`rpg raide` é chamado com a
    janela de manutenção ligada. `restante_seg` vai pra mensagem de recusa —
    negar sem dizer quanto falta deixa quem tentou sem saber se tenta nem
    daqui a 1 minuto ou daqui a 1 hora."""

    def __init__(self, restante_seg):
        self.restante_seg = restante_seg


def ligar_manutencao(minutos, owner_id):
    global _manutencao_fim, _manutencao_owner_id, _manutencao_notificada
    _manutencao_fim = time.time() + minutos * 60
    _manutencao_owner_id = owner_id
    _manutencao_notificada = False


def desligar_manutencao():
    global _manutencao_fim
    _manutencao_fim = None


def manutencao_ativa():
    """True se a janela está ligada e ainda não passou do prazo. Expirada
    conta como desligada e já limpa o estado — mesmo padrão de em_luta()."""
    global _manutencao_fim
    if _manutencao_fim is None:
        return False
    if time.time() >= _manutencao_fim:
        _manutencao_fim = None
        return False
    return True


def manutencao_restante():
    if not manutencao_ativa():
        return 0
    return _manutencao_fim - time.time()


def manutencao_owner_id():
    return _manutencao_owner_id


def manutencao_notificada():
    return _manutencao_notificada


def marcar_manutencao_notificada():
    global _manutencao_notificada
    _manutencao_notificada = True


def ninguem_em_luta():
    """True se não há ninguém travado por luta agora — usado pra saber se a
    manutenção já pode avisar o dono que dá pra reiniciar."""
    return len(_em_luta) == 0


def fora_de_manutencao():
    """Check pra comando que ABRE luta nova — `rpg boss`/`rpg party`/`rpg
    raide`. Luta já em andamento não passa por aqui de novo (o motor de
    combate não rechama o comando), só a abertura de uma luta nova é
    barrada."""
    async def predicado(ctx):
        if manutencao_ativa():
            raise ManutencaoAtiva(manutencao_restante())
        return True
    return commands.check(predicado)


# ---------------------------------------------------------------- dungeon
class DungeonAberta(commands.CheckFailure):
    """Levantado quando `rpg viajar` é chamado com uma run de dungeon aberta."""


MENSAGEM_DUNGEON_ABERTA = (
    "🕳️ Você está dentro da dungeon — `rpg dungeon sair` primeiro (sem penalidade), ou termine a run."
)


def fora_de_dungeon():
    """Check pra `rpg viajar` -- viajar e dungeon não coexistem, senão dava
    pra sair do andar 9 no meio de uma run sem fechar ela. Ao contrário de
    em_luta() acima, a run SOBREVIVE a restart (persiste em dungeon_run, não
    neste módulo) -- então esse check lê o banco pela função de dungeon.py,
    não um dict em memória daqui. Ver decisoes.md § Dungeon (fatia 1)."""
    async def predicado(ctx):
        if dungeon.tem_run_aberta(ctx.author.id):
            raise DungeonAberta()
        return True
    return commands.check(predicado)


def fmt_restante(segundos):
    segundos = int(segundos)
    if segundos < 60:
        return f"{segundos}s"
    minutos, segundos = divmod(segundos, 60)
    return f"{minutos}m {segundos}s"
