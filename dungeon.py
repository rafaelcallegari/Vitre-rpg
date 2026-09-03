# dungeon.py
# Motor da dungeon do andar 9 (fatia 1/4 -- ver decisoes.md). Entrada,
# sorteio, persistência (sobrevive a restart da Discloud), avanço sala a
# sala, fim por morte, retomada. SEM os espelhos de verdade, SEM o Orbe, SEM
# as skills de ascensão -- isso entra nas fatias 2-4, num pacote só, e só aí
# vai pra produção (deploy). `salas`/`indice` moram em dungeon_run
# (database.py); HP e mana são os do jogador de sempre, não uma cópia --
# regeneração fora de jogo vale dentro da dungeon.
#
# Segue o padrão H = {} / instalar(bot, contexto) de combate.py/raide.py
# (ver decisoes.md/arquitetura.md): as funções puras de estado (sortear,
# ler/criar/apagar run) usam só database.py/game_data.py, importados direto;
# só a resolução da sala de combate precisa de bot.py (stats, simular_combate,
# a_processar_morte, aplicar_xp...), e essas passam por H pra não criar
# import circular.
import random

import discord

import database as db
import game_data

H = {}

_POOL_POR_CHAVE = {s["chave"]: s for s in game_data.DUNGEON_POOL}

COR_DUNGEON = 0x4B0082


def sortear_salas():
    chaves = [s["chave"] for s in game_data.DUNGEON_POOL]
    return random.sample(chaves, game_data.DUNGEON_SALAS_POR_RUN)


def obter_run(user_id):
    return db.get_dungeon_run(user_id)


def tem_run_aberta(user_id):
    return obter_run(user_id) is not None


def criar_run(user_id):
    db.criar_dungeon_run(user_id, sortear_salas())
    return obter_run(user_id)


def sair(user_id):
    db.apagar_dungeon_run(user_id)


def sala_atual(run):
    return _POOL_POR_CHAVE[run["salas"][run["indice"]]]


# ------------------------------------------------------------- resolução

async def resolver_sala_atual(ctx, j, run):
    """Resolve a sala em run['indice'] e avança (ou encerra) a run. Chamada
    tanto pra run recém-criada quanto pra uma retomada."""
    s = H["stats"](j)
    sala = sala_atual(run)
    if sala["tipo"] == "combate":
        await _resolver_combate(ctx, j, s, run, sala)
    else:
        await _resolver_sem_combate(ctx, run, sala)


async def _resolver_combate(ctx, j, s, run, sala):
    andar = game_data.ANDARES[9]
    mob = random.choice(andar["monstros"])
    hp = j["hp"] if j["hp"] > 0 else int(s["hp_max"] * 0.3)
    hp_final, venceu, log = H["simular_combate"](s, hp, mob, 9)

    e = discord.Embed(title=f"{sala['nome']} — {mob['nome']}", color=COR_DUNGEON)
    e.description = sala["texto"] + "\n\n" + "\n".join(log)

    if not venceu:
        perda = await H["a_processar_morte"](j, s, na_dungeon=True)
        e.color = 0x8B0000
        e.add_field(
            name="Você caiu na dungeon",
            value=f"Perdeu **{perda}** 🪙 e acordou no ponto de retorno com 30% de HP. A run foi encerrada.",
            inline=False,
        )
        await ctx.send(embed=e)
        return

    nivel, xp, subiu = H["aplicar_xp"](j, mob["xp"])
    drops = H["rolar_drops"](mob)
    for item in drops:
        db.add_item(j["user_id"], item)
    hp_final = H["hp_depois_do_nivel"](hp_final, nivel, subiu, s["atribs"])
    db.atualizar_jogador(
        j["user_id"], hp=hp_final, xp=xp, nivel=nivel,
        pontos=H["pontos_por_subir"](j, subiu), moedas=j["moedas"] + mob["moedas"],
    )
    recompensa = f"+{mob['xp']} XP · +{mob['moedas']} 🪙"
    if drops:
        recompensa += "\n" + "\n".join(f"{game_data.ITENS[i]['emoji']} {game_data.ITENS[i]['nome']}" for i in drops)
    e.add_field(name="Vitória", value=recompensa, inline=False)
    await _concluir_sala(ctx, j["user_id"], run, e)


