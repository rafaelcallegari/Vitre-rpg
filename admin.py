# admin.py
# Comandos administrativos — restritos ao dono do bot (commands.is_owner(),
# checa contra o dono do app no portal do Discord). Não depende de nada de
# bot.py, então não usa o padrão H — mesmo estilo do agenda.py.

import os

import discord
from discord.ext import commands, tasks

import database as db
import travas

TIMEOUT_CONFIRMACAO = 30

CANAL_TORRE_ID = os.getenv("CANAL_TORRE_ID")

# categoria -> cor/ícone/título/moldura do embed de `rpg aviso`. Mapa de
# domínio: constante nomeada, acesso por `.get()`, nunca subscript direto —
# a chave vem de texto digitado no Discord, mesma regra do PAPEL_NPC
# (decisoes.md § Padrão — mapa de domínio nunca é subscript direto).
CATEGORIAS_AVISO = {
    "manutencao": {
        "cor": 0xF4A261,
        "icone": "🔧",
        "titulo": "Manutenção",
        "descricao": "o bot vai cair ou já voltou",
        "moldura": "🗼 A Torre vai fechar por um instante — nada é perdido.",
    },
    "atualizacao": {
        "cor": 0x2A9D8F,
        "icone": "🆕",
        "titulo": "Atualização",
        "descricao": "mudança que entrou no jogo",
        "moldura": "🗼 A Torre mudou.",
    },
    "evento": {
        "cor": 0x9B5DE5,
        "icone": "🎉",
        "titulo": "Evento",
        "descricao": "coisa acontecendo com hora marcada",
        "moldura": "🗼 Algo especial está acontecendo.",
    },
    "urgente": {
        "cor": 0xE63946,
        "icone": "🚨",
        "titulo": "Urgente",
        "descricao": "precisa de atenção agora",
        "moldura": "🗼 Atenção imediata.",
    },
    "recado": {
        "cor": 0x8D99AE,
        "icone": "💬",
        "titulo": "Recado",
        "descricao": "o resto",
        "moldura": "🗼 Um recado da administração.",
    },
}

EXEMPLO_AVISO = "rpg aviso manutencao --everyone Bot reiniciando em 10 minutos"

INTERVALO_CHECAGEM_MANUTENCAO_SEG = 15

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
    "a guilda em si — nome, membros e cargo do Discord continuam de pé; "
    "ninguém refunda nem paga os 5.000 de fundação de novo",
)

