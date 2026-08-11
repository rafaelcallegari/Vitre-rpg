# comercio.py
# Comprar/vender/forjar/melhorar/desmanchar dentro do diálogo com o
# mercador e o ferreiro -- substitui o antigo `rpg loja`. Mesmo padrão de
# combate.py/profissoes.py: não importa bot.py (evita import circular), os
# helpers chegam por instalar(). Ver decisoes.md § Comércio dentro do diálogo.
import discord

import database as db
import profissoes
from game_data import ITENS, ANDARES

H = {}


class ShimCtx:
    """Bridge mínimo pra chamar os comandos de texto que já existem
    (comprar/vender/craftar/melhorar/desmanchar) direto do callback de um
    botão, sem duplicar a validação de moedas/andar_min/nível/desconto de
    Forjador que eles já fazem. Só cobre o que esses comandos e
    pegar_jogador() usam: `.author` e `.send()`."""

    def __init__(self, interaction):
        self.author = interaction.user
        self._interaction = interaction

    async def send(self, content=None, *, embed=None):
        kwargs = {}
        if content is not None:
            kwargs["content"] = content
        if embed is not None:
            kwargs["embed"] = embed
        if self._interaction.response.is_done():
            await self._interaction.followup.send(**kwargs)
        else:
            await self._interaction.response.send_message(**kwargs)


# ---------------- opções de select ----------------
def _opcoes_compra(disponiveis):
    return [
        discord.SelectOption(
            label=v["nome"][:100], description=f"{v['preco']} 🪙",
            value=chave, emoji=v.get("emoji"),
        )
        for chave, v in list(disponiveis.items())[:25]
    ]


def _opcoes_venda(user_id, tipos):
    opcoes = []
    for i in db.get_inventario(user_id):
        dado = ITENS.get(i["item"])
        if not dado or dado["tipo"] not in tipos or not dado.get("vendavel", True):
            continue
        unitario = dado["preco"] if dado["tipo"] == "material" else int(dado["preco"] * 0.5)
        opcoes.append(discord.SelectOption(
            label=f"{dado['nome']} x{i['qtd']}"[:100], description=f"{unitario} 🪙 cada",
            value=i["item"], emoji=dado.get("emoji"),
        ))
    return opcoes[:25]


def _opcoes_equipamento_inventario(user_id):
    """Pra desmanchar -- não filtra por `vendavel` (desmanchar não checa
    isso, e o item nunca fica sem dono: vira material de volta)."""
    opcoes = []
    for i in db.get_inventario(user_id):
        dado = ITENS.get(i["item"])
        if not dado or dado["tipo"] not in ("arma", "armadura"):
            continue
        opcoes.append(discord.SelectOption(
            label=f"{dado['nome']} x{i['qtd']}"[:100], value=i["item"], emoji=dado.get("emoji"),
        ))
    return opcoes[:25]


# ---------------- sub-tela de seleção ----------------
class SelectComercio(discord.ui.Select):
    def __init__(self, opcoes, ao_escolher):
        super().__init__(placeholder="Escolha...", options=opcoes, min_values=1, max_values=1)
        self._ao_escolher = ao_escolher

    async def callback(self, interaction):
        await self._ao_escolher(interaction, self.values[0])


class BotaoVoltarComercio(discord.ui.Button):
    def __init__(self, painel):
        super().__init__(label="Voltar", style=discord.ButtonStyle.secondary, row=1)
        self._painel = painel

    async def callback(self, interaction):
        j = db.get_jogador(interaction.user.id)
        await interaction.response.edit_message(embed=self._painel.embed(j), view=self._painel)


class MenuSelecaoView(discord.ui.View):
    """Sub-tela temporária: um select + Voltar. Depois de uma escolha, quem
    chamou (`PainelComercioBase._executar`) restaura o painel principal —
    essa view não volta sozinha."""

    def __init__(self, autor_id, opcoes, ao_escolher, painel):
        super().__init__(timeout=120)
        self.autor_id = autor_id
        self.mensagem = None
        self.add_item(SelectComercio(opcoes, ao_escolher))
        self.add_item(BotaoVoltarComercio(painel))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "Essa loja não é sua. Manda `rpg falar` você mesmo.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        if self.mensagem is None:
            return
        for item in self.children:
            item.disabled = True
        await self.mensagem.edit(view=self)


