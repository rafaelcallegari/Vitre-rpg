# condicoes.py
# Condições de combate: estado por luta, com duração em rodadas e efeito por
# rodada. É o motor genérico — sangramento, confusão e os elementos (fogo,
# gelo, raio, divino, sombrio, ar) são só sabores que uma skill futura vai
# aplicar chamando aplicar() com os parâmetros certos. Nenhum nome de
# condição fica hardcoded aqui, porque nenhuma skill existe ainda pra
# decidir duração e potência de verdade.
#
# Vive dentro da Luta (combate.py) — não persiste no banco, não sobrevive ao
# fim do combate. efeitos.py é outra coisa: buffs de poção que atravessam
# várias lutas. Isso aqui é por rodada, dentro de uma luta só.
#
# Cada condição é um dict:
#   alvo: "chefe" ou o user_id do combatente que carrega a condição
#   tipo: "dano_por_rodada" | "cura_por_rodada" | "pula_turno" | "redireciona"
#       | "vulneravel" | "reduz_dano" | "bonus_critico" | "bloqueia_skill"
#       | "chance_erro" | "reduz_cura" | "reflete_dano"
#   nome, emoji: pra aparecer no log da luta
#   valor: dano/cura fixo (int) OU fração do HP máximo (float < 1) para os
#          tipos de dano/cura; o user_id do alvo forçado para "redireciona";
#          fração de dano a mais tomado para "vulneravel"; fração de dano a
#          menos tomado para "reduz_dano"; bônus aditivo de chance de crítico
#          para "bonus_critico"; ignorado em "bloqueia_skill"; chance de
#          errar o próprio golpe em "chance_erro"; fração de cura a menos
#          recebida em "reduz_cura"; fração do dano recebido devolvida ao
#          CHEFE em "reflete_dano" (Represália, paladino, Step 2d)
#   duracao: rodadas restantes
#   origem: user_id de quem aplicou (opcional — usado pra drenar vida de volta)
#   drena: fração do dano devolvida à origem como cura, só em dano_por_rodada
#
# "vulneravel", "reduz_dano", "bonus_critico", "bloqueia_skill",
# "chance_erro" e "reduz_cura" não têm tick próprio — quem resolve a ação em
# combate.py consulta a função correspondente (multiplicador_dano_causado,
# reducao_dano_recebido, bonus_critico, pode_lancar_habilidade,
# chance_de_erro, reducao_cura_recebida) na hora de agir. As primeiras três
# nasceram nas skills de jogador (pacote das habilidades); as últimas três
# nasceram das condições que o CHEFE aplica no jogador, andares 11+
# (Choque, Vendaval, Ferida Sombria — ver decisoes.md).


def aplicar(luta, alvo, tipo, nome, emoji, duracao, valor, origem=None, drena=None, bonus_cura_ignorado=0.0):
    """Registra uma condição nova e já loga a aplicação no texto da luta.

    `bonus_cura_ignorado` é metadado puro (igual `drena`) -- não sabe nada
    sobre passivas nem ascensão, só carrega um número que `_tick_cura`
    consulta na hora de curar (ver Bênção, Step 2d). Fica em 0.0 (nenhum
    efeito) pra toda condição que não seja cura_por_rodada de um clérigo
    com essa passiva -- condicoes.py continua sem saber o que é um
    clérigo, quem chama que decide o valor."""
    luta.condicoes.append({
        "alvo": alvo, "tipo": tipo, "nome": nome, "emoji": emoji,
        "valor": valor, "duracao": duracao, "origem": origem, "drena": drena,
        "bonus_cura_ignorado": bonus_cura_ignorado,
    })
    luta.registrar(f"{emoji} **{nome}** aplicado em {_nome_alvo(luta, alvo)} — {duracao} rodada(s).")


def pode_agir(luta, alvo):
    """False se o alvo estiver com pula_turno ativo nesta rodada."""
    return not any(
        c["tipo"] == "pula_turno" and c["alvo"] == alvo and c["duracao"] > 0
        for c in luta.condicoes
    )


def alvo_forcado(luta):
    """user_id que o chefe é obrigado a atacar, ou None se ninguém provocou."""
    for c in luta.condicoes:
        if c["tipo"] == "redireciona" and c["alvo"] == "chefe" and c["duracao"] > 0:
            combatente = luta.por_id(c["valor"])
            if combatente and combatente.ativo:
                return combatente
    return None


def multiplicador_dano_causado(luta, alvo):
    """1.0 + soma das condições 'vulneravel' ativas nesse alvo — o alvo
    recebe mais dano de quem o ataca (ex.: Ruptura no chefe)."""
    return 1.0 + sum(
        c["valor"] for c in luta.condicoes if c["tipo"] == "vulneravel" and c["alvo"] == alvo
    )


def reducao_dano_recebido(luta, alvo):
    """Fração do dano a menos que o alvo toma, somada e com teto de 50% —
    nenhuma combinação de buffs deixa o alvo quase invulnerável."""
    return min(0.5, sum(
        c["valor"] for c in luta.condicoes if c["tipo"] == "reduz_dano" and c["alvo"] == alvo
    ))


def bonus_critico(luta, alvo):
    """Bônus aditivo de chance de crítico do alvo (ex.: Ponto Cego)."""
    return sum(
        c["valor"] for c in luta.condicoes if c["tipo"] == "bonus_critico" and c["alvo"] == alvo
    )


