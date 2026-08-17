# despertar.py
# Sequência de início do jogo (patch 0.3): abertura -> classe -> ofício ->
# pronome -> Elna acorda o jogador com as poções -> diálogo com ela. Chamado
# por `rpg comecar` (bot.py) via iniciar_despertar().
#
# Nada grava no banco até o botão de pronome ser clicado -- os valores
# escolhidos ficam só nos atributos de cada View, repassados adiante a cada
# `edit_message`. Abandonar no meio (fechar o Discord, deixar o botão expirar)
# não deixa registro parcial: `rpg comecar` de novo recomeça do zero, porque
# não existe jogador nenhum pra achar. Ver decisoes.md § despertar.
#
# O texto narrado (abertura, confirmações, falas da Elna) é do Rafael e mora
# em dialogos.DESPERTAR -- não mexer nele daqui. Os 8 cards de classe/ofício
# abaixo (CARDS_CLASSE/CARDS_OFICIO) são PROVISÓRIOS, de autoria própria desta
# implementação -- não são texto do Rafael, ele revisa depois.
#
# Duas dependências vêm de bot.py (não importado aqui de propósito, pra não
# criar import circular -- bot.py que importa despertar.py): a View de
# diálogo por botão (DialogoView) e a função que acha/cria a sala privada do
# jogador. iniciar_despertar() recebe as duas por parâmetro.

import discord

import atributos as at
import database as db
import dialogos
import pronomes
from game_data import ANDARES, CLASSES
from profissoes import PROFISSOES

ORDEM_CLASSES = ["ladino", "mago", "guerreiro", "orador"]
ORDEM_OFICIOS = ["forja", "alquimia", "encantador", "joalheiro"]

CARDS_CLASSE = {
    "ladino": (
        "Vive da velocidade e da brecha que ninguém viu. Ataca rápido, ataca "
        "certo, e já não está mais lá quando o golpe volta."
    ),
    "mago": (
        "Doma poder que não nasceu pra ser seguro. O cajado é só o que sobra "
        "do que a mente consegue segurar."
    ),
    "guerreiro": (
        "Não foge da linha de frente — é a linha de frente. Aço, força "
        "bruta e a teimosia de continuar de pé."
    ),
    "orador": (
        "Luta com o corpo mas pensa com a fé. Não precisa de arma quando a "
        "convicção já acerta primeiro."
    ),
}

CARDS_OFICIO = {
    "forja": (
        "Molda arma e armadura na bigorna. Sem ele, ninguém sobe andar "
        "nenhum com aço confiável nas mãos."
    ),
    "alquimia": (
        "Destila elixires que curam além do que qualquer poção de loja "
        "alcança. Trabalha com fogo baixo e paciência."
    ),
    "encantador": (
        "Grava um atributo extra em arma, armadura, anel ou colar que outra "
        "pessoa já fez. Não cria do zero — aperfeiçoa o que existe."
    ),
    "joalheiro": (
        "Lapida anel e colar do zero, escolhendo o atributo da peça antes "
        "mesmo dela existir. Trabalho fino, feito nos andares pares."
    ),
}

COR_DESPERTAR = 0x6A994E   # verde grama -- só desta sequência, andar ainda não existe pro jogador
ICONE_ELNA = "🧺"           # mesmo emoji de ICONES_NPC["mercador"] em bot.py


class _ViewSoAutor(discord.ui.View):
    """Base pros 3 passos de escolha -- só quem começou a sequência clica,
    igual DialogoView em bot.py."""

    def __init__(self, autor_id, timeout=300):
        super().__init__(timeout=timeout)
        self.autor_id = autor_id
        self.mensagem = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "Essa escolha não é sua. Manda `rpg comecar` você mesmo.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        if self.mensagem is None:
            return
        for item in self.children:
            item.disabled = True
        await self.mensagem.edit(view=self)


class BotaoClasse(discord.ui.Button):
    def __init__(self, chave):
        dados = CLASSES[chave]
        super().__init__(
            label=pronomes.concordar(dados["nome"], None), emoji=dados["emoji"],
            style=discord.ButtonStyle.primary,
        )
        self.chave = chave

    async def callback(self, interaction):
        await self.view.escolher(interaction, self.chave)


class BotaoOficio(discord.ui.Button):
    def __init__(self, chave):
        dados = PROFISSOES[chave]
        super().__init__(
            label=pronomes.concordar(dados["titulo"], None), emoji=dados["emoji"],
            style=discord.ButtonStyle.primary,
        )
        self.chave = chave

    async def callback(self, interaction):
        await self.view.escolher(interaction, self.chave)


class BotaoPronome(discord.ui.Button):
    def __init__(self, pronome, label):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.pronome = pronome

    async def callback(self, interaction):
        await self.view.escolher(interaction, self.pronome)


class EscolhaClasseView(_ViewSoAutor):
    def __init__(self, autor_id, ctx, deps):
        super().__init__(autor_id)
        self.ctx = ctx
        self.deps = deps
        for chave in ORDEM_CLASSES:
            self.add_item(BotaoClasse(chave))

    async def escolher(self, interaction, classe):
        nome_classe = pronomes.concordar(CLASSES[classe]["nome"], None)
        texto = pronomes.concordar(dialogos.DESPERTAR["confirmacao_classe"], None).format(classe=nome_classe)
        texto += "\n\n" + dialogos.DESPERTAR["pergunta_oficio"]

        e = interaction.message.embeds[0]
        e.description = texto
        e.clear_fields()
        for chave in ORDEM_OFICIOS:
            dados = PROFISSOES[chave]
            e.add_field(
                name=f"{dados['emoji']} {pronomes.concordar(dados['titulo'], None)}",
                value=CARDS_OFICIO[chave], inline=False,
            )

        proxima = EscolhaOficioView(self.autor_id, self.ctx, self.deps, classe)
        proxima.mensagem = interaction.message
        await interaction.response.edit_message(embed=e, view=proxima)