# ---------------- painel principal (mercador/ferreiro) ----------------
class PainelComercioBase(discord.ui.View):
    def __init__(self, autor_id, npc, andar_num):
        super().__init__(timeout=180)
        self.autor_id = autor_id
        self.npc = npc
        self.andar_num = andar_num
        self.mensagem = None

    def embed(self, j):
        nome = f"{self.npc['nome']} {self.npc['titulo']}".strip()
        e = discord.Embed(
            description=f"*{self.npc['fala']}*",
            color=ANDARES[self.andar_num]["cor"],
        )
        e.set_author(name=f"{H['ICONES_NPC'][self.npc['tipo']]} {nome}")
        e.set_footer(text=f"Você tem {j['moedas']} moedas")
        return e

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "Essa conversa não é sua. Manda `rpg falar` você mesmo.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        if self.mensagem is None:
            return
        for item in self.children:
            item.disabled = True
        await self.mensagem.edit(view=self)

    async def abrir_selecao(self, interaction, opcoes, mensagem_vazia, ao_escolher):
        if not opcoes:
            await interaction.response.send_message(mensagem_vazia, ephemeral=True)
            return
        view = MenuSelecaoView(self.autor_id, opcoes, ao_escolher, self)
        await interaction.response.edit_message(view=view)
        view.mensagem = interaction.message

    async def _executar(self, interaction, invocar):
        """`invocar(ctx)` chama o comando de texto de verdade via ShimCtx —
        a resposta dele (sucesso ou erro) vira mensagem nova, igual ao
        comando digitado, e o painel principal volta no lugar da seleção
        logo em seguida, já com as moedas atualizadas."""
        ctx = ShimCtx(interaction)
        await invocar(ctx)
        j = db.get_jogador(interaction.user.id)
        if j and interaction.message:
            await interaction.message.edit(embed=self.embed(j), view=self)

    def _sair(self, interaction):
        e = interaction.message.embeds[0]
        e.description = f"*Você se despede de {self.npc['nome']}.*"
        for item in self.children:
            item.disabled = True
        self.stop()
        return e


class MercadorView(PainelComercioBase):
    @discord.ui.button(label="Comprar", style=discord.ButtonStyle.success, row=0)
    async def comprar_btn(self, interaction, button):
        j = db.get_jogador(interaction.user.id)
        disponiveis = H["a_venda"](H["consumiveis_disponiveis"](j["andar_max"]))
        await self.abrir_selecao(
            interaction, _opcoes_compra(disponiveis),
            "Nada à venda aqui agora.", self._escolher_comprar,
        )

    async def _escolher_comprar(self, interaction, chave):
        async def invocar(ctx):
            await H["comprar"].callback(ctx, argumento=f"{chave} 1")
        await self._executar(interaction, invocar)

    @discord.ui.button(label="Vender", style=discord.ButtonStyle.danger, row=0)
    async def vender_btn(self, interaction, button):
        opcoes = _opcoes_venda(interaction.user.id, ("consumivel",))
        await self.abrir_selecao(
            interaction, opcoes,
            "Você não tem nada que esse mercador compre.", self._escolher_vender,
        )

    async def _escolher_vender(self, interaction, chave):
        async def invocar(ctx):
            await H["vender"].callback(ctx, argumento=f"{chave} 1")
        await self._executar(interaction, invocar)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.secondary, row=1)
    async def sair_btn(self, interaction, button):
        e = self._sair(interaction)
        await interaction.response.edit_message(embed=e, view=self)


