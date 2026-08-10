# profissoes.py
# Forja e Alquimia: escolha de oficio, nivel proprio e receitas.
# Mesmo padrao do combate.py: nao importa bot.py, recebe os helpers em instalar().

import random

import discord

import database as db
import paginacao
import travas
from game_data import ITENS, ANDARES

H = {}

CUSTO_TROCA = 1000        # moedas para trocar de profissao (zera o nivel)
NIVEL_MAXIMO = 10

# ---- melhoria (+1/+2) e desmanche ----
ANDAR_MATERIAL = {           # material do andar, so' existe ferreiro nos impares ate' o 9
    1: "presa_javali", 3: "osso_enferrujado", 5: "nucleo_gelado",
    7: "brasa_eterna", 9: "pena_do_trovao",
    # 11-15: sem ferreiro, mas arma elemental melhora com o drop de chao do
    # proprio andar (ver decisoes.md) -- consecutivos, nao so' impares.
    11: "pluma_eterea", 12: "farpa_eletrica", 13: "estilhaco_gelido",
    14: "cinza_quente", 15: "po_de_estrela",
}
NIVEL_MAX_UPGRADE = 2
PCT_STAT_POR_UPGRADE = 0.12
CUSTO_MATERIAL_UPGRADE = {1: 2, 2: 3}       # quantas unidades do material do andar
CUSTO_PRECO_UPGRADE = {1: 0.40, 2: 1.00}    # fracao do preco da peca
CHANCE_UPGRADE = {1: 1.0, 2: 0.70}
CHANCE_UPGRADE_FORJADOR = {1: 1.0, 2: 0.85}
DESCONTO_FORJADOR = 0.25    # so' em melhorar: material e moedas, so' pra quem e' Forjador
XP_UPGRADE = {1: 25, 2: 50}
PCT_REFUND_DESMANCHE = 0.50
PCT_XP_DESMANCHE = 0.40


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
    "couro_batido": {"profissao": "forja", "nivel": 1, "moedas": 400, "xp": 22,
                     "materiais": {"presa_javali": 3}},
    "malha_reforcada": {"profissao": "forja", "nivel": 3, "moedas": 1400, "xp": 75,
                        "materiais": {"osso_enferrujado": 3}},
    "placas_polidas": {"profissao": "forja", "nivel": 3, "moedas": 3000, "xp": 165,
                       "materiais": {"nucleo_gelado": 3}},
    "couraca_cinzas": {"profissao": "forja", "nivel": 5, "moedas": 6200, "xp": 340,
                       "materiais": {"brasa_eterna": 3}},
    "lamina_selo": {"profissao": "forja", "nivel": 7, "moedas": 8000, "xp": 180,
                    "materiais": {"fragmento_selo": 2, "pena_do_trovao": 3}},
    "adaga_selo": {"profissao": "forja", "nivel": 7, "moedas": 7000, "xp": 180,
                   "materiais": {"fragmento_selo": 2, "pena_do_trovao": 3}},
    "manto_selo": {"profissao": "forja", "nivel": 8, "moedas": 7500, "xp": 180,
                   "materiais": {"fragmento_selo": 2, "pena_do_trovao": 3}},
    "cajado_selo": {"profissao": "forja", "nivel": 7, "moedas": 8000, "xp": 180,
                    "materiais": {"fragmento_selo": 2, "pena_do_trovao": 3}},
    "manoplas_selo": {"profissao": "forja", "nivel": 7, "moedas": 7000, "xp": 180,
                      "materiais": {"fragmento_selo": 2, "pena_do_trovao": 3}},
    # ---- Forja, armas elementais (andares 11-15, ver decisoes.md) ----
    "espada_vento": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                     "materiais": {"sopro_contido": 2, "pluma_eterea": 3}},
    "arco_vento": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                   "materiais": {"sopro_contido": 2, "pluma_eterea": 3}},
    "cajado_vento": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                     "materiais": {"sopro_contido": 2, "pluma_eterea": 3}},
    "manopla_vento": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                      "materiais": {"sopro_contido": 2, "pluma_eterea": 3}},
    "machado_raio": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                     "materiais": {"semente_de_trovao": 2, "farpa_eletrica": 3}},
    "adaga_raio": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                   "materiais": {"semente_de_trovao": 2, "farpa_eletrica": 3}},
    "cajado_raio": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                    "materiais": {"semente_de_trovao": 2, "farpa_eletrica": 3}},
    "manopla_raio": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                     "materiais": {"semente_de_trovao": 2, "farpa_eletrica": 3}},
    "martelo_gelo": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                     "materiais": {"lasca_de_silencio": 2, "estilhaco_gelido": 3}},
    "foice_gelo": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                   "materiais": {"lasca_de_silencio": 2, "estilhaco_gelido": 3}},
    "cajado_gelo": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                    "materiais": {"lasca_de_silencio": 2, "estilhaco_gelido": 3}},
    "manopla_gelo": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                     "materiais": {"lasca_de_silencio": 2, "estilhaco_gelido": 3}},
    "espada_solario": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                       "materiais": {"brasa_sem_fumaca": 2, "cinza_quente": 3}},
    "arco_solario": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                     "materiais": {"brasa_sem_fumaca": 2, "cinza_quente": 3}},
    "cajado_solario": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                       "materiais": {"brasa_sem_fumaca": 2, "cinza_quente": 3}},
    "manopla_solario": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                        "materiais": {"brasa_sem_fumaca": 2, "cinza_quente": 3}},
    "machado_sombrio": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                        "materiais": {"sombra_dobrada": 2, "po_de_estrela": 3}},
    "adaga_sombria": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                      "materiais": {"sombra_dobrada": 2, "po_de_estrela": 3}},
    "cajado_sombrio": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                       "materiais": {"sombra_dobrada": 2, "po_de_estrela": 3}},
    "manopla_sombria": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                        "materiais": {"sombra_dobrada": 2, "po_de_estrela": 3}},
    "martelo_divino": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                       "materiais": {"prego_de_luz": 2, "po_de_estrela": 3}},
    "foice_divina": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                     "materiais": {"prego_de_luz": 2, "po_de_estrela": 3}},
    "cajado_divino": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                      "materiais": {"prego_de_luz": 2, "po_de_estrela": 3}},
    "manopla_divina": {"profissao": "forja", "nivel": 9, "moedas": 10000, "xp": 260,
                       "materiais": {"prego_de_luz": 2, "po_de_estrela": 3}},
    # ---- Alquimia
    "elixir_ervas": {"profissao": "alquimia", "nivel": 1, "moedas": 200, "xp": 20,
                     "materiais": {"seda_sussurrante": 3}},
    "elixir_vermelho": {"profissao": "alquimia", "nivel": 4, "moedas": 900, "xp": 90,
                        "materiais": {"cristal_de_sal": 3}},
    "elixir_mana": {"profissao": "alquimia", "nivel": 4, "moedas": 900, "xp": 90,
                    "materiais": {"cristal_de_sal": 3}},
    "nectar_torre": {"profissao": "alquimia", "nivel": 7, "moedas": 2600, "xp": 300,
                     "materiais": {"fragmento_sino": 3}},
}


