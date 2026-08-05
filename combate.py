# combate.py
# Combate por turnos dos chefes, solo ou em party, com botoes na mensagem.
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

TIMEOUT_RODADA = 60          # segundos sem clicar = saiu da luta
TIMEOUT_SALA = 90            # janela da sala de espera
MAX_PARTY = 4
MAX_POCOES = 3               # por luta, por pessoa
REDUCAO_DEFENDENDO = 0.50    # dano que sobra quando voce defende
CHANCE_CARREGAR = 0.30       # por rodada
MULTIPLICADOR_CARREGADO = 3.0
PENETRACAO_BASE = 0.30       # fracao da defesa que o chefe ignora
PENETRACAO_POR_ANDAR = 0.015
PENETRACAO_CARREGADO = 0.25  # somada a base no golpe pesado
FUGA_POR_DESFALQUE = 0.15    # cada companheiro perdido facilita a fuga
HP_MINIMO_PARA_ENTRAR = 0.40

COR_DERROTA = 0x8B0000
COR_FUGA = 0x6C757D
COR_SALA = 0xA8DADC


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
    itens = db.get_inventario(user_id)
    return [
        i for i in itens
        if i["item"] in ITENS and ITENS[i["item"]]["tipo"] == "consumivel"
    ][:5]


async def responder(interaction, embed, view):
    """Confirma a interacao antes de qualquer trabalho pesado e depois edita.

    Sem o defer, o token vence em 3 segundos — e gravar HP, drop e XP no
    SQLite passa disso com facilidade quando tem gente jogando junto.
    """
    if not interaction.response.is_done():
        await interaction.response.defer()
    await interaction.edit_original_response(embed=embed, view=view)


def cura_do_item(dado, hp_max):
    if "cura_pct" in dado:
        return max(1, int(hp_max * dado["cura_pct"]))
    return dado.get("cura", 0)


# ------------------------------------------------------------- combatente

class Combatente:
    """Um jogador dentro da luta. Solo e' uma party de um."""

    def __init__(self, jogador, s):
        self.id = jogador["user_id"]
        self.nome = jogador["nome"]
        self.jogador = jogador
        self.s = s
        self.hp = max(0, jogador["hp"])
        self.acao = None            # o que ele escolheu nesta rodada
        self.defendendo = False
        self.pocoes_usadas = 0
        self.caiu = False
        self.fugiu = False
        self.saiu = False

    @property
    def ativo(self):
        return not (self.caiu or self.fugiu or self.saiu)

    def salvar_hp(self):
        db.atualizar_jogador(self.id, hp=max(0, self.hp))

    def barra(self):
        estado = ""
        if self.caiu:
            estado = " — caiu"
        elif self.fugiu:
            estado = " — fugiu"
        elif self.saiu:
            estado = " — saiu da luta"
        elif self.acao:
            estado = " — pronto"
        return (f"{H['barra_hp'](self.hp, self.s['hp_max'])} "
                f"{max(0, self.hp)}/{self.s['hp_max']}{estado}")


# ------------------------------------------------------------ estado da luta

