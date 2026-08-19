# raide.py
# Raide de guilda: chefe fixo, fora da progressão da torre. Reusa o motor de
# combate de combate.py (Combatente, Luta, PainelLuta) em vez de duplicá-lo —
# só a sala de espera (restrita a membros da guilda) e a recompensa (tudo pro
# baú, nada de andar/XP individual) são diferentes. Precisa vir depois de
# combate.instalar() no wiring de bot.py, porque usa combate.H por baixo.

import random

import discord

import atributos as at
import combate
import condicoes
import database as db
import salao
import travas
from game_data import (
    ITENS, RAIDE_CHEFE, ANDAR_MINIMO_RAIDE, ANDAR_REFERENCIA_RAIDE,
    RECOMPENSA_MOEDAS_RAIDE, QTD_ACESSORIOS_RAIDE, ACESSORIOS_RAIDE,
)
from guildas import MEMBROS_PARA_VALER

H = {}

MIN_PARTICIPANTES_RAIDE = 3
COR_RAIDE = 0x6B2D5C   # roxo real — tom de audiência, não a cor do andar 7


# ------------------------------------------------------------ recompensa
async def recompensar_raide(combatente):
    """HP e mana cheios pra quem sobreviveu — sem XP, moedas ou andar
    individual. Tudo que a raide rende vai pro baú da guilda."""
    j, s = combatente.jogador, combatente.s
    db.atualizar_jogador(j["user_id"], hp=s["hp_max"], mana=s["mana_max"])


async def finalizar_vitoria_raide(luta, guilda_id, iniciador_id):
    luta.encerrada = True
    vencedores = [c for c in luta.participantes if c.ativo]
    for c in vencedores:
        await recompensar_raide(c)

    n = min(QTD_ACESSORIOS_RAIDE, len(ACESSORIOS_RAIDE))
    acessorios = random.sample(ACESSORIOS_RAIDE, n) if n else []
    for chave in acessorios:
        db.bau_add_item(guilda_id, chave, 1)
    db.guilda_add_moedas(guilda_id, RECOMPENSA_MOEDAS_RAIDE)
    db.guilda_log(guilda_id, iniciador_id, "raide", None, RECOMPENSA_MOEDAS_RAIDE)

    e = luta.embed(
        titulo=f"Audiência encerrada — {RAIDE_CHEFE['nome']} cai",
        cor=COR_RAIDE,
        rodape=f"Luta encerrada na rodada {luta.rodada}. Quem sobreviveu recuperou HP e mana.",
    )
    nomes = ", ".join(f"{ITENS[c]['emoji']} {ITENS[c]['nome']}" for c in acessorios) or "nenhum acessório dessa vez"
    e.add_field(
        name="Foi tudo pro baú da guilda — não pra mochila de ninguém",
        value=f"🪙 {RECOMPENSA_MOEDAS_RAIDE} moedas\n{nomes}",
        inline=False,
    )
    return e


# ------------------------------------------------------------------ painel
class PainelRaide(combate.PainelLuta):
    def __init__(self, luta, guilda_id, iniciador_id):
        super().__init__(luta)
        self.guilda_id = guilda_id
        self.iniciador_id = iniciador_id

    def _continuar(self, luta):
        return PainelRaide(luta, self.guilda_id, self.iniciador_id)

    async def fim_da_luta(self, interaction=None):
        luta = self.luta
        if luta.hp_chefe <= 0:
            return await finalizar_vitoria_raide(luta, self.guilda_id, self.iniciador_id)
        if not luta.ativos:
            if any(c.caiu for c in luta.participantes) and not any(
                c.fugiu or c.saiu for c in luta.participantes
            ):
                return await combate.finalizar_derrota(luta)
            return await combate.encerrar_por_abandono(luta)
        return None


