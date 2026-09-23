# principades.py
# Step F, commit 3: Principades. Cidade grande -- o comércio de fora da torre
# de verdade (Costa Verde, commit 2, não vende nada de propósito -- é lore).
# Módulo novo, mesma convenção do vilarejo.py (Step C) e do estrada.py (Step
# E): o conceito é grande o bastante pra merecer o próprio arquivo, sem tocar
# em game_data.py.
#
# Duas mecânicas, as duas ligam o mundo de fora à torre em vez de competir
# com ela:
# - Compra espólio ACIMA do valor de face -- dá motivo real pra viagem, liga
#   a dungeon do andar 9 (onde o espólio cai) ao mundo lá fora.
# - Vende materiais de profissão -- destrava quem quer craftar sem farmar.
#
# NUNCA vende arma, armadura nem encantamento -- isso é da torre (Selen e as
# 24 elementais no andar 9, o ferreiro de cada andar ímpar, o encantador de
# cada andar ímpar). Uma loja de cidade que vendesse equipamento esvaziaria
# exatamente o conteúdo que o jogador acabou de terminar (o cartão foi
# explícito). Este módulo só sabe vender `tipo == "material"` -- nunca
# precisou de uma lista de exclusão pra arma/armadura/encantamento, porque
# `materiais_a_venda()` nunca olha esses tipos pra começo de conversa.
from game_data import ITENS

# ---------------- espólio acima do valor de face ----------------
# Fora daqui, espólio já vende a preço cheio em qualquer lugar (`bot.vender`,
# `unitario = dado["preco"]` pra tipo "espolio" -- é loot puro, não craft,
# então não tinha desconto de revenda pra começo de conversa). Aqui, um
# bônus por cima. Não desequilibra nada rio acima: o espólio não é
# ingrediente de receita nenhuma, só "moeda de troca" (ver decisoes.md §
# Dungeon -- pool e armadilha) -- um bônus na revenda dele é só isso, mais
# moedas por viagem, não mais poder.
#
# 0.25 é ponto de partida pra playtest, mesma régua das outras constantes
# nomeadas do pacote (CHANCE_ENCONTRO_ESTRADA = 0.12, FRACAO_ROUBO_MOEDAS =
# 0.15) -- medir depois, não só chutar de vez.
BONUS_COMPRA_ESPOLIO = 0.25


def preco_compra_espolio(preco_face):
    return int(preco_face * (1 + BONUS_COMPRA_ESPOLIO))


# ---------------- materiais de profissão ----------------
# Multiplicador sobre o preço-base (o mesmo `ITENS[x]["preco"]` que `bot.
# vender` já paga em qualquer lugar) -- calibrado contra o tempo de farm
# equivalente, o cartão pediu medição, não chute:
#
# Tier "chão" (preço 12-800, monstro comum de qualquer andar 1-15): ~50% de
# chance por `rpg cacar` (cooldown de 60s, ver bot.COOLDOWN_CACAR) -- ~2
# caçadas (~2 min) por unidade em média, e cada caçada JÁ rende moedas/XP
# por conta própria, doa ou não o material (não é tempo perdido se não
# cair). No andar 11 (Grifo de Vidro -- 222 moedas/caçada, material "pluma
# etérea" a 480), 2 caçadas rendem ~444 moedas de brinde sozinho -- comprar
# 1 unidade a 8x (480*8 = 3840) fica ~8.6x mais caro que só o brinde, sem
# nem contar o tempo nem a garantia. No andar 1 (Javali -- 26 moedas/caçada,
# "presa de javali" a 12), a mesma conta (12*8 = 96 vs ~52 de brinde) já
# cobre quase 2x -- calibra mais apertado no chão baixo, que é onde a
# diferença importa menos (jogador cedo tem pouco craft de sobra pra fazer
# mesmo).
#
# Tier "chefe" (preço 1600-2800, material de arma elemental, andares
# 11-15): 100% de chance, mas só de CHEFE, cooldown de 900s = 15 min (ver
# bot.COOLDOWN_BOSS). Comprar a 8x (12800-22400 moedas) fica ordens de
# grandeza acima do que um chefe rende em moedas por kill -- de propósito:
# esse tier crafta arma elemental, é conteúdo de fim de jogo, tem que
# continuar raro pra quem farma, não virar prateleira.
MULTIPLICADOR_COMPRA_MATERIAL = 8


def materiais_a_venda():
    """Todo material comprável -- `loja` (default True) já filtra os de
    quest/fabricação especial (flor_do_andar_1, molde_do_manto e primos,
    todos `"loja": False`); `vendavel` (default True) filtra o fragmento
    do selo, que nem revenda tem. Preço já vem MULTIPLICADO -- quem chama
    (bot.comprar) usa `disponiveis[item]["preco"]` direto, sem saber nada
    sobre o multiplicador."""
    return {
        k: {**v, "preco": v["preco"] * MULTIPLICADOR_COMPRA_MATERIAL}
        for k, v in ITENS.items()
        if v["tipo"] == "material" and v.get("loja", True) and v.get("vendavel", True)
    }
