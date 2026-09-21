# vilarejo.py
# O alquimista e a taverna do vilarejo -- Step C, commit 2. Módulo novo, não
# emenda em npcs.py/bot.py: a mesma convenção do Step B (mundo.py nasceu
# sozinho) -- o conceito (o único lugar que vende elixir, a cerveja que
# atravessa pra qualquer luta) é grande o bastante pra merecer o próprio
# arquivo, sem tocar em game_data.py.
import database as db
from game_data import ITENS

# ---------------- o alquimista ----------------
# Os quatro elixires já existiam em game_data (`"loja": False` -- nenhum
# mercador da torre vende). O alquimista é a ÚNICA exceção comercial do
# vilarejo -- sem ferreiro, sem mercador de equipamento, sem encantador,
# isso fica pras cidades do step F. Preço e andar_min continuam intocados
# ("não rebalanceie nada aqui" -- o cartão foi explícito).
ELIXIRES = ("elixir_ervas", "elixir_vermelho", "nectar_torre", "elixir_mana")


def elixires_a_venda():
    return {k: ITENS[k] for k in ELIXIRES}


# ---------------- a cerveja ----------------
# Coragem líquida: mais dano causado, mais chance de errar -- sabor com
# mordida, não power-up (valores pequenos, de propósito). As duas condições
# (vulneravel no chefe / chance_erro no próprio jogador) já existem e já são
# testadas em condicoes.py; a cerveja só empresta elas.
PRECO_CERVEJA = 150
BONUS_DANO_CERVEJA = 0.10          # fração extra de dano causado na próxima luta
CHANCE_ERRO_CERVEJA = 0.08         # chance de errar o próprio golpe (teto real: 0.6, condicoes.py)
DURACAO_CERVEJA_RODADAS = 999      # "a luta inteira" -- condicoes.py só entende rodadas, não "a luta toda"


def comprar_cerveja(user_id):
    db.atualizar_jogador(user_id, cerveja_pendente=1)


def consumir_cerveja_pendente(user_id):
    """(multiplicador_dano, chance_erro) da cerveja pendente -- (1.0, 0.0)
    se não tem nenhuma -- e limpa a flag de uma vez, pra não aplicar duas
    vezes. O estado precisa sobreviver do momento da compra até o início de
    QUALQUER luta (cacar/explorar/boss/party/dungeon), por isso é uma
    coluna em `jogadores` (migração 24), não uma condição de `Luta` -- a
    cerveja nasce fora de combate nenhum. Ver decisoes.md § Step C."""
    j = db.get_jogador(user_id)
    if not j or not j["cerveja_pendente"]:
        return 1.0, 0.0
    db.atualizar_jogador(user_id, cerveja_pendente=0)
    return 1.0 + BONUS_DANO_CERVEJA, CHANCE_ERRO_CERVEJA