class FerreiroView(PainelComercioBase):
    # -------- fileira 1: transação (comprar/vender equipamento)
    @discord.ui.button(label="Comprar", style=discord.ButtonStyle.success, row=0)
    async def comprar_btn(self, interaction, button):
        disponiveis = H["a_venda"](H["equipamentos_do_andar"](self.andar_num))
        await self.abrir_selecao(
            interaction, _opcoes_compra(disponiveis),
            "Nada à venda aqui agora.", self._escolher_comprar,
        )

    async def _escolher_comprar(self, interaction, chave):
        async def invocar(ctx):
            await H["comprar"].callback(ctx, argumento=f"{chave} 1")
        await self._executar(interaction, invocar)

    @discord.ui.button(label="Vender", style=discord.ButtonStyle.danger, row=0)
    async def vender_btn(self, interaction, button):
        opcoes = _opcoes_venda(interaction.user.id, ("arma", "armadura"))
        await self.abrir_selecao(
            interaction, opcoes,
            "Você não tem equipamento pra vender.", self._escolher_vender,
        )

    async def _escolher_vender(self, interaction, chave):
        async def invocar(ctx):
            await H["vender"].callback(ctx, argumento=f"{chave} 1")
        await self._executar(interaction, invocar)

    # -------- fileira 2: oficina (forjar/melhorar/desmanchar)
    # Sempre habilitada, mesmo pra quem não é Forjador -- disabled=True não
    # gera interação nenhuma no Discord, e o ponto é justamente ensinar que
    # a profissão existe. Só "Forjar" recusa por ofício errado: é a única
    # das três que exige ser Forjador de verdade (melhorar/desmanchar já
    # funcionam pra qualquer um hoje, só com bônus pra quem tem Forja — ver
    # decisoes.md).
    @discord.ui.button(label="Forjar", style=discord.ButtonStyle.primary, row=1)
    async def forjar_btn(self, interaction, button):
        j = db.get_jogador(interaction.user.id)
        if j["profissao"] != "forja":
            atual = profissoes.PROFISSOES[j["profissao"]]["nome"] if j["profissao"] else "nenhum"
            await interaction.response.send_message(
                f"Essa bancada é de Forja — seu ofício é {atual}. "
                f"Precisa ser Forjador pra fabricar aqui (`rpg profissao`).",
                ephemeral=True,
            )
            return
        prontas = {
            k: v for k, v in profissoes.receitas_da("forja").items()
            if profissoes.pode_fazer(j, k, v)
        }
        opcoes = [
            discord.SelectOption(
                label=ITENS[k]["nome"][:100], description=f"{v['moedas']} 🪙",
                value=k, emoji=ITENS[k].get("emoji"),
            )
            for k, v in list(prontas.items())[:25]
        ]
        await self.abrir_selecao(
            interaction, opcoes,
            "Nada pronto pra fabricar agora — `rpg receitas` mostra o que falta.",
            self._escolher_forjar,
        )

    async def _escolher_forjar(self, interaction, chave):
        async def invocar(ctx):
            await H["_bot"].get_command("craftar").callback(ctx, argumento=f"{chave} 1")
        await self._executar(interaction, invocar)

    @discord.ui.button(label="Melhorar", style=discord.ButtonStyle.primary, row=1)
    async def melhorar_btn(self, interaction, button):
        j = db.get_jogador(interaction.user.id)
        opcoes = []
        if j["arma"]:
            opcoes.append(discord.SelectOption(label=f"Arma — {ITENS[j['arma']]['nome']}"[:100], value="arma"))
        if j["armadura"]:
            opcoes.append(discord.SelectOption(
                label=f"Armadura — {ITENS[j['armadura']]['nome']}"[:100], value="armadura"
            ))
        await self.abrir_selecao(
            interaction, opcoes,
            "Você não tem nada equipado pra melhorar.", self._escolher_melhorar,
        )

    async def _escolher_melhorar(self, interaction, slot):
        async def invocar(ctx):
            await H["_bot"].get_command("melhorar").callback(ctx, argumento=slot)
        await self._executar(interaction, invocar)

    @discord.ui.button(label="Desmanchar", style=discord.ButtonStyle.primary, row=1)
    async def desmanchar_btn(self, interaction, button):
        opcoes = _opcoes_equipamento_inventario(interaction.user.id)
        await self.abrir_selecao(
            interaction, opcoes,
            "Você não tem equipamento pra desmanchar.", self._escolher_desmanchar,
        )

    async def _escolher_desmanchar(self, interaction, chave):
        async def invocar(ctx):
            await H["_bot"].get_command("desmanchar").callback(ctx, argumento=f"{chave} 1")
        await self._executar(interaction, invocar)

    # -------- fileira 3: sair
    @discord.ui.button(label="Sair", style=discord.ButtonStyle.secondary, row=2)
    async def sair_btn(self, interaction, button):
        e = self._sair(interaction)
        await interaction.response.edit_message(embed=e, view=self)


# ---------------- ponto de entrada ----------------
async def abrir_comercio(ctx, j, npc):
    """Chamado por bot.py:falar() quando o NPC é mercador ou ferreiro —
    substitui o embed estático + footer de comando de antes."""
    view = MercadorView(ctx.author.id, npc, j["andar"]) if npc["tipo"] == "mercador" \
        else FerreiroView(ctx.author.id, npc, j["andar"])
    view.mensagem = await ctx.send(embed=view.embed(j), view=view)


def instalar(bot, contexto):
    H.update(contexto)
    H["_bot"] = bot
