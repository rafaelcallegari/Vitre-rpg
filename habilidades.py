# habilidades.py
# Infraestrutura do sistema de habilidades: quem conhece o quê, afinidade de
# arma, poder base de dano/efeito, e o comando pra ver a lista fora de
# combate. O botão de lançar e os efeitos de cada skill (dano, condição,
# cura, redirecionamento) vivem em combate.py, porque dependem do estado da
# luta (mana/fúria/energia do combatente, turno, HP do chefe).

import discord

import atributos as at
import paginacao
from game_data import CLASSES, HABILIDADES

H = {}

FATOR_FORA_DE_AFINIDADE = 0.5  # fora da arma da classe, a skill rende metade

NOME_RECURSO = {"mana": "mana", "furia": "fúria", "energia": "energia"}


# ------------------------------------------------------------ conhecimento

def extras_de(jogador):
    """Chaves de habilidade destravadas por sidequest (não por atributo)."""
    return set(t for t in (jogador["habilidades_extras"] or "").split(",") if t)


def conhecida(jogador, chave, dados, extras=None):
    """Sem requisito = vem da classe. Com requisito = precisa do atributo.
    Marcada como sidequest = só conta se estiver em habilidades_extras,
    não importa o atributo."""
    if dados.get("sidequest"):
        extras = extras_de(jogador) if extras is None else extras
        return chave in extras
    requisito = dados.get("requisito")
    if not requisito:
        return True
    atributo, minimo = requisito
    return int(jogador[atributo] or 0) >= minimo


def habilidades_da_classe(classe):
    return {k: v for k, v in HABILIDADES.items() if v["classe"] == classe}


def conhecidas(jogador):
    """Habilidades da classe do jogador que ele já destravou."""
    if not jogador["classe"]:
        return {}
    extras = extras_de(jogador)
    return {
        k: v for k, v in habilidades_da_classe(jogador["classe"]).items()
        if conhecida(jogador, k, v, extras)
    }


def lancaveis(jogador, recurso_atual):
    """Das conhecidas, quais cabem no recurso disponível agora (mana, fúria
    ou energia — cada classe só usa um, então um número basta)."""
    return {k: v for k, v in conhecidas(jogador).items() if v["custo"] <= recurso_atual}


def poder_base(jogador, bonus_arma=0):
    """Base de dano/efeito de habilidade — mesma forma de at.ataque, COM o
    bônus de atk da arma equipada (bonus_arma), escalando no
    atributo_habilidade da classe do jogador.

    Até a correção de decisoes.md § Dano de skill abaixo do ataque básico,
    essa função não recebia bonus_arma — skill de dano crescia só com o
    atributo, enquanto o ataque normal também cresce com o atk da arma
    (+8 no andar 1 a +82 no andar 9). Skill ficava pra trás sozinha, cada
    vez mais, conforme o jogador progredia na torre."""
    atributo = CLASSES[jogador["classe"]]["atributo_habilidade"]
    return at.ataque(int(jogador[atributo] or 0), bonus_arma)


# --------------------------------------------------------------- afinidade

def fator_afinidade(classe, arma):
    """1.0 com a arma da afinidade da classe; reduzido fora dela.

    Nada é proibido — jogar fora da afinidade só rende menos.
    """
    dados = CLASSES.get(classe)
    if not dados:
        return 1.0
    arma_atributo = (arma or {}).get("atributo", "destreza")
    return 1.0 if arma_atributo == dados["afinidade_arma"] else FATOR_FORA_DE_AFINIDADE


# ---------------------------------------------------------------- instalacao

def instalar(bot, contexto):
    H.update(contexto)

    @bot.command(name="habilidades", aliases=["skills", "magias", "habilidade"])
    async def habilidades_cmd(ctx, pagina: int = 1):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not j["classe"]:
            await ctx.send("Você ainda não escolheu uma classe. `rpg classe` mostra as opções.")
            return

        dados_classe = CLASSES[j["classe"]]
        conhec = conhecidas(j)
        entradas = [
            (f"{d['emoji']} {d['nome']} — {d['custo']} {NOME_RECURSO[d['recurso']]}", d["desc"])
            for d in conhec.values()
        ]
        await paginacao.enviar_paginado(
            ctx, entradas, f"{dados_classe['emoji']} Habilidades de {dados_classe['nome']}", 0x6A4C93,
            rodape_extra="Só é possível lançar em luta de chefe — rpg boss", pagina_inicial=pagina,
            mensagem_vazia="Nenhuma habilidade conhecida ainda.",
        )

    print("habilidades.py carregado — 8 skills no catálogo (2 por classe).")