def pode_lancar_habilidade(luta, alvo):
    """False se o alvo estiver sob Choque (ou qualquer 'bloqueia_skill').
    Consultada no clique do botão Habilidade — antes do tick da própria
    rodada, ao contrário das outras consultas abaixo (por isso a duração
    de Choque não precisa do "+1" que pula_turno/vulneravel precisam)."""
    return not any(
        c["tipo"] == "bloqueia_skill" and c["alvo"] == alvo and c["duracao"] > 0
        for c in luta.condicoes
    )


def chance_de_erro(luta, alvo):
    """Soma das chances do alvo simplesmente errar o próprio golpe nesta
    rodada (Vendaval) — teto de 60%, pra golpe nunca virar impossível."""
    return min(0.6, sum(
        c["valor"] for c in luta.condicoes
        if c["tipo"] == "chance_erro" and c["alvo"] == alvo and c["duracao"] > 0
    ))


def reducao_cura_recebida(luta, alvo):
    """Fração da cura a menos que o alvo recebe (Ferida Sombria), com teto
    de 80% — nunca deixa a cura completamente inútil. Filtra por
    duracao > 0 de propósito: diferente das outras consultas, esta também
    é chamada de dentro do próprio tick() (quando uma cura_por_rodada
    resolve), então uma Ferida Sombria expirando na mesma rodada não pode
    contar."""
    return min(0.8, sum(
        c["valor"] for c in luta.condicoes
        if c["tipo"] == "reduz_cura" and c["alvo"] == alvo and c["duracao"] > 0
    ))


def fracao_reflexao(luta, alvo):
    """Represália (paladino): soma das frações de dano que `alvo` devolve
    ao CHEFE quando toma dano nesta rodada -- teto de 1.0 (nunca devolve
    mais do que recebeu). Filtra por `duracao > 0` igual reducao_cura_
    recebida -- consultada no MOMENTO em que o dano chega no combatente,
    nunca dentro do próprio tick() (dano_por_rodada não reflete: só dano
    direto do chefe, ver combate._aplicar_dano_do_chefe)."""
    return min(1.0, sum(
        c["valor"] for c in luta.condicoes
        if c["tipo"] == "reflete_dano" and c["alvo"] == alvo and c["duracao"] > 0
    ))


def tick(luta):
    """Roda uma vez no início de cada rodada: aplica dano/cura contínuos,
    derruba a duração de tudo em 1 e descarta o que expirou."""
    ainda_ativas = []
    for c in luta.condicoes:
        if c["tipo"] in ("dano_por_rodada", "cura_por_rodada"):
            _aplicar_efeito_rodada(luta, c)
        c["duracao"] -= 1
        if c["duracao"] > 0:
            ainda_ativas.append(c)
    luta.condicoes = ainda_ativas


# ------------------------------------------------------------------ interno

def _nome_alvo(luta, alvo):
    if alvo == "chefe":
        return luta.chefe["nome"]
    combatente = luta.por_id(alvo)
    return combatente.nome if combatente else "alguém que já saiu"


def _valor_absoluto(valor, hp_max):
    """valor < 1 é fração do HP máximo; valor >= 1 é quantidade fixa."""
    return max(1, int(hp_max * valor)) if 0 < valor < 1 else int(valor)


def _aplicar_efeito_rodada(luta, cond):
    if cond["tipo"] == "dano_por_rodada":
        _tick_dano(luta, cond)
    elif cond["tipo"] == "cura_por_rodada":
        _tick_cura(luta, cond)


def _tick_dano(luta, cond):
    if cond["alvo"] == "chefe":
        dano = _valor_absoluto(cond["valor"], luta.hp_chefe_max)
        luta.hp_chefe -= dano
        luta.registrar(f"{cond['emoji']} {luta.chefe['nome']} sofre **{dano}** de {cond['nome']}.")
    else:
        c = luta.por_id(cond["alvo"])
        if not c or not c.ativo:
            return
        dano = _valor_absoluto(cond["valor"], c.s["hp_max"])
        c.hp -= dano
        luta.registrar(f"{cond['emoji']} {c.nome} sofre **{dano}** de {cond['nome']}.")
        if c.hp <= 0:
            c.caiu = True
    if cond.get("origem") and cond.get("drena"):
        curador = luta.por_id(cond["origem"])
        if curador and curador.ativo:
            # piso de 1, por consistência com o dano acima (_valor_absoluto já
            # garante isso pro `dano`) -- na escala de HP de chefe que a
            # Sanguessuga usa hoje isso nunca morde, é só a mesma regra dos
            # dois lados da mesma condição. Ver decisoes.md § Buffar o
            # sombrio «Sanguessuga».
            cura = max(1, int(dano * cond["drena"]))
            curador.hp = min(curador.s["hp_max"], curador.hp + cura)


def _tick_cura(luta, cond):
    if cond["alvo"] == "chefe":
        return  # chefe não cura por condição — guarda por segurança, não deveria acontecer
    c = luta.por_id(cond["alvo"])
    if not c or not c.ativo:
        return
    cura = _valor_absoluto(cond["valor"], c.s["hp_max"])
    # Bênção (clérigo, Step 2d): reducao_cura_recebida continua com o
    # mesmo teto de 0.8 -- só o valor CONSULTADO aqui, pra esta cura
    # específica, sai reduzido pelo bônus que a condição carrega (0.0 pra
    # toda cura que não veio de um clérigo com a passiva). Nunca negativo.
    reducao = max(0.0, reducao_cura_recebida(luta, cond["alvo"]) - cond.get("bonus_cura_ignorado", 0.0))
    cura = int(cura * (1 - reducao))
    antes = c.hp
    c.hp = min(c.s["hp_max"], c.hp + cura)
    luta.registrar(f"{cond['emoji']} {c.nome} recupera **{c.hp - antes}** de {cond['nome']}.")
