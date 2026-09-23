# estrada.py
# Step E, commit 1: a estrada. `rpg viajar` fora da torre (Mirante <-> vilarejo,
# Step B/C) passa a poder ser interrompido por um encontro -- a estrada entre
# os dois lugares ganha risco de verdade, não só distância. A escada que sobe
# de volta pro andar 15 (a porta) fica de fora de propósito: é o mesmo degrau
# de sempre, não "estrada" nenhuma -- só as duas pernas que atravessam terreno
# aberto (ver decisoes.md § Step E).
#
# Mesmo padrão H = {} / instalar(bot, contexto) de combate.py/dungeon.py/
# raide.py -- reaproveita o motor de combate de verdade (combate.Luta,
# PainelLuta) em vez de escrever um sistema de luta paralelo. Só o FIM da
# luta é diferente (chegar ao destino, ser roubado, recuperar o que foi
# roubado) -- mesmo padrão de dungeon.PainelEspelho/raide.PainelRaide,
# overriding só `fim_da_luta`/`_continuar`, nunca os botões.
import random

import discord

import combate
import database as db
import game_data
import incursao
import mundo

H = {}

# Chance de encontro por viagem -- constante nomeada, o cartão pediu baixa o
# bastante pra viajar não virar farm de bandido, alta o bastante pra estrada
# ter fama. Ponto de partida pra playtest, mede depois (ver decisoes.md).
CHANCE_ENCONTRO_ESTRADA = 0.12

COR_ESTRADA = 0x5A4632

# ---------------- commit 2: os ladrões, de 1 a 4 ----------------
GRUPO_MIN, GRUPO_MAX = 1, 4

# Nomes e cara própria -- "bandido de estrada, não monstro. Eles falam." Cada
# um tem uma fala mostrada na abertura do encontro (ver iniciar_encontro).
BANDIDOS = [
    {"nome": "Renco, o Faca Torta", "fala": "Sua bolsa, ou sua sorte — só peço uma vez."},
    {"nome": "Ivete dos Dedos Leves", "fala": "Relaxa. Eu levo rápido, você nem sente."},
    {"nome": "Bruno Calo", "fala": "Ninguém passa por aqui de graça, e você não é ninguém."},
    {"nome": "A Viúva do Posto", "fala": "Chamam ela assim porque quem resiste vira viúvo."},
    {"nome": "Tomé Sem Sombra", "fala": "Eu já andei essa estrada mais vezes do que você respirou hoje."},
    {"nome": "Iuna, a Que Não Erra", "fala": "Não é pessoal. É só a estrada cobrando pedágio."},
]


def houve_encontro():
    return random.random() < CHANCE_ENCONTRO_ESTRADA


