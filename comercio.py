# comercio.py
# Comprar/vender/forjar/melhorar/desmanchar (mercador/ferreiro), descansar
# (taverneiro) e viajar (carroceiro) dentro do diálogo -- substitui o antigo
# `rpg loja`. Mesmo padrão de combate.py/profissoes.py: não importa bot.py
# (evita import circular), os helpers chegam por instalar(). Ver
# decisoes.md § Comércio dentro do diálogo e § Ações de diálogo de todos os NPCs.
import discord

import atributos as at
import database as db
import dialogos
import npcs
import profissoes
import pronomes
from game_data import ITENS, ANDARES

H = {}

QUANTIDADES_COMPRA = (1, 5, 10, 25)


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


# ---------------- opções de select: preço + stat + status ----------------
def _truncar(texto, limite):
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _texto_stat_absoluto(item_dado):
    """Valor bruto do item, sem comparação nenhuma -- "" pra tipo sem stat
    pra mostrar (material, joia crua ainda sem atributo lapidado)."""
    tipo = item_dado.get("tipo")
    if tipo == "arma":
        return f"atk {item_dado.get('atk', 0)}"
    if tipo == "armadura":
        return f"def {item_dado.get('def', 0)}"
    if tipo in ("anel", "colar") and "atributo" in item_dado:
        sigla = at.ATRIBUTOS[item_dado["atributo"]]["sigla"]
        return f"{sigla} +{item_dado.get('bonus', 0)}"
    if tipo == "consumivel":
        return H["descricao_cura"](item_dado)
    return ""


def _par_equipado(s, item_dado):
    """(chave, dado) da peça equipada no MESMO slot do item_dado, lido de
    `H["stats"](j)["equipamento"]` (já resolve bônus de melhoria/joia/
    encantamento da instância -- ver decisoes.md § Instâncias de item).
    None se o tipo não tem slot (poção, material) ou o slot está vazio."""
    tipo = item_dado.get("tipo")
    if tipo not in ("arma", "armadura", "anel", "colar"):
        return None
    return s["equipamento"].get(tipo)


def _delta_comparavel(item_dado, dado_eq):
    """Diferença numérica contra a peça equipada, ou None quando não há
    base comparável (anel/colar de atributo diferente -- comparar +4 FOR
    com +2 INT não informa nada)."""
    tipo = item_dado.get("tipo")
    if tipo == "arma":
        return item_dado.get("atk", 0) - dado_eq.get("atk", 0)
    if tipo == "armadura":
        return item_dado.get("def", 0) - dado_eq.get("def", 0)
    if tipo in ("anel", "colar") and item_dado.get("atributo") == dado_eq.get("atributo"):
        return item_dado.get("bonus", 0) - dado_eq.get("bonus", 0)
    return None


def _marca_indisponivel(item_dado, j):
    """💸 sem moeda pro preço, 🔒 sem requisito (andar_min) -- os dois
    continuam clicáveis nos selects de Comprar; a recusa de verdade (e o
    ensino da regra: quanto falta, onde fica o ferreiro certo) acontece no
    comando de texto por trás (`comprar()`, bot.py), não aqui. 🔒 hoje não
    dispara na prática -- os call sites de `_opcoes_compra` já filtram
    `disponiveis` por andar_min/andar_max antes de chegar aqui (mercador por
    `andar_max`, ferreiro só vende do próprio andar) -- mas a checagem fica
    correta pra se essa pré-filtragem mudar (ver decisoes.md)."""
    if item_dado.get("andar_min", 1) > j["andar_max"]:
        return "🔒 "
    if item_dado.get("preco", 0) > j["moedas"]:
        return "💸 "
    return ""


def _texto_stat_e_delta(item_dado, s, limite):
    """Stat absoluto + delta contra a peça equipada do mesmo slot, dentro de
    `limite` caracteres. Estoura truncando o NOME da peça equipada -- nunca
    o preço, o stat ou o número do delta (ver decisoes.md § status na
    compra)."""
    stat = _texto_stat_absoluto(item_dado)
    if not stat:
        return ""
    par = _par_equipado(s, item_dado)
    delta = _delta_comparavel(item_dado, par[1]) if par else None
    if delta is None:
        return _truncar(stat, limite)
    sinal = "+" if delta >= 0 else ""
    nome_eq = par[1].get("nome", par[0])
    sufixo_fixo = f" ({sinal}{delta} vs "
    espaco_nome = limite - len(stat) - len(sufixo_fixo) - 1   # 1 = ")"
    if espaco_nome <= 0:
        return _truncar(stat, limite)
    nome_cortado = nome_eq if len(nome_eq) <= espaco_nome else nome_eq[: espaco_nome - 1] + "…"
    return f"{stat}{sufixo_fixo}{nome_cortado})"