# ---------------------------------------------------------------- progressao

def xp_para_subir(nivel):
    """XP necessario para sair do nivel N para o N+1."""
    return 50 * nivel


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


def pode_fazer(j, chave, receita):
    if receita["nivel"] > j["prof_nivel"]:
        return False
    if j["moedas"] < receita["moedas"]:
        return False
    return not falta_material(j["user_id"], receita)


# ---------------------------------------------------- listagem de receitas (rpg receitas)
# Armas elementais (Pacote 2) viraram 24 receitas de Forja de uma vez — um
# field por receita estourou o limite de 25 fields do Discord. Agrupadas por
# "elemento" (game_data.ITENS[chave]["elemento"]) viram 6 fields; o resto (>25
# jogadores acumulando muito, ou catálogo crescendo mais) vai pra paginação
# genérica em paginacao.py. Ver decisoes.md § Paginação de embeds.
NOME_ELEMENTO = {"ar": "Ar", "raio": "Raio", "gelo": "Gelo", "fogo": "Fogo",
                  "sombrio": "Sombrio", "divino": "Divino"}
EMOJI_ELEMENTO = {"ar": "🌪️", "raio": "⚡", "gelo": "❄️", "fogo": "🔥",
                   "sombrio": "🌑", "divino": "✨"}


