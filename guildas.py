# guildas.py
# Guildas: baú compartilhado, cargo e canal no Discord, viagem grátis pra
# home. Não importa bot.py (evita import circular): os helpers chegam por
# instalar(), mesmo padrão de combate.py/habilidades.py/profissoes.py.

import time

import discord

import andares_altos
import database as db
import paginacao
import pronomes
import salao
import travas
from admin import ConfirmarAcao
from game_data import ITENS, ANDARES, ANDAR_MAXIMO

H = {}

CUSTO_FUNDAR = 5000
MEMBROS_PARA_VALER = 3        # abaixo disso, sem viagem grátis pra home (ver decisoes.md)
CATEGORIA_GUILDAS = "Guildas"
COR_GUILDA = 0xC9A227
EXPIRA_CONVITE_SEGUNDOS = 24 * 3600
LIMITE_CONVITES_GUILDA = 5    # convites pendentes ao mesmo tempo, por guilda — não é spam
COOLDOWN_HOME_SEGUNDOS = 3 * 3600   # 1 troca de home a cada 3h, por guilda


# ---------------------------------------------------------- Discord: cargo e canal
async def criar_cargo_e_canal(ctx, nome_guilda):
    """(cargo, canal, erro) — erro é None se deu certo. Não gasta moeda nem
    grava no banco; quem chama decide a ordem (só cobra se isso funcionar)."""
    guild = ctx.guild
    if not guild.me.guild_permissions.manage_roles or not guild.me.guild_permissions.manage_channels:
        return None, None, (
            "Preciso das permissões **Gerenciar Cargos** e **Gerenciar Canais** "
            "pra fundar uma guilda. Fala com quem administra o servidor."
        )
    try:
        cargo = await guild.create_role(name=f"Guilda {nome_guilda}", mentionable=True)
        categoria = discord.utils.get(guild.categories, name=CATEGORIA_GUILDAS)
        if categoria is None:
            categoria = await guild.create_category(CATEGORIA_GUILDAS)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            cargo: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, embed_links=True,
                read_message_history=True, manage_channels=True,
            ),
        }
        slug = H["normalizar"](nome_guilda)
        slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-") or "guilda"
        while "--" in slug:
            slug = slug.replace("--", "-")
        canal = await guild.create_text_channel(
            f"guilda-{slug[:80]}", category=categoria, overwrites=overwrites,
            topic=f"Sala da guilda {nome_guilda}. Só membros enxergam.",
        )
    except discord.Forbidden:
        return None, None, "O Discord recusou: falta permissão pra criar cargo ou canal."
    except discord.HTTPException as erro:
        return None, None, f"O Discord recusou a criação ({erro.status}). Tenta de novo."
    return cargo, canal, None


async def desfazer_guilda(ctx, guilda):
    """Apaga cargo, canal e as linhas da guilda no banco — chamado quando
    o último membro sai."""
    if ctx.guild:
        cargo = ctx.guild.get_role(guilda["cargo_id"])
        canal = ctx.guild.get_channel(guilda["canal_id"])
        try:
            if cargo:
                await cargo.delete(reason="Guilda desfeita — ficou sem membros.")
            if canal:
                await canal.delete(reason="Guilda desfeita — ficou sem membros.")
        except discord.Forbidden:
            pass
    db.apagar_guilda(guilda["id"])


