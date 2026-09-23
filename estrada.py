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
import mundo

H = {}

# Chance de encontro por viagem -- constante nomeada, o cartão pediu baixa o
# bastante pra viajar não virar farm de bandido, alta o bastante pra estrada
# ter fama. Ponto de partida pra playtest, mede depois (ver decisoes.md).
CHANCE_ENCONTRO_ESTRADA = 0.12

COR_ESTRADA = 0x5A4632


def houve_encontro():
    return random.random() < CHANCE_ENCONTRO_ESTRADA


# ---------------- o grupo (placeholder do commit 1 -- Commit 2 sorteia de verdade) ----------------
def sortear_grupo(jogador):
    """Commit 1: um bandido só, fixo -- só pra provar que a viagem para e a
    luta acontece. Commit 2 substitui isto por um grupo de 1 a 4, nomeado e
    escalado pelo andar_max do jogador (ver decisoes.md § Step E)."""
    return [{"nome": "Bandido de Estrada", "hp": 60, "atk": 8, "def": 2, "xp": 0, "moedas": 0}]


async def iniciar_encontro(ctx, j, destino_mundo):
    """Chamado por bot._viajar_fora quando `houve_encontro()` deu positivo
    -- a viagem PARA aqui: `mundo.descer_para_o_vilarejo`/`subir_para_o_
    mirante` ainda não rodou. `destino_mundo` (mundo.VILAREJO ou mundo.
    MIRANTE) só é aplicado de verdade dentro de `_finalizar_vitoria_estrada`/
    `_finalizar_derrota_estrada` -- "vencendo, o jogador chega ao destino;
    perdendo, a viagem se resolve sem morte" (o cartão foi explícito: os
    dois casos chegam, só fugir é que não)."""
    s = H["stats"](j)
    c = combate.Combatente(j, s)
    grupo = sortear_grupo(j)
    luta = combate.Luta([c], grupo, andar_num=j["andar"])
    painel = PainelEstrada(luta, j["user_id"], destino_mundo)
    e = luta.embed(
        titulo="Bandidos na estrada!",
        cor=COR_ESTRADA,
        rodape="A viagem para -- vença pra continuar.",
    )
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
    bandidos não são farm (ver decisoes.md § Step E), só obstáculo."""
    luta.encerrada = True
    c = luta.participantes[0]
    c.salvar_estado()
    _completar_viagem(user_id, destino_mundo)
    dados_lugar = mundo.LOCAIS_FORA[destino_mundo]
    e = luta.embed(
        titulo="Os bandidos recuam",
        cor=COR_ESTRADA,
        rodape=f"Vencido na rodada {luta.rodada}.",
    )
    e.add_field(name="Você chega", value=f"{dados_lugar['nome']} -- a estrada ficou livre dessa vez.", inline=False)
    return e


async def _finalizar_derrota_estrada(luta, user_id, destino_mundo):
    """Ladrão não mata -- nada de processar_morte, nada de penalidade da
    torre. A viagem se resolve sem morte: o jogador ainda chega, só mais
    pobre (commit 3 decide o que exatamente se perde)."""
    luta.encerrada = True
    c = luta.participantes[0]
    c.salvar_estado()
    _completar_viagem(user_id, destino_mundo)
    dados_lugar = mundo.LOCAIS_FORA[destino_mundo]
    e = luta.embed(
        titulo="Os bandidos levam o que querem",
        cor=combate.COR_DERROTA,
        rodape=f"Caído na rodada {luta.rodada}.",
    )
    e.add_field(
        name="Assaltado, mas vivo",
        value=f"Você chega em {dados_lugar['nome']} de qualquer jeito -- só que mais leve.",
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