class EscolhaOficioView(_ViewSoAutor):
    def __init__(self, autor_id, ctx, deps, classe):
        super().__init__(autor_id)
        self.ctx = ctx
        self.deps = deps
        self.classe = classe
        for chave in ORDEM_OFICIOS:
            self.add_item(BotaoOficio(chave))

    async def escolher(self, interaction, oficio):
        nome_oficio = pronomes.concordar(PROFISSOES[oficio]["titulo"], None)
        texto = pronomes.concordar(dialogos.DESPERTAR["confirmacao_oficio"], None).format(oficio=nome_oficio)

        e = interaction.message.embeds[0]
        e.description = texto
        e.clear_fields()

        proxima = EscolhaPronomeView(self.autor_id, self.ctx, self.deps, self.classe, oficio)
        proxima.mensagem = interaction.message
        await interaction.response.edit_message(embed=e, view=proxima)


class EscolhaPronomeView(_ViewSoAutor):
    def __init__(self, autor_id, ctx, deps, classe, oficio):
        super().__init__(autor_id)
        self.ctx = ctx
        self.deps = deps
        self.classe = classe
        self.oficio = oficio
        self.add_item(BotaoPronome("ele", "ele / dele"))
        self.add_item(BotaoPronome("ela", "ela / dela"))
        self.add_item(BotaoPronome("elu", "elu / delu"))

    async def escolher(self, interaction, pronome):
        user_id = interaction.user.id

        # sequência dupla (ex.: dois `rpg comecar` abertos, só um terminado) --
        # a segunda a chegar aqui não sobrescreve quem já existe.
        existente = db.get_jogador(user_id)
        if existente and existente["classe"]:
            await interaction.response.send_message(
                "Essa sequência não vale mais — você já terminou o despertar em "
                "outra. Manda `rpg perfil`.", ephemeral=True,
            )
            return

        db.criar_jogador(user_id, interaction.user.display_name)
        db.atualizar_jogador(
            user_id, classe=self.classe, profissao=self.oficio,
            prof_nivel=1, prof_xp=0, pronome=pronome,
        )
        db.add_item(user_id, "pocao_p", 3)

        for item in self.children:
            item.disabled = True
        e = interaction.message.embeds[0]
        e.description += f"\n\n*(pronome: {pronome})*"
        await interaction.response.edit_message(embed=e, view=self)

        canal, _ = await self.deps["obter_canal_privado"](self.ctx)

        elna_texto = pronomes.concordar(dialogos.DESPERTAR["elna_acorda"], pronome)
        e_elna = discord.Embed(description=f"*{elna_texto}*", color=COR_DESPERTAR)
        e_elna.set_author(name=f"{ICONE_ELNA} Elna da Barraca Torta")
        e_elna.set_footer(text="Você recebeu 🧪 Poção Pequena x3")

        opcoes = [
            {"label": "Agradecer", "resposta": dialogos.DESPERTAR["elna_agradecer"]},
            {"label": "Perguntar onde está", "resposta": dialogos.DESPERTAR["elna_onde_esta"]},
            {"label": "Olhar em volta", "resposta": dialogos.DESPERTAR["elna_olhar_envolta"]},
        ]
        DialogoView = self.deps["dialogo_view_cls"]
        view_elna = DialogoView(user_id, pronome, opcoes, dialogos.SAIDA_PADRAO)
        view_elna.mensagem = await self.ctx.send(embed=e_elna, view=view_elna)

        e_final = discord.Embed(
            title="Você acordou no 1º andar",
            description=(
                "A porta atrás de você não abre mais.\n\n"
                "Dez andares acima existe um selo. Cada andar tem um chefe, e "
                "cada chefe guarda a escada.\n\n"
                "Comece com `rpg cacar`. Fale com quem mora aqui: `rpg npcs`."
            ),
            color=ANDARES[1]["cor"],
        )
        e_final.add_field(
            name="Atributos",
            value=(
                f"Você começa com {at.BASE} em cada um. A cada nível vêm "
                f"**{at.PONTOS_POR_NIVEL} pontos** para distribuir — `rpg status`."
            ),
            inline=False,
        )
        if canal:
            e_final.add_field(
                name="Sua sala", value=f"{canal.mention} — só você e o bot enxergam.", inline=False,
            )
        e_final.set_footer(text="`rpg ajuda` mostra a lista completa de comandos.")
        await self.ctx.send(embed=e_final)


async def iniciar_despertar(ctx, *, dialogo_view_cls, obter_canal_privado):
    deps = {"dialogo_view_cls": dialogo_view_cls, "obter_canal_privado": obter_canal_privado}

    e = discord.Embed(
        description=dialogos.DESPERTAR["abertura"] + "\n\n" + dialogos.DESPERTAR["pergunta_classe"],
        color=COR_DESPERTAR,
    )
    for chave in ORDEM_CLASSES:
        dados = CLASSES[chave]
        e.add_field(
            name=f"{dados['emoji']} {pronomes.concordar(dados['nome'], None)}",
            value=CARDS_CLASSE[chave], inline=False,
        )

    view = EscolhaClasseView(ctx.author.id, ctx, deps)
    view.mensagem = await ctx.send(embed=e, view=view)
