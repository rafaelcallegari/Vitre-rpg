# dungeon.py
# Motor da dungeon do andar 9. Entrada, sorteio, persistência (sobrevive a
# restart da Discloud), avanço sala a sala, fim por morte, retomada, a
# camada de armadilha. SEM os espelhos de verdade, SEM o Orbe, SEM as
# skills de ascensão -- isso entra em fatias futuras, num pacote só, e só aí
# vai pra produção (deploy). `salas`/`indice` moram em dungeon_run
# (database.py); HP e mana são os do jogador de sempre, não uma cópia --
# regeneração fora de jogo vale dentro da dungeon.
#
# Segue o padrão H = {} / instalar(bot, contexto) de combate.py/raide.py
# (ver decisoes.md/arquitetura.md): as funções puras de estado (sortear,
# ler/criar/apagar run) usam só database.py/game_data.py, importados direto;
# só a resolução da sala de combate precisa de bot.py (stats, simular_combate,
# a_processar_morte, aplicar_xp...), e essas passam por H pra não criar
# import circular. `instalar(bot, contexto)` recebe `globals()` de bot.py
# inteiro, então H também tem `fmt_tempo`, `COOLDOWN_DUNGEON` etc.
import random

import discord

import atributos as at
import combate
import database as db
import game_data
import passivas

H = {}

_POOL_POR_CHAVE = {s["chave"]: s for s in game_data.DUNGEON_POOL}
_ESPOLIOS = [chave for chave, dado in game_data.ITENS.items() if dado.get("tipo") == "espolio"]

COR_DUNGEON = 0x4B0082
COR_ARMADILHA = 0x8B0000

COOLDOWN_DUNGEON = 900   # por RUN, contado na entrada -- ver decisoes.md § Dungeon -- cooldown


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


# ------------------------------------------------------------- armadilha
# Três portas, nesta ordem, pra todo personagem -- Percepção nunca dispara
# (só decide se dá pra escolher), Esquiva e Força só rolam se a porta
# anterior falhar. Usa os atributos BRUTOS do jogador (at.extrair, não
# `s["atribs"]`) de propósito -- anel/colar podem somar atributo, e a
# armadilha não pode virar algo que se compra com equipamento (só se upa).
# Ver decisoes.md § Dungeon -- pool e armadilha.

def _alvo_armadilha(nivel):
    return game_data.DUNGEON_ARMADILHA_DIFICULDADE_POR_NIVEL * nivel + game_data.DUNGEON_ARMADILHA_DIFICULDADE_BASE


def _passa_no_teste(valor_atributo, alvo):
    return valor_atributo + random.randint(1, 20) >= alvo


def _resolver_portas_armadilha(atribs, nivel):
    """Devolve "percepcao" | "esquiva" | "forca" | "falhou"."""
    alvo = _alvo_armadilha(nivel)
    if _passa_no_teste(atribs["inteligencia"], alvo):
        return "percepcao"
    if _passa_no_teste(atribs["destreza"], alvo):
        return "esquiva"
    if _passa_no_teste(atribs["forca"], alvo):
        return "forca"
    return "falhou"


def _sortear_condicao_armadilha():
    return dict(random.choice(game_data.DUNGEON_CONDICOES_ARMADILHA))


def _hp_atual(j, s):
    """Mesma regra de sempre pra HP não registrado (nunca jogou, ou morreu
    fora daqui): 30% do máximo, nunca <= 0."""
    return j["hp"] if j["hp"] > 0 else int(s["hp_max"] * 0.3)


def _aplicar_dano_armadilha(user_id, j, s):
    """Nunca mata -- piso em 1 HP. Traps não reusam processar_morte (ver
    decisoes.md): dano modesto, ponto de partida pra playtest, e integrar
    com o caminho de morte/penalidade duplicaria o que já existe pra
    combate. Devolve o dano aplicado.

    Muta `j["hp"]` em memória, além de gravar no banco -- se a mesma sala
    ainda for resolver um combate logo em seguida (dano_por_rodada da
    condição carregada bate ANTES do combate da sala, `_prosseguir_sala`),
    quem lê `j["hp"]` depois precisa ver o valor JÁ reduzido, não o
    instantâneo de antes de entrar na sala."""
    dano = max(1, int(game_data.DUNGEON_ARMADILHA_FRACAO_DANO * s["hp_max"]))
    hp_novo = max(1, _hp_atual(j, s) - dano)
    db.atualizar_jogador(user_id, hp=hp_novo)
    j["hp"] = hp_novo
    return dano


