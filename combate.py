# combate.py
# Combate por turnos dos chefes, com botoes na mensagem.
# Nao importa bot.py (evita import circular): os helpers chegam por instalar().

import random

import discord

import atributos as at
import database as db
from game_data import ITENS, ANDARES, ANDAR_MAXIMO
from npcs import ANDAR_DESBLOQUEIA_CARROCA

# helpers emprestados do bot.py, preenchidos por instalar()
H = {}

# ---------------------------------------------------------------- constantes

TIMEOUT_RODADA = 600          # segundos parado antes de considerar abandono
MAX_POCOES = 3               # por luta
REDUCAO_DEFENDENDO = 0.50    # dano que sobra quando voce defende
CHANCE_CARREGAR = 0.30       # por rodada
MULTIPLICADOR_CARREGADO = 3.0
PENETRACAO_BASE = 0.30       # fracao da defesa que o chefe ignora
PENETRACAO_POR_ANDAR = 0.015
PENETRACAO_CARREGADO = 0.25  # somada a base no golpe pesado

COR_DERROTA = 0x8B0000
COR_FUGA = 0x6C757D


def penetracao_do_andar(andar_num, carregado=False):
    pen = PENETRACAO_BASE + PENETRACAO_POR_ANDAR * (andar_num - 1)
    if carregado:
        pen += PENETRACAO_CARREGADO
    return min(0.85, pen)


def dano_do_chefe(chefe, s, andar_num, defendendo=False, carregado=False):
    """Defender anula a penetracao e ainda corta o dano pela metade."""
    pen = 0.0 if defendendo else penetracao_do_andar(andar_num, carregado)
    bruto = chefe["atk"] * random.uniform(0.85, 1.15)
    if carregado:
        bruto *= MULTIPLICADOR_CARREGADO
    if random.random() < at.CRITICO_BASE:
        bruto *= at.MULTIPLICADOR_CRITICO
    valor = at.aplicar_defesa(bruto, s["def"] * (1 - pen))
    if defendendo:
        valor = max(1, int(valor * REDUCAO_DEFENDENDO))
    return valor


def pocoes_na_mochila(user_id):
    """Consumiveis que o jogador tem agora, no maximo 5 tipos."""
    itens = db.get_inventario(user_id)
    return [
        i for i in itens
        if i["item"] in ITENS and ITENS[i["item"]]["tipo"] == "consumivel"
    ][:5]


# ------------------------------------------------------------ estado da luta

