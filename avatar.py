# avatar.py
# Avatar cosmético do jogador -- aparece como thumbnail no `rpg perfil`.
# Módulo próprio, instalado pelo padrão simples de admin.py/agenda.py
# (`instalar(bot)`, sem os helpers de stats/combate de bot.py) porque não
# depende de nada disso, só de `jogadores.avatar_msg_id`/`avatar_url` e do
# canal de arquivo.
#
# A fonte da verdade é o ID DA MENSAGEM repostada em CANAL_ARQUIVO_ID, não a
# URL do anexo -- a URL do CDN do Discord expira por ASSINATURA (parâmetro
# `ex` na query string), não porque o arquivo sumiu. Enquanto a mensagem
# existir, pedir ela de novo (`fetch_message`) devolve uma URL nova com
# assinatura fresca pro MESMO arquivo -- por isso o cache é só otimização,
# nunca a fonte. Ver decisoes.md § avatar do jogador.
import io
import os
import time
import urllib.parse

import aiohttp
import discord

import database as db

# NUNCA ler CANAL_ARQUIVO_ID pra uma constante de módulo aqui em cima --
# `os.getenv` rodando na hora do `import avatar` já pegou None em produção
# uma vez, porque bot.py importava este módulo ANTES de chamar
# `load_dotenv()`. `_canal_arquivo_id()` lê a env var de novo a cada
# chamada -- não pode ficar congelado errado não importa a ordem de import
# (ver decisoes.md § canal de arquivo indisponível).
TAMANHO_MAXIMO_BYTES = 8 * 1024 * 1024
TIMEOUT_DOWNLOAD_SEG = 15

# margem de segurança antes do `ex` vencer de verdade -- evita servir uma
# URL que expira nos próximos minutos e falha silenciosamente quando o
# embed for renderizado do lado do cliente Discord.
MARGEM_EXPIRACAO_SEG = 300

TIPOS_ACEITOS = {"image/png", "image/jpeg", "image/webp"}
EXTENSAO_POR_TIPO = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}

MSG_TIPO_INVALIDO = "Só aceito imagem **png**, **jpg** ou **webp**. Manda de novo nesse formato."
MSG_TAMANHO_INVALIDO = f"Imagem grande demais -- o limite é {TAMANHO_MAXIMO_BYTES // (1024 * 1024)}MB."
MSG_LINK_INVALIDO = (
    "Não consegui baixar uma imagem válida desse link -- confere se é um "
    "link direto pra imagem (não uma página) e tenta de novo."
)

# três causas diferentes pro mesmo "não consegui postar no canal de
# arquivo" -- cada uma precisava de um restart+leitura de log diferente pra
# descobrir qual era, antes de virarem mensagem separada.
MSG_CANAL_SEM_ID = (
    "CANAL_ARQUIVO_ID não está configurado -- avisa o dono do bot (checar o `.env`)."
)
MSG_CANAL_NAO_ENCONTRADO = (
    "Não encontrei o canal de arquivo configurado -- avisa o dono do bot "
    "(ID errado, ou o bot não está naquele servidor)."
)
MSG_CANAL_SEM_PERMISSAO = (
    "O bot não tem permissão de postar no canal de arquivo -- avisa o dono "
    "do bot (falta Ver Canal ou Anexar Arquivos)."
)
MENSAGENS_CANAL = {
    "sem_id": MSG_CANAL_SEM_ID,
    "nao_encontrado": MSG_CANAL_NAO_ENCONTRADO,
    "sem_permissao": MSG_CANAL_SEM_PERMISSAO,
}

PICREW_URL = "https://picrew.me/en/image_maker/683306"

_canal_cache = None


def _normalizar_tipo(content_type):
    if not content_type:
        return None
    return content_type.split(";")[0].strip().lower()


def _url_expirada(url):
    """True se a assinatura `ex` da URL do CDN já venceu, está pra vencer
    (dentro de MARGEM_EXPIRACAO_SEG), ou é ilegível -- em qualquer um
    desses casos o chamador deve refazer o fetch em vez de arriscar servir
    uma URL morta."""
    try:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        expira_em = int(query["ex"][0], 16)
    except (KeyError, IndexError, ValueError):
        return True
    return expira_em - MARGEM_EXPIRACAO_SEG <= time.time()


