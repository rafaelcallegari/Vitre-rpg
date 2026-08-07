# trocas.py
# Pix (transferência de moedas à distância) e trade (troca presencial de
# item/moeda). Mesmo padrão do combate.py/profissoes.py: não importa bot.py,
# recebe os helpers em instalar(). Nenhuma tabela nova — pix é uma
# UPDATE só, e o estado de uma troca em andamento vive em memória (ver
# decisoes.md, se o bot cair no meio a troca simplesmente não aconteceu).

import discord

import database as db
from game_data import ANDARES, ITENS

H = {}

TIMEOUT_PIX = 60
TIMEOUT_TROCA = 3 * 60
MAX_ITENS_TROCA = 8

# user_id de quem tem um pix/troca pendente agora — só um de cada por vez.
PIX_PENDENTES = set()
TROCAS_ATIVAS = set()


def _extrair_valor(texto):
    """Acha o primeiro token só de dígitos no argumento — a menção (<@123>)
    nunca bate nisso, então funciona sem precisar cortar a menção manualmente."""
    for token in texto.split():
        if token.isdigit():
            return int(token)
    return None


# ==================== pix ====================
class ConfirmarPix(discord.ui.View):
    def __init__(self, autor_id):
        super().__init__(timeout=TIMEOUT_PIX)
        self.autor_id = autor_id
        self.confirmado = None  # None = estourou o tempo, True/False = clicou
        self.mensagem = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("Só quem mandou o pix confirma.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.success, emoji="✅")
    async def confirmar(self, interaction, button):
        self.confirmado = True
        self.stop()
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction, button):
        self.confirmado = False
        self.stop()
        await interaction.response.edit_message(view=None)

    async def on_timeout(self):
        if self.mensagem:
            await self.mensagem.edit(view=None)


# ==================== trade ====================
class Troca:
    def __init__(self, iniciador_id, alvo_id, andar):
        self.iniciador_id = iniciador_id
        self.alvo_id = alvo_id
        self.andar = andar
        self.ofertas = {
            iniciador_id: {"itens": {}, "moedas": 0},
            alvo_id: {"itens": {}, "moedas": 0},
        }
        self.prontos = {iniciador_id: False, alvo_id: False}
        self.mensagem = None

    def resetar_prontos(self):
        for uid in self.prontos:
            self.prontos[uid] = False


def embed_troca(troca, membro_a, membro_b, titulo="🤝 Troca"):
    e = discord.Embed(title=titulo, color=ANDARES[troca.andar]["cor"])
    for user_id, membro in ((troca.iniciador_id, membro_a), (troca.alvo_id, membro_b)):
        oferta = troca.ofertas[user_id]
        linhas = [f"{ITENS[k]['emoji']} {ITENS[k]['nome']} x{q}" for k, q in oferta["itens"].items()]
        if oferta["moedas"]:
            linhas.append(f"🪙 {oferta['moedas']} moedas")
        valor = "\n".join(linhas) if linhas else "*(vazio)*"
        pronto = "✅ Pronto" if troca.prontos[user_id] else "⏳ Ajustando"
        e.add_field(name=f"{membro.display_name} — {pronto}", value=valor, inline=True)
    e.set_footer(text="Qualquer alteração na oferta derruba os dois ✅ de novo.")
    return e


def _liberar(*user_ids):
    for uid in user_ids:
        TROCAS_ATIVAS.discard(uid)


def _checar_item_para_oferta(user_id, chave, qtd, oferta_atual):
    """Devolve None se o item pode entrar na oferta, ou a mensagem de erro."""
    if not ITENS[chave].get("vendavel", True):
        return f"**{ITENS[chave]['nome']}** não se troca — é intransferível."
    if db.get_upgrade(user_id, chave) > 0:
        nivel = db.get_upgrade(user_id, chave)
        return (
            f"**{ITENS[chave]['nome']}** está melhorado (+{nivel}) — o bônus é preso a você, "
            "não dá pra transferir. Desmancha (`rpg desmanchar`) ou oferece uma cópia sem "
            "melhoria, se tiver mais de uma."
        )
    novo_item = chave not in oferta_atual["itens"]
    if novo_item and len(oferta_atual["itens"]) >= MAX_ITENS_TROCA:
        return f"Máximo de {MAX_ITENS_TROCA} itens distintos por oferta."
    return None


