# bot.py
import asyncio
import os
import random
import time
import unicodedata

import discord
from discord.ext import commands
from dotenv import load_dotenv

import andares_altos
import atributos as at
import database as db
import dialogos
import habilidades as hab
import paginacao
import pronomes
import travas
from game_data import (
    ITENS, ANDARES, ANDAR_MAXIMO, TITULOS, CLASSES, ASCENSOES, xp_necessario,
)
from npcs import (
    ANDAR_DESBLOQUEIA_CARROCA, HORARIOS_CARROCA, JANELA_CARROCA_MIN,
    agora, carroca_ativa, proxima_carroca, custo_viagem,
    consumiveis_disponiveis, equipamentos_do_andar,
    npcs_do_andar, ferreiro_do_andar, taverneiro_do_andar, guia_do_andar, encontrar_npc,
    opcoes_do_dialogo,
)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

PREFIXOS = ("rpg ", "rpg")

COOLDOWN_CACAR = 60
COOLDOWN_EXPLORAR = 180
COOLDOWN_BOSS = 900
COOLDOWN_DESCANSAR = 2 * 60 * 60
CUSTO_DESCANSAR = 150

GUIA_A_CADA_ACOES = 3   # acima do Selo, a Guia comenta a cada N comandos fora de luta

# `rpg viajar` nunca alcança acima disso, mesmo com andar_max maior — andar
# 12+ só se chega lutando pra cima a partir do 11, nunca de teleporte. Ver
# decisoes.md § Teto de viajar acima do Selo.
LIMITE_VIAJAR = andares_altos.ANDAR_ACIMA_DO_SELO + 1

ICONES_NPC = {"mercador": "🧺", "ferreiro": "🔨", "carroceiro": "🐎", "conversa": "💬", "taverneiro": "🍺", "guia": "🕯️"}

# categoria onde `rpg priv` cria as salas. Se não existir, o bot cria.
CATEGORIA_SALAS = "Torre — Salas"


def obter_prefixo(bot, message):
    conteudo = message.content.lower()
    for p in PREFIXOS:
        if conteudo.startswith(p):
            return message.content[:len(p)]
    return commands.when_mentioned(bot, message)


intents = discord.Intents.default()
intents.message_content = True
intents.members = True   # guildas precisam resolver membros/cargos — liga "Server Members Intent" no portal

bot = commands.Bot(command_prefix=obter_prefixo, intents=intents, case_insensitive=True)
bot.remove_command("help")


# ==================== helpers ====================
def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto.lower().strip())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def encontrar_item(texto, chaves_validas=None):
    alvo = normalizar(texto)
    if not alvo:
        return None
    fonte = list(chaves_validas) if chaves_validas is not None else list(ITENS.keys())
    for k in fonte:
        if normalizar(k) == alvo or normalizar(ITENS[k]["nome"]) == alvo:
            return k
    for k in fonte:
        if alvo in normalizar(k) or alvo in normalizar(ITENS[k]["nome"]):
            return k
    return None


def encontrar_classe(texto):
    alvo = normalizar(texto)
    if not alvo:
        return None
    for k, dados in CLASSES.items():
        if normalizar(k) == alvo or normalizar(dados["nome"]) == alvo:
            return k
    for k, dados in CLASSES.items():
        if alvo in normalizar(dados["nome"]):
            return k
    return None


def encontrar_titulo(texto, chaves_validas):
    alvo = normalizar(texto)
    if not alvo:
        return None
    for k in chaves_validas:
        if normalizar(k) == alvo or normalizar(TITULOS[k]["nome"]) == alvo:
            return k
    for k in chaves_validas:
        if alvo in normalizar(TITULOS[k]["nome"]):
            return k
    return None


def a_venda(itens):
    """Tira do balcão tudo que é exclusivo de craft."""
    return {k: v for k, v in itens.items() if v.get("loja", True)}


def descricao_cura(dado):
    """Consumível pode curar HP ou restaurar mana, cada um fixo ou por porcentagem."""
    if "cura_pct" in dado:
        return f"cura {int(dado['cura_pct'] * 100)}% da vida"
    if "cura" in dado:
        return f"cura {dado['cura']}"
    if "mana_pct" in dado:
        return f"restaura {int(dado['mana_pct'] * 100)}% da mana"
    return f"restaura {dado.get('mana', 0)} de mana"


def nome_de_canal(membro):
    """Nome valido de canal a partir do apelido: minusculo, sem acento, sem espaco."""
    base = normalizar(membro.display_name)
    limpo = "".join(c if c.isalnum() else "-" for c in base).strip("-")
    while "--" in limpo:
        limpo = limpo.replace("--", "-")
    return f"torre-{limpo[:80]}" if limpo else f"torre-{membro.id}"


def separar_quantidade(texto):
    partes = texto.strip().rsplit(" ", 1)
    if len(partes) == 2 and partes[1].isdigit():
        return partes[0].strip(), max(1, int(partes[1]))
    return texto.strip(), 1


def com_bonus_upgrade(item_dado, item_chave, user_id, campo):
    """Copia o item aplicando +12% no atk/def por nivel de melhoria (+1/+2)."""
    if not item_chave or campo not in item_dado:
        return item_dado
    nivel = db.get_upgrade(user_id, item_chave)
    if not nivel:
        return item_dado
    item_dado = dict(item_dado)
    item_dado[campo] = int(item_dado[campo] * (1 + 0.12 * nivel))
    return item_dado


def bonus_atributo_equipamento(*pecas):
    """Soma o bônus de atributo de qualquer peça equipada que declare
    "atributo"+"bonus" — anel, colar, e agora as armas elementais dos
    andares 11+ também. Não passa por com_bonus_upgrade de propósito:
    `rpg melhorar` só mexe em atk/def, nunca nesse bônus."""
    bonus = {}
    for peca in pecas:
        if peca and "atributo" in peca and "bonus" in peca:
            bonus[peca["atributo"]] = bonus.get(peca["atributo"], 0) + peca["bonus"]
    return bonus


def stats(j):
    arma = com_bonus_upgrade(ITENS.get(j["arma"], {}), j["arma"], j["user_id"], "atk")
    armadura = com_bonus_upgrade(ITENS.get(j["armadura"], {}), j["armadura"], j["user_id"], "def")
    anel = ITENS.get(j["anel"], {})
    colar = ITENS.get(j["colar"], {})
    atribs_base = at.extrair(j)
    bonus = bonus_atributo_equipamento(arma, anel, colar)
    atribs = {k: atribs_base[k] + bonus.get(k, 0) for k in atribs_base}
    s = at.ficha(j["nivel"], atribs, arma, armadura, j["classe"])
    s["atribs"] = atribs
    return s


def hp_depois_do_nivel(hp_atual, nivel_novo, subiu, atribs):
    """Crescimento por nivel + cura parcial. Nunca passa do teto."""
    hp_max = at.hp_maximo(nivel_novo, atribs["constituicao"])
    if not subiu:
        return min(max(0, hp_atual), hp_max)
    crescimento = at.HP_POR_NIVEL * subiu
    cura = int(hp_max * at.CURA_LEVEL_UP)
    return min(hp_max, max(0, hp_atual) + crescimento + cura)


def fmt_tempo(segundos):
    segundos = int(segundos)
    if segundos < 60:
        return f"{segundos}s"
    if segundos < 3600:
        return f"{segundos // 60}m {segundos % 60}s"
    return f"{segundos // 3600}h {(segundos % 3600) // 60}m"


def barra_hp(atual, maximo, tamanho=12):
    atual = max(0, atual)
    cheio = int(tamanho * atual / maximo) if maximo else 0
    return "█" * cheio + "░" * (tamanho - cheio)


def calcular_dano(atk, defesa, critico=at.CRITICO_BASE):
    """Devolve (dano, foi_critico) — o booleano importa pra Fúria do Guerreiro."""
    bruto = atk * random.uniform(0.85, 1.15)
    foi_critico = random.random() < critico
    if foi_critico:
        bruto *= at.MULTIPLICADOR_CRITICO
    return at.aplicar_defesa(bruto, defesa), foi_critico


def simular_combate(s, hp, mob, andar_num):
    hp_mob = mob["hp"]
    des = s["atribs"]["destreza"]
    des_mob = at.destreza_monstro(andar_num)
    log = []

    if random.random() >= at.chance_iniciativa(des, des_mob):
        dm, _ = calcular_dano(mob["atk"], s["def"])
        hp -= dm
        log.append(f"O inimigo é mais rápido e abre com **{dm}**.")
        if hp <= 0:
            return hp, False, log[-4:]

    for _ in range(60):
        d, _ = calcular_dano(s["atk"], mob["def"], s["critico"])
        hp_mob -= d
        if hp_mob <= 0:
            log.append(f"Você acerta **{d}** e derruba o alvo.")
            return hp, True, log[-4:]
        if random.random() < at.chance_esquiva(des, des_mob):
            log.append(f"Você **{d}** ▸ esquivou do contra-ataque")
            continue
        dm, _ = calcular_dano(mob["atk"], s["def"])
        hp -= dm
        log.append(f"Você **{d}** ▸ inimigo **{dm}**")
        if hp <= 0:
            return hp, False, log[-4:]
    return hp, False, log[-4:]


