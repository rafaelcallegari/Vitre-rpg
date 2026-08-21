# salao.py
# Salão da Guilda: tier derivado da quantidade TOTAL de tesouros de chefe
# depositados (não distintos -- é a decisão que sustenta todo o desenho, ver
# decisoes.md § Salão da Guilda). Módulo "sem instalar()", igual em espírito
# a andares_altos.py/dialogos.py: só funções puras + views de Discord que não
# precisam de H, importado direto por guildas.py/raide.py/admin.py. Não
# importa guildas.py nem bot.py -- quem chama já sabe quantos membros a
# guilda tem e passa isso como parâmetro, evita import circular.

import re
import time
import unicodedata

import discord

import database as db
import paginacao
from game_data import ITENS, SALAO_TIERS

COR_SALAO = 0x8B6914
LIMITE_ASSINATURA = 140

_PADRAO_MENCAO_MASSA = re.compile(r"@(everyone|here)\b", re.IGNORECASE)


def _normalizar(texto):
    texto = unicodedata.normalize("NFD", texto.lower().strip())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------- catálogo
def tesouros_do_catalogo():
    """Chaves de ITENS com tipo 'tesouro' -- fonte única, nunca lista escrita
    à mão (senão o próximo tesouro novo esquece de entrar aqui)."""
    return [k for k, v in ITENS.items() if v.get("tipo") == "tesouro"]


def eh_tesouro(item):
    return item in ITENS and ITENS[item].get("tipo") == "tesouro"


def extrair_tesouro(texto):
    """(chave, resto) a partir de um texto livre tipo 'Coroa Velha alguma
    mensagem aqui' -- casa o NOME ou a CHAVE de um tesouro conhecido contra
    o início do texto, palavra por palavra (não por índice de string: nomes
    acentuados mudam de tamanho ao normalizar, então fatiar por posição seria
    furado). (None, "") se nada bateu."""
    palavras = texto.strip().split()
    melhor = None  # (chave, n_palavras_consumidas)
    for chave in tesouros_do_catalogo():
        for candidato in (chave, ITENS[chave]["nome"]):
            n = len(candidato.split())
            if not n or n > len(palavras):
                continue
            trecho = " ".join(palavras[:n])
            if _normalizar(trecho) == _normalizar(candidato):
                if not melhor or n > melhor[1]:
                    melhor = (chave, n)
    if not melhor:
        return None, ""
    chave, n = melhor
    return chave, " ".join(palavras[n:]).strip()


# ------------------------------------------------------------------- tiers
def tier_por_total(total):
    """SALAO_TIERS em ordem crescente de min_tesouros -- devolve o tier mais
    alto que `total` já alcançou (nunca None, o tier 0 sempre serve de piso)."""
    atual = SALAO_TIERS[0]
    for t in SALAO_TIERS:
        if total >= t["min_tesouros"]:
            atual = t
    return atual


def proximo_tier(total):
    """O tier seguinte ainda não alcançado, ou None se já é o máximo."""
    for t in SALAO_TIERS:
        if total < t["min_tesouros"]:
            return t
    return None


def tier_efetivo(total, membros_count, membros_minimo):
    """O tier que realmente vale pra benefício (home liberada, cooldown de
    raide) -- abaixo do piso de membros, o Salão não concede nada, mesmo com
    tesouro de sobra (ver decisoes.md § Piso de membros: sem isso o ótimo é
    fundar guilda solo e ser o próprio Salão). A CONTAGEM e a vitrine
    continuam mostrando o tier "de verdade" (por `tier_por_total`); só o
    benefício é suprimido aqui."""
    if membros_count < membros_minimo:
        return SALAO_TIERS[0]
    return tier_por_total(total)


# --------------------------------------------------------------- sanitização
def mencao_em_massa(texto):
    return bool(_PADRAO_MENCAO_MASSA.search(texto))


def normalizar_assinatura(texto):
    """Quebra de linha e espaço redundante viram um espaço só -- mantém a
    vitrine em uma linha por tesouro."""
    return " ".join(texto.split())


# -------------------------------------------------------------------- vitrine
def _fmt_cooldown(segundos):
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    return f"{horas}h{minutos:02d}" if minutos else f"{horas}h"


_LINHA_CURTA = (
    "Tesouro de chefe: segundo drop do chefe de cada andar 1–10, conta pro total da guilda "
    "inteira, zera por temporada — sem bônus de combate."
)


