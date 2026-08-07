# admin.py
# Comandos administrativos — restritos ao dono do bot (commands.is_owner(),
# checa contra o dono do app no portal do Discord). Não depende de nada de
# bot.py, então não usa o padrão H — mesmo estilo do agenda.py.

import discord
from discord.ext import commands

import database as db

TIMEOUT_CONFIRMACAO = 30

TABELAS_APAGADAS = (
    "**inventario** — todo item de todo mundo",
    "**cooldowns** — senão alguém sai do reset com `rpg boss` travado numa luta que não existe mais",
    "**upgrades** — nível de melhoria é preso a (user_id, item), não ao slot equipado. "
    "Sobrevivendo, quem recompra a mesma arma inicial no ferreiro ganha o bônus de volta de graça.",
    "**chefes_derrotados** — senão quem já matou o chefe de um andar 11+ antes do reset "
    "volta com a chance de material já reduzida pra 15%, sem nunca ter matado de novo.",
)

COLUNAS_ZERADAS = (
    "nível, XP, moedas, HP, mana",
    "atributos (volta pra distribuição inicial) e pontos livres",
    "arma, armadura, anel e colar equipados",
    "classe",
    "profissão — e o nível/XP de ofício junto, senão quem reescolher a mesma "
    "profissão começa com a curva antiga já andada",
    "andar atual e andar máximo",
)

PRESERVADO = (
    "a linha em `jogadores` — ninguém precisa rodar `rpg comecar` de novo",
    "títulos já concedidos, o título equipado e `criado_em` (data que alimenta o Beta Tester)",
    "contagem de mortes",
)


def embed_confirmacao(total_jogadores):
    e = discord.Embed(
        title="⚠️ Reset de temporada",
        description=f"Isso afeta **{total_jogadores}** jogador(es) já cadastrados. "
                     "Backup automático roda antes de qualquer UPDATE/DELETE.",
        color=0xE63946,
    )
    e.add_field(name="Zerado em `jogadores`", value="\n".join(f"• {c}" for c in COLUNAS_ZERADAS), inline=False)
    e.add_field(name="Tabelas apagadas por inteiro", value="\n".join(f"• {t}" for t in TABELAS_APAGADAS), inline=False)
    e.add_field(name="Preservado", value="\n".join(f"• {p}" for p in PRESERVADO), inline=False)
    e.set_footer(text=f"{TIMEOUT_CONFIRMACAO}s pra confirmar, senão cancela sozinho")
    return e


def embed_confirmacao_jogador(jogador):
    e = discord.Embed(
        title=f"⚠️ Resetar classe e profissão — {jogador['nome']}",
        description="Zera classe, profissão e o nível/XP de ofício desse jogador. "
                     "Nível, atributos, equipamento e andar não mudam.",
        color=0xE63946,
    )
    e.add_field(
        name="Estado atual",
        value=(
            f"Classe: **{jogador['classe'] or '—'}**\n"
            f"Profissão: **{jogador['profissao'] or '—'}** "
            f"(ofício nível {jogador['prof_nivel']}, {jogador['prof_xp']} XP)"
        ),
        inline=False,
    )
    e.set_footer(text=f"{TIMEOUT_CONFIRMACAO}s pra confirmar, senão cancela sozinho")
    return e


class ConfirmarAcao(discord.ui.View):
    """Confirmar/Cancelar genérico — reusado por qualquer comando admin que
    precise de um "tem certeza?" antes de mexer no banco."""

    def __init__(self, autor_id):
        super().__init__(timeout=TIMEOUT_CONFIRMACAO)
        self.autor_id = autor_id
        self.confirmado = None
        self.mensagem = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("Só quem chamou o comando confirma.", ephemeral=True)
            return False
        return True

    def _travar(self):
        for item in self.children:
            item.disabled = True
        self.stop()

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirmar(self, interaction, button):
        self.confirmado = True
        self._travar()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction, button):
        self.confirmado = False
        self._travar()
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        self.confirmado = False
        self._travar()
        if self.mensagem:
            await self.mensagem.edit(view=self)


def instalar(bot):
    @bot.command(name="resetartemporada", aliases=["resettemporada"])
    @commands.is_owner()
    async def resetar_temporada(ctx):
        total = db.contar_jogadores()
        view = ConfirmarAcao(ctx.author.id)
        mensagem = await ctx.send(embed=embed_confirmacao(total), view=view)
        view.mensagem = mensagem
        await view.wait()

        if not view.confirmado:
            motivo = "Cancelado." if view.confirmado is False else "Tempo esgotado — cancelado."
            await ctx.send(motivo)
            return

        try:
            caminho_backup = db.backup_banco()
        except Exception as erro:
            await ctx.send(f"❌ Backup falhou — **nada foi alterado**. Erro: `{erro}`")
            return

        afetados = db.resetar_temporada()
        await ctx.send(
            f"✅ **{afetados}** jogador(es) resetados pra nova temporada.\n"
            f"Backup salvo em `{caminho_backup}`."
        )

    @resetar_temporada.error
    async def resetar_temporada_erro(ctx, erro):
        if isinstance(erro, commands.NotOwner):
            await ctx.send("Esse comando é só do dono do bot.")
            return
        raise erro

    @bot.command(name="resetarjogador", aliases=["resetclasse", "resetprofissao"])
    @commands.is_owner()
    async def resetar_jogador(ctx, membro: discord.Member):
        jogador = db.get_jogador(membro.id)
        if not jogador:
            await ctx.send(f"{membro.display_name} ainda não tem personagem — nunca rodou `rpg comecar`.")
            return
        if not jogador["classe"] and not jogador["profissao"]:
            await ctx.send(f"{jogador['nome']} já está sem classe e sem profissão. Nada a fazer.")
            return

        view = ConfirmarAcao(ctx.author.id)
        mensagem = await ctx.send(embed=embed_confirmacao_jogador(jogador), view=view)
        view.mensagem = mensagem
        await view.wait()

        if not view.confirmado:
            motivo = "Cancelado." if view.confirmado is False else "Tempo esgotado — cancelado."
            await ctx.send(motivo)
            return

        db.resetar_classe_profissao(membro.id)
        await ctx.send(f"✅ Classe e profissão de **{jogador['nome']}** resetadas.")

    @resetar_jogador.error
    async def resetar_jogador_erro(ctx, erro):
        if isinstance(erro, commands.NotOwner):
            await ctx.send("Esse comando é só do dono do bot.")
            return
        if isinstance(erro, (commands.MemberNotFound, commands.MissingRequiredArgument)):
            await ctx.send("Uso: `rpg resetarjogador @membro`")
            return
        raise erro

    print("admin.py carregado — rpg resetartemporada e rpg resetarjogador (dono do bot).")