def _campo_receita(chave, receita, j):
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
             else f"cura {int(item['cura_pct'] * 100)}%" if "cura_pct" in item
             else f"restaura {int(item['mana_pct'] * 100)}% de mana")
    nome = f"{item['emoji']} {item['nome']} — {marca}"
    valor = f"{ganho}\n{texto_materiais(receita)} + {receita['moedas']} 🪙"
    return nome, valor


def _campo_elemento(elemento, pares, j):
    """pares: lista de (chave, receita) das 4 armas daquele elemento — todas
    com o mesmo custo/material, então mostra isso uma vez só no fim."""
    linhas = []
    for chave, receita in pares:
        item = ITENS[chave]
        pronto = pode_fazer(j, chave, receita)
        marca = "✅" if pronto else ("🔒" if receita["nivel"] > j["prof_nivel"] else "⬜")
        linhas.append(f"{marca} {item['emoji']} {item['nome']} (+{item['bonus']} {item['atributo'][:3].upper()})")
    _, receita_qualquer = pares[0]
    linhas.append(f"{texto_materiais(receita_qualquer)} + {receita_qualquer['moedas']} 🪙 cada")
    nome = f"{EMOJI_ELEMENTO[elemento]} {NOME_ELEMENTO[elemento]}"
    return nome, "\n".join(linhas)


def entradas_receitas(j, apenas_prontas):
    """Lista de (nome, valor) pra alimentar paginacao.enviar_paginado — as
    receitas normais uma a uma, as armas elementais agrupadas por elemento."""
    todas = sorted(receitas_da(j["profissao"]).items(), key=lambda kv: kv[1]["nivel"])
    normais = [(k, r) for k, r in todas if "elemento" not in ITENS[k]]
    elementais = [(k, r) for k, r in todas if "elemento" in ITENS[k]]

    entradas = []
    for chave, receita in normais:
        if apenas_prontas and not pode_fazer(j, chave, receita):
            continue
        entradas.append(_campo_receita(chave, receita, j))

    por_elemento = {}
    for chave, receita in elementais:
        por_elemento.setdefault(ITENS[chave]["elemento"], []).append((chave, receita))
    for elemento in ("ar", "raio", "gelo", "fogo", "sombrio", "divino"):
        pares = por_elemento.get(elemento)
        if not pares:
            continue
        if apenas_prontas:
            pares = [(k, r) for k, r in pares if pode_fazer(j, k, r)]
            if not pares:
                continue
        entradas.append(_campo_elemento(elemento, pares, j))
    return entradas


# ------------------------------------------------------------ melhoria/desmanche

def material_de_upgrade(item_chave):
    """O material do andar que custo_melhorar cobra para essa peca. Fonte
    unica pras duas funcoes -- refund_desmanche precisa saber exatamente essa
    chave pra so' bonificar, no desmanche, o material que a melhoria de fato
    gasta (ver decisoes.md, o bug do fragmento_selo)."""
    return ANDAR_MATERIAL[ITENS[item_chave]["andar_min"]]


def custo_melhorar(item_chave, alvo_nivel, eh_forjador):
    """(material, qtd, moedas) para tentar +1 ou +2 nesse item."""
    item = ITENS[item_chave]
    material = material_de_upgrade(item_chave)
    qtd = CUSTO_MATERIAL_UPGRADE[alvo_nivel]
    moedas = int(item["preco"] * CUSTO_PRECO_UPGRADE[alvo_nivel])
    if eh_forjador:
        qtd = max(1, int(qtd * (1 - DESCONTO_FORJADOR)))
        moedas = max(1, int(moedas * (1 - DESCONTO_FORJADOR)))
    return material, qtd, moedas