def aplicar_xp(j, ganho):
    nivel, xp = j["nivel"], j["xp"] + ganho
    subiu = 0
    while xp >= xp_necessario(nivel):
        xp -= xp_necessario(nivel)
        nivel += 1
        subiu += 1
    return nivel, xp, subiu


def pontos_por_subir(j, subiu):
    return int(j["pontos"] or 0) + at.PONTOS_POR_NIVEL * subiu


def rolar_drops(mob):
    return [item for item, chance in mob.get("drops", []) if random.random() < chance]


def aplicar_regeneracao(j):
    """Devolve o jogador com o HP e a mana que recuperou parado. Só grava o que mudou."""
    s = stats(j)
    agora_ts = time.time()
    campos = {}
    novo_hp = at.hp_regenerado(j["hp"], s["hp_max"], j["hp_em"], j["combate_em"], agora_ts)
    if novo_hp != j["hp"]:
        campos["hp"] = novo_hp
        j["hp"] = novo_hp
        j["hp_em"] = agora_ts
    nova_mana = at.mana_regenerada(j["mana"], s["mana_max"], j["mana_em"], j["combate_em"], agora_ts)
    if nova_mana != j["mana"]:
        campos["mana"] = nova_mana
        j["mana"] = nova_mana
        j["mana_em"] = agora_ts
    if campos:
        db.atualizar_jogador(j["user_id"], **campos)
    return j


async def pegar_jogador(ctx):
    j = db.get_jogador(ctx.author.id)
    if not j:
        await ctx.send("Você ainda não entrou na torre. Manda `rpg comecar`.")
        return None
    return aplicar_regeneracao(j)


async def bloqueado_por_cooldown(ctx, comando, segundos):
    restante = db.checar_cooldown(ctx.author.id, comando)
    if restante > 0:
        await ctx.send(f"⏳ `rpg {comando}` volta em **{fmt_tempo(restante)}**.")
        return True
    db.set_cooldown(ctx.author.id, comando, segundos)
    db.marcar_combate(ctx.author.id)  # entrou em combate: a regeneração pausa
    return False


def processar_morte(j, s):
    """Penalidade normal (20% das moedas, volta com 30% do HP) + reconquista:
    morrer acima do andar 10 zera andar_max pra 10 — o andar 11+ inteiro
    precisa ser reconquistado do zero. `chefes_derrotados` NÃO zera aqui —
    a torre esquece onde o jogador estava, nunca quem ele matou (ver
    decisoes.md § Morte e reconquista / Roguelike acima do Selo)."""
    perda = int(j["moedas"] * 0.20)
    campos = {
        "hp": int(s["hp_max"] * 0.3),
        "moedas": j["moedas"] - perda,
        "mortes": j["mortes"] + 1,
    }
    if j["andar"] > andares_altos.ANDAR_ACIMA_DO_SELO:
        campos["andar"] = andares_altos.ANDAR_ACIMA_DO_SELO
        campos["andar_max"] = andares_altos.ANDAR_ACIMA_DO_SELO
    db.atualizar_jogador(j["user_id"], **campos)
    return perda


async def a_processar_morte(*args, **kwargs):
    return await asyncio.to_thread(processar_morte, *args, **kwargs)


def conheceu_bramm(j):
    return j["andar_max"] >= ANDAR_DESBLOQUEIA_CARROCA


# ==================== eventos ====================
@bot.event
async def on_ready():
    db.init_db()
    agenda.iniciar()
    print(f"Online como {bot.user} — prefixo: rpg")


@bot.event
async def on_command_error(ctx, erro):
    if isinstance(erro, commands.CommandNotFound):
        return
    if isinstance(erro, travas.EmLutaDeChefe):
        await ctx.send(travas.MENSAGEM_BLOQUEIO)
        return
    if isinstance(erro, commands.BadArgument):
        await ctx.send("Não entendi os argumentos. Confere `rpg ajuda`.")
        return
    # Caso não mapeado (ex.: "database is locked"): sem isso o traceback ia
    # só pro console e o jogador achava que o bot travou e repetia o comando.
    # `raise erro` continua depois do send — é o que já manda o traceback
    # completo pro console via on_error padrão do discord.py.
    await ctx.send("🗼 A Torre engasgou processando esse comando. Tenta de novo em alguns segundos.")
    raise erro


@bot.after_invoke
async def falar_guia_acima_do_selo(ctx):
    """A cada GUIA_A_CADA_ACOES comandos executados enquanto o jogador está
    acima do Selo, a Guia comenta — só fora de luta de chefe, porque os
    cliques de botão do PainelLuta são interações do discord.ui, não passam
    por comando nenhum (nem por aqui). Ver decisoes.md § A Guia."""
    if ctx.command_failed:
        return
    j = db.get_jogador(ctx.author.id)
    if not j or j["andar"] <= andares_altos.ANDAR_ACIMA_DO_SELO:
        return
    acoes = (j["acoes_andar_alto"] or 0) + 1
    if acoes < GUIA_A_CADA_ACOES:
        db.atualizar_jogador(ctx.author.id, acoes_andar_alto=acoes)
        return
    db.atualizar_jogador(ctx.author.id, acoes_andar_alto=0)
    fala = andares_altos.fala_da_guia(j["andar"], j["mortes"])
    if fala:
        await ctx.send(f"🕯️ *A Guia:* \"{fala}\"")


# ==================== progressão ====================
@bot.command(name="comecar", aliases=["start", "iniciar"])
async def comecar(ctx):
    if db.get_jogador(ctx.author.id):
        await ctx.send("Você já está na torre. Manda `rpg perfil`.")
        return
    db.criar_jogador(ctx.author.id, ctx.author.display_name)
    db.add_item(ctx.author.id, "pocao_p", 3)
    e = discord.Embed(
        title="Você acordou no 1º andar",
        description=(
            "A porta atrás de você não abre mais.\n\n"
            "Dez andares acima existe um selo. Cada andar tem um chefe, e cada chefe "
            "guarda a escada.\n\n"
            "Comece com `rpg cacar`. Fale com quem mora aqui: `rpg npcs`."
        ),
        color=ANDARES[1]["cor"],
    )
    e.add_field(name="Você recebeu", value="🧪 Poção Pequena x3", inline=False)
    e.add_field(
        name="Atributos",
        value=(
            f"Você começa com {at.BASE} em cada um. A cada nível vêm "
            f"**{at.PONTOS_POR_NIVEL} pontos** para distribuir — `rpg status`."
        ),
        inline=False,
    )
    e.set_footer(text="A lista completa de comandos vem logo abaixo.")
    await ctx.send(embed=e)
    await ctx.send(embed=embed_ajuda())


