# mural.py
# A Praça, commit 2: o mural. `rpg trade` (trocas.py) é presencial e
# síncrono -- os dois confirmam ao mesmo tempo, e se o bot cair no meio a
# troca simplesmente não aconteceu (estado em memória, de propósito). O
# mural é o oposto: assíncrono, um jogador publica e vai embora, outro
# aceita horas depois sem os dois online juntos -- por isso a oferta mora
# numa TABELA (database.py, `mural_ofertas`), não em memória.
#
# Publicar É reservar: o item sai do inventário (ou a instância solta o
# `dono`, mesma técnica do roubo dos ladrões -- Step E) na hora de
# publicar, não na hora de aceitar. Sem isso, dava pra oferecer a mesma
# peça em cinco anúncios, ou vender ela no mercador e deixar o anúncio de
# pé prometendo algo que já não existe mais.
#
# Um `@bot.command` só, dispatch manual pela primeira palavra -- mesmo
# padrão de `rpg guilda` (guildas.py), não `@bot.group` (nunca usado neste
# projeto). Mesmo H = {} / instalar(bot, contexto) de combate.py/trocas.py.
import discord

import database as db
import mundo
from game_data import ITENS

H = {}

MAX_OFERTAS_POR_JOGADOR = 5   # o mural não pode virar loja de uma pessoa só


def _na_praca(jogador):
    return jogador["mundo"] == mundo.PRACA


async def _exigir_praca(ctx, jogador):
    """O mural é móvel da Praça, não serviço global -- "outro chega horas
    depois, VÊ, e aceita" pressupõe estar lá. `rpg viajar praca` é de
    graça, de qualquer andar, sem cooldown (commit 1), então a exigência
    nunca é um perrengue real."""
    if _na_praca(jogador):
        return True
    await ctx.send("O mural fica na Praça. `rpg viajar praca` (de graça, de qualquer andar).")
    return False


def _checar_item_para_oferta(chave):
    """None se o item pode ir pro mural, ou a mensagem de recusa --
    mesmo espírito de trocas._checar_item_para_oferta, só que aqui não
    há limite de itens distintos (cada oferta é UM item só)."""
    dado = ITENS[chave]
    if not dado.get("vendavel", True):
        return f"**{dado['nome']}** não se troca — é intransferível."
    return None


def _resolver_item_e_reserva(user_id, texto_item, qtd_pedida):
    """Devolve (chave, qtd, instancia_id, erro). Mesma prioridade de
    `bot.vender`: cópia comum primeiro (não mexe numa peça melhorada à
    toa quando existe cópia comum de sobra); sem cópia comum sobrando, o
    número digitado deixa de ser "quantidade" e vira "qual instância"
    (#1, #2...) -- ver decisoes.md § Instâncias de item."""
    inventario = {i["item"]: i["qtd"] for i in db.get_inventario(user_id) if i["item"] in ITENS}
    mochila_instancias = db.instancias_por_chave(user_id)
    chave = H["encontrar_item"](texto_item, set(inventario) | set(mochila_instancias))
    if not chave:
        return None, None, None, "Você não tem esse item na mochila."

    erro = _checar_item_para_oferta(chave)
    if erro:
        return None, None, None, erro

    plain_qtd = inventario.get(chave, 0)
    if plain_qtd >= qtd_pedida:
        return chave, qtd_pedida, None, None

    lista_instancias = mochila_instancias.get(chave, [])
    if plain_qtd == 0 and lista_instancias:
        if not (1 <= qtd_pedida <= len(lista_instancias)):
            return None, None, None, (
                f"Você tem {len(lista_instancias)} **{ITENS[chave]['nome']}** na mochila — "
                f"`rpg inventario` mostra qual é qual, o número escolhe qual instância ofertar."
            )
        instancia = lista_instancias[qtd_pedida - 1]
        return chave, 1, instancia["id"], None

    return None, None, None, f"Você só tem {plain_qtd}x **{ITENS[chave]['nome']}**."


def _linha_da_oferta(oferta):
    dado = ITENS[oferta["item"]]
    sufixo = ""
    if oferta["instancia_id"]:
        instancia = db.get_instancia(oferta["instancia_id"])
        if instancia and instancia["nivel_melhoria"]:
            sufixo = f" +{instancia['nivel_melhoria']}"
    quantidade = "" if oferta["instancia_id"] else f" x{oferta['qtd']}"
    return f"`#{oferta['id']}` {dado['emoji']} **{dado['nome']}{sufixo}**{quantidade} — {oferta['preco']} 🪙"