def _mover(conn, de_id, para_id, oferta):
    """Aplica uma oferta já revalidada — mesma forma de UPDATE que
    database.atualizar_jogador/add_item/remove_item usam, só que na mesma
    conexão das duas ofertas, pra ficar tudo atômico."""
    if oferta["moedas"]:
        conn.execute("UPDATE jogadores SET moedas = moedas - ? WHERE user_id = ?", (oferta["moedas"], de_id))
        conn.execute("UPDATE jogadores SET moedas = moedas + ? WHERE user_id = ?", (oferta["moedas"], para_id))
    for chave, qtd in oferta["itens"].items():
        conn.execute(
            "UPDATE inventario SET qtd = qtd - ? WHERE user_id = ? AND item = ?", (qtd, de_id, chave)
        )
        conn.execute(
            "DELETE FROM inventario WHERE user_id = ? AND item = ? AND qtd <= 0", (de_id, chave)
        )
        conn.execute(
            """INSERT INTO inventario (user_id, item, qtd) VALUES (?, ?, ?)
               ON CONFLICT(user_id, item) DO UPDATE SET qtd = qtd + excluded.qtd""",
            (para_id, chave, qtd),
        )


def _commitar_troca(troca):
    """Revalida saldo, inventário, andar e melhoria dos dois dentro de uma
    única conexão antes de mover qualquer coisa. Devolve (sucesso, motivo)."""
    with db.conectar() as conn:
        row_a = conn.execute(
            "SELECT * FROM jogadores WHERE user_id = ?", (troca.iniciador_id,)
        ).fetchone()
        row_b = conn.execute(
            "SELECT * FROM jogadores WHERE user_id = ?", (troca.alvo_id,)
        ).fetchone()
        if not row_a or not row_b:
            return False, "um dos dois não tem mais personagem."
        ja, jb = dict(row_a), dict(row_b)

        if ja["andar"] != jb["andar"]:
            return False, "vocês não estão mais no mesmo andar."

        oferta_a = troca.ofertas[troca.iniciador_id]
        oferta_b = troca.ofertas[troca.alvo_id]

        if ja["moedas"] < oferta_a["moedas"]:
            return False, f"{ja['nome']} não tem mais {oferta_a['moedas']} 🪙 (saldo atual: {ja['moedas']})."
        if jb["moedas"] < oferta_b["moedas"]:
            return False, f"{jb['nome']} não tem mais {oferta_b['moedas']} 🪙 (saldo atual: {jb['moedas']})."

        for user_id, oferta, nome in ((troca.iniciador_id, oferta_a, ja["nome"]),
                                       (troca.alvo_id, oferta_b, jb["nome"])):
            for chave, qtd in oferta["itens"].items():
                row = conn.execute(
                    "SELECT qtd FROM inventario WHERE user_id = ? AND item = ?", (user_id, chave)
                ).fetchone()
                tem = row["qtd"] if row else 0
                if tem < qtd:
                    return False, f"{nome} não tem mais {qtd}x {ITENS[chave]['nome']} (tem {tem})."
                nivel_row = conn.execute(
                    "SELECT nivel FROM upgrades WHERE user_id = ? AND item = ?", (user_id, chave)
                ).fetchone()
                if nivel_row and nivel_row["nivel"] > 0:
                    return False, (
                        f"**{ITENS[chave]['nome']}** de {nome} foi melhorada depois da oferta — "
                        "não pode ser trocada assim."
                    )

        _mover(conn, troca.iniciador_id, troca.alvo_id, oferta_a)
        _mover(conn, troca.alvo_id, troca.iniciador_id, oferta_b)

    return True, None