def sortear_grupo(jogador):
    """Grupo de 1 a 4, nomeado -- estatísticas escaladas pelo MESMO
    andar de referência das incursões (`incursao.andar_referencia`,
    andar_max travado em [1, ANDAR_MAXIMO]), não pelo andar em si (fora
    da torre `andar` é só congelado, não significa nada -- ver Step B).
    Reaproveita os números já tunados de `game_data.ANDARES` em vez de
    inventar uma curva nova, mesmo raciocínio do Step D.

    "Um grupo de quatro não pode ser quatro vezes um" -- hp e atk do
    monstro de referência são DIVIDIDOS pelo tamanho do grupo (o total
    de HP pra derrubar e o total de dano por rodada ficam calibrados
    contra UM jogador, não multiplicam por bandido); a defesa NÃO
    divide -- ela não soma entre bandidos do jeito que hp/atk somam, e
    um bandido individual mais fácil de acertar não é o que o cartão
    pediu. Ver decisoes.md § Step E pro raciocínio completo."""
    tamanho = random.randint(GRUPO_MIN, GRUPO_MAX)
    escolhidos = random.sample(BANDIDOS, tamanho)
    referencia = incursao.andar_referencia(jogador)
    monstros_referencia = game_data.ANDARES[referencia]["monstros"]
    base = monstros_referencia[random.randrange(len(monstros_referencia))]
    return [
        {
            "nome": bandido["nome"],
            "hp": max(1, base["hp"] // tamanho),
            "atk": max(1, base["atk"] // tamanho),
            "def": base["def"],
            "xp": 0,
            "moedas": 0,
            "fala": bandido["fala"],
        }
        for bandido in escolhidos
    ]


# ---------------- commit 3: perder é ser roubado ----------------
# Ladrão não mata -- nada de processar_morte, nada de penalidade da torre.
# Isso é o segundo tipo de derrota do jogo: a torre pune com morte, a
# estrada pune com prejuízo. Fração menor que a penalidade de morte (0.20,
# bot.processar_morte) -- a estrada é o prejuízo mais leve dos dois, de
# propósito (ela nem tira o "chegar ao destino").
FRACAO_ROUBO_MOEDAS = 0.15

# A peça roubada é sempre uma das EQUIPADAS -- nunca mochila. Decisão (o
# cartão pediu pra documentar): é o que está exposto, visível, o que um
# assalto de verdade levaria; a mochila fica de fora pra não precisar
# escolher ENTRE cópias/instâncias empilhadas lá dentro. Guarda a
# INSTÂNCIA INTEIRA quando a peça tinha uma -- recomendação do próprio
# cartão ("sem isso, recuperar devolve uma casca"): melhoria, encantamento,
# joia e efeito (Step D) atravessam o roubo intactos, só trocam de "dono"
# no banco (ver database.soltar_instancia_para_roubo) até a devolução
# (commit 4).
SLOTS_EQUIPAVEIS = ("arma", "armadura", "anel", "colar", "mortalha")


def roubar(user_id):
    """Sorteia dinheiro OU uma peça, 50/50 quando os dois são possíveis
    -- sem dinheiro, força peça; sem peça equipada, força dinheiro; sem
    nenhum dos dois, não há o que levar. Devolve a frase pro embed de
    derrota."""
    j = db.get_jogador(user_id)
    slots_ocupados = [slot for slot in SLOTS_EQUIPAVEIS if j[slot]]
    tem_moedas = j["moedas"] > 0
    if not slots_ocupados and not tem_moedas:
        return "Eles reviram seus bolsos e não acham nada — você não tinha nada pra perder."

    roubar_peca = bool(slots_ocupados) and (not tem_moedas or random.random() < 0.5)
    if roubar_peca:
        slot = random.choice(slots_ocupados)
        item = j[slot]
        instancia_id = j[f"{slot}_instancia_id"]
        db.atualizar_jogador(user_id, **{slot: None, f"{slot}_instancia_id": None})
        db.registrar_roubo_item(user_id, item, instancia_id)
        if instancia_id:
            db.soltar_instancia_para_roubo(instancia_id)
        dado = game_data.ITENS[item]
        return f"Levaram {dado.get('emoji', '')} **{dado['nome']}** — seu {slot} ficou vazio.".replace("  ", " ")

    valor = max(1, int(j["moedas"] * FRACAO_ROUBO_MOEDAS))
    db.atualizar_jogador(user_id, moedas=j["moedas"] - valor)
    db.registrar_roubo_moedas(user_id, valor)
    return f"Levaram **{valor}** 🪙."


# ---------------- commit 4: o revide ----------------
def devolver_um_roubo(user_id):
    """Qualquer grupo de bandidos VENCIDO devolve o que a estrada levou
    -- não precisa ser o mesmo grupo que roubou (o cartão foi
    explícito). Mais de uma perda acumulada? Uma por vitória, a mais
    antiga primeiro (FIFO -- `roubos_pendentes` já ordena por id) --
    "dá mais vida à estrada" que devolver tudo de uma vez só (o cartão
    sugeriu essa opção, escolhida e documentada aqui: voltar tudo junto
    reduziria cada roubo a um número que zera na primeira vitória
    seguinte; devolver aos poucos mantém um motivo pra viajar de novo).
    None se não havia nada pendente -- `_finalizar_vitoria_estrada` só
    mostra o campo "revide" quando tem descrição de verdade."""
    pendentes = db.roubos_pendentes(user_id)
    if not pendentes:
        return None
    roubo = pendentes[0]
    if roubo["tipo"] == "moedas":
        j = db.get_jogador(user_id)
        db.atualizar_jogador(user_id, moedas=j["moedas"] + roubo["valor"])
        db.remover_roubo(roubo["id"])
        return f"Devolveram **{roubo['valor']}** 🪙 que a estrada tinha levado."
    if roubo["instancia_id"]:
        db.devolver_instancia_roubada(roubo["instancia_id"], user_id)
    else:
        db.add_item(user_id, roubo["item"], 1)
    db.remover_roubo(roubo["id"])
    dado = game_data.ITENS[roubo["item"]]
    return f"Devolveram {dado.get('emoji', '')} **{dado['nome']}** que a estrada tinha levado.".replace("  ", " ")


async def iniciar_encontro(ctx, j, destino_mundo):
    """Chamado por bot._viajar_fora quando `houve_encontro()` deu positivo
    -- a viagem PARA aqui: `mundo.descer_para_o_vilarejo`/`subir_para_o_
    mirante` ainda não rodou. `destino_mundo` (mundo.VILAREJO ou mundo.
    MIRANTE) só é aplicado de verdade dentro de `_finalizar_vitoria_estrada`/
    `_finalizar_derrota_estrada` -- "vencendo, o jogador chega ao destino;
    perdendo, a viagem se resolve sem morte" (o cartão foi explícito: os
    dois casos chegam, só fugir é que não).

    `andar_num` da Luta usa o mesmo andar de REFERÊNCIA que `sortear_
    grupo` já usa pra escalar hp/atk (`incursao.andar_referencia`) --
    fora da torre `j["andar"]` é só congelado (Step B), não pode
    alimentar `at.destreza_monstro`."""
    s = H["stats"](j)
    c = combate.Combatente(j, s)
    grupo = sortear_grupo(j)
    luta = combate.Luta([c], grupo, andar_num=incursao.andar_referencia(j))
    painel = PainelEstrada(luta, j["user_id"], destino_mundo)
    falas = "\n".join(f"*“{b.get('fala')}”* — {b['nome']}" for b in grupo if b.get("fala"))
    e = luta.embed(
        titulo="Bandidos na estrada!",
        cor=COR_ESTRADA,
        rodape="A viagem para -- vença pra continuar.",
    )
    if falas:
        e.description = f"{e.description}\n\n{falas}" if e.description else falas
    painel.mensagem = await ctx.send(embed=e, view=painel)


class PainelEstrada(combate.PainelLuta):
    """Mesmos botões de sempre (Atacar/Defender/Habilidade/Mortalha/Fugir)
    -- só o FIM muda. Sempre solo (a viagem é individual, ninguém convida
    party pra `rpg viajar`)."""

    def __init__(self, luta, user_id, destino_mundo):
        super().__init__(luta)
        self.user_id = user_id
        self.destino_mundo = destino_mundo

    def _continuar(self, luta):
        return PainelEstrada(luta, self.user_id, self.destino_mundo)

    async def fim_da_luta(self, interaction=None):
        luta = self.luta
        if not luta.inimigos_ativos:
            return await _finalizar_vitoria_estrada(luta, self.user_id, self.destino_mundo)
        if not luta.ativos:
            combate._talvez_auto_ressuscitar(luta)   # clérigo solo -- a luta de estrada é sempre solo
            if not luta.ativos:
                if any(c.caiu for c in luta.participantes) and not any(
                    c.fugiu or c.saiu for c in luta.participantes
                ):
                    return await _finalizar_derrota_estrada(luta, self.user_id, self.destino_mundo)
                return await _finalizar_abandono_estrada(luta)
        return None


def _completar_viagem(user_id, destino_mundo):
    if destino_mundo == mundo.VILAREJO:
        mundo.descer_para_o_vilarejo(user_id)
    else:
        mundo.subir_para_o_mirante(user_id)


async def _finalizar_vitoria_estrada(luta, user_id, destino_mundo):
    """Vencendo, o jogador chega ao destino -- a estrada não pune quem
    ganhou (o cartão foi explícito). Sem recompensa de XP/moedas: os
    bandidos não são farm (ver decisoes.md § Step E), só obstáculo --
    a única recompensa de vencer é `devolver_um_roubo` (commit 4), que
    só existe se houver algo pendente."""
    luta.encerrada = True
    c = luta.participantes[0]
    c.salvar_estado()
    _completar_viagem(user_id, destino_mundo)
    descricao_devolucao = devolver_um_roubo(user_id)
    dados_lugar = mundo.LOCAIS_FORA[destino_mundo]
    e = luta.embed(
        titulo="Os bandidos recuam",
        cor=COR_ESTRADA,
        rodape=f"Vencido na rodada {luta.rodada}.",
    )
    e.add_field(name="Você chega", value=f"{dados_lugar['nome']} -- a estrada ficou livre dessa vez.", inline=False)
    if descricao_devolucao:
        e.add_field(name="🤝 O revide", value=descricao_devolucao, inline=False)
    return e


async def _finalizar_derrota_estrada(luta, user_id, destino_mundo):
    """Ladrão não mata -- nada de processar_morte, nada de penalidade da
    torre. A viagem se resolve sem morte: o jogador ainda chega, só mais
    pobre (`roubar`, commit 3, decide exatamente o quê)."""
    luta.encerrada = True
    c = luta.participantes[0]
    c.salvar_estado()
    _completar_viagem(user_id, destino_mundo)
    descricao_roubo = roubar(user_id)
    dados_lugar = mundo.LOCAIS_FORA[destino_mundo]
    e = luta.embed(
        titulo="Os bandidos levam o que querem",
        cor=combate.COR_DERROTA,
        rodape=f"Caído na rodada {luta.rodada}.",
    )
    e.add_field(name="Assaltado", value=descricao_roubo, inline=False)
    e.add_field(
        name="Mas vivo",
        value=f"Você chega em {dados_lugar['nome']} de qualquer jeito.",
        inline=False,
    )
    return e


async def _finalizar_abandono_estrada(luta):
    """Fugir não pune (sem roubo) mas também não completa a viagem --
    o jogador volta pra onde estava, não pra onde ia."""
    luta.encerrada = True
    e = luta.embed(
        titulo="Você foge dos bandidos",
        cor=combate.COR_FUGA,
        rodape="Sem punição, mas sem chegar -- tenta de novo quando quiser.",
    )
    e.add_field(name="Sem vencedor", value="Você corre de volta pelo mesmo caminho.", inline=False)
    return e


def instalar(bot, contexto):
    H.update(contexto)