class Luta:
    def __init__(self, combatentes, chefe, andar_num):
        self.participantes = combatentes
        self.chefe = chefe
        self.andar_num = andar_num
        self.hp_chefe = chefe["hp"] * len(combatentes)
        self.hp_chefe_max = self.hp_chefe
        self.rodada = 1
        self.carregando = False
        self.encerrada = False
        self.log = []

    @property
    def ativos(self):
        return [c for c in self.participantes if c.ativo]

    @property
    def desfalque(self):
        """Quantos companheiros a party perdeu — facilita a fuga de quem ficou."""
        return len(self.participantes) - len(self.ativos)

    @property
    def em_party(self):
        return len(self.participantes) > 1

    def por_id(self, user_id):
        return next((c for c in self.participantes if c.id == user_id), None)

    def registrar(self, linha):
        self.log.append(linha)

    def chance_de_fuga(self, combatente):
        base = at.chance_fuga(
            combatente.s["atribs"]["destreza"],
            at.destreza_monstro(self.andar_num),
            eh_chefe=True,
        )
        return min(0.90, base + FUGA_POR_DESFALQUE * self.desfalque)

    def embed(self, titulo=None, cor=None, rodape=None):
        andar = ANDARES[self.andar_num]
        e = discord.Embed(
            title=titulo or f"Chefe do andar {self.andar_num} — {self.chefe['nome']}",
            color=cor if cor is not None else andar["cor"],
        )
        e.add_field(
            name=self.chefe["nome"],
            value=f"{H['barra_hp'](self.hp_chefe, self.hp_chefe_max)} "
                  f"{max(0, self.hp_chefe)}/{self.hp_chefe_max}",
            inline=False,
        )
        for c in self.participantes:
            e.add_field(name=c.nome, value=c.barra(), inline=False)
        if self.log:
            limite = 4 if self.em_party else 2
            e.add_field(
                name=f"── Rodada {self.rodada} ──",
                value="\n".join(self.log[-limite:]),
                inline=False,
            )
        if self.carregando and not self.encerrada:
            e.add_field(
                name="⚠️ Alguma coisa vai acontecer",
                value=f"*{self.chefe['nome']} está preparando um golpe.* "
                      f"Ele acerta **todo mundo** — Defender anula a penetração de armadura.",
                inline=False,
            )
        if rodape:
            e.set_footer(text=rodape)
        elif not self.encerrada:
            faltam = [c.nome for c in self.ativos if not c.acao]
            espera = ("Sua vez" if not self.em_party
                      else "Esperando: " + ", ".join(faltam) if faltam else "Resolvendo…")
            e.set_footer(text=f"{espera} · {TIMEOUT_RODADA}s para agir")
        return e

    # -------- resolucao da rodada
    def turno_do_chefe(self):
        """O chefe age uma vez por rodada, contra a party inteira."""
        alvos = self.ativos
        if not alvos:
            return

        if self.carregando:
            self.carregando = False
            self.registrar(f"💥 **Golpe carregado** — {self.chefe['nome']} acerta todo mundo:")
            for c in alvos:
                dano = dano_do_chefe(
                    self.chefe, c.s, self.andar_num,
                    defendendo=c.defendendo, carregado=True,
                )
                c.hp -= dano
                aparou = " (aparou)" if c.defendendo else ""
                self.registrar(f"· {c.nome} toma **{dano}**{aparou}")
                if c.hp <= 0:
                    c.caiu = True
        elif random.random() < CHANCE_CARREGAR:
            self.carregando = True
            self.registrar(f"{self.chefe['nome']} recua e começa a se preparar.")
        else:
            alvo = random.choice(alvos)
            des = alvo.s["atribs"]["destreza"]
            if random.random() < at.chance_esquiva(des, at.destreza_monstro(self.andar_num)):
                self.registrar(f"{alvo.nome} esquivou do ataque.")
            else:
                dano = dano_do_chefe(
                    self.chefe, alvo.s, self.andar_num, defendendo=alvo.defendendo
                )
                alvo.hp -= dano
                self.registrar(f"{self.chefe['nome']} ataca **{alvo.nome}** — {dano} de dano")
                if alvo.hp <= 0:
                    alvo.caiu = True

        for c in self.participantes:
            c.defendendo = False
            c.acao = None
            c.salvar_hp()
        self.rodada += 1


# ---------------------------------------------------------- fim de combate

async def recompensar(luta, combatente):
    """Paga um sobrevivente e sobe o andar dele."""
    j, s, chefe = combatente.jogador, combatente.s, luta.chefe
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
    return nivel, subiu, novo_andar


async def finalizar_vitoria(luta):
    luta.encerrada = True
    vencedores = [c for c in luta.participantes if c.ativo]
    novo_andar = min(luta.andar_num + 1, ANDAR_MAXIMO)
    linhas = []
    for c in vencedores:
        nivel, subiu, novo_andar = await recompensar(luta, c)
        linha = f"**{c.nome}** — +{luta.chefe['xp']} XP · +{luta.chefe['moedas']} 🪙 · 🔷 Fragmento"
        if subiu:
            linha += f"\n· subiu para o **nível {nivel}** (+{at.PONTOS_POR_NIVEL * subiu} pontos)"
        linhas.append(linha)

    e = luta.embed(
        titulo=f"Chefe derrotado — {luta.chefe['nome']}",
        rodape=f"Luta encerrada na rodada {luta.rodada}. Quem sobreviveu recuperou todo o HP.",
    )
    e.add_field(name="Recompensas", value="\n".join(linhas) or "Ninguém sobrou de pé.", inline=False)
    if luta.andar_num == ANDAR_MAXIMO:
        e.add_field(
            name="🌑 Décimo Selo",
            value="A porta abre. Do outro lado tem uma escada que continua subindo — e ela não acaba.",
            inline=False,
        )
    elif vencedores:
        e.add_field(
            name=f"⬆️ Andar {novo_andar} destrancado",
            value=f"**{ANDARES[novo_andar]['nome']}**\n{ANDARES[novo_andar]['descricao']}",
            inline=False,
        )
        if novo_andar == ANDAR_DESBLOQUEIA_CARROCA:
            e.add_field(
                name="🐎 Vocês conheceram Bramm",
                value="O carroceiro passa por aqui três vezes por dia e não cobra. `rpg carroca`",
                inline=False,
            )
    return e