async def _resolver_sem_combate(ctx, run, sala):
    """evento/armadilha/achado nesta fatia: só a narrativa avança a sala,
    sem efeito mecânico -- o conteúdo de verdade (Orbe, espelhos, skills de
    ascensão) entra nas fatias seguintes, ver decisoes.md."""
    e = discord.Embed(title=sala["nome"], description=sala["texto"], color=COR_DUNGEON)
    await _concluir_sala(ctx, run["user_id"], run, e)


async def _concluir_sala(ctx, user_id, run, embed):
    novo_indice = run["indice"] + 1
    if novo_indice >= game_data.DUNGEON_SALAS_POR_RUN:
        sair(user_id)
        embed.add_field(
            name="🏆 Dungeon concluída",
            value="Você atravessou as 5 salas. (Recompensa de conclusão entra numa fatia futura.)",
            inline=False,
        )
    else:
        db.atualizar_dungeon_run_indice(user_id, novo_indice)
        proxima = _POOL_POR_CHAVE[run["salas"][novo_indice]]
        embed.add_field(
            name=f"Sala {novo_indice + 1}/{game_data.DUNGEON_SALAS_POR_RUN}",
            value=f"Chame `rpg dungeon` de novo pra seguir — {proxima['nome']} espera.",
            inline=False,
        )
    await ctx.send(embed=embed)


# ------------------------------------------------------------- comando

async def _executar_entrar_ou_continuar(ctx, j):
    run = obter_run(j["user_id"])
    if run is None:
        if j["andar"] != 9:
            await ctx.send(
                "A dungeon só abre pra quem está fisicamente no andar 9 — "
                f"você está no andar {j['andar']}. `rpg viajar 9` primeiro."
            )
            return
        if j["nivel"] < game_data.NIVEL_ASCENSAO_PADRAO:
            await ctx.send(
                f"A dungeon é o portão da ascensão — abre só a partir do nível "
                f"{game_data.NIVEL_ASCENSAO_PADRAO} (você é nível {j['nivel']})."
            )
            return
        run = criar_run(j["user_id"])
    await resolver_sala_atual(ctx, j, run)


async def _executar_sair(ctx, j):
    if obter_run(j["user_id"]) is None:
        await ctx.send("Você não está em nenhuma dungeon agora.")
        return
    sair(j["user_id"])
    await ctx.send("Você saiu da dungeon sem penalidade.")


def instalar(bot, contexto):
    H.update(contexto)

    @bot.hybrid_group(
        name="dungeon", aliases=["dg", "masmorra"], fallback="entrar",
        description="Entra ou continua na dungeon do andar 9 (nível 15+).",
    )
    async def dungeon_cmd(ctx, *, argumento: str = ""):
        """`rpg dungeon sair` digitado aqui como texto livre continua
        funcionando (é o que o teste de callback direto exercita), mas quem
        chama por slash usa o subcomando `sair` de verdade, logo abaixo --
        mesmo padrão de `rpg profissao trocar`, ver decisoes.md § comandos
        híbridos (leva 1)."""
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        acao = H["normalizar"](argumento.strip()) if argumento.strip() else ""
        if acao in ("sair", "leave", "cancelar"):
            await _executar_sair(ctx, j)
            return
        await _executar_entrar_ou_continuar(ctx, j)

    @dungeon_cmd.command(
        name="sair", aliases=["leave", "cancelar"],
        description="Abandona a run da dungeon sem penalidade.",
    )
    async def dungeon_sair(ctx):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        await _executar_sair(ctx, j)

    print("dungeon.py carregado — motor da dungeon do andar 9 (fatia 1/4, sem deploy ainda).")
