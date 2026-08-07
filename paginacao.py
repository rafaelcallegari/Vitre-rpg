# paginacao.py
# Paginação genérica de embeds. Nenhum comando deve montar um Embed com um
# número de fields (ou um value) que dependa do tamanho de uma lista sem
# passar por aqui — é o único lugar que guarda os limites reais do Discord,
# então uma mudança de limite (ou de catálogo grande demais) se resolve num
# lugar só, não em cada comando que lista alguma coisa.
#
# Motivo de existir: `rpg receitas` quebrou com "400 Bad Request — Must be
# 25 or fewer" assim que as 24 armas elementais do Pacote 2 empurraram o
# catálogo de Forja além do limite de fields por embed. Ver decisoes.md.

import discord

# ---------------------------------------------------------------- limites
MAX_FIELDS_POR_EMBED = 25
MAX_CHARS_POR_FIELD = 1024
MAX_CHARS_POR_EMBED = 6000     # título + descrição + soma de todos os fields + rodapé

ITENS_POR_PAGINA = 9           # entre 8 e 10, pedido
TIMEOUT_PAGINACAO = 120


def _truncar(texto, limite):
    texto = str(texto)
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def paginar(entradas, titulo="", descricao="", por_pagina=ITENS_POR_PAGINA):
    """entradas: lista de (nome, valor). Devolve lista de páginas — cada
    página é uma lista de (nome, valor) truncados e agrupados respeitando
    ao mesmo tempo por_pagina, MAX_FIELDS_POR_EMBED e MAX_CHARS_POR_EMBED
    (título/descrição/rodapé entram no orçamento fixo de cada página, então
    agrupar em menos fields não basta se o texto for grande demais)."""
    limite_campos = min(por_pagina, MAX_FIELDS_POR_EMBED)
    orcamento_fixo = len(titulo) + len(descricao) + 40  # margem pro rodapé "Página X de Y"

    paginas = []
    pagina_atual = []
    chars_usados = orcamento_fixo
    for nome, valor in entradas:
        nome = _truncar(nome, 256)          # limite de nome de field, de brinde
        valor = _truncar(valor, MAX_CHARS_POR_FIELD)
        custo = len(nome) + len(valor)
        estoura = pagina_atual and (
            len(pagina_atual) >= limite_campos or chars_usados + custo > MAX_CHARS_POR_EMBED
        )
        if estoura:
            paginas.append(pagina_atual)
            pagina_atual = []
            chars_usados = orcamento_fixo
        pagina_atual.append((nome, valor))
        chars_usados += custo
    if pagina_atual or not paginas:
        paginas.append(pagina_atual)
    return paginas


class PaginacaoView(discord.ui.View):
    """Botões ◀ ▶ editando a mesma mensagem. No timeout, REMOVE os botões
    (não só desabilita) — é lista, não decisão, então um botão morto na
    tela não vale a pena manter."""

    def __init__(self, autor_id, paginas, montar_embed, pagina_inicial=0):
        super().__init__(timeout=TIMEOUT_PAGINACAO)
        self.autor_id = autor_id
        self.paginas = paginas
        self.montar_embed = montar_embed   # (indice, dados_da_pagina) -> discord.Embed
        self.pagina = max(0, min(pagina_inicial, len(paginas) - 1))
        self.mensagem = None
        self._atualizar_botoes()

    def _atualizar_botoes(self):
        self.anterior.disabled = self.pagina <= 0
        self.proxima.disabled = self.pagina >= len(self.paginas) - 1

    def embed_atual(self):
        return self.montar_embed(self.pagina, self.paginas[self.pagina])

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "Essa lista não é sua — manda o comando de novo pra ver a sua.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def anterior(self, interaction, button):
        self.pagina = max(0, self.pagina - 1)
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=self.embed_atual(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def proxima(self, interaction, button):
        self.pagina = min(len(self.paginas) - 1, self.pagina + 1)
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=self.embed_atual(), view=self)

    async def on_timeout(self):
        if self.mensagem is None:
            return
        try:
            await self.mensagem.edit(view=None)
        except discord.HTTPException:
            pass


async def enviar_paginado(
    ctx, entradas, titulo, cor, descricao=None, rodape_extra="",
    por_pagina=ITENS_POR_PAGINA, pagina_inicial=1, mensagem_vazia="Nada pra mostrar aqui.",
):
    """Monta e envia a lista paginada. pagina_inicial é 1-indexado (o que o
    jogador digita: `rpg receitas 2`) — fora do intervalo é só recortado pro
    mais perto, sem virar erro."""
    if not entradas:
        await ctx.send(mensagem_vazia)
        return

    paginas = paginar(entradas, titulo=titulo, descricao=descricao or "", por_pagina=por_pagina)
    total = len(paginas)
    indice_inicial = max(0, min(pagina_inicial - 1, total - 1))

    def montar(indice, dados):
        e = discord.Embed(title=titulo, description=descricao, color=cor)
        for nome, valor in dados:
            e.add_field(name=nome, value=valor, inline=False)
        rodape = f"Página {indice + 1} de {total}"
        if rodape_extra:
            rodape += f" · {rodape_extra}"
        e.set_footer(text=rodape)
        return e

    if total == 1:
        await ctx.send(embed=montar(0, paginas[0]))
        return

    view = PaginacaoView(ctx.author.id, paginas, montar, pagina_inicial=indice_inicial)
    view.mensagem = await ctx.send(embed=view.embed_atual(), view=view)