def _texto_salao_vazio(progresso):
    return (
        f"{progresso}\n\n"
        "Tesouro de chefe é o segundo drop garantido do chefe de cada andar 1–10 — não é "
        "vendável, não equipa, não é material de craft. Só serve pro Salão.\n"
        "O Salão conta o total depositado pela guilda inteira, não só o seu, e o progresso é "
        "POR TEMPORADA — zera a cada reset (o que já caiu fica de pé no histórico, "
        "`rpg guilda salao historico`).\n"
        "O Salão **não dá bônus de combate**: o que o tier destrava é o andar máximo pra home "
        "da guilda e um cooldown de raide menor.\n\n"
        "`rpg guilda depositar <tesouro>` depois de vencer um chefe (1-10) preenche isso."
    )


def _entrada_tesouro(row):
    dado = ITENS.get(row["item"], {})
    nome_item = f"{dado.get('emoji', '')} {dado.get('nome', row['item'])}".strip()
    quando = time.strftime("%d/%m/%Y", time.localtime(row["depositado_em"])) if row["depositado_em"] else "?"
    nome = f"{nome_item} — <@{row['user_id']}>"
    if row["mensagem"]:
        valor = f"*{discord.utils.escape_markdown(row['mensagem'])}*\n`{quando}`"
    else:
        valor = f"sem assinatura\n`{quando}`"
    return nome, valor


def _descricao_progresso(total):
    tier = tier_por_total(total)
    prox = proximo_tier(total)
    descricao = f"**{tier['nome']}** — {total} tesouro(s) depositado(s) nesta temporada."
    if prox:
        descricao += (
            f" Faltam **{prox['min_tesouros'] - total}** pro tier **{prox['nome']}** — libera home "
            f"até o andar {prox['andar_home_max']} e cooldown de raide de {_fmt_cooldown(prox['cooldown_raide'])}."
        )
    else:
        descricao += " Tier máximo — nada mais pra destravar aqui."
    return descricao


async def acao_vitrine(ctx, guilda, pagina=1):
    temporada = db.temporada_atual()
    linhas = db.tesouros_do_salao(guilda["id"], temporada)
    total = len(linhas)
    progresso = _descricao_progresso(total)
    descricao = f"{_LINHA_CURTA}\n{progresso}" if total else _texto_salao_vazio(progresso)
    entradas = [_entrada_tesouro(r) for r in linhas]
    await paginacao.enviar_paginado(
        ctx, entradas, f"🏛️ Salão de {guilda['nome']}", COR_SALAO,
        descricao=descricao,
        rodape_extra="rpg guilda depositar <tesouro> · rpg guilda salao historico",
        pagina_inicial=pagina,
        mensagem_vazia=_texto_salao_vazio(progresso),
        allowed_mentions=discord.AllowedMentions.none(),
    )


