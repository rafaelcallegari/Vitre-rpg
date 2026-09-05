# chefe_ia.py
# Motor GERAL de decisão de chefe (Step 3, commit 1) -- espelha
# condicoes.py/passivas.py na forma: cada leitura é uma função pura
# `fn(luta, alvo_id) -> valor`, e a Luta carrega o próprio estado
# (`luta.historico_ia`, ver combate.Luta.__init__).
#
# Lê SÓ o que aconteceu NAQUELA luta -- nada persiste entre lutas, de
# propósito: num jogo de chat o jogador não vê o estado interno da IA,
# e um chefe que "adivinha" usando informação de fora daquela luta lê
# como injustiça, não como inteligência. Ver decisoes.md § Step 3.
#
# A decisão sai de REGRAS LEGÍVEIS, nunca peso aleatório -- cada regra
# de `decidir_acao` é uma condição determinística, checada em ordem de
# prioridade fixa; a primeira que bate vence. Telegrafar é requisito,
# não sabor: toda decisão diferente de "padrao" carrega um "motivo" --
# o texto que vai pro log da luta, pra o jogador entender O QUE o chefe
# notou, nunca só que ele "ficou mais difícil do nada".
#
# Os chefes da torre (andares 1-10) NÃO usam este motor nesta passada
# -- `Luta.turno_do_chefe` não importa nem chama nada daqui (ver
# tests/test_chefe_ia.py, teste que trava essa fronteira). O primeiro
# consumidor real são os espelhos (Step 3, commit 3) -- os chefes da
# torre herdam o motor depois, em cartão próprio.
LIMIAR_CURAS_PARA_REDUZIR_CURA = 2      # curou isso ou mais nesta luta -- vale aplicar reduz_cura nele
LIMIAR_FRACAO_RECURSO_SEGURANDO = 0.8   # ainda com isso ou mais do recurso -- vale pressionar antes que gaste
LIMIAR_FRACAO_HP_BAIXO = 0.35           # hp/hp_max nisso ou abaixo -- o carregado vale mais que o combo


def _registro(luta, jogador_id):
    """Cria o registro deste jogador na hora, se ainda não existir --
    `luta.historico_ia` nasce vazio em `Luta.__init__`, cada jogador só
    ganha uma entrada quando alguma leitura ou registro precisa dela."""
    return luta.historico_ia.setdefault(
        jogador_id, {"curas": 0, "habilidades": {}, "fracao_recurso": 1.0}
    )


# ------------------------------------------------------------ registro

def registrar_cura(luta, jogador_id):
    """Chamado quando esse jogador cura (a si ou a um aliado) nesta
    luta -- ataque normal nunca cura, então isto só soma em cima de uma
    skill/mortalha/poção de cura de verdade."""
    _registro(luta, jogador_id)["curas"] += 1


def registrar_habilidade(luta, jogador_id, chave):
    """Chamado quando esse jogador lança a skill `chave` -- conta
    quantas vezes cada uma foi usada nesta luta."""
    h = _registro(luta, jogador_id)
    h["habilidades"][chave] = h["habilidades"].get(chave, 0) + 1


def registrar_fracao_recurso(luta, jogador_id, fracao):
    """Fração do recurso (mana/fúria/energia) que o jogador tinha ANTES
    da última ação -- sobrescreve, não soma (é uma leitura do instante,
    não um contador acumulado)."""
    _registro(luta, jogador_id)["fracao_recurso"] = fracao


# ------------------------------------------------------------ leituras

def vezes_curou(luta, jogador_id):
    return _registro(luta, jogador_id)["curas"]


def curou_demais(luta, jogador_id):
    """Curou LIMIAR_CURAS_PARA_REDUZIR_CURA vezes ou mais -- vale
    aplicar reduz_cura nele (ver condicoes.py)."""
    return vezes_curou(luta, jogador_id) >= LIMIAR_CURAS_PARA_REDUZIR_CURA


def vezes_usou_habilidade(luta, jogador_id, chave):
    return _registro(luta, jogador_id)["habilidades"].get(chave, 0)


def segurando_recurso(luta, jogador_id):
    """Ainda com LIMIAR_FRACAO_RECURSO_SEGURANDO ou mais do recurso --
    ele não gastou (ou gastou pouco); vale pressionar antes que gaste."""
    return _registro(luta, jogador_id)["fracao_recurso"] >= LIMIAR_FRACAO_RECURSO_SEGURANDO


def fracao_hp(luta, jogador_id):
    c = luta.por_id(jogador_id)
    if not c or not c.ativo:
        return 0.0
    return max(0, c.hp) / c.s["hp_max"]


def com_pouco_hp(luta, jogador_id):
    return fracao_hp(luta, jogador_id) <= LIMIAR_FRACAO_HP_BAIXO


def condicoes_no_chefe(luta):
    """Condições ativas no chefe agora -- duração > 0, mesmo filtro que
    condicoes.py usa nas próprias consultas."""
    return [c for c in luta.condicoes if c["alvo"] == "chefe" and c["duracao"] > 0]


def condicoes_no_jogador(luta, jogador_id):
    return [c for c in luta.condicoes if c["alvo"] == jogador_id and c["duracao"] > 0]


# ------------------------------------------------------------ decisão

def decidir_acao(luta, jogador_id):
    """Ordem de prioridade FIXA -- a primeira regra que bate vence,
    nunca um peso sorteado entre as que bateram. Devolve {"acao",
    "motivo"}; "motivo" é sempre uma string quando "acao" != "padrao"
    (telegrafar é requisito) e sempre None quando é "padrao" (nada de
    especial pra contar)."""
    if com_pouco_hp(luta, jogador_id):
        return {
            "acao": "priorizar_carregado",
            "motivo": "viu você com pouco HP e prepara o golpe mais pesado.",
        }
    if curou_demais(luta, jogador_id):
        return {
            "acao": "reduzir_cura",
            "motivo": "viu você se curar demais e prepara a ferida.",
        }
    if segurando_recurso(luta, jogador_id):
        return {
            "acao": "pressionar",
            "motivo": "viu você guardando recurso e ataca antes que gaste.",
        }
    return {"acao": "padrao", "motivo": None}