def refund_desmanche(item_chave, nivel_upgrade):
    """(materiais devolvidos, xp de oficio devolvido) ao desmanchar uma peca."""
    receita = RECEITAS.get(item_chave)
    material_upgrade = material_de_upgrade(item_chave)
    if receita:
        materiais_base = receita["materiais"]
        xp = int(receita["xp"] * PCT_XP_DESMANCHE)
    else:
        materiais_base = {material_upgrade: 3}
        xp = 0
    materiais = {
        mat: max(1, int(qtd * PCT_REFUND_DESMANCHE))
             + (nivel_upgrade if mat == material_upgrade else 0)
        for mat, qtd in materiais_base.items()
    }
    return materiais, xp


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
    async def receitas(ctx, *, argumento: str = ""):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not j["profissao"]:
            await ctx.send("Você ainda não escolheu um ofício. Manda `rpg profissao`.")
            return

        partes = argumento.split()
        modo_tudo = bool(partes) and H["normalizar"](partes[0]) == "tudo"
        resto = partes[1:] if modo_tudo else partes
        pagina = int(resto[0]) if resto and resto[0].isdigit() else 1

        dados = PROFISSOES[j["profissao"]]
        npc = bancada_no_andar(j["andar"], j["profissao"])
        onde = (f"Tem um aqui no andar {j['andar']}." if npc
                else f"Não tem nenhum no andar {j['andar']} — precisa viajar.")

        if modo_tudo:
            entradas = entradas_receitas(j, apenas_prontas=False)
            titulo = f"{dados['emoji']} Receitas de {dados['nome']} — lista completa"
            rodape_extra = "rpg craftar <item> <qtd>"
        else:
            entradas = entradas_receitas(j, apenas_prontas=True)
            titulo = f"{dados['emoji']} O que você pode fazer agora"
            rodape_extra = "rpg receitas tudo — lista completa · rpg craftar <item> <qtd>"

        await paginacao.enviar_paginado(
            ctx, entradas, titulo, ANDARES[j["andar"]]["cor"],
            descricao=f"Você trabalha na bancada do **{dados['npc']}**. {onde}",
            rodape_extra=rodape_extra, pagina_inicial=pagina,
            mensagem_vazia=(
                "Nada pronto pra fabricar agora — falta nível de ofício, moedas ou material. "
                "`rpg receitas tudo` mostra o catálogo inteiro."
            ),
        )

    @bot.command(name="craftar", aliases=["craft", "forjar", "fabricar"])
    @travas.fora_de_luta()
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

    @bot.command(name="melhorar", aliases=["upgrade", "aprimorar"])
    @travas.fora_de_luta()
    async def melhorar(ctx, *, argumento: str = ""):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return

        alvo = H["normalizar"](argumento)
        if alvo.startswith("armad"):
            slot = "armadura"
        elif alvo.startswith("arm"):
            slot = "arma"
        else:
            await ctx.send("Uso: `rpg melhorar arma` ou `rpg melhorar armadura`.")
            return

        item_chave = j[slot]
        if not item_chave:
            await ctx.send(f"Você não tem {slot} equipada pra melhorar.")
            return

        npc = bancada_no_andar(j["andar"], "forja")
        if not npc:
            await ctx.send(
                f"Precisa de um **ferreiro** pra isso, e não tem nenhum no andar {j['andar']}."
            )
            return

        nivel_atual = db.get_upgrade(j["user_id"], item_chave)
        if nivel_atual >= NIVEL_MAX_UPGRADE:
            await ctx.send(f"**{ITENS[item_chave]['nome']}** já está no teto: +{NIVEL_MAX_UPGRADE}.")
            return

        alvo_nivel = nivel_atual + 1
        eh_forjador = j["profissao"] == "forja"
        material, qtd_material, custo = custo_melhorar(item_chave, alvo_nivel, eh_forjador)

        if not db.tem_item(j["user_id"], material, qtd_material):
            tem = next((i["qtd"] for i in db.get_inventario(j["user_id"]) if i["item"] == material), 0)
            await ctx.send(
                f"Falta material: {ITENS[material]['emoji']} {ITENS[material]['nome']} "
                f"x{qtd_material - tem}."
            )
            return
        if j["moedas"] < custo:
            await ctx.send(f"Faltam **{custo - j['moedas']}** moedas para essa melhoria.")
            return

        db.remove_item(j["user_id"], material, qtd_material)
        campos = {"moedas": j["moedas"] - custo}

        chance = (CHANCE_UPGRADE_FORJADOR if eh_forjador else CHANCE_UPGRADE)[alvo_nivel]
        sucesso = random.random() < chance

        dados = PROFISSOES["forja"]
        e = discord.Embed(
            title=f"⚒️ Melhorar {ITENS[item_chave]['nome']} para +{alvo_nivel}",
            description=f"*{npc['nome']} espia a peça e decide se vale o risco.*",
            color=ANDARES[j["andar"]]["cor"],
        )
        e.add_field(
            name="Gasto",
            value=f"{ITENS[material]['emoji']} {ITENS[material]['nome']} x{qtd_material} + {custo} 🪙"
                  + (" (desconto de Forjador)" if eh_forjador else ""),
            inline=False,
        )

        if sucesso:
            db.set_upgrade(j["user_id"], item_chave, alvo_nivel)
            e.add_field(name="✅ Sucesso", value=f"Peça agora é **+{alvo_nivel}**.", inline=False)
            if eh_forjador:
                nivel, xp, subiu = aplicar_xp_profissao(
                    j["prof_nivel"], j["prof_xp"], XP_UPGRADE[alvo_nivel]
                )
                campos["prof_nivel"], campos["prof_xp"] = nivel, xp
                if subiu:
                    e.add_field(
                        name="⬆️ Ofício melhorou",
                        value=f"**{dados['nome']} nível {nivel}**.", inline=False,
                    )
        else:
            e.add_field(
                name="❌ Falhou",
                value="A peça não quebrou, mas o material e as moedas já foram gastos.",
                inline=False,
            )

        db.atualizar_jogador(j["user_id"], **campos)
        await ctx.send(embed=e)

    @bot.command(name="desmanchar", aliases=["desmontar", "sucatear"])
    @travas.fora_de_luta()
    async def desmanchar(ctx, *, argumento: str = ""):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not argumento:
            await ctx.send("Uso: `rpg desmanchar <item>`. Só equipamento, e não pode estar equipado.")
            return

        texto, vezes = H["separar_quantidade"](argumento)
        possuidos = [
            i["item"] for i in db.get_inventario(j["user_id"])
            if i["item"] in ITENS and ITENS[i["item"]]["tipo"] in ("arma", "armadura")
        ]
        item_chave = H["encontrar_item"](texto, possuidos)
        if not item_chave:
            fora = H["encontrar_item"](texto)
            if fora and ITENS[fora]["tipo"] not in ("arma", "armadura"):
                await ctx.send(f"**{ITENS[fora]['nome']}** não é equipamento — não dá pra desmanchar.")
            else:
                await ctx.send("Você não tem esse equipamento (sem estar equipado) na mochila.")
            return
        if not db.tem_item(j["user_id"], item_chave, vezes):
            await ctx.send(f"Você não tem {vezes}x **{ITENS[item_chave]['nome']}** sobrando na mochila.")
            return

        nivel_upgrade = db.get_upgrade(j["user_id"], item_chave)
        materiais, xp_peca = refund_desmanche(item_chave, nivel_upgrade)

        db.remove_item(j["user_id"], item_chave, vezes)
        for mat, qtd in materiais.items():
            db.add_item(j["user_id"], mat, qtd * vezes)
        db.set_upgrade(j["user_id"], item_chave, 0)

        texto_devolvido = " · ".join(
            f"{ITENS[m]['emoji']} {ITENS[m]['nome']} x{q * vezes}" for m, q in materiais.items()
        )
        e = discord.Embed(
            title=f"🔨 Desmanchou {ITENS[item_chave]['nome']}" + (f" x{vezes}" if vezes > 1 else ""),
            description=f"Devolveu {texto_devolvido}.",
            color=ANDARES[j["andar"]]["cor"],
        )
        if nivel_upgrade:
            e.add_field(name="Upgrade zerado", value=f"A peça estava +{nivel_upgrade}.", inline=False)

        if j["profissao"] == "forja" and xp_peca:
            ganho = xp_peca * vezes
            nivel, xp, subiu = aplicar_xp_profissao(j["prof_nivel"], j["prof_xp"], ganho)
            db.atualizar_jogador(j["user_id"], prof_nivel=nivel, prof_xp=xp)
            e.add_field(name="Ofício", value=f"+{ganho} XP de Forja.", inline=False)
            if subiu:
                e.add_field(name="⬆️ Ofício melhorou", value=f"**Forja nível {nivel}**.", inline=False)

        await ctx.send(embed=e)

    print("profissoes.py carregado — forja e alquimia no ar.")