GUILDA_RESET = (
    "**baú da guilda** (`guilda_bau`) — todo item guardado é apagado",
    "**moedas da guilda** voltam a 0 — senão quem tem guilda começa a temporada "
    "rico enquanto quem não tem começa do zero",
    "**Salão da guilda** volta a Tier 0 — o histórico de quem depositou o quê em "
    "temporadas passadas fica guardado, só a contagem ativa reseta "
    "(`rpg guilda salao historico`)",
    "**home da guilda** volta pro andar 1 — junto do Salão, pra não sobrar home em "
    "andar alto sem tesouro nenhum da temporada nova pra justificar aquele tier",
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
    e.add_field(name="Guildas", value="\n".join(f"• {g}" for g in GUILDA_RESET), inline=False)
    e.add_field(name="Preservado", value="\n".join(f"• {p}" for p in PRESERVADO), inline=False)
    e.set_footer(text=f"{TIMEOUT_CONFIRMACAO}s pra confirmar, senão cancela sozinho")
    return e


def texto_ajuda_aviso():
    """Pura, sem `ctx` — lida direto de `CATEGORIAS_AVISO` pra nunca
    desatualizar (some uma categoria do dict, some daqui sozinho)."""
    linhas = [
        f"{dados['icone']} `{categoria}` — {dados['descricao']}"
        for categoria, dados in CATEGORIAS_AVISO.items()
    ]
    return (
        "🗼 **Categorias de `rpg aviso`**\n"
        + "\n".join(linhas)
        + f"\n\nExemplo: `{EXEMPLO_AVISO}`"
    )


def embed_aviso(categoria, mensagem):
    """Pura — sem `ctx` nem rede, só monta o Embed. Levanta `ValueError` (texto
    já pronto pra mandar de volta pro jogador) se a categoria não existe."""
    dados = CATEGORIAS_AVISO.get(categoria.lower())
    if dados is None:
        validas = ", ".join(CATEGORIAS_AVISO)
        raise ValueError(f"Categoria `{categoria}` não existe. Válidas: {validas}.")
    e = discord.Embed(
        title=f"{dados['icone']} {dados['titulo']}",
        description=mensagem,
        color=dados["cor"],
    )
    e.set_footer(text=dados["moldura"])
    return e


async def avisar_dono_pode_reiniciar(bot, owner_id):
    """DM de "pode reiniciar" — separado do loop/comando que chama pra dar
    pra testar sem precisar de bot de verdade (só um bot falso com
    fetch_user). HTTPException cobre tanto usuário não encontrado quanto DM
    fechada (Forbidden é subclasse), sem derrubar quem chamou."""
    try:
        usuario = await bot.fetch_user(owner_id)
        await usuario.send(
            "✅ Nenhuma luta ativa agora — pode reiniciar o bot com segurança. "
            "A manutenção segue ligada até `rpg manutencao fim` ou o prazo acabar."
        )
    except discord.HTTPException as erro:
        print(f"admin.py: falha ao avisar fim de manutenção — {erro}")


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

    @bot.command(name="removeravatar")
    @commands.is_owner()
    async def remover_avatar(ctx, membro: discord.Member):
        """Moderação de conteúdo -- sem confirmação por botão de propósito.
        Diferente de resetartemporada/resetarjogador (perdem progresso de
        jogo), tirar um avatar é reversível na hora (o jogador manda outro)
        e o Rafael só roda isso depois de já ter visto a imagem errada --
        não precisa de "tem certeza?" pra algo que ele decidiu olhando."""
        jogador = db.get_jogador(membro.id)
        if not jogador:
            await ctx.send(f"{membro.display_name} ainda não tem personagem — nunca rodou `rpg comecar`.")
            return
        if not jogador["avatar_msg_id"]:
            await ctx.send(f"{jogador['nome']} já está sem avatar. Nada a fazer.")
            return

        db.atualizar_jogador(membro.id, avatar_msg_id=None, avatar_url=None)
        await ctx.send(f"✅ Avatar de **{jogador['nome']}** removido.")

    @remover_avatar.error
    async def remover_avatar_erro(ctx, erro):
        if isinstance(erro, commands.NotOwner):
            await ctx.send("Esse comando é só do dono do bot.")
            return
        if isinstance(erro, (commands.MemberNotFound, commands.MissingRequiredArgument)):
            await ctx.send("Uso: `rpg removeravatar @membro`")
            return
        raise erro

    @tasks.loop(seconds=INTERVALO_CHECAGEM_MANUTENCAO_SEG)
    async def checar_fim_de_manutencao():
        """Só existe enquanto há luta em andamento pra esperar — se ninguém
        estava lutando quando a manutenção ligou, o aviso já saiu na hora
        (dentro do comando) e esse loop nem chega a nascer. Poll em vez de
        gancho dentro de combate.py/raide.py de propósito: os pontos onde
        uma luta termina são vários (vitória, derrota, fuga, timeout, em
        dois arquivos) e travas._em_luta já é a fonte única da verdade —
        ler o tamanho dela a cada 15s é mais simples e menos arriscado do
        que espalhar uma chamada nova em cada um desses pontos."""
        if not travas.manutencao_ativa():
            checar_fim_de_manutencao.stop()
            return
        if travas.manutencao_notificada() or not travas.ninguem_em_luta():
            return
        travas.marcar_manutencao_notificada()
        await avisar_dono_pode_reiniciar(bot, travas.manutencao_owner_id())

    @bot.command(name="aviso")
    @commands.is_owner()
    async def aviso_cmd(ctx, categoria: str = None, *, resto: str = None):
        if categoria is None:
            await ctx.send(texto_ajuda_aviso())
            return

        marcar_everyone = False
        if resto:
            partes = resto.split(maxsplit=1)
            if partes[0].lower() == "--everyone":
                marcar_everyone = True
                resto = partes[1] if len(partes) > 1 else None

        if not resto:
            await ctx.send("Uso: `rpg aviso <categoria> [--everyone] <mensagem>`")
            return

        try:
            embed = embed_aviso(categoria, resto)
        except ValueError as erro:
            await ctx.send(str(erro))
            return

        canal = bot.get_channel(int(CANAL_TORRE_ID)) if CANAL_TORRE_ID else None
        if canal is None:
            await ctx.send("CANAL_TORRE_ID não configurado (ou canal não encontrado) — aviso não foi enviado.")
            return

        try:
            await canal.send(
                content="@everyone" if marcar_everyone else None,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(everyone=marcar_everyone),
            )
        except discord.HTTPException as erro:
            await ctx.send(f"❌ Falha ao enviar o aviso: `{erro}`")
            return

        await ctx.send(f"✅ Aviso enviado em {canal.mention}.")

    @aviso_cmd.error
    async def aviso_cmd_erro(ctx, erro):
        # `categoria` e `resto` têm default None -- MissingRequiredArgument
        # não é mais alcançável aqui (ver `rpg aviso` sem argumento acima).
        if isinstance(erro, commands.NotOwner):
            await ctx.send("Esse comando é só do dono do bot.")
            return
        raise erro

    @bot.command(name="manutencao")
    @commands.is_owner()
    async def manutencao_cmd(ctx, arg: str = None):
        if arg is not None and arg.lower() == "fim":
            if not travas.manutencao_ativa():
                await ctx.send("Manutenção já está desligada.")
                return
            travas.desligar_manutencao()
            await ctx.send("✅ Manutenção desligada antes do prazo.")
            return

        if arg is None:
            if travas.manutencao_ativa():
                await ctx.send(f"🔧 Manutenção ativa — faltam **{travas.fmt_restante(travas.manutencao_restante())}**.")
            else:
                await ctx.send("Manutenção desligada. Uso: `rpg manutencao <minutos>` ou `rpg manutencao fim`.")
            return

        try:
            minutos = int(arg)
        except ValueError:
            await ctx.send("Uso: `rpg manutencao <minutos>` ou `rpg manutencao fim`.")
            return
        if minutos <= 0:
            await ctx.send("Minutos precisa ser um número positivo.")
            return

        travas.ligar_manutencao(minutos, ctx.author.id)
        await ctx.send(
            f"🔧 Manutenção ligada por **{minutos} min** — `rpg boss`/`rpg party`/`rpg raide` "
            "bloqueados até lá. Luta já em andamento não é interrompida."
        )

        if travas.ninguem_em_luta():
            travas.marcar_manutencao_notificada()
            await avisar_dono_pode_reiniciar(bot, ctx.author.id)
        elif not checar_fim_de_manutencao.is_running():
            checar_fim_de_manutencao.start()

    @manutencao_cmd.error
    async def manutencao_cmd_erro(ctx, erro):
        if isinstance(erro, commands.NotOwner):
            await ctx.send("Esse comando é só do dono do bot.")
            return
        raise erro

    print("admin.py carregado — rpg resetartemporada, rpg resetarjogador, rpg aviso e rpg manutencao (dono do bot).")