# ------------------------------------------------------------ sala de espera
class SalaDeEsperaRaide(discord.ui.View):
    """Igual em espírito à SalaDeEspera de combate.py, mas o Entrar só aceita
    quem é da mesma guilda — não escrevi como subclasse porque validar(),
    embed() e o mínimo de participantes são diferentes o bastante pra a
    herança não ajudar muito."""

    def __init__(self, anfitriao_id, guilda, jogador_anfitriao):
        super().__init__(timeout=combate.TIMEOUT_SALA)
        self.anfitriao_id = anfitriao_id
        self.guilda = guilda
        self.inscritos = [jogador_anfitriao["user_id"]]
        self.mensagem = None
        self.comecou = False

    def embed(self):
        nomes = []
        for uid in self.inscritos:
            j = db.get_jogador(uid)
            nomes.append(f"• **{j['nome']}** — nível {j['nivel']}")
        e = discord.Embed(
            title=f"Audiência com {RAIDE_CHEFE['nome']}",
            description=(
                f"Guilda **{self.guilda['nome']}**. Ela entra com "
                f"**{RAIDE_CHEFE['hp']} HP por pessoa** — mínimo de "
                f"{MIN_PARTICIPANTES_RAIDE} pra abrir a audiência, e precisa ter "
                f"destrancado o andar {ANDAR_MINIMO_RAIDE}.\n\n"
                "Tudo que ela derrubar vai pro baú da guilda, não pra mochila de ninguém."
            ),
            color=COR_RAIDE,
        )
        e.add_field(
            name=f"Na sala ({len(self.inscritos)}/{combate.MAX_PARTY})",
            value="\n".join(nomes), inline=False,
        )
        e.set_footer(
            text=f"{combate.TIMEOUT_SALA}s pra fechar · só quem abriu pode começar"
        )
        return e

    async def validar(self, interaction, j):
        guilda_dele = db.guilda_do_membro(j["user_id"])
        if not guilda_dele or guilda_dele["id"] != self.guilda["id"]:
            await interaction.response.send_message(
                "Só membros da guilda entram nessa audiência.", ephemeral=True
            )
            return False
        if j["andar_max"] < ANDAR_MINIMO_RAIDE:
            await interaction.response.send_message(
                f"Precisa ter destrancado o andar {ANDAR_MINIMO_RAIDE}.", ephemeral=True
            )
            return False
        s = H["stats"](j)
        if j["hp"] < s["hp_max"] * combate.HP_MINIMO_PARA_ENTRAR:
            await interaction.response.send_message(
                f"Você está com {max(0, j['hp'])}/{s['hp_max']}. Cure antes de entrar.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Entrar", emoji="🤝", style=discord.ButtonStyle.success)
    async def entrar(self, interaction, button):
        if self.comecou:
            await interaction.response.send_message("A audiência já começou.", ephemeral=True)
            return
        if interaction.user.id in self.inscritos:
            await interaction.response.send_message("Você já está na sala.", ephemeral=True)
            return
        if len(self.inscritos) >= combate.MAX_PARTY:
            await interaction.response.send_message("A sala está cheia.", ephemeral=True)
            return
        j = db.get_jogador(interaction.user.id)
        if not j:
            await interaction.response.send_message(
                "Você ainda não entrou na torre. Manda `rpg comecar`.", ephemeral=True
            )
            return
        if not await self.validar(interaction, j):
            return
        self.inscritos.append(j["user_id"])
        await combate.responder(interaction, self.embed(), self)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.secondary)
    async def sair(self, interaction, button):
        if interaction.user.id == self.anfitriao_id:
            await interaction.response.send_message(
                "Quem abriu a sala não pode sair — cancele deixando o tempo acabar.",
                ephemeral=True,
            )
            return
        if interaction.user.id not in self.inscritos:
            await interaction.response.send_message("Você não está na sala.", ephemeral=True)
            return
        self.inscritos.remove(interaction.user.id)
        await combate.responder(interaction, self.embed(), self)

    @discord.ui.button(label="Começar", emoji="⚔️", style=discord.ButtonStyle.danger)
    async def comecar(self, interaction, button):
        if interaction.user.id != self.anfitriao_id:
            await interaction.response.send_message(
                "Só quem abriu a sala pode começar.", ephemeral=True
            )
            return
        if len(self.inscritos) < MIN_PARTICIPANTES_RAIDE:
            await interaction.response.send_message(
                f"Precisa de pelo menos {MIN_PARTICIPANTES_RAIDE} na sala pra começar "
                f"({len(self.inscritos)} agora).",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        self.comecou = True
        self.stop()
        await iniciar_raide(interaction, self.inscritos, self.guilda["id"], self.anfitriao_id, editar=True)

    async def on_timeout(self):
        if self.comecou or self.mensagem is None:
            return
        for item in self.children:
            item.disabled = True
        e = self.embed()
        e.title = "A audiência não começou"
        e.color = combate.COR_FUGA
        await self.mensagem.edit(embed=e, view=self)


# --------------------------------------------------------------------- inicio
async def iniciar_raide(destino, ids, guilda_id, iniciador_id, editar=False):
    """destino é um ctx (comando) ou uma interaction (botão Começar) — mesmo
    contrato de combate.iniciar_luta."""
    combatentes = await combate.montar_combatentes(ids)
    travas.travar_todos([c.id for c in combatentes])
    luta = combate.Luta(combatentes, RAIDE_CHEFE, ANDAR_REFERENCIA_RAIDE)

    # Cooldown vem do tier do Salão, não é mais fixo -- Salão Vazio/Erguido
    # ficam nas 2h de sempre, Guarnecido cai pra 1h30, Coroado pra 1h (nunca
    # menos que isso, ver game_data.SALAO_TIERS e decisoes.md § Salão da
    # Guilda -- o número a vigiar). tier_efetivo trata guilda com menos de 3
    # membros como tier 0 mesmo com tesouro de sobra.
    membros_count = db.contar_membros_guilda(guilda_id)
    total_tesouros = db.contar_tesouros_salao(guilda_id)
    cooldown = salao.tier_efetivo(total_tesouros, membros_count, MEMBROS_PARA_VALER)["cooldown_raide"]
    db.set_cooldown_raide(guilda_id, cooldown)
    for c in combatentes:
        db.marcar_combate(c.id)

    # mesmo gate de combate.iniciar_luta — duplicado aqui porque iniciar_raide
    # não chama iniciar_luta, tem o próprio golpe de iniciativa. Não herda
    # RODADA_1_SEM_CHEFE de graça, então precisa do mesmo if explícito.
    if not combate.RODADA_1_SEM_CHEFE:
        mais_rapido = max(c.s["atribs"]["destreza"] for c in combatentes)
        if random.random() >= at.chance_iniciativa(mais_rapido, at.destreza_monstro(ANDAR_REFERENCIA_RAIDE)):
            alvo = random.choice(combatentes)
            dano = combate.dano_do_chefe(RAIDE_CHEFE, alvo.s, ANDAR_REFERENCIA_RAIDE)
            alvo.hp -= dano
            luta.registrar(f"{RAIDE_CHEFE['nome']} foi mais rápida e acerta {alvo.nome} — **{dano}**")
            if alvo.hp <= 0:
                alvo.caiu = True
            alvo.salvar_estado()

    painel = PainelRaide(luta, guilda_id, iniciador_id)
    if not luta.ativos:
        painel.travar()
        embed = await combate.finalizar_derrota(luta)
        travas.destravar_todos([c.id for c in combatentes])
        if editar:
            await combate.responder(destino, embed, painel)
        else:
            await destino.send(embed=embed, view=painel)
        return

    if editar:
        await combate.responder(destino, luta.embed(), painel)
        painel.mensagem = await destino.original_response()
    else:
        painel.mensagem = await destino.send(embed=luta.embed(), view=painel)


# ---------------------------------------------------------------- instalacao
def instalar(bot, contexto):
    H.update(contexto)

    @bot.command(name="raide", aliases=["audiencia", "raid"])
    @travas.fora_de_manutencao()
    async def raide_cmd(ctx):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if ctx.guild is None:
            await ctx.send("Esse comando só funciona dentro de um servidor.")
            return
        guilda = db.guilda_do_membro(j["user_id"])
        if not guilda:
            await ctx.send(
                "Você precisa estar em uma guilda pra isso. `rpg guilda criar <nome>` "
                "ou peça pro líder de uma te chamar."
            )
            return
        if ctx.channel.id != guilda["canal_id"]:
            canal = ctx.guild.get_channel(guilda["canal_id"])
            aviso = f" — {canal.mention}" if canal else ""
            await ctx.send(f"`rpg raide` só abre dentro do canal da sua guilda{aviso}.")
            return
        if j["andar_max"] < ANDAR_MINIMO_RAIDE:
            await ctx.send(
                f"Precisa ter destrancado o andar {ANDAR_MINIMO_RAIDE} pra desafiar "
                f"{RAIDE_CHEFE['nome']}."
            )
            return
        restante = db.checar_cooldown_raide(guilda["id"])
        if restante > 0:
            await ctx.send(f"A guilda já teve audiência recentemente. Volta em **{H['fmt_tempo'](restante)}**.")
            return

        view = SalaDeEsperaRaide(j["user_id"], guilda, j)
        view.mensagem = await ctx.send(embed=view.embed(), view=view)

    print("raide.py carregado — rpg raide (mínimo 3, cooldown de 2h a 1h por guilda conforme o tier do Salão).")