@bot.command(name="perfil", aliases=["profile", "p", "eu"])
async def perfil(ctx, membro: discord.Member = None):
    alvo = membro or ctx.author
    j = db.get_jogador(alvo.id)
    if not j:
        await ctx.send("Esse jogador ainda não entrou na torre.")
        return
    s = stats(j)
    andar = ANDARES[j["andar"]]
    titulo_dados = TITULOS.get(j["titulo"])
    nome_exibido = (
        f"{titulo_dados['emoji']} {titulo_dados['nome']} — {j['nome']}"
        if titulo_dados else j["nome"]
    )
    e = discord.Embed(title=nome_exibido, color=andar["cor"])
    e.add_field(name="Está em", value=f"**Andar {j['andar']}** — {andar['nome']}", inline=True)
    e.add_field(name="Nível", value=f"**{j['nivel']}**", inline=True)
    e.add_field(name="XP", value=f"{j['xp']}/{xp_necessario(j['nivel'])}", inline=True)
    hp_texto = f"{barra_hp(j['hp'], s['hp_max'])} {max(0, j['hp'])}/{s['hp_max']}"
    if j["hp"] < int(s["hp_max"] * at.REGEN_TETO):
        espera = at.segundos_para_regenerar(
            j["hp"], s["hp_max"], j["hp_em"], j["combate_em"], time.time()
        )
        hp_texto += (
            "\n*regenerando enquanto você não luta*" if espera == 0
            else f"\n*volta a regenerar em {fmt_tempo(espera)} de descanso*"
        )
    e.add_field(name="HP", value=hp_texto, inline=False)
    mana_texto = f"{max(0, j['mana'])}/{s['mana_max']}"
    if j["mana"] < s["mana_max"]:
        espera_mana = at.segundos_para_regenerar_mana(
            j["mana"], s["mana_max"], j["mana_em"], j["combate_em"], time.time()
        )
        mana_texto += (
            "\n*regenerando enquanto você não luta*" if espera_mana == 0
            else f"\n*volta a regenerar em {fmt_tempo(espera_mana)} de descanso*"
        )
    e.add_field(name="Mana", value=mana_texto, inline=False)
    classe_dados = CLASSES.get(j["classe"])
    e.add_field(
        name="Classe",
        value=f"{classe_dados['emoji']} {classe_dados['nome']}" if classe_dados
              else "— `rpg classe` para escolher",
        inline=True,
    )
    e.add_field(
        name="Atributos",
        value=" · ".join(
            f"{at.ATRIBUTOS[k]['sigla']} {s['atribs'][k]}" for k in at.ATRIBUTOS
        ),
        inline=False,
    )
    e.add_field(
        name="Ataque",
        value=f"{s['atk']} ({at.ATRIBUTOS[s['atributo_arma']]['sigla']}) · "
              f"crít {s['critico'] * 100:.0f}%",
        inline=True,
    )
    e.add_field(name="Defesa", value=f"{s['def']} (-{s['reducao'] * 100:.0f}% dano)", inline=True)
    e.add_field(name="Moedas", value=f"🪙 {j['moedas']}", inline=True)
    arma = ITENS[j["arma"]]["nome"] if j["arma"] else "—"
    armadura = ITENS[j["armadura"]]["nome"] if j["armadura"] else "—"
    anel = ITENS[j["anel"]]["nome"] if j["anel"] else "—"
    colar = ITENS[j["colar"]]["nome"] if j["colar"] else "—"
    e.add_field(
        name="Equipado",
        value=f"🗡️ {arma}\n🛡️ {armadura}\n💍 {anel}\n📿 {colar}",
        inline=False,
    )
    rodape = f"Andar mais alto destrancado: {j['andar_max']}/{ANDAR_MAXIMO}"
    if j["pontos"]:
        rodape = f"{j['pontos']} ponto(s) para distribuir · " + rodape
    if j["mortes"]:
        rodape += f" · Mortes: {j['mortes']}"
    e.set_footer(text=rodape)
    await ctx.send(embed=e)


@bot.command(name="cacar", aliases=["hunt", "h", "caçar"])
@travas.fora_de_luta()
async def cacar(ctx):
    j = await pegar_jogador(ctx)
    if not j:
        return
    if await bloqueado_por_cooldown(ctx, "cacar", COOLDOWN_CACAR):
        return

    s = stats(j)
    if j["hp"] <= 0:
        db.atualizar_jogador(j["user_id"], hp=int(s["hp_max"] * 0.3))
        j["hp"] = int(s["hp_max"] * 0.3)

    andar = ANDARES[j["andar"]]
    mob = random.choice(andar["monstros"])
    hp_final, venceu, log = simular_combate(s, j["hp"], mob, j["andar"])

    e = discord.Embed(title=f"Andar {j['andar']} — {mob['nome']}", color=andar["cor"])
    e.description = "\n".join(log)

    if venceu:
        nivel, xp, subiu = aplicar_xp(j, mob["xp"])
        drops = rolar_drops(mob)
        for item in drops:
            db.add_item(j["user_id"], item)
        hp_final = hp_depois_do_nivel(hp_final, nivel, subiu, s["atribs"])
        db.atualizar_jogador(
            j["user_id"], hp=hp_final, xp=xp, nivel=nivel,
            pontos=pontos_por_subir(j, subiu), moedas=j["moedas"] + mob["moedas"],
        )
        recompensa = f"+{mob['xp']} XP · +{mob['moedas']} 🪙"
        if drops:
            recompensa += "\n" + "\n".join(f"{ITENS[i]['emoji']} {ITENS[i]['nome']}" for i in drops)
        e.add_field(name="Vitória", value=recompensa, inline=False)
        if subiu:
            e.add_field(
                name="⬆️ Subiu de nível!",
                value=(
                    f"Agora você é **nível {nivel}** — +{at.PONTOS_POR_NIVEL * subiu} ponto(s) "
                    f"de atributo. Gaste com `rpg upar <atributo> <qtd>`."
                ),
                inline=False,
            )
        e.set_footer(text=f"HP: {max(0, hp_final)}/{at.hp_maximo(nivel, s['atribs']['constituicao'])}")
    else:
        perda = await a_processar_morte(j, s)
        e.color = 0x8B0000
        e.add_field(
            name="Você caiu",
            value=f"Perdeu **{perda}** 🪙 e acordou no ponto de retorno com 30% de HP.",
            inline=False,
        )
    await ctx.send(embed=e)


@bot.command(name="explorar", aliases=["adventure", "adv", "aventura"])
@travas.fora_de_luta()
async def explorar(ctx):
    j = await pegar_jogador(ctx)
    if not j:
        return
    if await bloqueado_por_cooldown(ctx, "explorar", COOLDOWN_EXPLORAR):
        return

    s = stats(j)
    andar = ANDARES[j["andar"]]
    hp = j["hp"] if j["hp"] > 0 else int(s["hp_max"] * 0.3)
    total_xp = total_moedas = 0
    drops_totais = []
    linhas = []
    caiu = False

    for _ in range(3):
        mob = random.choice(andar["monstros"])
        hp, venceu, _log = simular_combate(s, hp, mob, j["andar"])
        if not venceu:
            linhas.append(f"❌ Derrotado por **{mob['nome']}**.")
            caiu = True
            break
        total_xp += mob["xp"]
        total_moedas += mob["moedas"]
        drops_totais += rolar_drops(mob)
        linhas.append(f"✅ {mob['nome']} — HP restante: {max(0, hp)}")

    e = discord.Embed(title=f"Exploração — {andar['nome']}", color=andar["cor"])
    e.description = "\n".join(linhas)

    if caiu:
        perda = await a_processar_morte(j, s)
        e.color = 0x8B0000
        e.add_field(name="Você caiu", value=f"Perdeu **{perda}** 🪙. As recompensas foram perdidas.", inline=False)
    else:
        bonus = int(total_moedas * 0.5)
        for item in drops_totais:
            db.add_item(j["user_id"], item)
        nivel, xp, subiu = aplicar_xp(j, total_xp)
        hp = hp_depois_do_nivel(hp, nivel, subiu, s["atribs"])
        db.atualizar_jogador(
            j["user_id"], hp=hp, xp=xp, nivel=nivel, pontos=pontos_por_subir(j, subiu),
            moedas=j["moedas"] + total_moedas + bonus,
        )
        texto = f"+{total_xp} XP · +{total_moedas + bonus} 🪙 (bônus de exploração incluso)"
        if drops_totais:
            contagem = {}
            for i in drops_totais:
                contagem[i] = contagem.get(i, 0) + 1
            texto += "\n" + "\n".join(f"{ITENS[i]['emoji']} {ITENS[i]['nome']} x{q}" for i, q in contagem.items())
        e.add_field(name="Recompensas", value=texto, inline=False)
        if subiu:
            e.add_field(
                name="⬆️ Subiu de nível!",
                value=f"**Nível {nivel}** · +{at.PONTOS_POR_NIVEL * subiu} ponto(s) — `rpg upar`",
                inline=False,
            )
    await ctx.send(embed=e)


# ==================== andares e viagem ====================
@bot.command(name="andar", aliases=["floor", "local"])
async def andar_info(ctx):
    j = await pegar_jogador(ctx)
    if not j:
        return
    a = ANDARES[j["andar"]]
    e = discord.Embed(title=f"Andar {j['andar']} — {a['nome']}", description=a["descricao"], color=a["cor"])
    e.add_field(
        name="Habitantes hostis",
        value="\n".join(f"• {m['nome']} — {m['hp']} HP / {m['atk']} ATK" for m in a["monstros"]),
        inline=False,
    )
    if j["andar"] >= j["andar_max"]:
        e.add_field(name="Chefe", value=f"{a['boss']['nome']} — {a['boss']['hp']} HP / {a['boss']['atk']} ATK", inline=False)
    else:
        e.add_field(name="Chefe", value=f"~~{a['boss']['nome']}~~ — já derrotado", inline=False)
    pessoas = npcs_do_andar(j["andar"])
    if pessoas:
        e.add_field(
            name="Quem está por aqui",
            value="\n".join(f"{ICONES_NPC.get(n['tipo'], '•')} {n['nome']} {n['titulo']}".strip() for n in pessoas),
            inline=False,
        )
    e.set_footer(text=f"Destrancado até o andar {j['andar_max']}/{ANDAR_MAXIMO}")
    await ctx.send(embed=e)