def _descricao_compra(item_dado, j, s, limite=100):
    marca = _marca_indisponivel(item_dado, j)
    prefixo = f"{marca}{item_dado['preco']} 🪙"
    espaco_stat = limite - len(prefixo) - len(" · ")
    stat = _texto_stat_e_delta(item_dado, s, espaco_stat) if espaco_stat > 0 else ""
    return _truncar(f"{prefixo} · {stat}" if stat else prefixo, limite)


def _opcoes_compra(j, s, disponiveis):
    return [
        discord.SelectOption(
            label=v["nome"][:100], description=_descricao_compra(v, j, s),
            value=chave, emoji=v.get("emoji"),
        )
        for chave, v in list(disponiveis.items())[:25]
    ]


def _opcoes_venda(user_id, tipos):
    j = db.get_jogador(user_id)
    s = H["stats"](j)
    opcoes = []
    for i in db.get_inventario(user_id):
        dado = ITENS.get(i["item"])
        if not dado or dado["tipo"] not in tipos or not dado.get("vendavel", True):
            continue
        unitario = dado["preco"] if dado["tipo"] == "material" else int(dado["preco"] * 0.5)
        prefixo = f"{unitario} 🪙 cada"
        espaco_stat = 100 - len(prefixo) - len(" · ")
        stat = _texto_stat_e_delta(dado, s, espaco_stat) if espaco_stat > 0 else ""
        descricao = _truncar(f"{prefixo} · {stat}" if stat else prefixo, 100)
        opcoes.append(discord.SelectOption(
            label=f"{dado['nome']} x{i['qtd']}"[:100], description=descricao,
            value=i["item"], emoji=dado.get("emoji"),
        ))
    return opcoes[:25]


def _opcoes_quantidade(chave):
    """Segundo select do fluxo de Comprar -- quantidades fixas em vez de
    modal: mais rápido de clicar e não abre teclado no celular (ver
    decisoes.md). A descrição já mostra o TOTAL, não o preço unitário --
    é a confirmação, não precisa de um passo a mais depois do clique."""
    preco = ITENS[chave]["preco"]
    return [
        discord.SelectOption(
            label=f"{qtd}x", description=f"{preco * qtd} 🪙 no total", value=str(qtd),
        )
        for qtd in QUANTIDADES_COMPRA
    ]


def _opcoes_destino(j):
    """Pro Viajar do carroceiro -- mesma lista que `rpg viajar` sem
    argumento mostra (destino, custo), só que como select. O desconto da
    carroça já sai de `custo_e_motivo_viagem`, a mesma função que `rpg
    viajar` usa pra valer -- aqui é só pra exibir o preço antes do clique."""
    ativa, _ = H["carroca_ativa"]()
    gratis_carroca = ativa and H["conheceu_bramm"](j)
    teto = min(j["andar_max"], H["LIMITE_VIAJAR"])
    opcoes = []
    for n in range(1, teto + 1):
        if n == j["andar"]:
            continue
        custo, motivo = H["custo_e_motivo_viagem"](j, n, gratis_carroca)
        preco = "grátis" if motivo else f"{custo} 🪙"
        opcoes.append(discord.SelectOption(
            label=f"{n}. {ANDARES[n]['nome']}"[:100], description=preco, value=str(n),
        ))
    return opcoes[:25]


def _opcoes_atributo():
    """FOR/DES/CON/INT -- segundo passo de Encantar e de Lapidar, mesmo
    vocabulário de `at.encontrar_atributo` (profissoes.py chama a mesma
    função quando o comando de texto roda por trás do botão)."""
    return [
        discord.SelectOption(label="Força (FOR)", value="forca", emoji="💪"),
        discord.SelectOption(label="Destreza (DES)", value="destreza", emoji="🎯"),
        discord.SelectOption(label="Constituição (CON)", value="constituicao", emoji="🛡️"),
        discord.SelectOption(label="Inteligência (INT)", value="inteligencia", emoji="🔮"),
    ]


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