# ---------------------------------------------------------------------- ações
async def acao_status(ctx, j):
    guilda = db.guilda_do_membro(j["user_id"])
    if not guilda:
        e = discord.Embed(
            title="Você não tem guilda",
            description=(
                f"`rpg guilda criar <nome>` — custa **{CUSTO_FUNDAR}** 🪙.\n"
                f"Precisa de **{MEMBROS_PARA_VALER} membros** pra ela valer de verdade "
                "(viagem grátis pra home, entre outras coisas que vêm depois)."
            ),
            color=COR_GUILDA,
        )
        await ctx.send(embed=e)
        return

    membros = db.membros_da_guilda(guilda["id"])
    vale = len(membros) >= MEMBROS_PARA_VALER
    e = discord.Embed(title=f"🏰 {guilda['nome']}", color=COR_GUILDA)
    e.add_field(name="Líder", value=f"<@{guilda['lider_id']}>", inline=True)
    e.add_field(
        name="Membros",
        value=f"{len(membros)}" + ("" if vale else f"/{MEMBROS_PARA_VALER} pra valer"),
        inline=True,
    )
    e.add_field(
        name="Home",
        value=f"Andar {guilda['andar_home']} — {ANDARES[guilda['andar_home']]['nome']}",
        inline=True,
    )
    e.add_field(name="Moedas no baú", value=f"🪙 {guilda['moedas']}", inline=True)
    total_tesouros = db.contar_tesouros_salao(guilda["id"])
    tier = salao.tier_por_total(total_tesouros)
    e.add_field(
        name="🏛️ Salão", value=f"{tier['nome']} — {total_tesouros} tesouro(s)", inline=True
    )
    if not vale:
        e.add_field(
            name="⚠️ Ainda não vale",
            value=(
                "Com menos de 3 membros a viagem pra home continua sendo cobrada normal "
                "e o Salão não libera benefício nenhum, mesmo com tesouro de sobra."
            ),
            inline=False,
        )
    restante = db.checar_cooldown_raide(guilda["id"])
    raide_txt = f"Raide em {H['fmt_tempo'](restante)}" if restante > 0 else "Raide disponível agora"
    e.set_footer(text=f"{raide_txt} · rpg guilda bau · rpg guilda salao · rpg guilda log")
    await ctx.send(embed=e)


async def acao_criar(ctx, j, nome):
    if await travas.bloqueado(ctx):
        return
    if ctx.guild is None:
        await ctx.send("Esse comando só funciona dentro de um servidor.")
        return
    if db.guilda_do_membro(j["user_id"]):
        await ctx.send("Você já está em uma guilda. `rpg guilda sair` primeiro.")
        return
    nome = nome.strip()
    if not nome:
        await ctx.send("Uso: `rpg guilda criar <nome>`.")
        return
    if len(nome) > 32:
        await ctx.send("Nome muito longo — até 32 caracteres.")
        return
    if db.get_guilda_por_nome(nome):
        await ctx.send(f"Já existe uma guilda chamada **{nome}**. Escolhe outro nome.")
        return
    if j["moedas"] < CUSTO_FUNDAR:
        await ctx.send(f"Fundar uma guilda custa **{CUSTO_FUNDAR}** 🪙 e você tem {j['moedas']}.")
        return

    cargo, canal, erro = await criar_cargo_e_canal(ctx, nome)
    if erro:
        await ctx.send(erro)
        return

    db.atualizar_jogador(j["user_id"], moedas=j["moedas"] - CUSTO_FUNDAR)
    db.criar_guilda(nome, j["user_id"], 1, cargo.id, canal.id)
    try:
        await ctx.author.add_roles(cargo)
    except discord.Forbidden:
        pass

    e = discord.Embed(
        title=f"🏰 Guilda {nome} fundada",
        description=(
            f"{ctx.author.display_name} é o líder. Precisa de **{MEMBROS_PARA_VALER} membros** "
            "pra valer de verdade — `rpg guilda convidar @alguém`.\n\n"
            "Home é o andar 1 por enquanto — `rpg guilda home <andar>` muda."
        ),
        color=COR_GUILDA,
    )
    await canal.send(embed=e)
    await ctx.send(f"Guilda **{nome}** criada. Sala: {canal.mention}")


def _guild_discord(guilda):
    """O objeto discord.Guild dono da guilda, achado a partir do canal salvo
    (não guardamos o id do servidor em lugar nenhum) — usado quando a ação
    parte de uma DM (botão do convite), onde ctx.guild não existe."""
    canal = H["bot"].get_channel(guilda["canal_id"])
    return canal.guild if canal else None


async def _efetivar_entrada(guild_obj, membro_id, guilda):
    """O que só acontece de verdade na aceitação: cargo, linha em
    guilda_membros, log e limpeza dos outros convites pendentes da pessoa.
    (ok, erro) — erro é a mensagem pra mostrar se o Discord recusou o cargo."""
    cargo = guild_obj.get_role(guilda["cargo_id"]) if guild_obj else None
    membro = guild_obj.get_member(membro_id) if guild_obj else None
    if guild_obj and not membro:
        try:
            membro = await guild_obj.fetch_member(membro_id)
        except discord.NotFound:
            membro = None
    if cargo and membro:
        try:
            await membro.add_roles(cargo)
        except discord.Forbidden:
            return False, (
                "O Discord recusou atribuir o cargo da guilda — confere se meu cargo está "
                "ACIMA do cargo da guilda na lista de cargos do servidor. Ninguém foi adicionado."
            )

    db.adicionar_membro_guilda(membro_id, guilda["id"])
    db.guilda_log(guilda["id"], membro_id, "entrou")
    db.apagar_convites_do_jogador(membro_id)
    return True, None


