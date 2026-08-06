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
#   nome, emoji: pra aparecer no log da luta
#   valor: dano/cura fixo (int) OU fração do HP máximo (float < 1) para os
#          tipos de dano/cura; o user_id do alvo forçado para "redireciona"
#   duracao: rodadas restantes
#   origem: user_id de quem aplicou (opcional — usado pra drenar vida de volta)
#   drena: fração do dano devolvida à origem como cura, só em dano_por_rodada


def aplicar(luta, alvo, tipo, nome, emoji, duracao, valor, origem=None, drena=None):
    """Registra uma condição nova e já loga a aplicação no texto da luta."""
    luta.condicoes.append({
        "alvo": alvo, "tipo": tipo, "nome": nome, "emoji": emoji,
        "valor": valor, "duracao": duracao, "origem": origem, "drena": drena,
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
            cura = int(dano * cond["drena"])
            curador.hp = min(curador.s["hp_max"], curador.hp + cura)


def _tick_cura(luta, cond):
    if cond["alvo"] == "chefe":
        return  # chefe não cura por condição — guarda por segurança, não deveria acontecer
    c = luta.por_id(cond["alvo"])
    if not c or not c.ativo:
        return
    cura = _valor_absoluto(cond["valor"], c.s["hp_max"])
    antes = c.hp
    c.hp = min(c.s["hp_max"], c.hp + cura)
    luta.registrar(f"{cond['emoji']} {c.nome} recupera **{c.hp - antes}** de {cond['nome']}.")