async def acao_historico(ctx, guilda, resto):
    resto = resto.strip()
    if resto.isdigit():
        temporada = int(resto)
        linhas = db.tesouros_do_salao(guilda["id"], temporada)
        entradas = [_entrada_tesouro(r) for r in linhas]
        await paginacao.enviar_paginado(
            ctx, entradas, f"🏛️ Salão de {guilda['nome']} — temporada {temporada}", COR_SALAO,
            descricao=f"{len(linhas)} tesouro(s) — arquivo, somente leitura.",
            mensagem_vazia=f"Nada registrado pra **{guilda['nome']}** na temporada {temporada}.",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return

    atual = db.temporada_atual()
    passadas = [t for t in db.temporadas_com_salao(guilda["id"]) if t != atual]
    if not passadas:
        await ctx.send("Nenhuma temporada passada registrada pra essa guilda ainda.")
        return
    linhas = "\n".join(f"• Temporada {t} — `rpg guilda salao historico {t}`" for t in passadas)
    e = discord.Embed(title=f"Temporadas passadas — {guilda['nome']}", description=linhas, color=COR_SALAO)
    await ctx.send(embed=e)


# ---------------------------------------------------------------- depósito
async def depositar(ctx, j, guilda, item, assinatura, confirmar_acao_cls):
    """confirmar_acao_cls é a view Confirmar/Cancelar (admin.ConfirmarAcao) --
    recebida por parâmetro em vez de importada no topo do módulo pra não
    prender salao.py a admin.py na hora de importar (só precisa dela dentro
    desta função)."""
    if not db.tem_item(j["user_id"], item, 1):
        await ctx.send(f"Você não tem {ITENS[item]['emoji']} **{ITENS[item]['nome']}** na mochila.")
        return

    assinatura = normalizar_assinatura(assinatura)
    if len(assinatura) > LIMITE_ASSINATURA:
        await ctx.send(
            f"Assinatura muito longa — até {LIMITE_ASSINATURA} caracteres "
            f"(a sua tem {len(assinatura)}). Encurta e tenta de novo."
        )
        return
    if mencao_em_massa(assinatura):
        await ctx.send(
            "Assinatura não pode conter `@everyone`/`@here` — isso pingaria o servidor inteiro toda vez "
            "que alguém abrir o Salão, e o depósito não pode ser desfeito depois. Tira a menção e tenta de novo."
        )
        return

    e = discord.Embed(
        title=f"⚠️ Depositar {ITENS[item]['nome']} no Salão",
        description=(
            f"{ITENS[item]['emoji']} **{ITENS[item]['nome']}** sai da sua mochila e é cravado no Salão de "
            f"**{guilda['nome']}** — **isso não pode ser desfeito.**\n\n"
            + (f"Assinatura: *{discord.utils.escape_markdown(assinatura)}*" if assinatura else "Sem assinatura.")
        ),
        color=COR_SALAO,
    )
    view = confirmar_acao_cls(ctx.author.id)
    view.mensagem = await ctx.send(embed=e, view=view, allowed_mentions=discord.AllowedMentions.none())
    await view.wait()
    if not view.confirmado:
        await ctx.send("Depósito cancelado — o tesouro continua na mochila.")
        return

    if not db.remove_item(j["user_id"], item, 1):
        await ctx.send("Você não tem mais esse item — algo mudou nesse meio tempo. Nada foi depositado.")
        return
    db.depositar_tesouro_salao(guilda["id"], item, j["user_id"], assinatura or None)
    db.guilda_log(guilda["id"], j["user_id"], "depositou_salao", item, 1)

    total = db.contar_tesouros_salao(guilda["id"])
    tier = tier_por_total(total)
    prox = proximo_tier(total)
    falta = f" — faltam **{prox['min_tesouros'] - total}** pro tier {prox['nome']}" if prox else " — tier máximo"
    await ctx.send(
        f"🏛️ {ITENS[item]['emoji']} **{ITENS[item]['nome']}** cravado no Salão. "
        f"Total: **{total}** — {tier['nome']}{falta}."
    )


# ------------------------------------------------------------- assinatura
async def _editar_mensagem(ctx, guilda, item_texto, dono_id, nova_mensagem, quem_pediu_nome=None):
    tesouro, resto = extrair_tesouro(item_texto)
    if not tesouro:
        await ctx.send("Não reconheci esse tesouro pelo nome. Confere `rpg guilda salao`.")
        return
    if nova_mensagem is not None:
        nova_mensagem = normalizar_assinatura(nova_mensagem)
        if len(nova_mensagem) > LIMITE_ASSINATURA:
            await ctx.send(
                f"Assinatura muito longa — até {LIMITE_ASSINATURA} caracteres (a sua tem {len(nova_mensagem)})."
            )
            return
        if mencao_em_massa(nova_mensagem):
            await ctx.send("Assinatura não pode conter `@everyone`/`@here`.")
            return
        nova_mensagem = nova_mensagem or None

    linha = db.tesouro_salao_do_membro(guilda["id"], tesouro, dono_id, db.temporada_atual())
    if not linha:
        alvo_txt = quem_pediu_nome or "Você"
        await ctx.send(f"{alvo_txt} não depositou **{ITENS[tesouro]['nome']}** nesta temporada.")
        return
    db.definir_mensagem_tesouro_salao(linha["id"], nova_mensagem)
    if nova_mensagem:
        await ctx.send(f"Assinatura de **{ITENS[tesouro]['nome']}** atualizada.")
    else:
        await ctx.send(f"Assinatura de **{ITENS[tesouro]['nome']}** apagada.")


async def acao_assinar(ctx, j, guilda, resto):
    tesouro, mensagem = extrair_tesouro(resto)
    if not tesouro:
        await ctx.send("Uso: `rpg guilda salao assinar <tesouro> <mensagem>`.")
        return
    if not mensagem:
        await ctx.send("Uso: `rpg guilda salao assinar <tesouro> <mensagem>` — a mensagem não pode ser vazia.")
        return
    await _editar_mensagem(ctx, guilda, resto, j["user_id"], mensagem)


async def acao_apagar_assinatura(ctx, j, guilda, resto):
    if not resto.strip():
        await ctx.send("Uso: `rpg guilda salao apagar <tesouro>`.")
        return
    await _editar_mensagem(ctx, guilda, resto, j["user_id"], "")


async def acao_limpar_assinatura(ctx, j, guilda, resto):
    if guilda["lider_id"] != j["user_id"]:
        await ctx.send("Só o líder limpa a assinatura de outro membro.")
        return
    if not ctx.message.mentions:
        await ctx.send("Uso: `rpg guilda salao limpar @membro <tesouro>`.")
        return
    alvo = ctx.message.mentions[0]
    texto_sem_mencao = re.sub(r"<@!?\d+>", "", resto).strip()
    if not texto_sem_mencao:
        await ctx.send("Uso: `rpg guilda salao limpar @membro <tesouro>`.")
        return
    await _editar_mensagem(ctx, guilda, texto_sem_mencao, alvo.id, "", quem_pediu_nome=alvo.display_name)