async def _baixar_link(url, sessao=None):
    """Baixa até TAMANHO_MAXIMO_BYTES+1 bytes -- corta ali mesmo que o
    Content-Length minta ou falte, então nunca lê um corpo arbitrariamente
    grande na memória. None em qualquer falha (status, tipo, timeout,
    conexão) -- quem chama trata tudo como "link inválido", mensagem única.
    `sessao` é parâmetro pra dar pra injetar um fake nos testes."""
    fechar = sessao is None
    sessao = sessao or aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT_DOWNLOAD_SEG))
    try:
        async with sessao.get(url) as resp:
            if resp.status != 200:
                return None
            tipo = _normalizar_tipo(resp.headers.get("Content-Type"))
            if tipo not in TIPOS_ACEITOS:
                return None
            dados = await resp.content.read(TAMANHO_MAXIMO_BYTES + 1)
            if len(dados) > TAMANHO_MAXIMO_BYTES:
                return None
            return dados, tipo
    except (aiohttp.ClientError, TimeoutError):
        return None
    finally:
        if fechar:
            await sessao.close()


def _canal_arquivo_id():
    valor = os.getenv("CANAL_ARQUIVO_ID")
    return int(valor) if valor else None


async def _resolver_canal(bot):
    """`get_channel` (cache) primeiro, `fetch_channel` (API) como fallback
    -- um canal recém-criado pode não estar no cache de guild do bot ainda,
    e isso não é o mesmo problema que "canal não existe"/"sem permissão".
    Cacheia o objeto resolvido em `_canal_cache` pra não bater na API de
    novo depois da primeira vez. Devolve (canal, motivo): motivo é None no
    sucesso, ou uma chave de MENSAGENS_CANAL na falha."""
    global _canal_cache
    if _canal_cache is not None:
        return _canal_cache, None

    canal_id = _canal_arquivo_id()
    if canal_id is None:
        return None, "sem_id"

    canal = bot.get_channel(canal_id)
    if canal is not None:
        _canal_cache = canal
        return canal, None

    try:
        canal = await bot.fetch_channel(canal_id)
    except discord.Forbidden:
        return None, "sem_permissao"
    except discord.HTTPException:
        return None, "nao_encontrado"

    _canal_cache = canal
    return canal, None


async def diagnosticar_canal(bot):
    """Roda uma vez no `on_ready` -- responde no log qual das causas é (env
    var ausente, cache frio resolvido por fetch_channel, Forbidden,
    NotFound) sem precisar reproduzir o erro no Discord pra descobrir. Ver
    decisoes.md § canal de arquivo indisponível -- foi exatamente a falta
    disso que custou uma sessão de depuração em dois servidores."""
    global _canal_cache
    valor = os.getenv("CANAL_ARQUIVO_ID")
    if not valor:
        print("avatar.py: CANAL_ARQUIVO_ID não configurado -- rpg avatar vai recusar salvar imagem.")
        return

    canal_id = int(valor)
    canal = bot.get_channel(canal_id)
    if canal is not None:
        _canal_cache = canal
        print(f"avatar.py: CANAL_ARQUIVO_ID={valor} resolvido do cache -- #{canal.name}.")
        return

    print(f"avatar.py: CANAL_ARQUIVO_ID={valor} não está no cache do bot, tentando fetch_channel...")
    try:
        canal = await bot.fetch_channel(canal_id)
    except discord.Forbidden:
        print(f"avatar.py: CANAL_ARQUIVO_ID={valor} -- Forbidden (bot sem acesso ao canal).")
        return
    except discord.NotFound:
        print(f"avatar.py: CANAL_ARQUIVO_ID={valor} -- NotFound (nenhum canal com esse ID).")
        return
    except discord.HTTPException as erro:
        print(f"avatar.py: CANAL_ARQUIVO_ID={valor} -- falha ao buscar canal: {erro}")
        return

    _canal_cache = canal
    print(f"avatar.py: CANAL_ARQUIVO_ID={valor} resolvido via fetch_channel -- #{canal.name}.")