def _nota_andar_travado(oferta, destinatario):
    """Item recebido que ainda não dá pra equipar — guarda na mochila até
    destravar o andar. Não bloqueia a troca, só avisa."""
    notas = []
    for chave in oferta["itens"]:
        item = ITENS[chave]
        if item["tipo"] in ("arma", "armadura", "anel", "colar") and item["andar_min"] > destinatario["andar_max"]:
            notas.append(f"🔒 {item['nome']} só destrava lá no andar {item['andar_min']}.")
    return notas


class ModalItem(discord.ui.Modal, title="Oferecer item"):
    nome = discord.ui.TextInput(label="Item", placeholder="Ex: poção pequena", max_length=60)
    quantidade = discord.ui.TextInput(
        label="Quantidade (0 remove da oferta)", placeholder="1", default="1", max_length=4
    )

    def __init__(self, view, user_id):
        super().__init__()
        self.view_troca = view
        self.user_id = user_id

    async def on_submit(self, interaction):
        texto_qtd = self.quantidade.value.strip()
        if not texto_qtd.isdigit():
            await interaction.response.send_message("Quantidade precisa ser um número.", ephemeral=True)
            return
        qtd = int(texto_qtd)

        troca = self.view_troca.troca
        j = db.get_jogador(self.user_id)
        inventario = {i["item"]: i["qtd"] for i in db.get_inventario(self.user_id) if i["item"] in ITENS}
        chave = H["encontrar_item"](self.nome.value, inventario.keys())

        if not chave:
            equipados = {slot: j[slot] for slot in ("arma", "armadura", "anel", "colar") if j[slot]}
            achado = H["encontrar_item"](self.nome.value, equipados.values())
            if achado:
                await interaction.response.send_message(
                    f"**{ITENS[achado]['nome']}** está equipado — desequipe antes de oferecer.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message("Você não tem esse item na mochila.", ephemeral=True)
            return

        oferta = troca.ofertas[self.user_id]

        if qtd == 0:
            oferta["itens"].pop(chave, None)
            troca.resetar_prontos()
            await interaction.response.edit_message(
                embed=embed_troca(troca, self.view_troca.membro_a, self.view_troca.membro_b),
                view=self.view_troca,
            )
            return

        if qtd > inventario[chave]:
            await interaction.response.send_message(
                f"Você só tem {inventario[chave]}x **{ITENS[chave]['nome']}**.", ephemeral=True
            )
            return

        erro = _checar_item_para_oferta(self.user_id, chave, qtd, oferta)
        if erro:
            await interaction.response.send_message(erro, ephemeral=True)
            return

        oferta["itens"][chave] = qtd
        troca.resetar_prontos()
        await interaction.response.edit_message(
            embed=embed_troca(troca, self.view_troca.membro_a, self.view_troca.membro_b),
            view=self.view_troca,
        )


class ModalMoedas(discord.ui.Modal, title="Oferecer moedas"):
    valor = discord.ui.TextInput(label="Quantidade de moedas (0 remove)", placeholder="0", max_length=8)

    def __init__(self, view, user_id):
        super().__init__()
        self.view_troca = view
        self.user_id = user_id

    async def on_submit(self, interaction):
        texto = self.valor.value.strip()
        if not texto.isdigit():
            await interaction.response.send_message("Precisa ser um número.", ephemeral=True)
            return
        valor = int(texto)

        j = db.get_jogador(self.user_id)
        if valor > j["moedas"]:
            await interaction.response.send_message(f"Você só tem {j['moedas']} 🪙.", ephemeral=True)
            return

        troca = self.view_troca.troca
        troca.ofertas[self.user_id]["moedas"] = valor
        troca.resetar_prontos()
        await interaction.response.edit_message(
            embed=embed_troca(troca, self.view_troca.membro_a, self.view_troca.membro_b),
            view=self.view_troca,
        )


class TrocaView(discord.ui.View):
    def __init__(self, troca, membro_a, membro_b):
        super().__init__(timeout=TIMEOUT_TROCA)
        self.troca = troca
        self.membro_a = membro_a
        self.membro_b = membro_b

    def _membro(self, user_id):
        return self.membro_a if user_id == self.troca.iniciador_id else self.membro_b

    async def interaction_check(self, interaction):
        if interaction.user.id not in (self.troca.iniciador_id, self.troca.alvo_id):
            await interaction.response.send_message("Essa troca não é sua.", ephemeral=True)
            return False
        return True

    def _travar(self):
        for item in self.children:
            item.disabled = True
        self.stop()
        _liberar(self.troca.iniciador_id, self.troca.alvo_id)

    @discord.ui.button(label="Item", style=discord.ButtonStyle.primary, emoji="📦")
    async def botao_item(self, interaction, button):
        await interaction.response.send_modal(ModalItem(self, interaction.user.id))

    @discord.ui.button(label="Moedas", style=discord.ButtonStyle.primary, emoji="🪙")
    async def botao_moedas(self, interaction, button):
        await interaction.response.send_modal(ModalMoedas(self, interaction.user.id))

    @discord.ui.button(label="Limpar", style=discord.ButtonStyle.secondary, emoji="🧹")
    async def botao_limpar(self, interaction, button):
        self.troca.ofertas[interaction.user.id] = {"itens": {}, "moedas": 0}
        self.troca.resetar_prontos()
        await interaction.response.edit_message(
            embed=embed_troca(self.troca, self.membro_a, self.membro_b), view=self
        )

    @discord.ui.button(label="Pronto", style=discord.ButtonStyle.success, emoji="✅")
    async def botao_pronto(self, interaction, button):
        uid = interaction.user.id
        self.troca.prontos[uid] = not self.troca.prontos[uid]

        if not all(self.troca.prontos.values()):
            await interaction.response.edit_message(
                embed=embed_troca(self.troca, self.membro_a, self.membro_b), view=self
            )
            return

        sucesso, motivo = _commitar_troca(self.troca)
        self._travar()
        if not sucesso:
            await interaction.response.edit_message(
                content=f"❌ Troca cancelada na revalidação final: {motivo}",
                embed=None, view=self,
            )
            return

        ja = db.get_jogador(self.troca.iniciador_id)
        jb = db.get_jogador(self.troca.alvo_id)
        notas = (
            _nota_andar_travado(self.troca.ofertas[self.troca.iniciador_id], jb)
            + _nota_andar_travado(self.troca.ofertas[self.troca.alvo_id], ja)
        )
        e = embed_troca(self.troca, self.membro_a, self.membro_b, titulo="🤝 Troca concluída")
        if notas:
            e.add_field(name="Guardado, ainda travado", value="\n".join(notas), inline=False)
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.danger, emoji="✖️")
    async def botao_cancelar(self, interaction, button):
        self._travar()
        await interaction.response.edit_message(content="Troca cancelada.", embed=None, view=self)

    async def on_timeout(self):
        _liberar(self.troca.iniciador_id, self.troca.alvo_id)
        if self.troca.mensagem:
            await self.troca.mensagem.edit(content="⌛ Troca expirou.", embed=None, view=None)