class Luta:
    """Estado de uma luta de chefe.

    `participantes` ja e' uma lista com um elemento so' — quando party existir,
    o que muda e' o tamanho da lista e o indice de `turno_de`, nao a estrutura.
    """

    def __init__(self, jogador, s, chefe, andar_num):
        self.participantes = [jogador["user_id"]]
        self.turno_de = 0
        self.jogador = jogador
        self.s = s
        self.chefe = chefe
        self.andar_num = andar_num
        self.hp = max(0, jogador["hp"])
        self.hp_chefe = chefe["hp"]
        self.rodada = 1
        self.pocoes_usadas = 0
        self.carregando = False
        self.defendendo = False
        self.encerrada = False
        self.log = []

    # -------- helpers de estado
    @property
    def dono(self):
        return self.participantes[self.turno_de]

    def registrar(self, linha):
        self.log.append(linha)

    def salvar_hp(self):
        """Grava o HP a cada rodada: reiniciar o bot nao devolve vida."""
        db.atualizar_jogador(self.jogador["user_id"], hp=max(0, self.hp))

    def embed(self, titulo=None, cor=None, rodape=None):
        andar = ANDARES[self.andar_num]
        e = discord.Embed(
            title=titulo or f"Chefe do andar {self.andar_num} — {self.chefe['nome']}",
            color=cor if cor is not None else andar["cor"],
        )
        e.add_field(
            name=self.chefe["nome"],
            value=f"{H['barra_hp'](self.hp_chefe, self.chefe['hp'])} "
                  f"{max(0, self.hp_chefe)}/{self.chefe['hp']}",
            inline=False,
        )
        e.add_field(
            name=self.jogador["nome"],
            value=f"{H['barra_hp'](self.hp, self.s['hp_max'])} "
                  f"{max(0, self.hp)}/{self.s['hp_max']}",
            inline=False,
        )
        if self.log:
            e.add_field(
                name=f"── Rodada {self.rodada} ──",
                value="\n".join(self.log[-2:]),
                inline=False,
            )
        if self.carregando and not self.encerrada:
            e.add_field(
                name="⚠️ Alguma coisa vai acontecer",
                value=f"*{self.chefe['nome']} está preparando um golpe.* "
                      f"Defender anula a penetração de armadura dele.",
                inline=False,
            )
        if rodape:
            e.set_footer(text=rodape)
        elif not self.encerrada:
            e.set_footer(
                text=f"Sua vez · poções usadas {self.pocoes_usadas}/{MAX_POCOES} "
                     f"· {TIMEOUT_RODADA}s para agir"
            )
        return e

    # -------- turnos
    def turno_do_chefe(self):
        """Devolve True se o jogador caiu."""
        if self.carregando:
            dano = dano_do_chefe(
                self.chefe, self.s, self.andar_num,
                defendendo=self.defendendo, carregado=True,
            )
            self.hp -= dano
            self.carregando = False
            aviso = " (você aparou o pior)" if self.defendendo else ""
            self.registrar(f"💥 **Golpe carregado** — {dano} de dano{aviso}")
        elif random.random() < CHANCE_CARREGAR:
            self.carregando = True
            self.registrar(f"{self.chefe['nome']} recua e começa a se preparar.")
        else:
            des = self.s["atribs"]["destreza"]
            des_chefe = at.destreza_monstro(self.andar_num)
            if random.random() < at.chance_esquiva(des, des_chefe):
                self.registrar("Você esquivou do ataque.")
            else:
                dano = dano_do_chefe(
                    self.chefe, self.s, self.andar_num, defendendo=self.defendendo
                )
                self.hp -= dano
                self.registrar(f"{self.chefe['nome']} atacou — **{dano}** de dano")
        self.defendendo = False
        self.rodada += 1
        self.salvar_hp()
        return self.hp <= 0


# ---------------------------------------------------------- fim de combate

async def finalizar_vitoria(luta):
    j, s, chefe = luta.jogador, luta.s, luta.chefe
    for item in H["rolar_drops"](chefe):
        db.add_item(j["user_id"], item)
    nivel, xp, subiu = H["aplicar_xp"](j, chefe["xp"])
    novo_andar = min(luta.andar_num + 1, ANDAR_MAXIMO)
    novo_max = max(j["andar_max"], novo_andar)
    hp_cheio = at.hp_maximo(nivel, s["atribs"]["constituicao"])
    db.atualizar_jogador(
        j["user_id"], hp=hp_cheio, mana=s["mana_max"], xp=xp, nivel=nivel,
        pontos=H["pontos_por_subir"](j, subiu),
        moedas=j["moedas"] + chefe["moedas"], andar=novo_andar, andar_max=novo_max,
    )
    luta.encerrada = True
    e = luta.embed(
        titulo=f"Chefe derrotado — {chefe['nome']}",
        rodape=f"Você terminou a luta em {luta.rodada} rodadas e recuperou todo o HP.",
    )
    e.add_field(
        name="Recompensa",
        value=f"+{chefe['xp']} XP · +{chefe['moedas']} 🪙 · 🔷 Fragmento do Selo",
        inline=False,
    )
    if luta.andar_num == ANDAR_MAXIMO:
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
    return e


async def finalizar_derrota(luta):
    perda = H["processar_morte"](luta.jogador, luta.s)
    luta.encerrada = True
    e = luta.embed(
        titulo=f"Você caiu — {luta.chefe['nome']}",
        cor=COR_DERROTA,
        rodape=f"Caiu na rodada {luta.rodada}. O chefe volta com o HP cheio.",
    )
    e.add_field(
        name="Derrota",
        value=f"Perdeu **{perda}** 🪙 e acordou com 30% do HP.",
        inline=False,
    )
    return e