async def _repostar(bot, dados, nome_arquivo):
    """Sobe a imagem em CANAL_ARQUIVO_ID. Devolve ((msg_id, url), None) no
    sucesso, ou (None, motivo) na falha -- motivo é uma chave de
    MENSAGENS_CANAL, pra `rpg avatar` mostrar a causa certa em vez de um
    "indisponível" genérico que escondia três problemas diferentes."""
    canal, motivo = await _resolver_canal(bot)
    if canal is None:
        return None, motivo

    arquivo = discord.File(io.BytesIO(dados), filename=nome_arquivo)
    try:
        mensagem = await canal.send(file=arquivo)
    except discord.Forbidden:
        return None, "sem_permissao"
    except discord.HTTPException:
        return None, "nao_encontrado"
    return (mensagem.id, mensagem.attachments[0].url), None


async def obter_avatar_atualizado(bot, jogador):
    """URL pronta pra usar em `rpg perfil`/`rpg avatar` -- só refaz o fetch
    quando a assinatura em cache já venceu ou tá perto disso; URL ainda
    válida não gera nenhuma chamada de API. None se o jogador nunca definiu
    avatar OU se a mensagem/canal sumiu -- nunca deixa quem chama quebrar
    por causa de imagem."""
    if not jogador["avatar_msg_id"]:
        return None
    url_cache = jogador["avatar_url"]
    if url_cache and not _url_expirada(url_cache):
        return url_cache

    canal, _motivo = await _resolver_canal(bot)
    if canal is None:
        return None
    try:
        mensagem = await canal.fetch_message(jogador["avatar_msg_id"])
    except discord.HTTPException:
        return None
    if not mensagem.attachments:
        return None

    url_nova = mensagem.attachments[0].url
    db.atualizar_jogador(jogador["user_id"], avatar_url=url_nova)
    return url_nova


def _embed_avatar(url_atual):
    e = discord.Embed(title="🖼️ Seu avatar", color=0x8D99AE)
    if url_atual:
        e.description = "Esse é o que aparece no seu `rpg perfil`."
        e.set_thumbnail(url=url_atual)
    else:
        e.description = "Você ainda não definiu avatar -- usa o padrão do jogo."
    e.add_field(
        name="Como trocar",
        value=(
            "• `rpg avatar` + anexo de imagem (png, jpg ou webp, até "
            f"{TAMANHO_MAXIMO_BYTES // (1024 * 1024)}MB)\n"
            "• `rpg avatar <link>` com um link direto pra imagem\n"
            "• `rpg avatar remover` -- volta pro padrão"
        ),
        inline=False,
    )
    e.add_field(
        name="Onde fazer a arte",
        value=f"• Picrew — {PICREW_URL}",
        inline=False,
    )
    return e


def instalar(bot):
    @bot.command(name="avatar")
    async def avatar_cmd(ctx, link: str = None):
        jogador = db.get_jogador(ctx.author.id)
        if not jogador:
            await ctx.send("Você ainda não entrou na torre -- usa `rpg comecar` primeiro.")
            return

        if link and link.lower() == "remover":
            db.atualizar_jogador(ctx.author.id, avatar_msg_id=None, avatar_url=None)
            await ctx.send("Avatar removido -- voltou pro padrão.")
            return

        anexos = ctx.message.attachments
        if not anexos and not link:
            url_atual = await obter_avatar_atualizado(bot, jogador)
            await ctx.send(embed=_embed_avatar(url_atual))
            return

        if anexos:
            anexo = anexos[0]
            tipo = _normalizar_tipo(anexo.content_type)
            if tipo not in TIPOS_ACEITOS:
                await ctx.send(MSG_TIPO_INVALIDO)
                return
            if anexo.size > TAMANHO_MAXIMO_BYTES:
                await ctx.send(MSG_TAMANHO_INVALIDO)
                return
            dados = await anexo.read()
        else:
            resultado = await _baixar_link(link)
            if resultado is None:
                await ctx.send(MSG_LINK_INVALIDO)
                return
            dados, tipo = resultado

        nome_arquivo = f"avatar_{ctx.author.id}.{EXTENSAO_POR_TIPO[tipo]}"
        resultado, motivo = await _repostar(bot, dados, nome_arquivo)
        if resultado is None:
            await ctx.send(MENSAGENS_CANAL[motivo])
            return

        msg_id, url = resultado
        db.atualizar_jogador(ctx.author.id, avatar_msg_id=msg_id, avatar_url=url)
        await ctx.send("✅ Avatar atualizado -- aparece no seu `rpg perfil` a partir de agora.")

    print("avatar.py carregado -- rpg avatar.")