def instalar(bot, contexto):
    H.update(contexto)

    @bot.command(name="pix", aliases=["enviar", "pay"])
    async def pix(ctx, *, argumento: str = ""):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not ctx.message.mentions:
            await ctx.send("Uso: `rpg pix @alguém <valor>`. Ex: `rpg pix @Fulano 50`")
            return
        alvo = ctx.message.mentions[0]
        valor = _extrair_valor(argumento)
        if valor is None or valor <= 0:
            await ctx.send("Uso: `rpg pix @alguém <valor>` — o valor precisa ser um número inteiro positivo.")
            return
        if alvo.bot:
            await ctx.send("Bot não tem carteira. Manda pra uma pessoa.")
            return
        if alvo.id == ctx.author.id:
            await ctx.send("Não dá pra mandar pix pra você mesmo.")
            return
        destino = db.get_jogador(alvo.id)
        if not destino:
            await ctx.send(f"{alvo.display_name} ainda não entrou na torre — `rpg comecar` primeiro.")
            return
        if j["moedas"] < valor:
            await ctx.send(f"Faltam **{valor - j['moedas']}** moedas. Você tem {j['moedas']}.")
            return
        if ctx.author.id in PIX_PENDENTES:
            await ctx.send("Você já tem um pix esperando confirmação. Resolve esse antes de mandar outro.")
            return

        PIX_PENDENTES.add(ctx.author.id)
        view = ConfirmarPix(ctx.author.id)
        e = discord.Embed(
            title="💸 Confirmar pix",
            description=f"{ctx.author.mention} → {alvo.mention}\n**{valor}** 🪙",
            color=ANDARES[j["andar"]]["cor"],
        )
        e.set_footer(text=f"{TIMEOUT_PIX}s pra confirmar, senão cancela sozinho")
        mensagem = await ctx.send(embed=e, view=view)
        view.mensagem = mensagem
        await view.wait()
        PIX_PENDENTES.discard(ctx.author.id)

        if view.confirmado is None:
            await ctx.send("⌛ Tempo esgotado — pix cancelado.")
            return
        if not view.confirmado:
            await ctx.send("Cancelado.")
            return

        atual = db.get_jogador(ctx.author.id)
        if not atual or atual["moedas"] < valor:
            saldo = atual["moedas"] if atual else 0
            await ctx.send(
                f"❌ Pix cancelado — seu saldo mudou nesse meio tempo. "
                f"Você tem {saldo} 🪙, precisava de {valor}."
            )
            return
        destino_atual = db.get_jogador(alvo.id)
        if not destino_atual:
            await ctx.send(f"❌ Pix cancelado — {alvo.display_name} não tem mais personagem.")
            return

        db.atualizar_jogador(ctx.author.id, moedas=atual["moedas"] - valor)
        db.atualizar_jogador(alvo.id, moedas=destino_atual["moedas"] + valor)
        await ctx.send(f"✅ Pix de **{valor}** 🪙 enviado pra {alvo.display_name}.")

    @bot.command(name="trade", aliases=["trocar", "troca"])
    async def trade(ctx):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not ctx.message.mentions:
            await ctx.send("Uso: `rpg trade @alguém` — precisam estar no mesmo andar.")
            return
        alvo = ctx.message.mentions[0]
        if alvo.bot:
            await ctx.send("Bot não troca item com ninguém.")
            return
        if alvo.id == ctx.author.id:
            await ctx.send("Não dá pra trocar com você mesmo.")
            return
        destino = db.get_jogador(alvo.id)
        if not destino:
            await ctx.send(f"{alvo.display_name} ainda não entrou na torre — `rpg comecar` primeiro.")
            return
        if j["andar"] != destino["andar"]:
            await ctx.send(
                f"Troca é presencial: você está no andar {j['andar']}, "
                f"{alvo.display_name} está no andar {destino['andar']}. Precisam estar juntos."
            )
            return
        if ctx.author.id in TROCAS_ATIVAS:
            await ctx.send("Você já tem uma troca aberta. Termina ou cancela antes de abrir outra.")
            return
        if alvo.id in TROCAS_ATIVAS:
            await ctx.send(f"{alvo.display_name} já está em outra troca agora.")
            return

        troca = Troca(ctx.author.id, alvo.id, j["andar"])
        TROCAS_ATIVAS.add(ctx.author.id)
        TROCAS_ATIVAS.add(alvo.id)
        view = TrocaView(troca, ctx.author, alvo)
        mensagem = await ctx.send(
            content=f"{ctx.author.mention} {alvo.mention}",
            embed=embed_troca(troca, ctx.author, alvo),
            view=view,
        )
        troca.mensagem = mensagem

    print("trocas.py carregado — rpg pix e rpg trade no ar.")
