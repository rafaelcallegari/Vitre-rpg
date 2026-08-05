# bot.py
import os
import random
import time
import unicodedata

import discord
from discord.ext import commands
from dotenv import load_dotenv

import atributos as at
import database as db
from game_data import ITENS, ANDARES, ANDAR_MAXIMO, xp_necessario
from npcs import (
    ANDAR_DESBLOQUEIA_CARROCA, HORARIOS_CARROCA, JANELA_CARROCA_MIN,
    agora, carroca_ativa, proxima_carroca, custo_viagem,
    consumiveis_disponiveis, equipamentos_do_andar,
    npcs_do_andar, ferreiro_do_andar, encontrar_npc,
)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

PREFIXOS = ("rpg ", "rpg")

COOLDOWN_CACAR = 60
COOLDOWN_EXPLORAR = 180
COOLDOWN_BOSS = 900

ICONES_NPC = {"mercador": "🧺", "ferreiro": "🔨", "carroceiro": "🐎", "conversa": "💬"}

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


def a_venda(itens):
    """Tira do balcão tudo que é exclusivo de craft."""
    return {k: v for k, v in itens.items() if v.get("loja", True)}


def descricao_cura(dado):
    """Consumível pode curar valor fixo ou porcentagem do HP máximo."""
    if "cura_pct" in dado:
        return f"cura {int(dado['cura_pct'] * 100)}% da vida"
    return f"cura {dado.get('cura', 0)}"


def cura_do_item(dado, hp_max):
    if "cura_pct" in dado:
        return max(1, int(hp_max * dado["cura_pct"]))
    return dado.get("cura", 0)


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


def stats(j):
    arma = ITENS.get(j["arma"], {})
    armadura = ITENS.get(j["armadura"], {})
    atribs = at.extrair(j)
    s = at.ficha(j["nivel"], atribs, arma, armadura)
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
    bruto = atk * random.uniform(0.85, 1.15)
    if random.random() < critico:
        bruto *= at.MULTIPLICADOR_CRITICO
    return at.aplicar_defesa(bruto, defesa)


def simular_combate(s, hp, mob, andar_num):
    hp_mob = mob["hp"]
    des = s["atribs"]["destreza"]
    des_mob = at.destreza_monstro(andar_num)
    log = []

    if random.random() >= at.chance_iniciativa(des, des_mob):
        dm = calcular_dano(mob["atk"], s["def"])
        hp -= dm
        log.append(f"O inimigo é mais rápido e abre com **{dm}**.")
        if hp <= 0:
            return hp, False, log[-4:]

    for _ in range(60):
        d = calcular_dano(s["atk"], mob["def"], s["critico"])
        hp_mob -= d
        if hp_mob <= 0:
            log.append(f"Você acerta **{d}** e derruba o alvo.")
            return hp, True, log[-4:]
        if random.random() < at.chance_esquiva(des, des_mob):
            log.append(f"Você **{d}** ▸ esquivou do contra-ataque")
            continue
        dm = calcular_dano(mob["atk"], s["def"])
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
    """Devolve o jogador com o HP que ele recuperou parado. Só grava se mudou."""
    s = stats(j)
    novo = at.hp_regenerado(j["hp"], s["hp_max"], j["hp_em"], j["combate_em"], time.time())
    if novo != j["hp"]:
        db.atualizar_jogador(j["user_id"], hp=novo)
        j["hp"] = novo
        j["hp_em"] = time.time()
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
    perda = int(j["moedas"] * 0.20)
    db.atualizar_jogador(
        j["user_id"], hp=int(s["hp_max"] * 0.3),
        moedas=j["moedas"] - perda, mortes=j["mortes"] + 1,
    )
    return perda


def conheceu_bramm(j):
    return j["andar_max"] >= ANDAR_DESBLOQUEIA_CARROCA


# ==================== eventos ====================
@bot.event
async def on_ready():
    db.init_db()
    print(f"Online como {bot.user} — prefixo: rpg")


