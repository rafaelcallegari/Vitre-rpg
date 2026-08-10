# pronomes.py
# Concordância de gênero pro pronome do jogador ('ele'/'ela'/'elu') -- função
# pura, sem banco nem discord. Resolve dois tipos de marcador:
#
# 1. concordar(texto, pronome): troca cada {opcao_ele_elu|opcao_ela} no
#    texto pela opção certa -- primeira opção pra 'ele' e 'elu' (concordância
#    resolve em DOIS, não em três: os dois terminam em "o"), segunda pra
#    'ela'. Pensado pra concordância de adjetivo dentro da própria palavra:
#    "cansad{o|a}", "{o|a} únic{o|a}". Marcador vazio antes da barra é
#    válido ("doutor{|a}" -> "doutor"/"doutora"). Marcador malformado (sem
#    par de chaves, sem barra, chaves aninhadas) não casa com o regex e
#    volta sem mudança -- nunca lança exceção.
#
# 2. sujeito(pronome)/possessivo(pronome): pronome de terceira pessoa pra
#    texto que fala SOBRE o jogador pra outra pessoa (morte em party, log
#    de guilda, raide, embed de vitória) -- não COM ele. Aqui os três
#    pronomes são todos diferentes: ele/ela/elu, dele/dela/delu.
#
# Ver decisoes.md § pronomes do jogador.
import re

PRONOMES_VALIDOS = ("ele", "ela", "elu")
PADRAO = "elu"

_MARCADOR = re.compile(r"\{([^{}|]*)\|([^{}|]*)\}")

_POSSESSIVOS = {"ele": "dele", "ela": "dela", "elu": "delu"}


def concordar(texto, pronome):
    """'ele' e 'elu' pegam a primeira opção de cada marcador, 'ela' pega a
    segunda. Qualquer outra coisa (None, valor inválido) cai na primeira,
    mesmo espírito do default 'elu' da coluna no banco."""
    primeira = pronome != "ela"
    return _MARCADOR.sub(lambda m: m.group(1) if primeira else m.group(2), texto or "")


def sujeito(pronome):
    return pronome if pronome in PRONOMES_VALIDOS else PADRAO


def possessivo(pronome):
    return _POSSESSIVOS.get(pronome, _POSSESSIVOS[PADRAO])