# ---------------- painel principal (mercador/ferreiro/taverneiro/carroceiro) ----------------
class PainelComercioBase(discord.ui.View):
    def __init__(self, autor_id, npc, andar_num, pronome):
        super().__init__(timeout=180)   # decorators de cada subclasse já populam self.children aqui
        self.autor_id = autor_id
        self.npc = npc
        self.andar_num = andar_num
        self.pronome = pronome
        self.mensagem = None
        self._dado_dialogo = dialogos.DIALOGOS.get(npc.get("dialogo"), {})

        # opções de diálogo (perguntas da Lore) + Sair entram numa linha
        # livre, depois de tudo que a subclasse já desenhou por decorator --
        # nunca hardcoded, pra não colidir com fileira de mercador (1) vs
        # ferreiro (2). NPC sem pergunta na Lore (ex.: Bramm) só ganha Sair.
        linha_livre = max((c.row or 0) for c in self.children) + 1 if self.children else 0
        opcoes = npcs.opcoes_do_dialogo(npc["dialogo"], autor_id) if npc.get("dialogo") else []
        for opcao in opcoes:
            self.add_item(BotaoOpcaoComercio(opcao, linha_livre))
        linha_sair = linha_livre + 1 if opcoes else linha_livre
        saida = self._dado_dialogo.get("saida") or dialogos.SAIDA_PADRAO
        self.add_item(BotaoSairComercio(saida, linha_sair))

    def embed(self, j):
        nome = f"{self.npc['nome']} {self.npc['titulo']}".strip()
        abertura = self._dado_dialogo.get("abertura", self.npc["fala"])
        texto = pronomes.concordar(abertura, self.pronome)
        e = discord.Embed(description=f"*{texto}*", color=ANDARES[self.andar_num]["cor"])
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

    async def _pedir_quantidade_e_comprar(self, interaction, chave):
        """Segundo passo do Comprar: item já escolhido, agora a quantidade.
        Reaproveita `abrir_selecao`/`MenuSelecaoView` — mesma "Voltar" de
        sempre, que some com a quantidade e volta pro painel principal (não
        pro select de item; cancelar no meio manda escolher tudo de novo,
        troca aceitável por não duplicar navegação — ver decisoes.md)."""
        async def escolher_qtd(interaction2, qtd):
            async def invocar(ctx):
                await H["comprar"].callback(ctx, argumento=f"{chave} {qtd}")
            await self._executar(interaction2, invocar)

        await self.abrir_selecao(
            interaction, _opcoes_quantidade(chave), "Item não encontrado.", escolher_qtd,
        )


class BotaoOpcaoComercio(discord.ui.Button):
    """Uma pergunta da Lore -- mesmo papel do BotaoOpcaoDialogo da
    DialogoView (bot.py), só que dentro do painel de comércio/serviço."""

    def __init__(self, opcao, row):
        super().__init__(label=opcao["label"][:80], style=discord.ButtonStyle.secondary, row=row)
        self.resposta = opcao["resposta"]

    async def callback(self, interaction):
        e = interaction.message.embeds[0]
        e.description = f"*{pronomes.concordar(self.resposta, self.view.pronome)}*"
        await interaction.response.edit_message(embed=e, view=self.view)


class BotaoSairComercio(discord.ui.Button):
    """Sempre acrescentado por `PainelComercioBase.__init__` -- nunca um
    item de `opcoes` em dialogos.py. Mesmo comportamento do Sair da
    DialogoView: troca a descrição pela despedida e desabilita tudo."""

    def __init__(self, saida, row):
        super().__init__(label="Sair", style=discord.ButtonStyle.secondary, row=row)
        self.saida = saida

    async def callback(self, interaction):
        e = interaction.message.embeds[0]
        e.description = f"*{pronomes.concordar(self.saida, self.view.pronome)}*"
        for item in self.view.children:
            item.disabled = True
        self.view.stop()
        await interaction.response.edit_message(embed=e, view=self.view)


class MercadorView(PainelComercioBase):
    @discord.ui.button(label="Comprar", style=discord.ButtonStyle.success, row=0)
    async def comprar_btn(self, interaction, button):
        j = db.get_jogador(interaction.user.id)
        disponiveis = H["a_venda"](H["consumiveis_disponiveis"](j["andar_max"]))
        await self.abrir_selecao(
            interaction, _opcoes_compra(j, H["stats"](j), disponiveis),
            "Nada à venda aqui agora.", self._pedir_quantidade_e_comprar,
        )

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