@bot.event
async def on_command_error(ctx, erro):
    if isinstance(erro, commands.CommandNotFound):
        return
    if isinstance(erro, commands.BadArgument):
        await ctx.send("Não entendi os argumentos. Confere `rpg ajuda`.")
        return
    raise erro


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
    e = discord.Embed(title=f"{j['nome']}", color=andar["cor"])
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
    e.add_field(
        name="Mana",
        value=f"{max(0, j['mana'])}/{s['mana_max']}",
        inline=False,
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
    e.add_field(name="Equipado", value=f"🗡️ {arma}\n🛡️ {armadura}", inline=False)
    rodape = f"Andar mais alto destrancado: {j['andar_max']}/{ANDAR_MAXIMO}"
    if j["pontos"]:
        rodape = f"{j['pontos']} ponto(s) para distribuir · " + rodape
    if j["mortes"]:
        rodape += f" · Mortes: {j['mortes']}"
    e.set_footer(text=rodape)
    await ctx.send(embed=e)


@bot.command(name="cacar", aliases=["hunt", "h", "caçar"])
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
        perda = processar_morte(j, s)
        e.color = 0x8B0000
        e.add_field(
            name="Você caiu",
            value=f"Perdeu **{perda}** 🪙 e acordou no ponto de retorno com 30% de HP.",
            inline=False,
        )
    await ctx.send(embed=e)


@bot.command(name="explorar", aliases=["adventure", "adv", "aventura"])
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
        perda = processar_morte(j, s)
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


@bot.command(name="boss", aliases=["chefe"])
async def boss(ctx):
    j = await pegar_jogador(ctx)
    if not j:
        return

    if j["andar"] < j["andar_max"]:
        await ctx.send(
            f"A sala do chefe do andar {j['andar']} está vazia — você já limpou esse andar. "
            f"Manda `rpg viajar {j['andar_max']}` pra voltar pro topo."
        )
        return

    s = stats(j)
    if j["hp"] < s["hp_max"] * 0.4:
        await ctx.send(
            f"Você está machucado demais ({max(0, j['hp'])}/{s['hp_max']}). "
            f"Manda `rpg usar pocao pequena` antes."
        )
        return
    if await bloqueado_por_cooldown(ctx, "boss", COOLDOWN_BOSS):
        return

    andar = ANDARES[j["andar"]]
    chefe = andar["boss"]
    hp_final, venceu, log = simular_combate(s, j["hp"], chefe, j["andar"])

    e = discord.Embed(title=f"Chefe do andar {j['andar']} — {chefe['nome']}", color=andar["cor"])
    e.description = "\n".join(log)

    if venceu:
        for item in rolar_drops(chefe):
            db.add_item(j["user_id"], item)
        nivel, xp, subiu = aplicar_xp(j, chefe["xp"])
        novo_andar = min(j["andar"] + 1, ANDAR_MAXIMO)
        novo_max = max(j["andar_max"], novo_andar)
        hp_cheio = at.hp_maximo(nivel, s["atribs"]["constituicao"])
        db.atualizar_jogador(
            j["user_id"], hp=hp_cheio, mana=s["mana_max"], xp=xp, nivel=nivel,
            pontos=pontos_por_subir(j, subiu),
            moedas=j["moedas"] + chefe["moedas"], andar=novo_andar, andar_max=novo_max,
        )
        e.add_field(
            name="Chefe derrotado",
            value=f"+{chefe['xp']} XP · +{chefe['moedas']} 🪙 · 🔷 Fragmento do Selo",
            inline=False,
        )
        if j["andar"] == ANDAR_MAXIMO:
            e.add_field(
                name="🌑 Décimo Selo",
                value="A porta abre. Do outro lado tem uma escada que continua subindo — e ela não acaba.",
                inline=False,
            )
        else:
            e.add_field(
                name=f"⬆️ Andar {novo_andar} destrancado",
                value=f"**{ANDARES[novo_andar]['nome']}**\n{ANDARES[novo_andar]['descricao']}",
                inline=False,
            )
            if novo_andar == ANDAR_DESBLOQUEIA_CARROCA:
                e.add_field(
                    name="🐎 Você conheceu Bramm",
                    value="O carroceiro passa por aqui três vezes por dia e não cobra. `rpg carroca`",
                    inline=False,
                )
        if subiu:
            e.add_field(
                name="Nível",
                value=f"Você chegou ao **nível {nivel}** · +{at.PONTOS_POR_NIVEL * subiu} ponto(s).",
                inline=False,
            )
    else:
        perda = processar_morte(j, s)
        e.color = 0x8B0000
        e.add_field(name="Derrota", value=f"O chefe continua no lugar. Você perdeu **{perda}** 🪙.", inline=False)
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


@bot.command(name="viajar", aliases=["ir", "travel"])
async def viajar(ctx, destino: int = 0):
    j = await pegar_jogador(ctx)
    if not j:
        return

    ativa, parte_em = carroca_ativa()
    gratis = ativa and conheceu_bramm(j)

    if not destino:
        linhas = []
        for n in range(1, j["andar_max"] + 1):
            if n == j["andar"]:
                linhas.append(f"**{n}. {ANDARES[n]['nome']}** — você está aqui")
            else:
                custo = 0 if gratis else custo_viagem(j["andar"], n)
                preco = "grátis (carroça)" if gratis else f"{custo} 🪙"
                linhas.append(f"`{n}.` {ANDARES[n]['nome']} — {preco}")
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
    if destino == j["andar"]:
        await ctx.send("Você já está aqui.")
        return

    custo = 0 if gratis else custo_viagem(j["andar"], destino)
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
    if gratis:
        e.set_author(name="🐎 Você pegou carona com Bramm")
        e.set_footer(text=f"Não custou nada. A carroça parte {parte_em.strftime('%H:%M')}.")
    else:
        e.set_footer(text=f"Viagem: -{custo} 🪙 · restam {j['moedas'] - custo}")
    await ctx.send(embed=e)


@bot.command(name="carroca", aliases=["carroça", "bramm"])
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

    horarios = " · ".join(f"{h:02d}:00" for h in HORARIOS_CARROCA)
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
                 "carroceiro": "viagem grátis nos horários", "conversa": ""}[n["tipo"]]
        nome = f"{n['nome']} {n['titulo']}".strip()
        linhas.append(f"{ICONES_NPC.get(n['tipo'], '•')} **{nome}**" + (f" — {papel}" if papel else ""))
    e = discord.Embed(
        title=f"Quem está no andar {j['andar']}",
        description="\n".join(linhas),
        color=a["cor"],
    )
    e.set_footer(text="rpg falar <nome>")
    await ctx.send(embed=e)