async def finalizar_fuga(luta):
    db.set_cooldown(luta.jogador["user_id"], "boss", 0)
    luta.encerrada = True
    e = luta.embed(
        titulo=f"Você fugiu — {luta.chefe['nome']}",
        cor=COR_FUGA,
        rodape="O cooldown não foi consumido: dá para tentar de novo agora.",
    )
    e.add_field(
        name="Fuga",
        value="Você sai com o HP que sobrou. O chefe volta inteiro.",
        inline=False,
    )
    return e


# ------------------------------------------------------------------- views

class MenuPocoes(discord.ui.View):
    def __init__(self, painel):
        super().__init__(timeout=TIMEOUT_RODADA)
        self.painel = painel
        luta = painel.luta
        for linha in pocoes_na_mochila(luta.jogador["user_id"]):
            dados = ITENS[linha["item"]]
            self.add_item(BotaoPocao(linha["item"], dados, linha["qtd"]))
        self.add_item(BotaoVoltar())

    async def interaction_check(self, interaction):
        return await self.painel.interaction_check(interaction)


class BotaoPocao(discord.ui.Button):
    def __init__(self, chave, dados, qtd):
        super().__init__(
            label=f"{dados['nome']} ({qtd})",
            emoji=dados["emoji"],
            style=discord.ButtonStyle.success,
        )
        self.chave = chave

    async def callback(self, interaction):
        painel = self.view.painel
        luta = painel.luta
        if not db.remove_item(luta.jogador["user_id"], self.chave, 1):
            await interaction.response.edit_message(embed=luta.embed(), view=painel)
            return
        cura = ITENS[self.chave]["cura"]
        antes = max(0, luta.hp)
        luta.hp = min(luta.s["hp_max"], antes + cura)
        luta.pocoes_usadas += 1
        luta.registrar(
            f"{ITENS[self.chave]['emoji']} Bebeu **{ITENS[self.chave]['nome']}** "
            f"— +{luta.hp - antes} HP"
        )
        await painel.resolver_chefe(interaction)