class BotaoForjarMortalha(discord.ui.Button):
    """Só existe no painel da Selen (ver FerreiroView.__init__). Abre um
    select de 2 opções (Luz/Sombra) em vez de forjar na hora -- a escolha é
    travada, não dá pra ter uma confirmação a menos que essa."""

    def __init__(self, row):
        super().__init__(label="Forjar Mortalha", style=discord.ButtonStyle.primary, row=row)

    async def callback(self, interaction):
        faltando = [p for p in profissoes.PECAS_MORTALHA if not db.tem_item(interaction.user.id, p, 1)]
        if faltando:
            await interaction.response.send_message(
                "Ainda falta: " + " · ".join(f"{ITENS[p]['emoji']} {ITENS[p]['nome']}" for p in faltando),
                ephemeral=True,
            )
            return
        opcoes = [
            discord.SelectOption(
                label=ITENS["mortalha_luz"]["nome"], value="luz", emoji=ITENS["mortalha_luz"]["emoji"],
            ),
            discord.SelectOption(
                label=ITENS["mortalha_sombra"]["nome"], value="sombra", emoji=ITENS["mortalha_sombra"]["emoji"],
            ),
        ]
        await self.view.abrir_selecao(
            interaction, opcoes, "Nada pra escolher.", self.view._escolher_mortalha,
        )


class FerreiroView(PainelComercioBase):
    def __init__(self, autor_id, npc, andar_num, pronome):
        super().__init__(autor_id, npc, andar_num, pronome)
        if npc.get("dialogo") == "selen":
            # só a Selen monta a mortalha -- ver decisoes.md § Mortalha de
            # Luz/Sombra. Sempre visível (mesmo padrão do "Forjar" comum:
            # ensina que a mecânica existe), a recusa por peça faltando
            # acontece dentro do próprio botão.
            self.add_item(BotaoForjarMortalha(row=1))

    async def _escolher_mortalha(self, interaction, elemento):
        async def invocar(ctx):
            await H["_bot"].get_command("forjarmortalha").callback(ctx, escolha=elemento)
        await self._executar(interaction, invocar)

    # -------- fileira 1: transação (comprar/vender equipamento)
    @discord.ui.button(label="Comprar", style=discord.ButtonStyle.success, row=0)
    async def comprar_btn(self, interaction, button):
        j = db.get_jogador(interaction.user.id)
        disponiveis = H["a_venda"](H["equipamentos_do_andar"](self.andar_num))
        await self.abrir_selecao(
            interaction, _opcoes_compra(j, H["stats"](j), disponiveis),
            "Nada à venda aqui agora.", self._pedir_quantidade_e_comprar,
        )

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
            atual = (
                pronomes.concordar(profissoes.PROFISSOES[j["profissao"]]["nome"], j["pronome"])
                if j["profissao"] else "nenhum"
            )
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


class EncantadorView(PainelComercioBase):
    # -------- Encantar: peça equipada -> atributo (dois selects em sequência,
    # mesmo padrão de _pedir_quantidade_e_comprar) -- recusa ephemeral se o
    # jogador não é Encantador, igual ao "Forjar" do FerreiroView.
    @discord.ui.button(label="Encantar", style=discord.ButtonStyle.primary, row=0)
    async def encantar_btn(self, interaction, button):
        j = db.get_jogador(interaction.user.id)
        if j["profissao"] != "encantador":
            atual = (
                pronomes.concordar(profissoes.PROFISSOES[j["profissao"]]["nome"], j["pronome"])
                if j["profissao"] else "nenhum"
            )
            await interaction.response.send_message(
                f"Essa bancada é de Encantador — seu ofício é {atual}. "
                f"Precisa ser Encantador pra isso (`rpg profissao`).",
                ephemeral=True,
            )
            return
        opcoes = [
            discord.SelectOption(label=f"{slot.capitalize()} — {ITENS[j[slot]]['nome']}"[:100], value=slot)
            for slot in ("arma", "armadura", "anel", "colar") if j[slot]
        ]
        await self.abrir_selecao(
            interaction, opcoes, "Você não tem nada equipado pra encantar.", self._escolher_peca,
        )

    async def _escolher_peca(self, interaction, slot):
        async def escolher_atributo(interaction2, atributo):
            async def invocar(ctx):
                await H["_bot"].get_command("encantar").callback(ctx, argumento=f"{slot} {atributo}")
            await self._executar(interaction2, invocar)

        await self.abrir_selecao(
            interaction, _opcoes_atributo(), "Item não encontrado.", escolher_atributo,
        )

    # -------- Desencantar: só mostra peça que já está encantada
    @discord.ui.button(label="Desencantar", style=discord.ButtonStyle.danger, row=0)
    async def desencantar_btn(self, interaction, button):
        j = db.get_jogador(interaction.user.id)
        opcoes = []
        for slot in ("arma", "armadura", "anel", "colar"):
            if not j[slot]:
                continue
            instancia = db.get_instancia(j.get(f"{slot}_instancia_id"))
            if instancia and instancia["encantamento_atributo"]:
                opcoes.append(discord.SelectOption(
                    label=f"{slot.capitalize()} — {ITENS[j[slot]]['nome']}"[:100], value=slot,
                ))
        await self.abrir_selecao(
            interaction, opcoes, "Você não tem nada encantado pra remover.", self._escolher_desencantar,
        )

    async def _escolher_desencantar(self, interaction, slot):
        async def invocar(ctx):
            await H["_bot"].get_command("desencantar").callback(ctx, argumento=slot)
        await self._executar(interaction, invocar)


