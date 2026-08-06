# habilidades.py
# Infraestrutura do sistema de habilidades: quem conhece o quê, afinidade de
# arma, e o comando pra ver a lista fora de combate. O catálogo em si
# (game_data.HABILIDADES) está vazio de propósito — isso é só o motor.
# O botão de lançar dentro da luta de chefe vive em combate.py, porque
# depende do estado da luta (mana do combatente, turno).

import discord

from game_data import CLASSES, HABILIDADES

H = {}

FATOR_FORA_DE_AFINIDADE = 0.5  # placeholder — calibrar quando as primeiras skills existirem


# ------------------------------------------------------------ conhecimento

def extras_de(jogador):
    """Chaves de habilidade destravadas por sidequest (não por atributo)."""
    return set(t for t in (jogador["habilidades_extras"] or "").split(",") if t)


def conhecida(jogador, chave, dados, extras=None):
    """Sem requisito = vem da classe. Com requisito = precisa do atributo.
    Marcada como sidequest = só conta se estiver em habilidades_extras,
    não importa o atributo."""
    if dados.get("sidequest"):
        extras = extras_de(jogador) if extras is None else extras
        return chave in extras
    requisito = dados.get("requisito")
    if not requisito:
        return True
    atributo, minimo = requisito
    return int(jogador[atributo] or 0) >= minimo


def habilidades_da_classe(classe):
    return {k: v for k, v in HABILIDADES.items() if v["classe"] == classe}


def conhecidas(jogador):
    """Habilidades da classe do jogador que ele já destravou."""
    if not jogador["classe"]:
        return {}
    extras = extras_de(jogador)
    return {
        k: v for k, v in habilidades_da_classe(jogador["classe"]).items()
        if conhecida(jogador, k, v, extras)
    }


def lancaveis(jogador, mana_atual):
    """Das conhecidas, quais cabem na mana disponível agora."""
    return {k: v for k, v in conhecidas(jogador).items() if v["custo_mana"] <= mana_atual}


# --------------------------------------------------------------- afinidade

def fator_afinidade(classe, arma):
    """1.0 com a arma da afinidade da classe; reduzido fora dela.

    Nada é proibido — jogar fora da afinidade só rende menos.
    """
    dados = CLASSES.get(classe)
    if not dados:
        return 1.0
    arma_atributo = (arma or {}).get("atributo", "destreza")
    return 1.0 if arma_atributo == dados["afinidade_arma"] else FATOR_FORA_DE_AFINIDADE


# ---------------------------------------------------------------- instalacao

def instalar(bot, contexto):
    H.update(contexto)

    @bot.command(name="habilidades", aliases=["skills", "magias", "habilidade"])
    async def habilidades_cmd(ctx):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not j["classe"]:
            await ctx.send("Você ainda não escolheu uma classe. `rpg classe` mostra as opções.")
            return

        dados_classe = CLASSES[j["classe"]]
        conhec = conhecidas(j)
        e = discord.Embed(
            title=f"{dados_classe['emoji']} Habilidades de {dados_classe['nome']}",
            color=0x6A4C93,
        )
        if not conhec:
            e.description = (
                "Nenhuma habilidade no jogo ainda — só a infraestrutura está pronta "
                "(mana, requisito, afinidade de arma). O catálogo vem depois."
            )
        else:
            for chave, d in conhec.items():
                e.add_field(
                    name=f"{d['emoji']} {d['nome']} — {d['custo_mana']} mana",
                    value=d["desc"],
                    inline=False,
                )
        e.set_footer(text="Só é possível lançar em luta de chefe — rpg boss")
        await ctx.send(embed=e)

    print("habilidades.py carregado — infraestrutura de skills, catálogo vazio.")