async def finalizar_derrota(luta):
    """Ninguem sobrou: cada um que caiu paga a penalidade."""
    luta.encerrada = True
    perdas = []
    for c in luta.participantes:
        if c.caiu:
            perda = H["processar_morte"](c.jogador, c.s)
            perdas.append(f"**{c.nome}** perdeu {perda} 🪙")
    e = luta.embed(
        titulo=f"A party caiu — {luta.chefe['nome']}",
        cor=COR_DERROTA,
        rodape=f"Caíram na rodada {luta.rodada}. O chefe volta com o HP cheio.",
    )
    e.add_field(
        name="Derrota",
        value="\n".join(perdas) or "Ninguém sobrou.",
        inline=False,
    )
    return e


async def encerrar_por_abandono(luta):
    """Todo mundo fugiu ou sumiu — a luta acaba sem vencedor."""
    luta.encerrada = True
    fugiram = [c.nome for c in luta.participantes if c.fugiu]
    sumiram = [c.nome for c in luta.participantes if c.saiu]
    partes = []
    if fugiram:
        partes.append("Fugiram: " + ", ".join(fugiram))
    if sumiram:
        partes.append("Sumiram no meio: " + ", ".join(sumiram))
    e = luta.embed(
        titulo=f"A luta acabou — {luta.chefe['nome']}",
        cor=COR_FUGA,
        rodape="Quem fugiu não gastou o cooldown. Quem sumiu, gastou.",
    )
    e.add_field(name="Sem vencedor", value="\n".join(partes) or "—", inline=False)
    for c in luta.participantes:
        if c.fugiu:
            db.set_cooldown(c.id, "boss", 0)
    return e


# ------------------------------------------------------------------- views

class MenuPocoes(discord.ui.View):
    def __init__(self, painel, combatente):
        super().__init__(timeout=TIMEOUT_RODADA)
        self.painel = painel
        self.combatente = combatente
        for linha in pocoes_na_mochila(combatente.id):
            self.add_item(BotaoPocao(linha["item"], ITENS[linha["item"]], linha["qtd"]))
        self.add_item(BotaoVoltar())

    async def interaction_check(self, interaction):
        if interaction.user.id != self.combatente.id:
            await interaction.response.send_message("Essa mochila não é sua.", ephemeral=True)
            return False
        return True


class BotaoPocao(discord.ui.Button):
    def __init__(self, chave, dados, qtd):
        super().__init__(
            label=f"{dados['nome']} ({qtd})",
            emoji=dados["emoji"],
            style=discord.ButtonStyle.success,
        )
        self.chave = chave

    async def callback(self, interaction):
        await interaction.response.defer()
        painel = self.view.painel
        c = self.view.combatente
        if not db.remove_item(c.id, self.chave, 1):
            await responder(interaction, painel.luta.embed(), painel)
            return
        cura = cura_do_item(ITENS[self.chave], c.s["hp_max"])
        antes = max(0, c.hp)
        c.hp = min(c.s["hp_max"], antes + cura)
        c.pocoes_usadas += 1
        painel.luta.registrar(
            f"{ITENS[self.chave]['emoji']} {c.nome} bebe "
            f"**{ITENS[self.chave]['nome']}** — +{c.hp - antes} HP"
        )
        await painel.registrar_acao(interaction, c, "pocao")


