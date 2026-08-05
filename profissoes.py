# profissoes.py
# Forja e Alquimia: escolha de oficio, nivel proprio e receitas.
# Mesmo padrao do combate.py: nao importa bot.py, recebe os helpers em instalar().

import discord

import database as db
from game_data import ITENS, ANDARES

H = {}

CUSTO_TROCA = 1000        # moedas para trocar de profissao (zera o nivel)
NIVEL_MAXIMO = 10


PROFISSOES = {
    "forja": {
        "nome": "Forja", "titulo": "Ferreiro", "emoji": "⚒️", "npc": "ferreiro",
        "desc": "Bate armaduras que loja nenhuma vende. Trabalha na bigorna dos ferreiros.",
    },
    "alquimia": {
        "nome": "Alquimia", "titulo": "Alquimista", "emoji": "⚗️", "npc": "mercador",
        "desc": "Destila elixires que curam por porcentagem. Trabalha na banca dos mercadores.",
    },
}

APELIDOS = {
    "forja": "forja", "ferreiro": "forja", "ferraria": "forja", "forjar": "forja",
    "alquimia": "alquimia", "alquimista": "alquimia", "pocao": "alquimia",
}

# nivel, materiais, moedas e xp de cada receita
RECEITAS = {
    # ---- Forja
    "couro_batido": {"profissao": "forja", "nivel": 1, "moedas": 700, "xp": 35,
                     "materiais": {"presa_javali": 5}},
    "malha_reforcada": {"profissao": "forja", "nivel": 3, "moedas": 2400, "xp": 120,
                        "materiais": {"osso_enferrujado": 5}},
    "placas_polidas": {"profissao": "forja", "nivel": 5, "moedas": 5200, "xp": 260,
                       "materiais": {"nucleo_gelado": 5}},
    "couraca_cinzas": {"profissao": "forja", "nivel": 7, "moedas": 11000, "xp": 550,
                       "materiais": {"brasa_eterna": 5}},
    "lamina_selo": {"profissao": "forja", "nivel": 9, "moedas": 8000, "xp": 900,
                    "materiais": {"fragmento_selo": 3, "pena_do_trovao": 5}},
    "adaga_selo": {"profissao": "forja", "nivel": 9, "moedas": 7000, "xp": 900,
                   "materiais": {"fragmento_selo": 3, "pena_do_trovao": 5}},
    "manto_selo": {"profissao": "forja", "nivel": 9, "moedas": 7500, "xp": 900,
                   "materiais": {"fragmento_selo": 3, "pena_do_trovao": 5}},
    # ---- Alquimia
    "elixir_ervas": {"profissao": "alquimia", "nivel": 1, "moedas": 200, "xp": 20,
                     "materiais": {"seda_sussurrante": 3}},
    "elixir_vermelho": {"profissao": "alquimia", "nivel": 4, "moedas": 900, "xp": 90,
                        "materiais": {"cristal_de_sal": 3}},
    "nectar_torre": {"profissao": "alquimia", "nivel": 7, "moedas": 2600, "xp": 300,
                     "materiais": {"fragmento_sino": 3}},
}


# ---------------------------------------------------------------- progressao

def xp_para_subir(nivel):
    """XP necessario para sair do nivel N para o N+1."""
    return int(50 * nivel ** 1.4)


def aplicar_xp_profissao(nivel, xp_atual, ganho):
    nivel, xp = nivel, xp_atual + ganho
    subiu = 0
    while nivel < NIVEL_MAXIMO and xp >= xp_para_subir(nivel):
        xp -= xp_para_subir(nivel)
        nivel += 1
        subiu += 1
    if nivel >= NIVEL_MAXIMO:
        xp = 0
    return nivel, xp, subiu


def encontrar_profissao(texto):
    chave = H["normalizar"](texto or "")
    if chave in APELIDOS:
        return APELIDOS[chave]
    for nome in PROFISSOES:
        if nome.startswith(chave) and chave:
            return nome
    return None


def receitas_da(profissao):
    return {k: v for k, v in RECEITAS.items() if v["profissao"] == profissao}


def bancada_no_andar(andar_num, profissao):
    """O NPC daquele oficio esta neste andar? Devolve o NPC ou None."""
    tipo = PROFISSOES[profissao]["npc"]
    return next((n for n in H["npcs_do_andar"](andar_num) if n["tipo"] == tipo), None)


def falta_material(user_id, receita, vezes=1):
    """Lista de (item, quanto falta). Vazia = da' pra fazer."""
    tem = {i["item"]: i["qtd"] for i in db.get_inventario(user_id)}
    faltando = []
    for item, qtd in receita["materiais"].items():
        preciso = qtd * vezes
        if tem.get(item, 0) < preciso:
            faltando.append((item, preciso - tem.get(item, 0)))
    return faltando