# ------------------------------------------------------------- resolução

async def resolver_sala_atual(ctx, j, run):
    """Resolve a sala em run['indice'] e avança (ou encerra) a run. Chamada
    tanto pra run recém-criada quanto pra uma retomada."""
    s = H["stats"](j)
    sala = sala_atual(run)
    condicao = db.consumir_condicao_armadilha(j["user_id"])
    if sala["armadilha"]:
        await _resolver_armadilha(ctx.send, j, s, run, sala, condicao, ctx.author.id)
        return
    await _prosseguir_sala(ctx.send, j, s, run, sala, condicao, linhas_extra=[])


async def _resolver_armadilha(enviar, j, s, run, sala, condicao, user_id):
    """A sala anuncia nome e texto -- nunca a armadilha. Ela dispara na
    interação, não no rótulo. Ver decisoes.md."""
    resultado = _resolver_portas_armadilha(at.extrair(j), j["nivel"])
    if resultado == "percepcao":
        e = discord.Embed(title=sala["nome"], color=COR_ARMADILHA)
        e.description = sala["texto"] + "\n\nAlgo aqui não está certo -- você percebe antes de encostar."
        view = _ViewEscolhaArmadilha(user_id, j, s, run, sala, condicao)
        await enviar(embed=e, view=view)
        return
    linhas_extra = []
    if resultado == "esquiva":
        linhas_extra.append("💨 Você sente o mecanismo se mover e sai de cima a tempo -- ileso.")
    elif resultado == "forca":
        dano = _aplicar_dano_armadilha(user_id, j, s)
        linhas_extra.append(f"💥 Você não escapa a tempo, mas arrebenta o mecanismo com força — **{dano}** de dano, nada além disso.")
    else:
        dano = _aplicar_dano_armadilha(user_id, j, s)
        nova_condicao = _sortear_condicao_armadilha()
        db.definir_condicao_armadilha(user_id, nova_condicao)
        linhas_extra.append(
            f"💥 A armadilha pega em cheio — **{dano}** de dano. "
            f"{nova_condicao['emoji']} **{nova_condicao['nome']}** segue com você pra próxima sala."
        )
    await _prosseguir_sala(enviar, j, s, run, sala, condicao, linhas_extra)


async def _resolver_desarmar(enviar, j, s, run, sala, condicao, user_id):
    """Desarmar dá espólio GARANTIDO (sem rolagem) -- Instinto de Ladrão
    mexe em CHANCE/quantidade (ver passivas.bonus_material), então não
    tem o que aumentar aqui; a passiva entra nos achados de verdade
    (rolagem probabilística), não nesta recompensa fixa."""
    espolio = random.choice(_ESPOLIOS)
    dado = game_data.ITENS[espolio]
    db.add_item(user_id, espolio)
    linhas_extra = [f"🔧 Você desarma o mecanismo e leva o espólio: {dado['emoji']} **{dado['nome']}**."]
    await _prosseguir_sala(enviar, j, s, run, sala, condicao, linhas_extra)


async def _resolver_contornar(enviar, j, s, run, sala, condicao):
    linhas_extra = ["🚶 Você contorna sem tocar em nada."]
    await _prosseguir_sala(enviar, j, s, run, sala, condicao, linhas_extra)


async def _prosseguir_sala(enviar, j, s, run, sala, condicao, linhas_extra):
    """`enviar` é uma função `async def enviar(*, embed, view=None)` --
    `ctx.send` no caminho normal, o followup de uma interação de botão na
    escolha da Percepção -- pra dividir o MESMO caminho de resolução do
    conteúdo (combate/evento/achado) não importa de onde ele foi chamado.

    A condição da armadilha que sobrou da sala ANTERIOR (`condicao`) foi
    consumida no início de `resolver_sala_atual` (uma vez só, não importa
    o tipo desta sala). `dano_por_rodada` bate aqui, na abertura desta
    sala, direto -- é o único tipo sorteado que faz sentido fora de
    combate; `vulneravel`/`chance_erro` só têm efeito se ESTA sala for de
    combate (ver `_aplicar_condicao_no_combate`)."""
    if condicao and condicao["tipo"] == "dano_por_rodada":
        dano = _aplicar_dano_armadilha(j["user_id"], j, s)   # mesma fórmula de dano, piso em 1
        linhas_extra.append(f"{condicao['emoji']} **{condicao['nome']}** cobra o preço — **{dano}** de dano.")
        condicao = None
    if sala["tipo"] == "combate":
        await _resolver_combate(enviar, j, s, run, sala, condicao, linhas_extra)
    else:
        await _resolver_sem_combate(enviar, j, run, sala, linhas_extra)