def embed_mural(ofertas):
    e = discord.Embed(title="🪧 O Mural da Praça", color=0xD9A441)
    if not ofertas:
        e.description = "Nenhuma oferta agora. `rpg mural oferecer <item> <quantidade> <preço>` deixa a primeira."
        return e
    e.description = "\n".join(_linha_da_oferta(o) for o in ofertas)
    e.set_footer(text="rpg mural aceitar <#> · rpg mural cancelar <#> (só as suas)")
    return e


async def _acao_ver(ctx):
    ofertas = db.ofertas_mural_abertas()
    await ctx.send(embed=embed_mural(ofertas))


async def _acao_oferecer(ctx, j, resto):
    if not resto:
        await ctx.send("Uso: `rpg mural oferecer <item> <quantidade> <preço>`. Ex: `rpg mural oferecer pocao pequena 5 200`")
        return

    texto_restante, preco = H["separar_quantidade"](resto)
    texto_item, qtd = H["separar_quantidade"](texto_restante)
    if preco <= 0:
        await ctx.send("O preço precisa ser maior que zero.")
        return

    if db.contar_ofertas_mural(j["user_id"]) >= MAX_OFERTAS_POR_JOGADOR:
        await ctx.send(f"Máximo de {MAX_OFERTAS_POR_JOGADOR} anúncios abertos por vez. Cancela um antes de publicar outro.")
        return

    chave, qtd_final, instancia_id, erro = _resolver_item_e_reserva(j["user_id"], texto_item, qtd)
    if erro:
        await ctx.send(erro)
        return

    oferta_id = db.publicar_oferta_mural(j["user_id"], chave, qtd_final, instancia_id, preco)
    dado = ITENS[chave]
    sufixo = " (instância)" if instancia_id else f" x{qtd_final}"
    await ctx.send(
        f"📌 Oferta `#{oferta_id}` publicada: {dado['emoji']} **{dado['nome']}**{sufixo} por **{preco}** 🪙. "
        f"`rpg mural cancelar {oferta_id}` desfaz."
    )


async def _acao_aceitar(ctx, j, resto):
    if not resto.strip().isdigit():
        await ctx.send("Uso: `rpg mural aceitar <#>` — o número aparece em `rpg mural`.")
        return
    sucesso, resultado = db.aceitar_oferta_mural(int(resto.strip()), j["user_id"])
    if not sucesso:
        await ctx.send(f"❌ {resultado}")
        return
    oferta = resultado
    dado = ITENS[oferta["item"]]
    sufixo = "" if oferta["instancia_id"] else f" x{oferta['qtd']}"
    await ctx.send(f"✅ Você levou {dado['emoji']} **{dado['nome']}**{sufixo} por **{oferta['preco']}** 🪙.")


async def _acao_cancelar(ctx, j, resto):
    if not resto.strip().isdigit():
        await ctx.send("Uso: `rpg mural cancelar <#>` — só suas próprias ofertas.")
        return
    sucesso, resultado = db.cancelar_oferta_mural(int(resto.strip()), j["user_id"])
    if not sucesso:
        await ctx.send(f"❌ {resultado}")
        return
    await ctx.send(f"🧹 Oferta `#{resto.strip()}` cancelada — devolvido pra mochila.")


def instalar(bot, contexto):
    H.update(contexto)

    @bot.command(name="mural", aliases=["quadro"])
    async def mural_cmd(ctx, *, argumento: str = ""):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not await _exigir_praca(ctx, j):
            return

        partes = argumento.split(maxsplit=1)
        acao = H["normalizar"](partes[0]) if partes else ""
        resto = partes[1] if len(partes) > 1 else ""

        if not acao:
            await _acao_ver(ctx)
        elif acao in ("oferecer", "publicar", "anunciar"):
            await _acao_oferecer(ctx, j, resto)
        elif acao in ("aceitar", "comprar", "pegar"):
            await _acao_aceitar(ctx, j, resto)
        elif acao in ("cancelar", "remover"):
            await _acao_cancelar(ctx, j, resto)
        else:
            await ctx.send("Não conheço esse comando de mural. Opções: oferecer, aceitar, cancelar.")

    print("mural.py carregado — rpg mural (ver/oferecer/aceitar/cancelar), A Praça commit 2.")