class JoalheiroView(PainelComercioBase):
    # -------- Lapidar: anel/colar -> atributo, mesmo padrão de dois selects
    @discord.ui.button(label="Lapidar", style=discord.ButtonStyle.primary, row=0)
    async def lapidar_btn(self, interaction, button):
        j = db.get_jogador(interaction.user.id)
        if j["profissao"] != "joalheiro":
            atual = (
                pronomes.concordar(profissoes.PROFISSOES[j["profissao"]]["nome"], j["pronome"])
                if j["profissao"] else "nenhum"
            )
            await interaction.response.send_message(
                f"Essa bancada é de Joalheiro — seu ofício é {atual}. "
                f"Precisa ser Joalheiro pra isso (`rpg profissao`).",
                ephemeral=True,
            )
            return
        opcoes = [
            discord.SelectOption(label="Anel", value="anel", emoji="💍"),
            discord.SelectOption(label="Colar", value="colar", emoji="📿"),
        ]
        await self.abrir_selecao(interaction, opcoes, "Nada pra lapidar.", self._escolher_tipo)

    async def _escolher_tipo(self, interaction, tipo):
        async def escolher_atributo(interaction2, atributo):
            async def invocar(ctx):
                await H["_bot"].get_command("lapidar").callback(ctx, argumento=f"{tipo} {atributo}")
            await self._executar(interaction2, invocar)

        await self.abrir_selecao(
            interaction, _opcoes_atributo(), "Item não encontrado.", escolher_atributo,
        )


class TaverneiroView(PainelComercioBase):
    @discord.ui.button(label="Descansar", style=discord.ButtonStyle.success, row=0)
    async def descansar_btn(self, interaction, button):
        async def invocar(ctx):
            await H["descansar"].callback(ctx)
        await self._executar(interaction, invocar)


class CarroceiroView(PainelComercioBase):
    def embed(self, j):
        e = super().embed(j)
        ativa, parte_em = H["carroca_ativa"]()
        if ativa:
            restante = (parte_em - H["agora"]()).total_seconds()
            estado = (
                f"**Parada agora.** Sai às {parte_em.strftime('%H:%M')} — "
                f"faltam **{H['fmt_tempo'](restante)}**. `rpg viajar` não custa nada enquanto ela estiver aqui."
            )
        else:
            prox = H["proxima_carroca"]()
            falta = (prox - H["agora"]()).total_seconds()
            estado = f"Não está aqui agora. Próxima às **{prox.strftime('%H:%M')}**, em **{H['fmt_tempo'](falta)}**."
        e.add_field(name="🐎 Horário da carroça", value=estado, inline=False)
        return e

    @discord.ui.button(label="Viajar", style=discord.ButtonStyle.success, row=0)
    async def viajar_btn(self, interaction, button):
        j = db.get_jogador(interaction.user.id)
        await self.abrir_selecao(
            interaction, _opcoes_destino(j),
            "Nenhum destino disponível — você só destrancou este andar.", self._escolher_destino,
        )

    async def _escolher_destino(self, interaction, destino):
        async def invocar(ctx):
            await H["viajar"].callback(ctx, destino=int(destino))
        await self._executar(interaction, invocar)


# ---------------- ponto de entrada ----------------
VIEW_POR_TIPO = {
    "mercador": MercadorView,
    "ferreiro": FerreiroView,
    "taverneiro": TaverneiroView,
    "carroceiro": CarroceiroView,
    "encantador": EncantadorView,
    "joalheiro": JoalheiroView,
}


async def abrir_comercio(ctx, j, npc):
    """Chamado por bot.py:falar() pros quatro tipos de NPC de mecânica
    (mercador/ferreiro/taverneiro/carroceiro) — substitui o embed estático +
    footer de comando de antes."""
    view = VIEW_POR_TIPO[npc["tipo"]](ctx.author.id, npc, j["andar"], j["pronome"])
    view.mensagem = await ctx.send(embed=view.embed(j), view=view)


def instalar(bot, contexto):
    H.update(contexto)
    H["_bot"] = bot
