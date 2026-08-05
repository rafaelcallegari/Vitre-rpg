# efeitos.py
# Efeitos temporarios contados em COMBATES, nao em minutos — o bot cai junto
# com o PC, e buff por tempo evaporaria sem ter sido usado.
# Mesmo padrao do combate.py: dict H, nao importa bot.py.

import discord

import database as db

H = {}

MAX_ATIVOS = 2          # quantos efeitos podem coexistir

CATALOGO = {
    "furia": {
        "nome": "Fúria", "emoji": "⚔️",
        "desc": "aumenta o dano dos seus golpes",
        "aplica": "atk",
    },
    "sorte": {
        "nome": "Sorte", "emoji": "🍀",
        "desc": "aumenta a chance de drop dos monstros",
        "aplica": "drop",
    },
    "guarda": {
        "nome": "Guarda", "emoji": "🛡️",
        "desc": "aumenta a sua defesa",
        "aplica": "def",
    },
}


# ---------------------------------------------------------------- consultas

def ativos(user_id):
    """{chave: {"valor": 0.25, "restantes": 4}} — só o que ainda vale."""
    return {k: v for k, v in db.get_efeitos(user_id).items() if k in CATALOGO}


def multiplicador(user_id, alvo, cache=None):
    """Quanto multiplicar `atk`, `def` ou `drop`. 1.0 = sem efeito."""
    tabela = cache if cache is not None else ativos(user_id)
    fator = 1.0
    for chave, dados in tabela.items():
        if CATALOGO[chave]["aplica"] == alvo:
            fator *= 1 + dados["valor"]
    return fator


def aplicar_em_stats(jogador, s):
    """Deixa atk e def já com os efeitos embutidos.

    Fazendo aqui, todo o resto do jogo (caçada, chefe, party, perfil) enxerga
    o valor com buff sem precisar saber que efeitos existem.
    """
    tabela = ativos(jogador["user_id"])
    if not tabela:
        s["efeitos"] = {}
        return s
    s["atk"] = int(s["atk"] * multiplicador(None, "atk", tabela))
    s["def"] = int(s["def"] * multiplicador(None, "def", tabela))
    s["efeitos"] = tabela
    return s


def bonus_drop(user_id, cache=None):
    """Fator que multiplica a chance de cada drop."""
    return multiplicador(user_id, "drop", cache)


# ------------------------------------------------------------------ escrita

def conceder(user_id, efeito, valor, combates):
    """Aplica um efeito. Devolve (ok, mensagem)."""
    if efeito not in CATALOGO:
        return False, "Esse efeito não existe."
    tabela = ativos(user_id)
    if efeito not in tabela and len(tabela) >= MAX_ATIVOS:
        nomes = ", ".join(CATALOGO[k]["nome"] for k in tabela)
        return False, (
            f"Você já está com {MAX_ATIVOS} efeitos ativos ({nomes}). "
            f"Espere um deles acabar."
        )
    renovou = efeito in tabela
    db.set_efeito(user_id, efeito, valor, combates)
    dados = CATALOGO[efeito]
    verbo = "renovado" if renovou else "ativo"
    return True, (
        f"{dados['emoji']} **{dados['nome']}** {verbo} — +{int(valor * 100)}% "
        f"pelos próximos **{combates}** combates."
    )


def consumir(user_id):
    """Um combate a menos em tudo que estiver ativo."""
    db.consumir_efeitos(user_id)


# ------------------------------------------------------------------ display

def resumo(user_id, tabela=None):
    """Linha curta para o rodapé do perfil. Vazio se não houver nada."""
    tabela = tabela if tabela is not None else ativos(user_id)
    if not tabela:
        return ""
    return " · ".join(
        f"{CATALOGO[k]['emoji']} {CATALOGO[k]['nome']} +{int(v['valor'] * 100)}% "
        f"({v['restantes']})"
        for k, v in tabela.items()
    )


def instalar(bot, contexto):
    H.update(contexto)

    @bot.command(name="efeitos", aliases=["buffs", "efeito"])
    async def efeitos_cmd(ctx):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        tabela = ativos(j["user_id"])
        e = discord.Embed(
            title=f"Efeitos de {j['nome']}",
            color=0x9D4EDD,
        )
        if not tabela:
            e.description = (
                "Nenhum efeito ativo.\n\n"
                "Poções de efeito são fabricadas por quem tem **Alquimia** "
                "(`rpg receitas`). Você pode ter até "
                f"**{MAX_ATIVOS}** ao mesmo tempo."
            )
        else:
            e.description = f"Até {MAX_ATIVOS} efeitos ao mesmo tempo."
            for chave, dados in tabela.items():
                info = CATALOGO[chave]
                e.add_field(
                    name=f"{info['emoji']} {info['nome']} +{int(dados['valor'] * 100)}%",
                    value=f"{info['desc']}\nAcaba em **{dados['restantes']}** combate(s)",
                    inline=False,
                )
            e.set_footer(text="A contagem cai a cada caçada, exploração ou chefe.")
        await ctx.send(embed=e)

    print("efeitos.py carregado — buffs contados em combates.")