@bot.command(name="falar", aliases=["conversar", "talk"])
async def falar(ctx, *, quem: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
        return
    n = encontrar_npc(j["andar"], quem)
    if not n:
        await ctx.send("Não tem ninguém com esse nome neste andar. Confere `rpg npcs`.")
        return
    nome = f"{n['nome']} {n['titulo']}".strip()
    e = discord.Embed(description=f"*{n['fala']}*", color=ANDARES[j["andar"]]["cor"])
    e.set_author(name=f"{ICONES_NPC.get(n['tipo'], '•')} {nome}")
    if n["tipo"] in ("mercador", "ferreiro"):
        e.set_footer(text="rpg loja")
    elif n["tipo"] == "carroceiro":
        e.set_footer(text="rpg carroca")
    await ctx.send(embed=e)


# ==================== economia ====================
@bot.command(name="inventario", aliases=["inventory", "inv", "i", "mochila", "inventário"])
async def inventario(ctx):
    j = await pegar_jogador(ctx)
    if not j:
        return
    itens = db.get_inventario(j["user_id"])
    if not itens:
        await ctx.send("Sua mochila está vazia.")
        return
    linhas = [
        f"{ITENS[i['item']]['emoji']} **{ITENS[i['item']]['nome']}** x{i['qtd']}"
        for i in itens if i["item"] in ITENS
    ]
    e = discord.Embed(title=f"Mochila de {j['nome']}", description="\n".join(linhas), color=0xC9ADA7)
    e.set_footer(text=f"🪙 {j['moedas']} moedas")
    await ctx.send(embed=e)


@bot.command(name="loja", aliases=["shop", "store"])
async def loja(ctx):
    j = await pegar_jogador(ctx)
    if not j:
        return
    a = ANDARES[j["andar"]]
    e = discord.Embed(title=f"Comércio do andar {j['andar']} — {a['nome']}", color=0xE9C46A)

    mercador = next((n for n in npcs_do_andar(j["andar"]) if n["tipo"] == "mercador"), None)
    consumiveis = a_venda(consumiveis_disponiveis(j["andar_max"]))
    if consumiveis:
        nome = f"{mercador['nome']} {mercador['titulo']}".strip() if mercador else "Mercador"
        e.add_field(
            name=f"🧺 {nome}",
            value="\n".join(
                f"{v['emoji']} **{v['nome']}** — {v['preco']} 🪙 ({descricao_cura(v)})"
                for v in consumiveis.values()
            ),
            inline=False,
        )

    ferreiro = ferreiro_do_andar(j["andar"])
    equipamentos = a_venda(equipamentos_do_andar(j["andar"]))
    if ferreiro and equipamentos:
        nome = f"{ferreiro['nome']} {ferreiro['titulo']}".strip()
        e.add_field(
            name=f"🔨 {nome}",
            value="\n".join(
                f"{v['emoji']} **{v['nome']}** — {v['preco']} 🪙"
                + (f" (+{v['atk']} ATK)" if "atk" in v else "")
                + (f" (+{v['def']} DEF)" if "def" in v else "")
                for v in equipamentos.values()
            ),
            inline=False,
        )
    else:
        andares_com_forja = sorted({v["andar_min"] for v in ITENS.values()
                                    if v["tipo"] in ("arma", "armadura") and v.get("loja", True)})
        e.add_field(
            name="🔨 Sem ferreiro aqui",
            value="Equipamento só nos andares " + ", ".join(str(n) for n in andares_com_forja) + ".",
            inline=False,
        )

    e.set_footer(text=f"Você tem {j['moedas']} moedas · rpg comprar <item> <qtd>")
    await ctx.send(embed=e)


@bot.command(name="comprar", aliases=["buy"])
async def comprar(ctx, *, argumento: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
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
    hp = max(0, j["hp"])
    falta = s["hp_max"] - hp
    if falta <= 0:
        await ctx.send(f"Seu HP já está cheio ({hp}/{s['hp_max']}). Não gastei nada.")
        return

    cura = cura_do_item(ITENS[item], s["hp_max"])
    bastam = -(-falta // cura)  # divisão pra cima: quantas realmente curam
    usadas = min(pedidas, bastam, inventario[item])
    if not db.remove_item(j["user_id"], item, usadas):
        await ctx.send("Você não tem esse item.")
        return

    novo_hp = min(s["hp_max"], hp + cura * usadas)
    db.atualizar_jogador(j["user_id"], hp=novo_hp)
    msg = (f"{ITENS[item]['emoji']} Usou **{ITENS[item]['nome']}**"
           + (f" x{usadas}" if usadas > 1 else "")
           + f" — HP: {novo_hp}/{s['hp_max']}")
    if usadas < pedidas:
        motivo = "o resto passaria do seu HP máximo" if bastam < pedidas else "você não tinha mais"
        msg += f"\nUsei {usadas} de {pedidas}: {motivo}."
    await ctx.send(msg)


@bot.command(name="equipar", aliases=["equip", "e"])
async def equipar(ctx, *, texto: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
        return
    possuidos = [i["item"] for i in db.get_inventario(j["user_id"]) if i["item"] in ITENS]
    item = encontrar_item(texto, possuidos)
    if not item or ITENS[item]["tipo"] not in ("arma", "armadura"):
        await ctx.send("Você não tem esse equipamento na mochila.")
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
    e.set_footer(text=f"rpg upar <atributo> <qtd> · rpg respec ({at.custo_respec(j['nivel'])} 🪙)")
    await ctx.send(embed=e)


@bot.command(name="upar", aliases=["up", "distribuir", "gastar"])
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
    if chave == "inteligencia":
        msg += "\n⚠️ Mana ainda não tem uso — habilidades vêm depois. `rpg respec` desfaz."
    await ctx.send(msg)


@bot.command(name="respec", aliases=["redistribuir", "resetar"])
async def respec(ctx, confirmacao: str = ""):
    j = await pegar_jogador(ctx)
    if not j:
        return
    custo = at.custo_respec(j["nivel"])
    if confirmacao.lower() not in ("confirmar", "sim", "confirm"):
        await ctx.send(
            f"Redistribuir todos os atributos custa **{custo}** 🪙 e devolve "
            f"**{at.pontos_ganhos(j['nivel'])}** ponto(s) do zero.\n"
            f"Se for isso mesmo: `rpg respec confirmar`."
        )
        return
    if j["moedas"] < custo:
        await ctx.send(f"Faltam **{custo - j['moedas']}** moedas para o respec.")
        return

    base = at.distribuicao_inicial()
    hp_max = at.hp_maximo(j["nivel"], base["constituicao"])
    mana_max = at.mana_maxima(j["nivel"], base["inteligencia"])
    db.atualizar_jogador(
        j["user_id"], moedas=j["moedas"] - custo, pontos=at.pontos_ganhos(j["nivel"]),
        hp=min(max(0, j["hp"]), hp_max), mana=min(max(0, j["mana"]), mana_max),
        **base,
    )
    await ctx.send(
        f"Atributos zerados por {custo} 🪙. Você tem **{at.pontos_ganhos(j['nivel'])}** "
        f"ponto(s) livres — `rpg status` para conferir antes de gastar."
    )


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
            "`rpg npcs` · `rpg falar <nome>`"
        ),
        inline=False,
    )
    e.add_field(
        name="Personagem",
        value=(
            "`rpg perfil` (`p`) · `rpg inventario` (`inv`)\n"
            "`rpg status` — atributos e pontos livres\n"
            "`rpg upar <atributo> <qtd>` · `rpg respec`\n"
            "`rpg usar <item> <qtd>` · `rpg equipar <item>`"
        ),
        inline=False,
    )
    e.add_field(
        name="Ofício",
        value=(
            "`rpg profissao` — escolhe entre Forja e Alquimia\n"
            "`rpg receitas` — o que você consegue fabricar\n"
            "`rpg craftar <item> <qtd>` — fabrica na bancada do NPC"
        ),
        inline=False,
    )
    e.add_field(
        name="Economia",
        value="`rpg loja` · `rpg comprar <item> <qtd>` · `rpg vender <item> <qtd>` · `rpg ranking`",
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

# profissões — o módulo ainda pode não existir; quando existir, é só soltar na pasta
try:
    import profissoes

    profissoes.instalar(bot, globals())
except ModuleNotFoundError:
    print("profissoes.py ainda não está na pasta — craft desligado.")

bot.run(TOKEN)