def custo_e_motivo_viagem(j, destino, gratis_carroca):
    """(custo, motivo) — motivo é None se pago, "carroça" ou "guilda" se de graça.

    A graça da guilda é checada por membro, não por guilda: quem tem
    andar_max abaixo da home da guilda paga o preço normal mesmo pertencendo
    a ela (ver guildas § home). A carroça não sobe o Selo — sem carroça
    acima do andar 10 de propósito (ver decisoes.md § Andares 11-15).
    """
    if gratis_carroca and destino <= andares_altos.ANDAR_ACIMA_DO_SELO:
        return 0, "carroça"
    if db.viagem_gratis_guilda(j["user_id"], j["andar_max"], destino):
        return 0, "guilda"
    return custo_viagem(j["andar"], destino), None


@bot.command(name="viajar", aliases=["ir", "travel"])
@travas.fora_de_luta()
async def viajar(ctx, destino: int = 0):
    j = await pegar_jogador(ctx)
    if not j:
        return

    ativa, parte_em = carroca_ativa()
    gratis_carroca = ativa and conheceu_bramm(j)

    if not destino:
        linhas = []
        teto_viagem = min(j["andar_max"], LIMITE_VIAJAR)
        for n in range(1, teto_viagem + 1):
            if n == j["andar"]:
                linhas.append(f"**{n}. {ANDARES[n]['nome']}** — você está aqui")
            else:
                custo, motivo = custo_e_motivo_viagem(j, n, gratis_carroca)
                preco = f"grátis ({motivo})" if motivo else f"{custo} 🪙"
                linhas.append(f"`{n}.` {ANDARES[n]['nome']} — {preco}")
        if j["andar"] > teto_viagem:
            linhas.append(
                f"**{j['andar']}. {ANDARES[j['andar']]['nome']}** — você está aqui, "
                f"mas `rpg viajar` não alcança daqui pra lá de novo depois que sair."
            )
        e = discord.Embed(title="Para onde?", description="\n".join(linhas), color=0xA8DADC)
        e.set_footer(text="rpg viajar <número> · você tem "
                          f"{j['moedas']} moedas")
        await ctx.send(embed=e)
        return

    if destino < 1 or destino > ANDAR_MAXIMO:
        await ctx.send(f"Andar inválido. A torre vai de 1 a {ANDAR_MAXIMO}.")
        return
    if destino > j["andar_max"]:
        await ctx.send(f"Você ainda não destrancou o andar {destino}. Derrote o chefe do andar {j['andar_max']} primeiro.")
        return
    if destino > LIMITE_VIAJAR:
        await ctx.send(
            f"`rpg viajar` só chega até o andar {LIMITE_VIAJAR}. Andar {destino} só se alcança "
            f"lutando pra cima a partir do {LIMITE_VIAJAR} — não tem teleporte de volta pra lá."
        )
        return
    if destino == j["andar"]:
        await ctx.send("Você já está aqui.")
        return

    custo, motivo = custo_e_motivo_viagem(j, destino, gratis_carroca)
    if j["moedas"] < custo:
        await ctx.send(
            f"A viagem custa **{custo}** 🪙 e você tem {j['moedas']}. "
            f"Se puder esperar, o Bramm leva de graça — `rpg carroca`."
        )
        return

    db.atualizar_jogador(j["user_id"], andar=destino, moedas=j["moedas"] - custo)
    a = ANDARES[destino]
    e = discord.Embed(
        title=f"Andar {destino} — {a['nome']}",
        description=a["descricao"],
        color=a["cor"],
    )
    if motivo == "carroça":
        e.set_author(name="🐎 Você pegou carona com Bramm")
        e.set_footer(text=f"Não custou nada. A carroça parte {parte_em.strftime('%H:%M')}.")
    elif motivo == "guilda":
        e.set_author(name="🏠 Viagem de volta pra casa")
        e.set_footer(text="Não custou nada — o andar é a home da sua guilda.")
    else:
        e.set_footer(text=f"Viagem: -{custo} 🪙 · restam {j['moedas'] - custo}")
    await ctx.send(embed=e)


@bot.command(name="carroca", aliases=["carroça", "bramm"])
@travas.fora_de_luta()
async def carroca(ctx):
    j = await pegar_jogador(ctx)
    if not j:
        return
    if not conheceu_bramm(j):
        await ctx.send(
            f"Você ouviu falar de um carroceiro, mas ainda não o encontrou. "
            f"Dizem que ele passa pelo andar {ANDAR_DESBLOQUEIA_CARROCA}."
        )
        return

    horarios = " · ".join(f"{h:02d}:{m:02d}" for h, m in HORARIOS_CARROCA)
    ativa, parte_em = carroca_ativa()
    e = discord.Embed(title="🐎 Bramm, o Carroceiro", color=0xB08968)
    if ativa:
        restante = (parte_em - agora()).total_seconds()
        e.description = (
            f"**A carroça está parada agora.** Ela sai às {parte_em.strftime('%H:%M')} "
            f"— faltam **{fmt_tempo(restante)}**.\n\n"
            f"Enquanto ela estiver aqui, `rpg viajar <andar>` não custa nada."
        )
        e.color = 0x2A9D8F
    else:
        prox = proxima_carroca()
        falta = (prox - agora()).total_seconds()
        e.description = (
            f"A carroça não está aqui. A próxima passa às **{prox.strftime('%H:%M')}**, "
            f"daqui a **{fmt_tempo(falta)}**.\n\n"
            f"Se tiver pressa, `rpg viajar` mostra o preço da viagem paga."
        )
    e.set_footer(text=f"Horários: {horarios} (horário de Brasília) · fica {JANELA_CARROCA_MIN} min parado")
    await ctx.send(embed=e)


@bot.command(name="npcs", aliases=["gente", "moradores"])
async def listar_npcs(ctx):
    j = await pegar_jogador(ctx)
    if not j:
        return
    pessoas = npcs_do_andar(j["andar"])
    if not pessoas:
        await ctx.send("Não tem ninguém vivo neste andar.")
        return
    a = ANDARES[j["andar"]]
    linhas = []
    for n in pessoas:
        papel = {"mercador": "vende poções", "ferreiro": "vende equipamento daqui",
                 "carroceiro": "viagem grátis nos horários", "conversa": "",
                 "taverneiro": "cura HP e mana cheios por moedas",
                 "guia": f"leva de volta pro andar {andares_altos.ANDAR_ACIMA_DO_SELO} de graça"}[n["tipo"]]
        nome = f"{n['nome']} {n['titulo']}".strip()
        linhas.append(f"{ICONES_NPC.get(n['tipo'], '•')} **{nome}**" + (f" — {papel}" if papel else ""))
    e = discord.Embed(
        title=f"Quem está no andar {j['andar']}",
        description="\n".join(linhas),
        color=a["cor"],
    )
    e.set_footer(text="rpg falar <nome>")
    await ctx.send(embed=e)


class BotaoOpcaoDialogo(discord.ui.Button):
    """Um botão por opção de fala — a `resposta` é dado (dialogos.py), o
    botão só existe pra mostrar ela e continuar a conversa aberta."""

    def __init__(self, opcao):
        super().__init__(label=opcao["label"], style=discord.ButtonStyle.secondary)
        self.resposta = opcao["resposta"]

    async def callback(self, interaction):
        e = interaction.message.embeds[0]
        e.description = f"*{pronomes.concordar(self.resposta, self.view.pronome)}*"
        await interaction.response.edit_message(embed=e, view=self.view)


class BotaoSairDialogo(discord.ui.Button):
    """Não é uma opção de `dialogos.py` — a DialogoView acrescenta esse
    botão sozinha, sempre por último. Sair troca a descrição pela linha de
    despedida do NPC e trava a view (desabilita tudo), igual ao timeout mas
    com texto em vez de silêncio."""

    def __init__(self, saida):
        super().__init__(label="Sair", style=discord.ButtonStyle.secondary)
        self.saida = saida

    async def callback(self, interaction):
        e = interaction.message.embeds[0]
        e.description = f"*{pronomes.concordar(self.saida, self.view.pronome)}*"
        for item in self.view.children:
            item.disabled = True
        self.view.stop()
        await interaction.response.edit_message(embed=e, view=self.view)