def _montar_descricao(sala, linhas_extra, log=None):
    """Texto da sala + qualquer linha extra (armadilha, condição que
    atravessou) + o log de combate, se houver -- essa ordem sempre, pra
    quem lê entender a sequência dos eventos."""
    partes = [sala["texto"]] + linhas_extra
    if log:
        partes.append("\n".join(log))
    return "\n\n".join(partes)


def _aplicar_condicao_no_combate(condicao, s, mob):
    """Vulnerável/Tontura (armadilha) modificam só ESTA luta -- cópias de
    `s`/`mob`, o jogador de verdade nunca é tocado por isto. Sem Luta
    aqui pra aplicar a condição de verdade (ver condicoes.py), então o
    efeito de 2 rodadas nominal vira "essa luta inteira" -- aproximação
    deliberada, documentada em decisoes.md."""
    if not condicao:
        return s, mob
    s, mob = dict(s), dict(mob)
    if condicao["tipo"] == "vulneravel":
        mob["atk"] = int(mob["atk"] * (1 + condicao["valor"]))
    elif condicao["tipo"] == "chance_erro":
        s["atk"] = int(s["atk"] * (1 - condicao["valor"]))
    return s, mob


async def _resolver_combate(enviar, j, s, run, sala, condicao, linhas_extra):
    andar = game_data.ANDARES[9]
    mob = random.choice(andar["monstros"])
    s_luta, mob_luta = _aplicar_condicao_no_combate(condicao, s, mob)
    hp = _hp_atual(j, s)
    hp_final, venceu, log = H["simular_combate"](s_luta, hp, mob_luta, 9)

    e = discord.Embed(title=f"{sala['nome']} — {mob['nome']}", color=COR_DUNGEON)
    e.description = _montar_descricao(sala, linhas_extra, log)

    if not venceu:
        # Auto-ressurreição (clérigo) tem que rodar ANTES de
        # processar_morte(na_dungeon=True) -- senão a run já foi apagada e
        # a penalidade já foi cobrada de alguém que, na verdade, não
        # morreu. Sem Luta aqui (a dungeon usa simular_combate, instantâneo
        # -- ver cabeçalho do arquivo): o contador `auto_ressurreicao_usada`
        # de combate.Luta (uma vez por LUTA) não alcança aqui, então o
        # gasto mora na PRÓPRIA dungeon_run (coluna `auto_ressurreicao_usada`,
        # migração 18) -- uma vez por RUN inteira, não uma vez por sala.
        # `rpg dungeon sair` + recomeçar apaga a run e cria outra, zerando
        # o gasto de propósito. Ver decisoes.md § Step 2d.
        if passivas.e_clerigo(j) and not run["auto_ressurreicao_usada"]:
            hp_revivido = int(combate.FRACAO_HP_AUTO_RESSURREICAO * s["hp_max"])
            db.atualizar_jogador(j["user_id"], hp=hp_revivido)
            db.marcar_dungeon_run_ressuscitou(j["user_id"])
            e.color = COR_ARMADILHA
            e.add_field(
                name="✨ Você se recusa a cair",
                value=(
                    f"A auto-ressurreição do clérigo te traz de volta com **{hp_revivido}** HP. "
                    f"Foi a única vez que vale nesta run -- chame `rpg dungeon` de novo pra tentar "
                    f"esta sala outra vez."
                ),
                inline=False,
            )
            await enviar(embed=e)
            return
        perda = await H["a_processar_morte"](j, s, na_dungeon=True)
        e.color = COR_ARMADILHA
        e.add_field(
            name="Você caiu na dungeon",
            value=f"Perdeu **{perda}** 🪙 e acordou no ponto de retorno com 30% de HP. A run foi encerrada.",
            inline=False,
        )
        await enviar(embed=e)
        return

    nivel, xp, subiu = H["aplicar_xp"](j, mob["xp"])
    drops = H["rolar_drops"](mob, passivas.bonus_material(j))
    for item in drops:
        db.add_item(j["user_id"], item)
    hp_final = H["hp_depois_do_nivel"](hp_final, nivel, subiu, s["atribs"])
    bonus_moedas = mob["moedas"] + int(mob["moedas"] * passivas.bonus_moedas(j))
    db.atualizar_jogador(
        j["user_id"], hp=hp_final, xp=xp, nivel=nivel,
        pontos=H["pontos_por_subir"](j, subiu), moedas=j["moedas"] + bonus_moedas,
    )
    recompensa = f"+{mob['xp']} XP · +{bonus_moedas} 🪙"
    if drops:
        recompensa += "\n" + "\n".join(f"{game_data.ITENS[i]['emoji']} {game_data.ITENS[i]['nome']}" for i in drops)
    e.add_field(name="Vitória", value=recompensa, inline=False)
    await _concluir_sala(enviar, j["user_id"], run, e)