def texto_materiais(receita, vezes=1):
    return " · ".join(
        f"{ITENS[i]['emoji']} {ITENS[i]['nome']} x{q * vezes}"
        for i, q in receita["materiais"].items()
    )


# ---------------------------------------------------------------- instalacao

def instalar(bot, contexto):
    H.update(contexto)

    @bot.command(name="profissao", aliases=["profissão", "oficio", "ofício", "prof"])
    async def profissao(ctx, *, argumento: str = ""):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return

        partes = argumento.strip().split(None, 1)
        acao = H["normalizar"](partes[0]) if partes else ""
        resto = partes[1] if len(partes) > 1 else ""

        # ---- trocar de profissao
        if acao in ("trocar", "mudar"):
            nova = encontrar_profissao(resto)
            if not nova:
                await ctx.send("Trocar para qual? `rpg profissao trocar forja` ou `alquimia`.")
                return
            if not j["profissao"]:
                await ctx.send("Você ainda não tem profissão. Manda `rpg profissao forja`.")
                return
            if nova == j["profissao"]:
                await ctx.send(f"Você já é da **{PROFISSOES[nova]['nome']}**.")
                return
            if j["moedas"] < CUSTO_TROCA:
                await ctx.send(
                    f"A troca custa **{CUSTO_TROCA}** 🪙 e você tem {j['moedas']}."
                )
                return
            db.atualizar_jogador(
                j["user_id"], profissao=nova, prof_nivel=1, prof_xp=0,
                moedas=j["moedas"] - CUSTO_TROCA,
            )
            await ctx.send(
                f"{PROFISSOES[nova]['emoji']} Agora você é da **{PROFISSOES[nova]['nome']}** "
                f"— nível 1, do zero. Custou {CUSTO_TROCA} 🪙."
            )
            return

        # ---- escolher pela primeira vez
        if argumento and not j["profissao"]:
            escolhida = encontrar_profissao(argumento)
            if not escolhida:
                await ctx.send("Não conheço esse ofício. É `forja` ou `alquimia`.")
                return
            db.atualizar_jogador(j["user_id"], profissao=escolhida, prof_nivel=1, prof_xp=0)
            dados = PROFISSOES[escolhida]
            await ctx.send(
                f"{dados['emoji']} Você agora é **{dados['titulo']}**, nível 1.\n"
                f"{dados['desc']}\nManda `rpg receitas` pra ver o que já consegue fazer."
            )
            return

        if argumento and j["profissao"]:
            await ctx.send(
                f"Você já é da **{PROFISSOES[j['profissao']]['nome']}**. "
                f"Pra mudar: `rpg profissao trocar <nova>` ({CUSTO_TROCA} 🪙, zera o nível)."
            )
            return

        # ---- sem argumento: ficha ou menu
        if not j["profissao"]:
            e = discord.Embed(
                title="Escolha um ofício",
                description=(
                    "Você só pode ter **um**. Trocar depois custa "
                    f"{CUSTO_TROCA} 🪙 e zera o nível — então converse com a galera "
                    "antes: dois ferreiros e nenhum alquimista deixa todo mundo sem elixir."
                ),
                color=ANDARES[j["andar"]]["cor"],
            )
            for chave, dados in PROFISSOES.items():
                e.add_field(
                    name=f"{dados['emoji']} {dados['nome']}",
                    value=f"{dados['desc']}\n`rpg profissao {chave}`",
                    inline=False,
                )
            await ctx.send(embed=e)
            return

        dados = PROFISSOES[j["profissao"]]
        nivel, xp = j["prof_nivel"], j["prof_xp"]
        e = discord.Embed(
            title=f"{dados['emoji']} {dados['titulo']} nível {nivel}",
            description=dados["desc"],
            color=ANDARES[j["andar"]]["cor"],
        )
        if nivel < NIVEL_MAXIMO:
            e.add_field(name="Progresso", value=f"{xp}/{xp_para_subir(nivel)} XP de ofício", inline=False)
        else:
            e.add_field(name="Progresso", value="Nível máximo.", inline=False)
        destravadas = [k for k, v in receitas_da(j["profissao"]).items() if v["nivel"] <= nivel]
        e.add_field(name="Receitas destravadas", value=str(len(destravadas)), inline=True)
        e.set_footer(text=f"rpg receitas · rpg craftar <item> · trocar custa {CUSTO_TROCA} 🪙")
        await ctx.send(embed=e)

    @bot.command(name="receitas", aliases=["receita", "craftaveis"])
    async def receitas(ctx):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not j["profissao"]:
            await ctx.send("Você ainda não escolheu um ofício. Manda `rpg profissao`.")
            return

        dados = PROFISSOES[j["profissao"]]
        npc = bancada_no_andar(j["andar"], j["profissao"])
        e = discord.Embed(
            title=f"{dados['emoji']} Receitas de {dados['nome']}",
            description=(
                f"Você trabalha na bancada do **{dados['npc']}**. "
                + (f"Tem um aqui no andar {j['andar']}." if npc
                   else f"Não tem nenhum no andar {j['andar']} — precisa viajar.")
            ),
            color=ANDARES[j["andar"]]["cor"],
        )
        for chave, receita in sorted(receitas_da(j["profissao"]).items(),
                                     key=lambda kv: kv[1]["nivel"]):
            item = ITENS[chave]
            travada = receita["nivel"] > j["prof_nivel"]
            faltando = falta_material(j["user_id"], receita)
            if travada:
                marca = f"🔒 nível {receita['nivel']}"
            elif faltando or j["moedas"] < receita["moedas"]:
                marca = "⬜ falta material"
            else:
                marca = "✅ pode fazer"
            ganho = (f"+{item['def']} DEF" if "def" in item
                     else f"+{item['atk']} ATK" if "atk" in item
                     else f"cura {int(item.get('cura_pct', 0) * 100)}%")
            e.add_field(
                name=f"{item['emoji']} {item['nome']} — {marca}",
                value=f"{ganho}\n{texto_materiais(receita)} + {receita['moedas']} 🪙",
                inline=False,
            )
        e.set_footer(text="rpg craftar <item> <qtd>")
        await ctx.send(embed=e)

    @bot.command(name="craftar", aliases=["craft", "forjar", "fabricar"])
    async def craftar(ctx, *, argumento: str = ""):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not j["profissao"]:
            await ctx.send("Você ainda não escolheu um ofício. Manda `rpg profissao`.")
            return
        if not argumento:
            await ctx.send("Uso: `rpg craftar <item> <qtd>`. Confere `rpg receitas`.")
            return

        texto, vezes = H["separar_quantidade"](argumento)
        minhas = receitas_da(j["profissao"])
        chave = H["encontrar_item"](texto, minhas.keys())
        if not chave:
            fora = H["encontrar_item"](texto, RECEITAS.keys())
            if fora:
                dono = PROFISSOES[RECEITAS[fora]["profissao"]]
                await ctx.send(
                    f"**{ITENS[fora]['nome']}** é receita de **{dono['nome']}**, "
                    f"não da sua. Alguém com esse ofício faz pra você."
                )
            else:
                await ctx.send("Não conheço essa receita. Confere `rpg receitas`.")
            return

        receita = minhas[chave]
        if receita["nivel"] > j["prof_nivel"]:
            await ctx.send(
                f"**{ITENS[chave]['nome']}** exige {PROFISSOES[j['profissao']]['nome']} "
                f"nível {receita['nivel']} — você está no {j['prof_nivel']}."
            )
            return

        npc = bancada_no_andar(j["andar"], j["profissao"])
        if not npc:
            await ctx.send(
                f"Não dá pra trabalhar no meio do mato: precisa de um "
                f"**{PROFISSOES[j['profissao']]['npc']}**, e não tem nenhum no andar {j['andar']}."
            )
            return

        faltando = falta_material(j["user_id"], receita, vezes)
        if faltando:
            await ctx.send(
                "Falta material: "
                + " · ".join(f"{ITENS[i]['emoji']} {ITENS[i]['nome']} x{q}" for i, q in faltando)
            )
            return
        custo = receita["moedas"] * vezes
        if j["moedas"] < custo:
            await ctx.send(f"Faltam **{custo - j['moedas']}** moedas para essa fabricação.")
            return

        for item, qtd in receita["materiais"].items():
            db.remove_item(j["user_id"], item, qtd * vezes)
        db.add_item(j["user_id"], chave, vezes)

        nivel, xp, subiu = aplicar_xp_profissao(
            j["prof_nivel"], j["prof_xp"], receita["xp"] * vezes
        )
        db.atualizar_jogador(
            j["user_id"], moedas=j["moedas"] - custo, prof_nivel=nivel, prof_xp=xp
        )

        dados = PROFISSOES[j["profissao"]]
        e = discord.Embed(
            title=f"{dados['emoji']} {ITENS[chave]['nome']}" + (f" x{vezes}" if vezes > 1 else ""),
            description=(
                f"*{npc['nome']} empresta a bancada e olha por cima do seu ombro.*\n\n"
                f"Gastou {texto_materiais(receita, vezes)} + {custo} 🪙."
            ),
            color=ANDARES[j["andar"]]["cor"],
        )
        if subiu:
            e.add_field(
                name="⬆️ Ofício melhorou",
                value=f"**{dados['nome']} nível {nivel}** — `rpg receitas` pra ver o que abriu.",
                inline=False,
            )
        e.set_footer(text=f"Na mochila. Equipa com `rpg equipar {ITENS[chave]['nome']}`"
                     if ITENS[chave]["tipo"] in ("arma", "armadura")
                     else "Na mochila. Usa com `rpg usar`")
        await ctx.send(embed=e)

    print("profissoes.py carregado — forja e alquimia no ar.")