class DialogoView(discord.ui.View):
    """Mandada pública com `ctx.send` de propósito — o Rafael quer que o
    canal veja que existe conteúdo. Só o autor consegue clicar; o resto
    recebe recusa ephemeral. Nada aqui é consumido: `rpg falar` de novo
    mostra as mesmas opções, sempre."""

    def __init__(self, autor_id, pronome, opcoes, saida):
        super().__init__(timeout=120)
        self.autor_id = autor_id
        self.pronome = pronome
        self.mensagem = None
        for opcao in opcoes:
            self.add_item(BotaoOpcaoDialogo(opcao))
        self.add_item(BotaoSairDialogo(saida))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "Essa conversa não é sua. Manda `rpg falar` você mesmo.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """Desabilita os botões em vez de somem com eles — conversa não é
        combate, não tem pressa pra limpar a tela."""
        if self.mensagem is None:
            return
        for item in self.children:
            item.disabled = True
        await self.mensagem.edit(view=self)


@bot.command(name="falar", aliases=["conversar", "talk"])
@travas.fora_de_luta()
async def falar(ctx, *, quem: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
        return
    n = encontrar_npc(j["andar"], quem)
    if not n:
        await ctx.send("Não tem ninguém com esse nome neste andar. Confere `rpg npcs`.")
        return
    nome = f"{n['nome']} {n['titulo']}".strip()

    if n["tipo"] == "guia":
        # falar com ela já desce de graça — descer é sempre grátis, subir nunca
        fala = andares_altos.fala_da_guia(j["andar"], j["mortes"]) or n["fala"]
        destino = andares_altos.ANDAR_ACIMA_DO_SELO
        db.atualizar_jogador(j["user_id"], andar=destino)
        e = discord.Embed(description=f"*{fala}*", color=ANDARES[j["andar"]]["cor"])
        e.set_author(name=f"{ICONES_NPC['guia']} {nome}")
        e.set_footer(text=f"Ela te leva de volta pro andar {destino}. De graça — subir é que nunca é.")
        await ctx.send(embed=e)
        return

    if n["tipo"] == "conversa" and n.get("dialogo"):
        dado = dialogos.DIALOGOS[n["dialogo"]]
        opcoes = opcoes_do_dialogo(n["dialogo"], j["user_id"])
        abertura = pronomes.concordar(dado["abertura"], j["pronome"])
        e = discord.Embed(description=f"*{abertura}*", color=ANDARES[j["andar"]]["cor"])
        e.set_author(name=f"{ICONES_NPC['conversa']} {nome}")
        saida = dado.get("saida") or dialogos.SAIDA_PADRAO
        view = DialogoView(ctx.author.id, j["pronome"], opcoes, saida)
        view.mensagem = await ctx.send(embed=e, view=view)
        return

    e = discord.Embed(description=f"*{n['fala']}*", color=ANDARES[j["andar"]]["cor"])
    e.set_author(name=f"{ICONES_NPC.get(n['tipo'], '•')} {nome}")
    if n["tipo"] in ("mercador", "ferreiro"):
        e.set_footer(text="rpg loja")
    elif n["tipo"] == "carroceiro":
        e.set_footer(text="rpg carroca")
    elif n["tipo"] == "taverneiro":
        e.set_footer(text="rpg descansar")
    await ctx.send(embed=e)


class PronomeView(discord.ui.View):
    """Só o autor escolhe o próprio pronome — resto do canal fica de fora,
    diferente da DialogoView (que é pública de propósito). PROVISÓRIO: este
    comando é um jeito de escolher enquanto o novo início do jogo (patch
    0.3) não existe. Quando ele nascer, a escolha muda pra lá e `rpg
    pronome` deixa de fazer sentido como comando solto — não esquecer de
    tirar. Ver decisoes.md § pronomes do jogador."""

    def __init__(self, autor_id):
        super().__init__(timeout=60)
        self.autor_id = autor_id

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "Essa escolha não é sua. Manda `rpg pronome` você mesmo.", ephemeral=True
            )
            return False
        return True

    async def _escolher(self, interaction, pronome):
        db.atualizar_jogador(interaction.user.id, pronome=pronome)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"Pronome definido: **{pronome}**.", view=self
        )

    @discord.ui.button(label="ele / dele", style=discord.ButtonStyle.primary)
    async def ele(self, interaction, button):
        await self._escolher(interaction, "ele")

    @discord.ui.button(label="ela / dela", style=discord.ButtonStyle.primary)
    async def ela(self, interaction, button):
        await self._escolher(interaction, "ela")

    @discord.ui.button(label="elu / delu", style=discord.ButtonStyle.primary)
    async def elu(self, interaction, button):
        await self._escolher(interaction, "elu")


@bot.command(name="pronome")
async def pronome_cmd(ctx):
    """PROVISÓRIO — ver PronomeView."""
    j = await pegar_jogador(ctx)
    if not j:
        return
    await ctx.send(
        f"Pronome atual: **{j['pronome']}**. Escolhe um (afeta concordância de "
        f"gênero nos textos, não muda nada mecânico):",
        view=PronomeView(ctx.author.id),
    )


@bot.command(name="descansar", aliases=["rest", "descanso"])
async def descansar(ctx):
    """Cura HP e mana cheios em qualquer andar até o Selo (10) — sem NPC
    físico exigido, só as duas tavernas (andares 1 e 10) têm um taverneiro
    de verdade pra dar a fala. Acima do Selo não tem descanso pago, mesma
    regra de "sem comércio" do resto dos andares 11-15. Preço fixo travado
    por cooldown (ver decisoes.md) — sem o cooldown, preço fixo ficaria mais
    barato que poção pra quem está bem machucado."""
    j = await pegar_jogador(ctx)
    if not j:
        return
    if j["andar"] > andares_altos.ANDAR_ACIMA_DO_SELO:
        await ctx.send("Não tem descanso pago acima do Selo. Sobe abastecido ou não sobe.")
        return

    npc = taverneiro_do_andar(j["andar"])
    nome_npc = f"{npc['nome']} {npc['titulo']}".strip() if npc else None

    s = stats(j)
    falta_hp = max(0, s["hp_max"] - max(0, j["hp"]))
    falta_mana = max(0, s["mana_max"] - max(0, j["mana"]))
    if falta_hp == 0 and falta_mana == 0:
        fala = pronomes.concordar(
            "Já está inteir{o|a}. Volta quando estiver acabad{o|a}."
            if npc else "Você já está inteir{o|a}. Não precisa descansar agora.",
            j["pronome"],
        )
        await ctx.send(f"*{nome_npc} olha pra você.* \"{fala}\"" if npc else fala)
        return

    restante = db.checar_cooldown(j["user_id"], "descansar")
    if restante > 0:
        await ctx.send(f"⏳ `rpg descansar` volta em **{fmt_tempo(restante)}**.")
        return
    if j["moedas"] < CUSTO_DESCANSAR:
        await ctx.send(
            f"*{nome_npc} olha os seus machucados.* \"Isso sai por **{CUSTO_DESCANSAR}** 🪙. Você tem {j['moedas']}.\""
            if npc else f"Descansar sai por **{CUSTO_DESCANSAR}** 🪙. Você tem {j['moedas']}."
        )
        return

    db.set_cooldown(j["user_id"], "descansar", COOLDOWN_DESCANSAR)
    db.atualizar_jogador(j["user_id"], hp=s["hp_max"], mana=s["mana_max"], moedas=j["moedas"] - CUSTO_DESCANSAR)
    descricao = pronomes.concordar(
        f"*{nome_npc} empurra um prato na sua frente e não pergunta nada.*" if npc
        else "*Você monta acampamento, cuida dos ferimentos e descansa até se sentir inteir{o|a} de novo.*",
        j["pronome"],
    )
    e = discord.Embed(title="🛏️ Descanso", description=descricao, color=ANDARES[j["andar"]]["cor"])
    e.add_field(name="Recuperado", value=f"HP +{falta_hp} · Mana +{falta_mana}", inline=False)
    e.set_footer(
        text=f"Custou {CUSTO_DESCANSAR} 🪙 · restam {j['moedas'] - CUSTO_DESCANSAR} · "
             f"próximo em {fmt_tempo(COOLDOWN_DESCANSAR)}"
    )
    await ctx.send(embed=e)


# ==================== economia ====================
@bot.command(name="inventario", aliases=["inventory", "inv", "i", "mochila", "inventário"])
async def inventario(ctx, pagina: int = 1):
    j = await pegar_jogador(ctx)
    if not j:
        return
    itens = db.get_inventario(j["user_id"])
    entradas = [
        (f"{ITENS[i['item']]['emoji']} {ITENS[i['item']]['nome']}", f"x{i['qtd']}")
        for i in itens if i["item"] in ITENS
    ]
    await paginacao.enviar_paginado(
        ctx, entradas, f"Mochila de {j['nome']}", 0xC9ADA7,
        rodape_extra=f"🪙 {j['moedas']} moedas", pagina_inicial=pagina,
        mensagem_vazia="Sua mochila está vazia.",
    )


@bot.command(name="loja", aliases=["shop", "store"])
@travas.fora_de_luta()
async def loja(ctx, pagina: int = 1):
    j = await pegar_jogador(ctx)
    if not j:
        return
    if j["andar"] > andares_altos.ANDAR_ACIMA_DO_SELO:
        await ctx.send(
            "Não tem comércio nenhum acima do Selo — nada é vendido, nem poção. "
            "Sobe abastecido ou não sobe."
        )
        return
    a = ANDARES[j["andar"]]
    partes_desc = []

    mercador = next((n for n in npcs_do_andar(j["andar"]) if n["tipo"] == "mercador"), None)
    consumiveis = a_venda(consumiveis_disponiveis(j["andar_max"]))
    entradas = [
        (f"🧺 {v['emoji']} {v['nome']}", f"{v['preco']} 🪙 ({descricao_cura(v)})")
        for v in consumiveis.values()
    ]
    if mercador:
        nome_mercador = f"{mercador['nome']} {mercador['titulo']}".strip()
        partes_desc.append(f"🧺 {nome_mercador}")

    ferreiro = ferreiro_do_andar(j["andar"])
    equipamentos = a_venda(equipamentos_do_andar(j["andar"]))
    if ferreiro and equipamentos:
        entradas += [
            (
                f"🔨 {v['emoji']} {v['nome']}",
                f"{v['preco']} 🪙"
                + (f" (+{v['atk']} ATK)" if "atk" in v else "")
                + (f" (+{v['def']} DEF)" if "def" in v else ""),
            )
            for v in equipamentos.values()
        ]
        nome_ferreiro = f"{ferreiro['nome']} {ferreiro['titulo']}".strip()
        partes_desc.append(f"🔨 {nome_ferreiro}")
    else:
        andares_com_forja = sorted({v["andar_min"] for v in ITENS.values()
                                    if v["tipo"] in ("arma", "armadura") and v.get("loja", True)})
        partes_desc.append(
            "🔨 Sem ferreiro aqui — equipamento só nos andares "
            + ", ".join(str(n) for n in andares_com_forja) + "."
        )

    await paginacao.enviar_paginado(
        ctx, entradas, f"Comércio do andar {j['andar']} — {a['nome']}", 0xE9C46A,
        descricao=" · ".join(partes_desc) or None,
        rodape_extra=f"Você tem {j['moedas']} moedas · rpg comprar <item> <qtd>",
        pagina_inicial=pagina, mensagem_vazia="Nada à venda aqui agora.",
    )


@bot.command(name="comprar", aliases=["buy"])
@travas.fora_de_luta()
async def comprar(ctx, *, argumento: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
        return
    if j["andar"] > andares_altos.ANDAR_ACIMA_DO_SELO:
        await ctx.send("Não tem ninguém vendendo nada acima do Selo.")
        return
    if not argumento:
        await ctx.send("Uso: `rpg comprar <item> <quantidade>`. Ex: `rpg comprar pocao pequena 3`")
        return
    texto, qtd = separar_quantidade(argumento)
    disponiveis = a_venda({**consumiveis_disponiveis(j["andar_max"]),
                           **equipamentos_do_andar(j["andar"])})
    item = encontrar_item(texto, disponiveis.keys())

    if not item:
        pista = encontrar_item(texto)
        if pista and not ITENS[pista].get("loja", True):
            await ctx.send(
                f"**{ITENS[pista]['nome']}** não se compra: é item de fabricação. "
                f"Confere `rpg receitas`."
            )
        elif pista and ITENS[pista]["tipo"] in ("arma", "armadura"):
            n = ITENS[pista]["andar_min"]
            await ctx.send(
                f"**{ITENS[pista]['nome']}** só é forjado no andar {n}. "
                + (f"Manda `rpg viajar {n}`." if n <= j["andar_max"] else "Você ainda não destrancou esse andar.")
            )
        elif pista and ITENS[pista]["tipo"] == "consumivel":
            await ctx.send(f"**{ITENS[pista]['nome']}** só aparece depois do andar {ITENS[pista]['andar_min']}.")
        else:
            await ctx.send("Item não encontrado. Confere `rpg loja`.")
        return

    custo = disponiveis[item]["preco"] * qtd
    if j["moedas"] < custo:
        await ctx.send(f"Faltam **{custo - j['moedas']}** moedas.")
        return
    db.add_item(j["user_id"], item, qtd)
    db.atualizar_jogador(j["user_id"], moedas=j["moedas"] - custo)
    await ctx.send(f"Comprou {ITENS[item]['emoji']} **{ITENS[item]['nome']}** x{qtd} por {custo} 🪙.")


@bot.command(name="vender", aliases=["sell"])
@travas.fora_de_luta()
async def vender(ctx, *, argumento: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
        return
    if not argumento:
        await ctx.send("Uso: `rpg vender <item> <quantidade>`.")
        return
    texto, qtd = separar_quantidade(argumento)
    possuidos = [i["item"] for i in db.get_inventario(j["user_id"]) if i["item"] in ITENS]
    item = encontrar_item(texto, possuidos)
    if not item or not db.tem_item(j["user_id"], item, qtd):
        await ctx.send("Você não tem isso nessa quantidade.")
        return
    dado = ITENS[item]
    if not dado.get("vendavel", True):
        await ctx.send(
            f"**{dado['nome']}** não se vende — cada chefe solta um só, e ele é "
            f"material de fabricação. Guarda."
        )
        return
    unitario = dado["preco"] if dado["tipo"] == "material" else int(dado["preco"] * 0.5)
    total = unitario * qtd
    db.remove_item(j["user_id"], item, qtd)
    db.atualizar_jogador(j["user_id"], moedas=j["moedas"] + total)
    await ctx.send(f"Vendeu **{dado['nome']}** x{qtd} por {total} 🪙.")


@bot.command(name="usar", aliases=["use", "u"])
@travas.fora_de_luta()
async def usar(ctx, *, texto: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
        return
    texto, pedidas = separar_quantidade(texto)
    inventario = {i["item"]: i["qtd"] for i in db.get_inventario(j["user_id"]) if i["item"] in ITENS}
    item = encontrar_item(texto, inventario.keys())
    if not item or ITENS[item]["tipo"] != "consumivel":
        await ctx.send("Você não tem esse consumível. Confere `rpg inventario`.")
        return

    s = stats(j)
    campo, restauro = at.restauracao_do_item(ITENS[item], s["hp_max"], s["mana_max"])
    rotulo, teto = ("HP", s["hp_max"]) if campo == "hp" else ("Mana", s["mana_max"])
    atual = max(0, j[campo])
    falta = teto - atual
    if falta <= 0:
        await ctx.send(f"Seu {rotulo} já está cheio ({atual}/{teto}). Não gastei nada.")
        return

    bastam = -(-falta // restauro)  # divisão pra cima: quantas realmente enchem
    usadas = min(pedidas, bastam, inventario[item])
    if not db.remove_item(j["user_id"], item, usadas):
        await ctx.send("Você não tem esse item.")
        return

    novo = min(teto, atual + restauro * usadas)
    db.atualizar_jogador(j["user_id"], **{campo: novo})
    msg = (f"{ITENS[item]['emoji']} Usou **{ITENS[item]['nome']}**"
           + (f" x{usadas}" if usadas > 1 else "")
           + f" — {rotulo}: {novo}/{teto}")
    if usadas < pedidas:
        motivo = f"o resto passaria do seu {rotulo} máximo" if bastam < pedidas else "você não tinha mais"
        msg += f"\nUsei {usadas} de {pedidas}: {motivo}."
    await ctx.send(msg)


@bot.command(name="equipar", aliases=["equip", "e"])
@travas.fora_de_luta()
async def equipar(ctx, *, texto: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
        return
    possuidos = [i["item"] for i in db.get_inventario(j["user_id"]) if i["item"] in ITENS]
    item = encontrar_item(texto, possuidos)
    if not item or ITENS[item]["tipo"] not in ("arma", "armadura", "anel", "colar"):
        await ctx.send("Você não tem esse equipamento na mochila.")
        return
    andar_min = ITENS[item]["andar_min"]
    if andar_min > j["andar_max"]:
        await ctx.send(
            f"**{ITENS[item]['nome']}** é do andar {andar_min} — você só destrancou até o andar "
            f"{j['andar_max']}. Fica guardado na mochila até você chegar lá."
        )
        return
    if not db.remove_item(j["user_id"], item, 1):
        await ctx.send("Você não tem esse item.")
        return
    slot = ITENS[item]["tipo"]
    antigo = j[slot]
    if antigo:
        db.add_item(j["user_id"], antigo, 1)
    db.atualizar_jogador(j["user_id"], **{slot: item})
    msg = f"Equipou {ITENS[item]['emoji']} **{ITENS[item]['nome']}**."
    if antigo:
        msg += f" {ITENS[antigo]['nome']} voltou pra mochila."
    await ctx.send(msg)


# ==================== atributos ====================
@bot.command(name="status", aliases=["atributos", "attr", "st"])
async def status(ctx):
    j = await pegar_jogador(ctx)
    if not j:
        return
    s = stats(j)
    e = discord.Embed(
        title=f"Atributos de {j['nome']}",
        description=f"Nível {j['nivel']} · **{j['pontos']}** ponto(s) para distribuir",
        color=ANDARES[j["andar"]]["cor"],
    )
    for chave, dados in at.ATRIBUTOS.items():
        e.add_field(
            name=f"{dados['emoji']} {dados['sigla']} — {s['atribs'][chave]}",
            value=dados["desc"],
            inline=False,
        )
    e.add_field(
        name="Resultado",
        value=(
            f"HP {max(0, j['hp'])}/{s['hp_max']} · Mana {max(0, j['mana'])}/{s['mana_max']}\n"
            f"Ataque {s['atk']} — escala com "
            f"**{at.ATRIBUTOS[s['atributo_arma']]['sigla']}** (sua arma)\n"
            f"Defesa {s['def']} (apara {s['reducao'] * 100:.0f}% do dano)\n"
            f"Esquiva {s['esquiva'] * 100:.0f}% · Crítico {s['critico'] * 100:.0f}%"
        ),
        inline=False,
    )
    custo_respec = "grátis" if j["respec_gratis"] else f"{at.custo_respec(j['nivel'])} 🪙"
    e.set_footer(text=f"rpg upar <atributo> <qtd> · rpg respec ({custo_respec})")
    await ctx.send(embed=e)


@bot.command(name="upar", aliases=["up", "distribuir", "gastar"])
@travas.fora_de_luta()
async def upar(ctx, *, argumento: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
        return
    if not argumento:
        await ctx.send(
            f"Você tem **{j['pontos']}** ponto(s). Uso: `rpg upar con 3`. "
            f"Atributos: FOR, DES, CON, INT — `rpg status` explica cada um."
        )
        return

    texto, qtd = separar_quantidade(argumento)
    chave = at.encontrar_atributo(texto)
    if not chave:
        await ctx.send("Não conheço esse atributo. Use FOR, DES, CON ou INT.")
        return
    if j["pontos"] < qtd:
        await ctx.send(f"Você tem só **{j['pontos']}** ponto(s) para gastar.")
        return

    atribs = at.extrair(j)
    novo_valor = atribs[chave] + qtd
    campos = {chave: novo_valor, "pontos": j["pontos"] - qtd}

    # ganhar CON ou INT aumenta o teto — o valor atual sobe junto, nao e' cura
    if chave == "constituicao":
        campos["hp"] = max(0, j["hp"]) + at.HP_POR_CON * qtd
    elif chave == "inteligencia":
        campos["mana"] = max(0, j["mana"]) + at.MANA_POR_INT * qtd

    db.atualizar_jogador(j["user_id"], **campos)
    dados = at.ATRIBUTOS[chave]
    msg = f"{dados['emoji']} **{dados['sigla']} {atribs[chave]} ▸ {novo_valor}**"
    if j["pontos"] - qtd:
        msg += f" · restam {j['pontos'] - qtd} ponto(s)"
    await ctx.send(msg)


@bot.command(name="respec", aliases=["redistribuir", "resetar"])
@travas.fora_de_luta()
async def respec(ctx, confirmacao: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
        return
    gratis = bool(j["respec_gratis"])
    custo = 0 if gratis else at.custo_respec(j["nivel"])
    if confirmacao.lower() not in ("confirmar", "sim", "confirm"):
        if gratis:
            aviso = (
                "Seu **respec é grátis** — sobrou do rebalanceamento de defesa "
                "(CON não dá mais defesa, só HP)."
            )
        else:
            aviso = f"Redistribuir todos os atributos custa **{custo}** 🪙."
        await ctx.send(
            f"{aviso} Devolve **{at.pontos_ganhos(j['nivel'])}** ponto(s) do zero.\n"
            f"Se for isso mesmo: `rpg respec confirmar`."
        )
        return
    if not gratis and j["moedas"] < custo:
        await ctx.send(f"Faltam **{custo - j['moedas']}** moedas para o respec.")
        return

    base = at.distribuicao_inicial()
    hp_max = at.hp_maximo(j["nivel"], base["constituicao"])
    mana_max = at.mana_maxima(j["nivel"], base["inteligencia"])
    campos = dict(
        moedas=j["moedas"] - custo, pontos=at.pontos_ganhos(j["nivel"]),
        hp=min(max(0, j["hp"]), hp_max), mana=min(max(0, j["mana"]), mana_max),
        **base,
    )
    if gratis:
        campos["respec_gratis"] = 0
    db.atualizar_jogador(j["user_id"], **campos)
    texto_custo = "de graça" if gratis else f"por {custo} 🪙"
    await ctx.send(
        f"Atributos zerados {texto_custo}. Você tem **{at.pontos_ganhos(j['nivel'])}** "
        f"ponto(s) livres — `rpg status` para conferir antes de gastar."
    )


@bot.command(name="titulo", aliases=["titulos", "title"])
async def titulo(ctx, *, argumento: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
        return
    possuidos = [t for t in (j["titulos_possuidos"] or "").split(",") if t]

    partes = argumento.strip().split(None, 1)
    acao = normalizar(partes[0]) if partes else ""
    resto = partes[1] if len(partes) > 1 else ""

    if acao in ("equipar", "usar", "vestir"):
        if not resto:
            await ctx.send("Equipar qual título? `rpg titulo equipar beta tester`.")
            return
        alvo = encontrar_titulo(resto, possuidos)
        if not alvo:
            await ctx.send(
                "Você não tem esse título." if possuidos
                else "Você ainda não conquistou nenhum título."
            )
            return
        db.atualizar_jogador(j["user_id"], titulo=alvo)
        await ctx.send(f"{TITULOS[alvo]['emoji']} Agora usando **{TITULOS[alvo]['nome']}**.")
        return

    if acao in ("remover", "tirar", "limpar"):
        db.atualizar_jogador(j["user_id"], titulo=None)
        await ctx.send("Título removido.")
        return

    pagina = int(acao) if acao.isdigit() else 1
    entradas = []
    for chave in possuidos:
        dados = TITULOS.get(chave)
        if not dados:
            continue
        marca = " — equipado" if chave == j["titulo"] else ""
        entradas.append((f"{dados['emoji']} {dados['nome']}{marca}", dados["desc"]))
    await paginacao.enviar_paginado(
        ctx, entradas, f"Títulos de {j['nome']}", ANDARES[j["andar"]]["cor"],
        rodape_extra="rpg titulo equipar <nome> · rpg titulo remover", pagina_inicial=pagina,
        mensagem_vazia="Nenhum título conquistado ainda.",
    )


def embed_info_classe(chave):
    """Prévia das 2 habilidades base de uma classe, sem exigir que o jogador
    já seja dela — é o que falta pra `rpg classe <classe>` não ser uma
    escolha às cegas (a escolha trava, sem troca depois)."""
    dados = CLASSES[chave]
    e = discord.Embed(
        title=f"{dados['emoji']} {dados['nome']} — habilidades base",
        description=dados["desc"],
        color=0x6A4C93,
    )
    for skill in hab.habilidades_da_classe(chave).values():
        requisito = ""
        if "requisito" in skill:
            atributo, minimo = skill["requisito"]
            requisito = f" (requer {minimo} {at.ATRIBUTOS[atributo]['sigla']})"
        e.add_field(
            name=f"{skill['emoji']} {skill['nome']} — {skill['custo']} "
                 f"{hab.NOME_RECURSO[skill['recurso']]}{requisito}",
            value=skill["desc"],
            inline=False,
        )
    e.set_footer(text=f"Prévia — `rpg classe {chave}` ainda trava a escolha, sem troca depois.")
    return e


@bot.command(name="classe", aliases=["class", "vocacao", "vocação"])
async def classe_cmd(ctx, *, argumento: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
        return

    partes = argumento.strip().split()
    pedir_info = len(partes) >= 2 and normalizar(partes[-1]) == "info"
    if pedir_info:
        alvo = encontrar_classe(" ".join(partes[:-1]))
        if not alvo:
            await ctx.send("Não conheço essa classe. `rpg classe` mostra as opções.")
            return
        await ctx.send(embed=embed_info_classe(alvo))
        return

    if j["classe"]:
        dados = CLASSES[j["classe"]]
        await ctx.send(
            f"Você já é **{dados['emoji']} {dados['nome']}**. Escolha travada, não dá pra trocar."
        )
        return

    if not argumento:
        e = discord.Embed(
            title="Escolha uma classe",
            description=(
                "Travada assim que escolher — não tem troca. `rpg classe <classe> info` mostra "
                "as habilidades base antes de decidir. `rpg ascencao` mostra no que cada uma "
                "vira mais pra frente."
            ),
            color=ANDARES[j["andar"]]["cor"],
        )
        for chave, dados in CLASSES.items():
            e.add_field(
                name=f"{dados['emoji']} {dados['nome']}",
                value=f"{dados['desc']}\n`rpg classe {chave}` · `rpg classe {chave} info`",
                inline=False,
            )
        await ctx.send(embed=e)
        return

    escolhida = encontrar_classe(argumento)
    if not escolhida:
        await ctx.send("Não conheço essa classe. `rpg classe` mostra as opções.")
        return
    db.atualizar_jogador(j["user_id"], classe=escolhida)
    dados = CLASSES[escolhida]
    await ctx.send(
        f"{dados['emoji']} Você agora é **{dados['nome']}**. Escolha travada.\n"
        f"`rpg ascencao` mostra o caminho lá na frente."
    )


@bot.command(name="ascencao", aliases=["ascensao", "ascensão", "ascenção"])
async def ascencao(ctx):
    e = discord.Embed(
        title="As 4 bases e as 12 ascensões",
        description=(
            "Habilidades ainda não existem — isso é o mapa do que vem por aí. "
            "A ascensão liberada por nível troca a base por um dos 3 ramos."
        ),
        color=0x6A4C93,
    )
    for chave, dados in CLASSES.items():
        ramos = ", ".join(a["nome"] for a in ASCENSOES.values() if a["base"] == chave)
        e.add_field(
            name=f"{dados['emoji']} {dados['nome']}",
            value=f"{dados['desc']}\nAscensões: {ramos}",
            inline=False,
        )
    await ctx.send(embed=e)


# ==================== servidor ====================
@bot.command(name="priv", aliases=["sala", "privado", "meucanal"])
async def priv(ctx):
    j = await pegar_jogador(ctx)
    if not j:
        return
    if ctx.guild is None:
        await ctx.send("Esse comando só funciona dentro de um servidor.")
        return
    if not ctx.guild.me.guild_permissions.manage_channels:
        await ctx.send(
            "Não tenho permissão de **Gerenciar Canais** neste servidor, "
            "então não consigo criar sua sala. Fala com quem administra."
        )
        return

    nome = nome_de_canal(ctx.author)
    existente = discord.utils.get(ctx.guild.text_channels, name=nome)
    if existente:
        await ctx.send(f"Sua sala já existe: {existente.mention}")
        return

    categoria = discord.utils.get(ctx.guild.categories, name=CATEGORIA_SALAS)
    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        ctx.author: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        ),
        ctx.guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, embed_links=True,
            read_message_history=True, manage_channels=True,
        ),
    }

    try:
        if categoria is None:
            categoria = await ctx.guild.create_category(CATEGORIA_SALAS)
        canal = await ctx.guild.create_text_channel(
            nome, category=categoria, overwrites=overwrites,
            topic=f"Sala de {ctx.author.display_name} na torre. Só você e o bot enxergam.",
        )
    except discord.Forbidden:
        await ctx.send("O Discord recusou: falta permissão pra criar canal ou categoria.")
        return
    except discord.HTTPException as erro:
        await ctx.send(f"O Discord recusou a criação da sala ({erro.status}). Tenta de novo.")
        return

    e = discord.Embed(
        title="Sua sala na torre",
        description=(
            f"Aqui é só seu, {ctx.author.display_name}. Pode grindar à vontade "
            f"que ninguém mais vê.\n\n"
            f"Seu personagem é o mesmo em qualquer canal — muda só o barulho."
        ),
        color=ANDARES[j["andar"]]["cor"],
    )
    e.set_footer(text="rpg cacar · rpg perfil · rpg ajuda")
    await canal.send(embed=e)
    await ctx.send(f"Pronto: {canal.mention}")


@bot.command(name="ranking", aliases=["top", "leaderboard", "lb"])
async def ranking(ctx):
    lista = db.ranking(10)
    if not lista:
        await ctx.send("Ninguém entrou na torre ainda.")
        return
    medalhas = ["🥇", "🥈", "🥉"]
    linhas = []
    for i, p in enumerate(lista):
        pos = medalhas[i] if i < 3 else f"`{i + 1}.`"
        linhas.append(f"{pos} **{p['nome']}** — andar {p['andar_max']}, nível {p['nivel']}")
    e = discord.Embed(title="Escalada da Torre", description="\n".join(linhas), color=0x2B2D42)
    await ctx.send(embed=e)


def embed_ajuda():
    e = discord.Embed(title="Comandos — prefixo `rpg`", color=0x457B9D)
    e.add_field(
        name="Progressão",
        value=(
            "`rpg comecar` — cria seu personagem\n"
            "`rpg cacar` (`h`) — combate rápido, 1 min\n"
            "`rpg explorar` (`adv`) — 3 inimigos, 3 min\n"
            "`rpg boss` — chefe do andar, 15 min\n"
            "`rpg party` — abre uma sala pra encarar o chefe junto"
        ),
        inline=False,
    )
    e.add_field(
        name="A torre",
        value=(
            "`rpg andar` — onde você está\n"
            "`rpg viajar <n>` — muda de andar (custa moedas)\n"
            "`rpg carroca` — horários da carona grátis\n"
            "`rpg npcs` · `rpg falar <nome>`\n"
            "`rpg descansar` — cura HP e mana cheios, 150 🪙, 1x a cada 2h (até o andar 10, não acima)"
        ),
        inline=False,
    )
    e.add_field(
        name="Personagem",
        value=(
            "`rpg perfil` (`p`) · `rpg inventario` (`inv`)\n"
            "`rpg status` — atributos e pontos livres\n"
            "`rpg upar <atributo> <qtd>` · `rpg respec`\n"
            "`rpg usar <item> <qtd>` · `rpg equipar <item>`\n"
            "`rpg titulo` — títulos conquistados e como equipar\n"
            "`rpg classe` · `rpg ascencao` — escolha travada, mapa das 12 ascensões\n"
            "`rpg habilidades` — o que você já destravou (só se lança contra chefe)"
        ),
        inline=False,
    )
    e.add_field(
        name="Ofício",
        value=(
            "`rpg profissao` — escolhe entre Forja e Alquimia\n"
            "`rpg receitas` — o que você consegue fabricar\n"
            "`rpg craftar <item> <qtd>` — fabrica na bancada do NPC\n"
            "`rpg melhorar <arma|armadura>` — tenta +1/+2 no ferreiro, qualquer jogador\n"
            "`rpg desmanchar <item> <qtd>` — devolve parte do material, item some"
        ),
        inline=False,
    )
    e.add_field(
        name="Economia",
        value=(
            "`rpg loja` · `rpg comprar <item> <qtd>` · `rpg vender <item> <qtd>` · `rpg ranking`\n"
            "`rpg pix @alguém <valor>` — manda moeda à distância, com confirmação por botão\n"
            "`rpg trade @alguém` — troca item/moeda com quem estiver no mesmo andar"
        ),
        inline=False,
    )
    e.add_field(
        name="Guilda",
        value=(
            "`rpg guilda` — status · `rpg guilda criar <nome>` (5.000 🪙)\n"
            "`rpg guilda convidar/expulsar @alguém` · `rpg guilda sair`\n"
            "`rpg guilda aceitar/recusar <nome>` · `rpg guilda convites` — convite vale 24h\n"
            "`rpg guilda home <andar>` — viagem grátis pra lá, checada por membro\n"
            "`rpg guilda bau` · `depositar <item> <qtd>` · `sacar <item> <qtd>` · `log`\n"
            "`rpg raide` — «Sua Majestade do Andar Nenhum», mínimo 3, 1x/dia por guilda"
        ),
        inline=False,
    )
    e.add_field(
        name="Sua sala",
        value="`rpg priv` — cria um canal só seu, pra não poluir o geral",
        inline=False,
    )
    return e


@bot.command(name="ajuda", aliases=["help", "comandos"])
async def ajuda(ctx):
    await ctx.send(embed=embed_ajuda())


# turnos do chefe — precisa vir depois dos helpers e dos comandos acima
import combate

combate.instalar(bot, globals())

# habilidades — infraestrutura de classes/skills; combate.py já importa o
# módulo, isso aqui só liga o comando `rpg habilidades`
import habilidades

habilidades.instalar(bot, globals())

# profissões — o módulo ainda pode não existir; quando existir, é só soltar na pasta
try:
    import profissoes

    profissoes.instalar(bot, globals())
except ModuleNotFoundError:
    print("profissoes.py ainda não está na pasta — craft desligado.")

# trocas — pix (transferência à distância) e trade (troca presencial de item/moeda)
import trocas

trocas.instalar(bot, globals())

# guildas — baú, cargo/canal no Discord, viagem grátis pra home (custo_e_motivo_viagem acima já chama db.viagem_gratis_guilda)
import guildas

guildas.instalar(bot, globals())

# raide — precisa vir depois de combate.instalar(), usa combate.H por baixo
import raide

raide.instalar(bot, globals())

# agenda — aviso automático da carroça do Bramm
import agenda

agenda.instalar(bot)

# admin — comandos restritos ao dono do bot (reset de temporada, etc.)
import admin

admin.instalar(bot)

if __name__ == "__main__":
    # guarda de main: importar este módulo (testes, um shell, outro script)
    # não pode conectar no Discord — só rodar `python bot.py` de verdade
    # conecta. Ver decisoes.md § Guarda de main + setup no nível do módulo.
    try:
        bot.run(TOKEN)
    finally:
        # conexão única de módulo (database.py) — precisa ser fechada explicitamente
        # agora que ninguém mais fecha ela por chamada.
        db.fechar_conexao()