async def _resolver_sem_combate(enviar, j, run, sala, linhas_extra):
    """evento/achado: só a narrativa avança a sala nesta fatia -- o
    conteúdo mecânico de verdade (Orbe, espelhos, skills de ascensão,
    os dois botões do evento, a diferenciação do achado) entra em
    cartões seguintes, ver decisoes.md."""
    e = discord.Embed(title=sala["nome"], description=_montar_descricao(sala, linhas_extra), color=COR_DUNGEON)
    await _concluir_sala(enviar, j["user_id"], run, e)


async def _concluir_sala(enviar, user_id, run, embed):
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
    await enviar(embed=embed)


# ------------------------------------------------------------- botões

class _ViewEscolhaArmadilha(discord.ui.View):
    """Percepção passou: desarmar (leva o mecanismo como espólio) ou
    contornar (segue sem nada) -- botões, como o evento. Só o dono da run
    pode clicar; os dois desativam depois de um clique."""

    def __init__(self, user_id, j, s, run, sala, condicao):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.j, self.s, self.run, self.sala, self.condicao = j, s, run, sala, condicao
        self.add_item(_BotaoArmadilha("desarmar", "🔧 Desarmar"))
        self.add_item(_BotaoArmadilha("contornar", "🚶 Contornar"))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Essa run não é sua.", ephemeral=True)
            return False
        return True


class _BotaoArmadilha(discord.ui.Button):
    def __init__(self, escolha, label):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.escolha = escolha

    async def callback(self, interaction):
        await interaction.response.defer()
        view: _ViewEscolhaArmadilha = self.view
        for item in view.children:
            item.disabled = True
        await interaction.edit_original_response(view=view)

        async def enviar(*, embed, view=None):
            kwargs = {"embed": embed}
            if view is not None:
                kwargs["view"] = view
            await interaction.followup.send(**kwargs)

        if self.escolha == "desarmar":
            await _resolver_desarmar(enviar, view.j, view.s, view.run, view.sala, view.condicao, view.user_id)
        else:
            await _resolver_contornar(enviar, view.j, view.s, view.run, view.sala, view.condicao)


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
        restante = db.checar_cooldown(j["user_id"], "dungeon")
        if restante > 0:
            await ctx.send(f"⏳ `rpg dungeon` volta em **{H['fmt_tempo'](restante)}**.")
            return
        db.set_cooldown(j["user_id"], "dungeon", COOLDOWN_DUNGEON)
        run = criar_run(j["user_id"])
    await resolver_sala_atual(ctx, j, run)


async def _executar_sair(ctx, j):
    if obter_run(j["user_id"]) is None:
        await ctx.send("Você não está em nenhuma dungeon agora.")
        return
    sair(j["user_id"])
    await ctx.send("Você saiu da dungeon sem penalidade. O cooldown desta run continua contando -- sair não devolve o tempo.")


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

    print("dungeon.py carregado — motor da dungeon do andar 9 (pool de dez salas + armadilha).")