class BotaoVoltar(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Voltar", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction):
        await interaction.response.defer()
        painel = self.view.painel
        await responder(interaction, painel.luta.embed(), painel)


class PainelLuta(discord.ui.View):
    def __init__(self, luta):
        super().__init__(timeout=TIMEOUT_RODADA)
        self.luta = luta
        self.mensagem = None

    # -------- utilidades
    def combatente_de(self, interaction):
        return self.luta.por_id(interaction.user.id)

    async def interaction_check(self, interaction):
        c = self.combatente_de(interaction)
        if c is None:
            await interaction.response.send_message(
                "Você não está nesta luta. Abra a sua com `rpg boss` ou `rpg party`.",
                ephemeral=True,
            )
            return False
        if not c.ativo:
            await interaction.response.send_message(
                "Você já saiu desta luta.", ephemeral=True
            )
            return False
        if c.acao:
            await interaction.response.send_message(
                "Você já agiu nesta rodada. Esperando o resto da party.", ephemeral=True
            )
            return False
        return True

    def travar(self):
        for item in self.children:
            item.disabled = True
        self.stop()

    async def encerrar(self, interaction, embed):
        self.travar()
        await responder(interaction, embed, self)

    async def fim_da_luta(self, interaction=None):
        """Devolve o embed final se a luta acabou, ou None se continua."""
        luta = self.luta
        if luta.hp_chefe <= 0:
            return await finalizar_vitoria(luta)
        if not luta.ativos:
            if any(c.caiu for c in luta.participantes) and not any(
                c.fugiu or c.saiu for c in luta.participantes
            ):
                return await finalizar_derrota(luta)
            return await encerrar_por_abandono(luta)
        return None

    # -------- fluxo da rodada
    async def registrar_acao(self, interaction, combatente, acao):
        """Guarda a escolha e resolve a rodada quando todos ja escolheram."""
        combatente.acao = acao
        if acao == "defender":
            combatente.defendendo = True

        luta = self.luta
        if any(c.acao is None for c in luta.ativos):
            await responder(interaction, luta.embed(), self)
            return

        # todos escolheram: ataques primeiro, depois o chefe
        for c in luta.ativos:
            if c.acao == "atacar":
                dano = H["calcular_dano"](c.s["atk"], luta.chefe["def"], c.s["critico"])
                luta.hp_chefe -= dano
                luta.registrar(f"{c.nome} acerta **{dano}**")
        fim = await self.fim_da_luta()
        if fim:
            await self.encerrar(interaction, fim)
            return

        luta.turno_do_chefe()
        fim = await self.fim_da_luta()
        if fim:
            await self.encerrar(interaction, fim)
            return
        await responder(interaction, luta.embed(), self)

    @discord.ui.button(label="Atacar", emoji="⚔️", style=discord.ButtonStyle.danger)
    async def atacar(self, interaction, button):
        await interaction.response.defer()
        c = self.combatente_de(interaction)
        await self.registrar_acao(interaction, c, "atacar")

    @discord.ui.button(label="Defender", emoji="🛡️", style=discord.ButtonStyle.primary)
    async def defender(self, interaction, button):
        await interaction.response.defer()
        c = self.combatente_de(interaction)
        self.luta.registrar(f"{c.nome} firma a guarda.")
        await self.registrar_acao(interaction, c, "defender")

    @discord.ui.button(label="Mochila", emoji="🎒", style=discord.ButtonStyle.success)
    async def mochila(self, interaction, button):
        c = self.combatente_de(interaction)
        if c.pocoes_usadas >= MAX_POCOES:
            await interaction.response.send_message(
                f"Você já usou {MAX_POCOES} poções nesta luta. Agora é no talento.",
                ephemeral=True,
            )
            return
        if not pocoes_na_mochila(c.id):
            await interaction.response.send_message(
                "Sua mochila não tem consumível nenhum.", ephemeral=True
            )
            return
        await responder(interaction, self.luta.embed(), MenuPocoes(self, c))

    @discord.ui.button(label="Fugir", emoji="🏃", style=discord.ButtonStyle.secondary)
    async def fugir(self, interaction, button):
        await interaction.response.defer()
        c = self.combatente_de(interaction)
        chance = self.luta.chance_de_fuga(c)
        if random.random() < chance:
            c.fugiu = True
            c.salvar_hp()
            self.luta.registrar(f"🏃 {c.nome} escapou da sala.")
            fim = await self.fim_da_luta()
            if fim:
                await self.encerrar(interaction, fim)
                return
            await responder(interaction, self.luta.embed(), self)
            return
        self.luta.registrar(f"{c.nome} tentou fugir e falhou ({chance * 100:.0f}%).")
        await self.registrar_acao(interaction, c, "fugir")

    async def on_timeout(self):
        """Quem nao clicou sai da luta. Se sobrar gente, a rodada resolve sem ele."""
        luta = self.luta
        if luta.encerrada or self.mensagem is None:
            return
        for c in luta.ativos:
            if c.acao is None:
                c.saiu = True
                c.salvar_hp()
                luta.registrar(f"⏱️ {c.nome} sumiu e saiu da luta.")

        if luta.ativos:
            for c in luta.ativos:
                if c.acao == "atacar":
                    dano = H["calcular_dano"](c.s["atk"], luta.chefe["def"], c.s["critico"])
                    luta.hp_chefe -= dano
                    luta.registrar(f"{c.nome} acerta **{dano}**")
            if luta.hp_chefe > 0:
                luta.turno_do_chefe()

        if luta.hp_chefe <= 0:
            embed = await finalizar_vitoria(luta)
        elif not luta.ativos:
            embed = (await finalizar_derrota(luta) if all(
                c.caiu for c in luta.participantes) else await encerrar_por_abandono(luta))
        else:
            # sobrou gente: a luta continua num painel novo
            novo = PainelLuta(luta)
            novo.mensagem = self.mensagem
            self.stop()
            await self.mensagem.edit(embed=luta.embed(), view=novo)
            return

        self.travar()
        await self.mensagem.edit(embed=embed, view=self)


# ------------------------------------------------------------ sala de espera

class SalaDeEspera(discord.ui.View):
    def __init__(self, anfitriao, jogador, andar_num):
        super().__init__(timeout=TIMEOUT_SALA)
        self.anfitriao = anfitriao
        self.andar_num = andar_num
        self.inscritos = [jogador["user_id"]]
        self.mensagem = None
        self.comecou = False

    def embed(self):
        chefe = ANDARES[self.andar_num]["boss"]
        nomes = []
        for uid in self.inscritos:
            j = db.get_jogador(uid)
            nomes.append(f"• **{j['nome']}** — nível {j['nivel']}")
        e = discord.Embed(
            title=f"Party para {chefe['nome']}",
            description=(
                f"Andar {self.andar_num}. O chefe entra com "
                f"**{chefe['hp']} HP por pessoa**, e cada um leva a recompensa inteira.\n\n"
                f"Só entra quem já destrancou o andar {self.andar_num} e está com pelo menos "
                f"{int(HP_MINIMO_PARA_ENTRAR * 100)}% de HP."
            ),
            color=COR_SALA,
        )
        e.add_field(name=f"Na sala ({len(self.inscritos)}/{MAX_PARTY})",
                    value="\n".join(nomes), inline=False)
        e.set_footer(text=f"{TIMEOUT_SALA}s para fechar · só {db.get_jogador(self.anfitriao)['nome']} pode começar")
        return e

    async def validar(self, interaction, j):
        anfitriao = db.get_jogador(self.anfitriao)
        if j["andar_max"] != anfitriao["andar_max"]:
            await interaction.response.send_message(
                f"Essa party é do andar {anfitriao['andar_max']} e você está no "
                f"{j['andar_max']}. Só dá para lutar com quem está no mesmo ponto da torre.",
                ephemeral=True,
            )
            return False
        s = H["stats"](j)
        if j["hp"] < s["hp_max"] * HP_MINIMO_PARA_ENTRAR:
            await interaction.response.send_message(
                f"Você está com {max(0, j['hp'])}/{s['hp_max']}. Cure antes de entrar.",
                ephemeral=True,
            )
            return False
        if db.checar_cooldown(j["user_id"], "boss") > 0:
            await interaction.response.send_message(
                "Seu cooldown de chefe ainda não voltou.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Entrar", emoji="🤝", style=discord.ButtonStyle.success)
    async def entrar(self, interaction, button):
        if self.comecou:
            await interaction.response.send_message("A luta já começou.", ephemeral=True)
            return
        if interaction.user.id in self.inscritos:
            await interaction.response.send_message("Você já está na sala.", ephemeral=True)
            return
        if len(self.inscritos) >= MAX_PARTY:
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
        await responder(interaction, self.embed(), self)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.secondary)
    async def sair(self, interaction, button):
        if interaction.user.id == self.anfitriao:
            await interaction.response.send_message(
                "Quem abriu a sala não pode sair — cancele deixando o tempo acabar.",
                ephemeral=True,
            )
            return
        if interaction.user.id not in self.inscritos:
            await interaction.response.send_message("Você não está na sala.", ephemeral=True)
            return
        self.inscritos.remove(interaction.user.id)
        await responder(interaction, self.embed(), self)

    @discord.ui.button(label="Começar", emoji="⚔️", style=discord.ButtonStyle.danger)
    async def comecar(self, interaction, button):
        if interaction.user.id != self.anfitriao:
            await interaction.response.send_message(
                "Só quem abriu a sala pode começar.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self.comecou = True
        self.stop()
        await iniciar_luta(interaction, self.inscritos, self.andar_num, editar=True)

    async def on_timeout(self):
        if self.comecou or self.mensagem is None:
            return
        for item in self.children:
            item.disabled = True
        e = self.embed()
        e.title = "A sala fechou sem começar"
        e.color = COR_FUGA
        await self.mensagem.edit(embed=e, view=self)


# --------------------------------------------------------------- inicio

async def montar_combatentes(ids):
    combatentes = []
    for uid in ids:
        j = db.get_jogador(uid)
        if not j:
            continue
        combatentes.append(Combatente(j, H["stats"](j)))
    return combatentes


async def iniciar_luta(destino, ids, andar_num, editar=False):
    """destino e' um ctx (comando) ou uma interaction (botao Começar)."""
    combatentes = await montar_combatentes(ids)
    chefe = ANDARES[andar_num]["boss"]
    luta = Luta(combatentes, chefe, andar_num)

    for c in combatentes:
        db.set_cooldown(c.id, "boss", H["COOLDOWN_BOSS"])
        db.marcar_combate(c.id)

    # iniciativa: o chefe pode abrir a luta batendo em alguem
    mais_rapido = max(c.s["atribs"]["destreza"] for c in combatentes)
    if random.random() >= at.chance_iniciativa(mais_rapido, at.destreza_monstro(andar_num)):
        alvo = random.choice(combatentes)
        dano = dano_do_chefe(chefe, alvo.s, andar_num)
        alvo.hp -= dano
        luta.registrar(f"{chefe['nome']} foi mais rápido e acerta {alvo.nome} — **{dano}**")
        if alvo.hp <= 0:
            alvo.caiu = True
        alvo.salvar_hp()

    painel = PainelLuta(luta)
    if not luta.ativos:
        painel.travar()
        embed = await finalizar_derrota(luta)
        if editar:
            await responder(destino, embed, painel)
        else:
            await destino.send(embed=embed, view=painel)
        return

    if editar:
        await responder(destino, luta.embed(), painel)
        painel.mensagem = await destino.original_response()
    else:
        painel.mensagem = await destino.send(embed=luta.embed(), view=painel)


# ---------------------------------------------------------------- instalacao

def instalar(bot, contexto):
    """Substitui o comando `boss` do bot.py e adiciona o `party`."""
    H.update(contexto)
    bot.remove_command("boss")

    async def checar_sala_do_chefe(ctx, j):
        """Regras comuns ao boss solo e a' party."""
        if j["andar"] < j["andar_max"]:
            await ctx.send(
                f"A sala do chefe do andar {j['andar']} está vazia — você já limpou esse andar. "
                f"Manda `rpg viajar {j['andar_max']}` pra voltar pro topo."
            )
            return False
        s = H["stats"](j)
        if j["hp"] < s["hp_max"] * HP_MINIMO_PARA_ENTRAR:
            await ctx.send(
                f"Você está machucado demais ({max(0, j['hp'])}/{s['hp_max']}). "
                f"Manda `rpg usar pocao pequena` antes."
            )
            return False
        return True

    @bot.command(name="boss", aliases=["chefe"])
    async def boss(ctx):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not await checar_sala_do_chefe(ctx, j):
            return
        restante = db.checar_cooldown(ctx.author.id, "boss")
        if restante > 0:
            await ctx.send(f"⏳ `rpg boss` volta em **{H['fmt_tempo'](restante)}**.")
            return
        await iniciar_luta(ctx, [j["user_id"]], j["andar"])

    @bot.command(name="party", aliases=["grupo", "raid"])
    async def party(ctx):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not await checar_sala_do_chefe(ctx, j):
            return
        restante = db.checar_cooldown(ctx.author.id, "boss")
        if restante > 0:
            await ctx.send(f"⏳ Seu cooldown de chefe volta em **{H['fmt_tempo'](restante)}**.")
            return
        sala = SalaDeEspera(j["user_id"], j, j["andar"])
        sala.mensagem = await ctx.send(embed=sala.embed(), view=sala)

    print("combate.py carregado — chefe por turnos, solo e em party.")