def _resolver_convite(convites, nome_guilda, comando):
    """Escolhe qual convite pendente uma pessoa quis dizer — por nome, ou o
    único que ela tem. (convite, erro); erro é None se achou um só."""
    nome_guilda = nome_guilda.strip()
    if nome_guilda:
        convite = next((c for c in convites if c["guilda_nome"].lower() == nome_guilda.lower()), None)
        if not convite:
            nomes = ", ".join(f"**{c['guilda_nome']}**" for c in convites)
            return None, f"Você não tem convite de **{nome_guilda}**. Convites abertos: {nomes}."
        return convite, None
    if len(convites) == 1:
        return convites[0], None
    nomes = ", ".join(f"**{c['guilda_nome']}**" for c in convites)
    return None, f"Você tem mais de um convite — especifica: `rpg guilda {comando} <nome>`. Abertos: {nomes}."


class BotaoAceitarConvite(discord.ui.View):
    """Atalho na DM do convite. NÃO é o caminho oficial — o bot roda no PC
    do Rafael e reinicia com frequência, então essa view some da memória
    bem antes das 24h de validade do convite. `rpg guilda aceitar <nome>`
    sempre funciona, botão ou não; por isso a mensagem do convite sempre
    cita o comando também."""

    def __init__(self, guilda_id, user_id):
        super().__init__(timeout=None)
        self.guilda_id = guilda_id
        self.user_id = user_id

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Esse convite não é seu.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.success, emoji="✅")
    async def aceitar(self, interaction, button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        if db.guilda_do_membro(self.user_id):
            await interaction.followup.send("Você já está em uma guilda.", ephemeral=True)
            return
        convite = db.get_convite(self.guilda_id, self.user_id)
        if not convite:
            await interaction.followup.send(
                "Esse convite não existe mais (venceu ou já foi resolvido). "
                "`rpg guilda convites` mostra o que está aberto agora.", ephemeral=True
            )
            return
        guilda = db.get_guilda(self.guilda_id)
        if not guilda:
            db.apagar_convite(self.guilda_id, self.user_id)
            await interaction.followup.send("Essa guilda não existe mais.", ephemeral=True)
            return

        ok, erro = await _efetivar_entrada(_guild_discord(guilda), self.user_id, guilda)
        if not ok:
            await interaction.followup.send(erro, ephemeral=True)
            return
        await interaction.followup.send(f"Você entrou na guilda **{guilda['nome']}**!", ephemeral=True)


async def acao_convidar(ctx, j):
    if ctx.guild is None:
        await ctx.send("Esse comando só funciona dentro de um servidor.")
        return
    guilda = db.guilda_do_membro(j["user_id"])
    if not guilda:
        await ctx.send("Você não está em uma guilda.")
        return
    if guilda["lider_id"] != j["user_id"]:
        await ctx.send("Só o líder convida.")
        return
    if not ctx.message.mentions:
        await ctx.send("Uso: `rpg guilda convidar @alguém`.")
        return

    alvo = ctx.message.mentions[0]
    if not db.get_jogador(alvo.id):
        await ctx.send(f"{alvo.display_name} ainda não entrou na torre — `rpg comecar` primeiro.")
        return
    if db.guilda_do_membro(alvo.id):
        await ctx.send(f"{alvo.display_name} já está em uma guilda.")
        return

    renovando = db.get_convite(guilda["id"], alvo.id) is not None
    if not renovando and db.contar_convites_pendentes_guilda(guilda["id"]) >= LIMITE_CONVITES_GUILDA:
        await ctx.send(
            f"**{guilda['nome']}** já tem {LIMITE_CONVITES_GUILDA} convites pendentes — "
            "espera algum expirar ou ser respondido antes de mandar outro."
        )
        return

    db.criar_ou_renovar_convite(guilda["id"], alvo.id, j["user_id"], EXPIRA_CONVITE_SEGUNDOS)
    prazo = H["fmt_tempo"](EXPIRA_CONVITE_SEGUNDOS)

    embed_convite = discord.Embed(
        title=f"🏰 Convite para {guilda['nome']}",
        description=(
            f"**{ctx.author.display_name}** te convidou pra guilda **{guilda['nome']}**.\n\n"
            f"`rpg guilda aceitar {guilda['nome']}` — entrar\n"
            f"`rpg guilda recusar {guilda['nome']}` — recusar\n\n"
            f"Vale por **{prazo}**. O comando é o jeito garantido de responder — o botão "
            "abaixo é só atalho e pode já não estar ativo se o bot tiver reiniciado."
        ),
        color=COR_GUILDA,
    )
    try:
        await alvo.send(embed=embed_convite, view=BotaoAceitarConvite(guilda["id"], alvo.id))
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send(
            f"Convite registrado pra {alvo.mention}, válido por {prazo}, mas não consegui mandar DM "
            f"(deve estar fechada) — avisa por fora: `rpg guilda aceitar {guilda['nome']}` responde."
        )
    else:
        await ctx.send(f"Convite enviado a {alvo.mention} por DM. Vale por {prazo}.")
    db.guilda_log(guilda["id"], j["user_id"], "convidou")


async def acao_aceitar(ctx, j, nome_guilda):
    if ctx.guild is None:
        await ctx.send("Esse comando só funciona dentro do servidor (não na DM).")
        return
    if db.guilda_do_membro(j["user_id"]):
        await ctx.send("Você já está em uma guilda. `rpg guilda sair` primeiro.")
        return

    convites = db.convites_do_jogador(j["user_id"])
    if not convites:
        await ctx.send("Você não tem convite pendente nenhum.")
        return
    convite, erro = _resolver_convite(convites, nome_guilda, "aceitar")
    if erro:
        await ctx.send(erro)
        return

    guilda = db.get_guilda(convite["guilda_id"])
    if not guilda:
        db.apagar_convite(convite["guilda_id"], j["user_id"])
        await ctx.send("Essa guilda não existe mais — o convite era antigo. Removido.")
        return

    ok, erro = await _efetivar_entrada(ctx.guild, j["user_id"], guilda)
    if not ok:
        await ctx.send(erro)
        return
    await ctx.send(f"Você entrou na guilda **{guilda['nome']}**!")


async def acao_recusar(ctx, j, nome_guilda):
    convites = db.convites_do_jogador(j["user_id"])
    if not convites:
        await ctx.send("Você não tem convite pendente nenhum.")
        return
    convite, erro = _resolver_convite(convites, nome_guilda, "recusar")
    if erro:
        await ctx.send(erro)
        return

    db.apagar_convite(convite["guilda_id"], j["user_id"])
    await ctx.send(f"Convite de **{convite['guilda_nome']}** recusado.")


async def acao_convites(ctx, j):
    convites = db.convites_do_jogador(j["user_id"])
    if not convites:
        await ctx.send("Nenhum convite pendente no momento.")
        return
    agora = time.time()
    linhas = [
        f"**{c['guilda_nome']}** — convidado por <@{c['convidado_por']}>, "
        f"expira em {H['fmt_tempo'](max(0, c['expira_em'] - agora))}"
        for c in convites
    ]
    e = discord.Embed(title="Seus convites de guilda", description="\n".join(linhas), color=COR_GUILDA)
    e.set_footer(text="rpg guilda aceitar <nome> · rpg guilda recusar <nome>")
    await ctx.send(embed=e)


async def acao_sair(ctx, j):
    guilda = db.guilda_do_membro(j["user_id"])
    if not guilda:
        await ctx.send("Você não está em uma guilda.")
        return

    membros = db.membros_da_guilda(guilda["id"])
    if ctx.guild:
        cargo = ctx.guild.get_role(guilda["cargo_id"])
        membro_discord = ctx.guild.get_member(j["user_id"])
        if cargo and membro_discord:
            try:
                await membro_discord.remove_roles(cargo)
            except discord.Forbidden:
                pass

    db.remover_membro_guilda(j["user_id"])

    if len(membros) <= 1:
        nome = guilda["nome"]
        await desfazer_guilda(ctx, guilda)
        await ctx.send(f"Você saiu — era o último membro, então a guilda **{nome}** foi desfeita.")
        return

    if guilda["lider_id"] == j["user_id"]:
        proximo = next(m for m in membros if m["user_id"] != j["user_id"])
        db.transferir_lideranca_guilda(guilda["id"], proximo["user_id"])
        await ctx.send(
            f"Você saiu. Como era o líder, a liderança de **{guilda['nome']}** passou pra "
            f"<@{proximo['user_id']}> (quem está há mais tempo na guilda)."
        )
    else:
        await ctx.send(f"Você saiu da guilda **{guilda['nome']}**.")


async def acao_expulsar(ctx, j):
    guilda = db.guilda_do_membro(j["user_id"])
    if not guilda:
        await ctx.send("Você não está em uma guilda.")
        return
    if guilda["lider_id"] != j["user_id"]:
        await ctx.send("Só o líder expulsa.")
        return
    if not ctx.message.mentions:
        await ctx.send("Uso: `rpg guilda expulsar @alguém`.")
        return

    alvo = ctx.message.mentions[0]
    if alvo.id == j["user_id"]:
        await ctx.send("Pra sair você mesmo, usa `rpg guilda sair`.")
        return
    alvo_guilda = db.guilda_do_membro(alvo.id)
    if not alvo_guilda or alvo_guilda["id"] != guilda["id"]:
        await ctx.send(f"{alvo.display_name} não é membro da sua guilda.")
        return

    db.remover_membro_guilda(alvo.id)
    if ctx.guild:
        cargo = ctx.guild.get_role(guilda["cargo_id"])
        if cargo:
            try:
                await alvo.remove_roles(cargo)
            except discord.Forbidden:
                pass
    db.guilda_log(guilda["id"], j["user_id"], "expulsou")
    expulso = pronomes.concordar("foi expuls{o|a}", db.get_jogador(alvo.id)["pronome"])
    await ctx.send(f"{alvo.display_name} {expulso} da guilda **{guilda['nome']}**.")


async def acao_home(ctx, j, argumento):
    guilda = db.guilda_do_membro(j["user_id"])
    if not guilda:
        await ctx.send("Você não está em uma guilda.")
        return
    if guilda["lider_id"] != j["user_id"]:
        await ctx.send("Só o líder muda a home.")
        return
    restante = db.checar_cooldown_home(guilda["id"])
    if restante > 0:
        await ctx.send(f"⏳ A home dessa guilda só troca de novo em **{H['fmt_tempo'](restante)}**.")
        return
    argumento = argumento.strip()
    if not argumento.isdigit():
        await ctx.send(f"Uso: `rpg guilda home <andar>`. Home atual: andar {guilda['andar_home']}.")
        return
    andar = int(argumento)
    if andar < 1 or andar > ANDAR_MAXIMO:
        await ctx.send(f"Andar inválido. A torre vai de 1 a {ANDAR_MAXIMO}.")
        return
    if andar > andares_altos.ANDAR_ACIMA_DO_SELO:
        await ctx.send(
            f"Home não pode passar do andar {andares_altos.ANDAR_ACIMA_DO_SELO} — "
            "acima do Selo não tem loja nem ferreiro, guilda não mora lá."
        )
        return
    # Gate do Salão -- guildas que já tinham home acima do que o tier atual
    # libera (de antes desse cartão existir) NÃO são rebaixadas em silêncio;
    # o gate só entra na hora de TROCAR, que é ato voluntário e já tem
    # cooldown de 3h (ver decisoes.md § Salão da Guilda -- migração).
    total_tesouros = db.contar_tesouros_salao(guilda["id"])
    membros = db.membros_da_guilda(guilda["id"])
    tier = salao.tier_efetivo(total_tesouros, len(membros), MEMBROS_PARA_VALER)
    if andar > tier["andar_home_max"]:
        prox = salao.proximo_tier(total_tesouros)
        extra = (
            f" — faltam **{prox['min_tesouros'] - total_tesouros}** tesouros pro tier {prox['nome']} "
            f"(libera até o andar {prox['andar_home_max']})"
            if prox and len(membros) >= MEMBROS_PARA_VALER
            else (f" — precisa de {MEMBROS_PARA_VALER}+ membros pro Salão valer alguma coisa"
                  if len(membros) < MEMBROS_PARA_VALER else "")
        )
        await ctx.send(
            f"O Salão da guilda está em **{tier['nome']}**, que libera home só até o andar "
            f"{tier['andar_home_max']}{extra}."
        )
        return
    if andar > j["andar_max"]:
        await ctx.send(f"Você (o líder) ainda não destrancou o andar {andar}.")
        return
    db.definir_home_guilda(guilda["id"], andar)
    db.set_cooldown_home(guilda["id"], COOLDOWN_HOME_SEGUNDOS)
    await ctx.send(f"Home da guilda **{guilda['nome']}** agora é o andar {andar} — {ANDARES[andar]['nome']}.")


async def acao_bau(ctx, j, argumento=""):
    guilda = db.guilda_do_membro(j["user_id"])
    if not guilda:
        await ctx.send("Você não está em uma guilda.")
        return
    itens = db.get_bau(guilda["id"])
    pagina = int(argumento) if argumento.strip().isdigit() else 1
    entradas = [
        (
            f"{ITENS[i['item']]['emoji']} {ITENS[i['item']]['nome']}" if i["item"] in ITENS else i["item"],
            f"x{i['qtd']}",
        )
        for i in itens
    ] or [("Itens", "Vazio.")]   # sem isso, o baú vazio perderia o field de moedas junto
    await paginacao.enviar_paginado(
        ctx, entradas, f"Baú de {guilda['nome']}", COR_GUILDA,
        descricao=f"🪙 {guilda['moedas']} moedas",
        rodape_extra="rpg guilda depositar <item> <qtd> · rpg guilda sacar <item> <qtd>",
        pagina_inicial=pagina,
    )


async def acao_depositar(ctx, j, argumento):
    if await travas.bloqueado(ctx):
        return
    guilda = db.guilda_do_membro(j["user_id"])
    if not guilda:
        await ctx.send("Você não está em uma guilda.")
        return
    if not argumento.strip():
        await ctx.send(
            "Uso: `rpg guilda depositar <item> <quantidade>` (baú) ou "
            "`rpg guilda depositar <tesouro> [assinatura]` (Salão, irreversível)."
        )
        return

    # tesouro de chefe é um fluxo à parte -- irreversível, com confirmação e
    # assinatura opcional (Salão), nunca cai no baú comum. Checa ANTES do
    # parsing de quantidade porque tesouro não tem quantidade (sempre 1) e
    # o resto do texto é a assinatura, não um número.
    tesouro, assinatura = salao.extrair_tesouro(argumento)
    if tesouro:
        await salao.depositar(ctx, j, guilda, tesouro, assinatura, ConfirmarAcao)
        return

    texto, qtd = H["separar_quantidade"](argumento)
    possuidos = [i["item"] for i in db.get_inventario(j["user_id"])]
    item = H["encontrar_item"](texto, possuidos)
    if not item or not db.remove_item(j["user_id"], item, qtd):
        tem = next((i["qtd"] for i in db.get_inventario(j["user_id"]) if i["item"] == item), 0) if item else 0
        await ctx.send(f"Você só tem {tem}x disso na mochila." if item else "Você não tem esse item.")
        return
    db.bau_add_item(guilda["id"], item, qtd)
    db.guilda_log(guilda["id"], j["user_id"], "depositou", item, qtd)
    await ctx.send(f"Depositado no baú: {ITENS[item]['emoji']} {ITENS[item]['nome']} x{qtd}.")


async def acao_sacar(ctx, j, argumento):
    if await travas.bloqueado(ctx):
        return
    guilda = db.guilda_do_membro(j["user_id"])
    if not guilda:
        await ctx.send("Você não está em uma guilda.")
        return
    if not argumento.strip():
        await ctx.send("Uso: `rpg guilda sacar <item> <quantidade>`.")
        return
    texto, qtd = H["separar_quantidade"](argumento)
    no_bau = [i["item"] for i in db.get_bau(guilda["id"])]
    item = H["encontrar_item"](texto, no_bau)
    if not item or not db.bau_remove_item(guilda["id"], item, qtd):
        tem = next((i["qtd"] for i in db.get_bau(guilda["id"]) if i["item"] == item), 0) if item else 0
        await ctx.send(f"O baú só tem {tem}x disso." if item else "Esse item não está no baú.")
        return
    db.add_item(j["user_id"], item, qtd)
    db.guilda_log(guilda["id"], j["user_id"], "sacou", item, qtd)
    await ctx.send(f"Sacado do baú: {ITENS[item]['emoji']} {ITENS[item]['nome']} x{qtd} — foi pra sua mochila.")


async def acao_log(ctx, j):
    guilda = db.guilda_do_membro(j["user_id"])
    if not guilda:
        await ctx.send("Você não está em uma guilda.")
        return
    entradas = db.get_guilda_log(guilda["id"], limite=10)
    if not entradas:
        await ctx.send("Nada no log ainda.")
        return
    linhas = []
    for ent in entradas:
        quando = time.strftime("%d/%m %H:%M", time.localtime(ent["quando"]))
        item_txt = ""
        if ent["item"]:
            nome_item = ITENS[ent["item"]]["nome"] if ent["item"] in ITENS else ent["item"]
            item_txt = f" {ent['qtd']}x {nome_item}"
        linhas.append(f"`{quando}` <@{ent['user_id']}> {ent['acao']}{item_txt}")
    e = discord.Embed(title=f"Log de {guilda['nome']}", description="\n".join(linhas), color=COR_GUILDA)
    await ctx.send(embed=e)


async def acao_salao(ctx, j, argumento):
    guilda = db.guilda_do_membro(j["user_id"])
    if not guilda:
        await ctx.send("Você não está em uma guilda.")
        return
    partes = argumento.split(maxsplit=1)
    sub = H["normalizar"](partes[0]) if partes else ""
    resto = partes[1] if len(partes) > 1 else ""

    if sub in ("historico", "historia"):
        await salao.acao_historico(ctx, guilda, resto)
    elif sub == "assinar":
        await salao.acao_assinar(ctx, j, guilda, resto)
    elif sub in ("apagar", "removerassinatura"):
        await salao.acao_apagar_assinatura(ctx, j, guilda, resto)
    elif sub == "limpar":
        await salao.acao_limpar_assinatura(ctx, j, guilda, resto)
    elif sub.isdigit():
        await salao.acao_vitrine(ctx, guilda, pagina=int(sub))
    else:
        await salao.acao_vitrine(ctx, guilda)


# ---------------------------------------------------------------- instalacao
def instalar(bot, contexto):
    H.update(contexto)

    @bot.command(name="guilda", aliases=["g", "guild"])
    async def guilda_cmd(ctx, *, argumento: str = ""):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return

        partes = argumento.split(maxsplit=1)
        acao = H["normalizar"](partes[0]) if partes else ""
        resto = partes[1] if len(partes) > 1 else ""

        if not acao:
            await acao_status(ctx, j)
        elif acao in ("criar", "fundar"):
            await acao_criar(ctx, j, resto)
        elif acao in ("convidar", "invite", "chamar"):
            await acao_convidar(ctx, j)
        elif acao in ("aceitar", "accept"):
            await acao_aceitar(ctx, j, resto)
        elif acao in ("recusar", "decline", "rejeitar"):
            await acao_recusar(ctx, j, resto)
        elif acao in ("convites", "invites", "convite"):
            await acao_convites(ctx, j)
        elif acao in ("sair", "leave"):
            await acao_sair(ctx, j)
        elif acao in ("expulsar", "kick"):
            await acao_expulsar(ctx, j)
        elif acao == "home":
            await acao_home(ctx, j, resto)
        elif acao in ("bau", "vault"):
            await acao_bau(ctx, j, resto)
        elif acao in ("depositar", "deposit", "guardar"):
            await acao_depositar(ctx, j, resto)
        elif acao in ("sacar", "retirar", "withdraw"):
            await acao_sacar(ctx, j, resto)
        elif acao in ("log", "historico"):
            await acao_log(ctx, j)
        elif acao in ("salao", "hall"):
            await acao_salao(ctx, j, resto)
        else:
            await ctx.send(
                "Não conheço esse comando de guilda. Opções: criar, convidar, aceitar, recusar, "
                "convites, sair, expulsar, home, bau, depositar, sacar, log, salao."
            )

    print(
        "guildas.py carregado — rpg guilda "
        "(criar/convidar/aceitar/recusar/convites/sair/expulsar/home/bau/depositar/sacar/log/salao)."
    )