class BotaoVoltar(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Voltar", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction):
        painel = self.view.painel
        await interaction.response.edit_message(embed=painel.luta.embed(), view=painel)


class PainelLuta(discord.ui.View):
    def __init__(self, luta):
        super().__init__(timeout=TIMEOUT_RODADA)
        self.luta = luta
        self.mensagem = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.luta.dono:
            await interaction.response.send_message(
                "Essa luta não é sua. Enfrente o seu próprio chefe com `rpg boss`.",
                ephemeral=True,
            )
            return False
        return True

    def travar(self):
        for item in self.children:
            item.disabled = True
        self.stop()

    async def encerrar(self, interaction, embed):
        self.travar()
        await interaction.response.edit_message(embed=embed, view=self)

    async def resolver_chefe(self, interaction):
        """Roda o turno do chefe depois da acao do jogador e atualiza a tela."""
        luta = self.luta
        if luta.hp_chefe <= 0:
            await self.encerrar(interaction, await finalizar_vitoria(luta))
            return
        caiu = luta.turno_do_chefe()
        if caiu:
            await self.encerrar(interaction, await finalizar_derrota(luta))
            return
        await interaction.response.edit_message(embed=luta.embed(), view=self)

    @discord.ui.button(label="Atacar", emoji="⚔️", style=discord.ButtonStyle.danger)
    async def atacar(self, interaction, button):
        luta = self.luta
        dano = H["calcular_dano"](luta.s["atk"], luta.chefe["def"])
        luta.hp_chefe -= dano
        luta.registrar(f"Você atacou — **{dano}** de dano")
        await self.resolver_chefe(interaction)

    @discord.ui.button(label="Defender", emoji="🛡️", style=discord.ButtonStyle.primary)
    async def defender(self, interaction, button):
        luta = self.luta
        luta.defendendo = True
        luta.registrar("Você firmou a guarda.")
        await self.resolver_chefe(interaction)

    @discord.ui.button(label="Mochila", emoji="🎒", style=discord.ButtonStyle.success)
    async def mochila(self, interaction, button):
        luta = self.luta
        if luta.pocoes_usadas >= MAX_POCOES:
            await interaction.response.send_message(
                f"Você já usou {MAX_POCOES} poções nesta luta. Agora é no talento.",
                ephemeral=True,
            )
            return
        if not pocoes_na_mochila(luta.jogador["user_id"]):
            await interaction.response.send_message(
                "Sua mochila não tem consumível nenhum.", ephemeral=True
            )
            return
        await interaction.response.edit_message(
            embed=luta.embed(), view=MenuPocoes(self)
        )

    @discord.ui.button(label="Fugir", emoji="🏃", style=discord.ButtonStyle.secondary)
    async def fugir(self, interaction, button):
        luta = self.luta
        des = luta.s["atribs"]["destreza"]
        chance = at.chance_fuga(des, at.destreza_monstro(luta.andar_num), eh_chefe=True)
        if random.random() < chance:
            await self.encerrar(interaction, await finalizar_fuga(luta))
            return
        luta.registrar(f"Você tentou fugir e não conseguiu ({chance * 100:.0f}% de chance).")
        await self.resolver_chefe(interaction)

    async def on_timeout(self):
        """Abandono: o chefe termina a luta sozinho e o cooldown segue queimado."""
        luta = self.luta
        if luta.encerrada or self.mensagem is None:
            return
        while luta.hp > 0 and luta.hp_chefe > 0 and luta.rodada < 60:
            dano = H["calcular_dano"](luta.s["atk"], luta.chefe["def"])
            luta.hp_chefe -= dano
            if luta.hp_chefe <= 0:
                break
            luta.turno_do_chefe()
        if luta.hp_chefe <= 0:
            embed = await finalizar_vitoria(luta)
            embed.set_author(name="⏱️ Você abandonou a luta — ela terminou sem você")
        else:
            embed = await finalizar_derrota(luta)
            embed.set_author(name="⏱️ Você abandonou a luta — o chefe não esperou")
        self.travar()
        await self.mensagem.edit(embed=embed, view=self)


# ---------------------------------------------------------------- instalacao

def instalar(bot, contexto):
    """Substitui o comando `boss` do bot.py pela versao por turnos."""
    H.update(contexto)
    bot.remove_command("boss")

    @bot.command(name="boss", aliases=["chefe"])
    async def boss(ctx):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return

        if j["andar"] < j["andar_max"]:
            await ctx.send(
                f"A sala do chefe do andar {j['andar']} está vazia — você já limpou esse andar. "
                f"Manda `rpg viajar {j['andar_max']}` pra voltar pro topo."
            )
            return

        s = H["stats"](j)
        if j["hp"] < s["hp_max"] * 0.4:
            await ctx.send(
                f"Você está machucado demais ({max(0, j['hp'])}/{s['hp_max']}). "
                f"Manda `rpg usar pocao pequena` antes."
            )
            return
        if await H["bloqueado_por_cooldown"](ctx, "boss", H["COOLDOWN_BOSS"]):
            return

        andar = ANDARES[j["andar"]]
        luta = Luta(j, s, andar["boss"], j["andar"])

        # iniciativa: o chefe pode abrir a luta
        des = s["atribs"]["destreza"]
        if random.random() >= at.chance_iniciativa(des, at.destreza_monstro(j["andar"])):
            dano = dano_do_chefe(luta.chefe, s, luta.andar_num)
            luta.hp -= dano
            luta.registrar(f"{luta.chefe['nome']} foi mais rápido — **{dano}** de dano")
            luta.salvar_hp()

        painel = PainelLuta(luta)
        if luta.hp <= 0:
            painel.travar()
            await ctx.send(embed=await finalizar_derrota(luta), view=painel)
            return
        painel.mensagem = await ctx.send(embed=luta.embed(), view=painel)