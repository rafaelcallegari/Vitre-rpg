# espelhos.py
# Step 3, commit 3: os quatro espelhos. Cada classe encontra sempre o
# próprio espelho -- game_data.DUNGEON_ESPELHOS (classe -> chave) e
# DUNGEON_ESPELHOS_DADOS (chave -> hp/atk/def/kit). Nenhuma passiva: o
# Arauto NÃO se levanta, a Graça Divina dele é só a Chama Divina (a luta
# é SEMPRE solo -- nunca o Reerguer). Sem fase 2, sem elemento de arma.
#
# ESCOLHA DE DESIGN (o ponto mais perigoso do step, ver decisoes.md):
# os `_efeito_*` de combate.py foram escritos pra JOGADOR atacando CHEFE
# -- `luta.hp_chefe -= dano`, condição em `alvo=jogador.id` ou
# `alvo="chefe"` dependendo de quem é o alvo, sempre nessa direção fixa.
# Generalizar essas funções pra aceitar as duas direções mexeria em
# código que a suíte inteira (750+ testes) cobre. Em vez disso, este
# arquivo tem versões PRÓPRIAS, na direção contrária -- duplicação
# deliberada, não preguiça: mais superfície de código, mas ZERO risco
# pro motor que já existe. Ver decisoes.md § Step 3 pro porquê por
# extenso.
import random

import atributos as at
import chefe_ia
import condicoes
import game_data

CHANCE_PANCADA_ESPELHO = 0.25   # fixa -- o espelho não tem "força" pra escalar como o jogador escala


def _rolar_dano_espelho(luta, multiplicador, critico_extra=0.0):
    """Mesma forma de `combate._rolar_dano_habilidade` (variação ±15%,
    crítico), mas a partir do `atk` do PRÓPRIO espelho (`luta.chefe`),
    não de um atributo de jogador -- o espelho não tem ficha de
    personagem, só hp/atk/def, como qualquer chefe. `condicoes.
    bonus_critico(luta, "chefe")` -- generica, já existia -- é quem faz
    o Ponto Cego (auto-buff) valer nos golpes seguintes do espelho."""
    bruto = luta.chefe["atk"] * multiplicador * random.uniform(0.85, 1.15)
    chance_critico = at.CRITICO_BASE + critico_extra + condicoes.bonus_critico(luta, "chefe")
    if random.random() < chance_critico:
        bruto *= at.MULTIPLICADOR_CRITICO
    return bruto


MULTIPLICADOR_ATAQUE_LEVE = 1.0   # fallback dos kits de utilidade (ver decisoes.md, calibragem do commit 4)


def _ataque_leve(luta, jogador):
    """Golpe "de reserva" -- usado quando a rotina cai numa habilidade
    de UTILIDADE que já está ativa/gasta (Ruptura repetida, Ponto Cego
    repetido, Voto de Ferro depois do único uso). Achado calibrando o
    commit 4: sem NENHUM fallback, o espelho ficava rodadas inteiras
    sem ameaçar nada sempre que "pressionar"/"reduzir_cura" repetia;
    com o fallback na FORÇA TOTAL do kit (2.0x, às vezes ignorando
    defesa), o espelho virava ofensiva constante em toda rodada, sem
    nenhuma folga -- este golpe fica no meio: sempre causa dano, nunca
    o melhor golpe do kit."""
    dano_bruto = _rolar_dano_espelho(luta, MULTIPLICADOR_ATAQUE_LEVE)
    return _aplicar_dano_no_jogador(luta, jogador, at.aplicar_defesa(dano_bruto, jogador.s["def"]))


def _aplicar_dano_no_jogador(luta, jogador, dano):
    """`multiplicador_dano_causado(luta, jogador.id)` é a mesma consulta
    genérica de `condicoes.py` que já existia -- soma de "vulneravel"
    ativas nesse alvo. Sem passar por aqui, a Ruptura revertida (que
    aplica vulnerável NO JOGADOR) seria puro teatro: a condição existiria
    mas nenhum dano a consultaria. Achado durante a medição do commit 4
    -- corrigido antes de calibrar em cima de um número errado."""
    dano = int(dano * condicoes.multiplicador_dano_causado(luta, jogador.id))
    dano = max(1, dano)
    jogador.hp -= dano
    if jogador.hp <= 0:
        jogador.caiu = True
    return dano


def _fracao_hp_chefe(luta):
    return max(0, luta.hp_chefe) / luta.hp_chefe_max


# ------------------------------------------------------------ mago (Espectro do Lich)

def _efeito_espelho_dardo_arcano(luta, jogador):
    """Ignora a defesa do jogador -- mesma característica do original."""
    dado = game_data.HABILIDADES["dardo_arcano"]
    dano = _aplicar_dano_no_jogador(luta, jogador, _rolar_dano_espelho(luta, 2.0))
    luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} crava **{dado['nome']}** em {jogador.nome} — {dano} de dano, ignorando a defesa.")


def _efeito_espelho_ruptura(luta, jogador):
    """Puro debuff, sem dano -- igual o original. `vulneravel` no
    jogador em vez de "chefe". Achado calibrando o commit 4: `condicoes.
    aplicar` nunca funde com uma condição já ativa -- se a rotina cair
    em "pressionar" de novo (comum quando o jogador não gasta muito
    recurso) ANTES da Ruptura anterior expirar, o dano ficaria
    empilhando "vulnerável" sem teto, uma escalada que não existe pro
    jogador fazendo a mesma coisa contra um chefe de verdade. Enquanto
    já tiver uma ativa, cai pra `_ataque_leve` (golpe de reserva, não
    Dardo Arcano em força total) em vez de empilhar mais."""
    dado = game_data.HABILIDADES["ruptura"]
    ja_ativa = any(c["tipo"] == "vulneravel" and c["alvo"] == jogador.id and c["duracao"] > 0 for c in luta.condicoes)
    if ja_ativa:
        dano = _ataque_leve(luta, jogador)
        luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} golpeia {jogador.nome} — {dano} de dano.")
        return
    condicoes.aplicar(
        luta, jogador.id, "vulneravel", dado["nome"], dado["emoji"],
        duracao=4, valor=0.20, origem="chefe",
    )
    luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} conjura **{dado['nome']}** — {jogador.nome} fica mais vulnerável.")


def _efeito_espelho_prisao_de_cristal(luta, jogador):
    """Dano + Travamento -- travamento aqui é `pula_turno` (bloqueia o
    ataque normal) E `bloqueia_skill` (bloqueia o botão Habilidade,
    condicoes.pode_lancar_habilidade já é consultado ali de propósito
    desde a Choque, andares 11+) juntos -- contra um CHEFE, pula_turno
    sozinho já bastava (chefe não lança skill própria antes deste
    step); contra um JOGADOR, ele tem os dois tipos de ação, então
    travar de verdade precisa travar os dois."""
    dado = game_data.HABILIDADES["prisao_de_cristal"]
    dano_bruto = _rolar_dano_espelho(luta, 2.0)
    dano = _aplicar_dano_no_jogador(luta, jogador, at.aplicar_defesa(dano_bruto, jogador.s["def"]))
    condicoes.aplicar(luta, jogador.id, "pula_turno", dado["nome"], dado["emoji"], duracao=2, valor=0, origem="chefe")
    condicoes.aplicar(luta, jogador.id, "bloqueia_skill", dado["nome"], dado["emoji"], duracao=2, valor=0, origem="chefe")
    luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} conjura **{dado['nome']}** — {dano} de dano e {jogador.nome} trava.")


ROTINA_MAGO = {
    "padrao": "dardo_arcano",
    "pressionar": "ruptura",
    "reduzir_cura": "ruptura",
    "priorizar_carregado": "prisao_de_cristal",
}


# ------------------------------------------------------------ guerreiro (Campeão da Arena)

def _efeito_espelho_golpe_aberto(luta, jogador):
    """Dano + sangramento empilhável (até 3), igual o original -- só que
    o valor do sangramento é fração do HP MÁXIMO DO JOGADOR agora, não
    do chefe."""
    dado = game_data.HABILIDADES["golpe_aberto"]
    dano_bruto = _rolar_dano_espelho(luta, 1.3)
    dano = _aplicar_dano_no_jogador(luta, jogador, at.aplicar_defesa(dano_bruto, jogador.s["def"]))
    luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} abre **{dado['nome']}** em {jogador.nome} — {dano} de dano.")
    stacks = [
        cond for cond in luta.condicoes
        if cond["tipo"] == "dano_por_rodada" and cond["nome"] == "Sangramento" and cond["alvo"] == jogador.id
    ]
    if len(stacks) >= 3:
        stacks[0]["duracao"] = 3
        luta.registrar(f"🩸 Sangramento renovado ({len(stacks)}/3 pilhas).")
    else:
        condicoes.aplicar(luta, jogador.id, "dano_por_rodada", "Sangramento", "🩸", duracao=3, valor=0.03, origem="chefe")


def _efeito_espelho_pancada_atordoante(luta, jogador):
    """Chance FIXA (o espelho não escala com "força" de personagem) --
    mesmo teto do original (0.25). Travamento completo, mesmo motivo de
    Prisão de Cristal: pula_turno + bloqueia_skill juntos.

    DIFERENÇA DELIBERADA do original: a versão do jogador nunca causa
    dano (é pura utilidade -- teto de chance, sem consolação). Achado
    calibrando o commit 4: um golpe que SÓ tenta atordoar, sem nunca
    causar dano, faz o Campeão da Arena passar rodadas inteiras sem
    ameaçar nada sempre que a rotina cai em "pressionar"/"reduzir_cura"
    (comum quando o jogador não gasta muito recurso -- ver chefe_ia.
    segurando_recurso) -- na prática, o mesmo "chefe que não ataca" que
    a guarda de Voto de Ferro corrigiu. Aqui a golpe SEMPRE causa dano
    (o golpe de reserva, `_ataque_leve` -- não a força total de Golpe
    Aberto, senão guerreiro ficaria mais pesado que os outros três kits,
    que reduziram o fallback pelo mesmo motivo) e ADICIONALMENTE tenta
    atordoar."""
    dado = game_data.HABILIDADES["pancada_atordoante"]
    dano = _ataque_leve(luta, jogador)
    if random.random() < CHANCE_PANCADA_ESPELHO:
        condicoes.aplicar(luta, jogador.id, "pula_turno", dado["nome"], dado["emoji"], duracao=2, valor=0, origem="chefe")
        condicoes.aplicar(luta, jogador.id, "bloqueia_skill", dado["nome"], dado["emoji"], duracao=2, valor=0, origem="chefe")
        luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} atordoa {jogador.nome} — {dano} de dano!")
    else:
        luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} acerta **{dado['nome']}** — {dano} de dano, mas não atordoa.")


def _efeito_espelho_golpe_oportunista(luta, jogador):
    """Escala com o quanto O PRÓPRIO ESPELHO já perdeu de HP -- mesmo
    espírito do original (mercenário escala com o quanto ELE MESMO já
    perdeu), só que "ele mesmo" agora é `luta.hp_chefe`."""
    dado = game_data.HABILIDADES["golpe_oportunista"]
    fracao_perdida = 1 - _fracao_hp_chefe(luta)
    multiplicador = 2.0 + 1.0 * fracao_perdida
    dano_bruto = _rolar_dano_espelho(luta, multiplicador)
    dano = _aplicar_dano_no_jogador(luta, jogador, at.aplicar_defesa(dano_bruto, jogador.s["def"]))
    luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} crava **{dado['nome']}** em {jogador.nome} — {dano} de dano.")


ROTINA_GUERREIRO = {
    "padrao": "golpe_aberto",
    "pressionar": "pancada_atordoante",
    "reduzir_cura": "pancada_atordoante",
    "priorizar_carregado": "golpe_oportunista",
}


# ------------------------------------------------------------ ladino (Assassino do Vento)

def _efeito_espelho_corte_rapido(luta, jogador):
    dado = game_data.HABILIDADES["corte_rapido"]
    golpes = []
    total = 0
    for _ in range(2):
        dano_bruto = _rolar_dano_espelho(luta, 1.35, critico_extra=0.10)
        dano = _aplicar_dano_no_jogador(luta, jogador, at.aplicar_defesa(dano_bruto, jogador.s["def"]))
        total += dano
        golpes.append(str(dano))
    luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} desfere **{dado['nome']}** em {jogador.nome} — {' + '.join(golpes)} = {total} de dano.")


def _efeito_espelho_ponto_cego(luta, jogador):
    """Auto-buff, sem dano -- `alvo="chefe"`, consultado por
    `_rolar_dano_espelho` (bonus_critico) em qualquer golpe seguinte.
    Mesma guarda de Ruptura: enquanto já tiver um buff ativo, cai pra
    `_ataque_leve` (golpe de reserva) em vez de empilhar mais bônus de
    crítico sem teto."""
    dado = game_data.HABILIDADES["ponto_cego"]
    ja_ativo = any(c["tipo"] == "bonus_critico" and c["alvo"] == "chefe" and c["duracao"] > 0 for c in luta.condicoes)
    if ja_ativo:
        dano = _ataque_leve(luta, jogador)
        luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} golpeia {jogador.nome} — {dano} de dano.")
        return
    condicoes.aplicar(luta, "chefe", "bonus_critico", dado["nome"], dado["emoji"], duracao=4, valor=0.45, origem="chefe")
    luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} conjura **{dado['nome']}** — os próximos golpes vêm mais certeiros.")


def _efeito_espelho_golpe_fatal(luta, jogador):
    """Escala com o quanto O JOGADOR já perdeu de HP -- execução, igual
    o original (que escala com o quanto o CHEFE já perdeu)."""
    dado = game_data.HABILIDADES["golpe_fatal"]
    fracao_perdida = 1 - max(0, jogador.hp) / jogador.s["hp_max"]
    multiplicador = 1.2 + 2.0 * fracao_perdida
    dano_bruto = _rolar_dano_espelho(luta, multiplicador)
    dano = _aplicar_dano_no_jogador(luta, jogador, at.aplicar_defesa(dano_bruto, jogador.s["def"]))
    luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} crava **{dado['nome']}** em {jogador.nome} — {dano} de dano.")


ROTINA_LADINO = {
    "padrao": "corte_rapido",
    "pressionar": "ponto_cego",
    "reduzir_cura": "ponto_cego",
    "priorizar_carregado": "golpe_fatal",
}


# ------------------------------------------------------------ orador (Arauto dos Deuses)

def _efeito_espelho_palavra_de_alento(luta, jogador):
    """SIMPLIFICAÇÃO DELIBERADA: o original regenera ao longo de 2
    rodadas (`cura_por_rodada`) -- mas `condicoes._tick_cura` recusa
    explicitamente curar `alvo == "chefe"` ("chefe não cura por
    condição", ver condicoes.py). Generalizar essa guarda pra abrir
    exceção pro chefe é o tipo de mudança "mexe em código que a suíte
    inteira cobre" que este cartão pede cautela extra -- optei por NÃO
    mexer nela. Em vez de uma regeneração por condição, o espelho cura
    o equivalente a 2 rodadas de uma vez, instantâneo. Ver decisoes.md."""
    dado = game_data.HABILIDADES["palavra_de_alento"]
    cura = int(2 * 0.08 * luta.hp_chefe_max)
    luta.hp_chefe = min(luta.hp_chefe_max, luta.hp_chefe + cura)
    luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} conjura **{dado['nome']}** — recupera {cura} de HP.")


def _efeito_espelho_voto_de_ferro(luta, jogador):
    """SIMPLIFICAÇÃO DELIBERADA: o original reduz o dano recebido por 2
    rodadas via `reduz_dano` -- mas NADA no caminho de dano do
    JOGADOR->CHEFE consulta `reducao_dano_recebido(luta, "chefe")` hoje
    (esse caminho nunca precisou, porque chefe nunca teve defesa
    temporária antes deste cartão) -- ligar isso exigiria tocar em ~13
    pontos que hoje fazem `luta.hp_chefe -= dano` direto, espalhados
    pelos efeitos de skill. Em vez disso, o Voto de Ferro do espelho é
    um reforço PERMANENTE de defesa (`luta.chefe["def"]`), não
    cronometrado em rodadas -- a defesa já é consultada por todo mundo
    (`_defesa_efetiva`), então isto funciona sem tocar em mais nada. Só
    aplica uma vez (`_voto_de_ferro_usado`). Achado calibrando o commit
    4: um no-op de verdade aqui (só logar "já jurou" e não fazer mais
    nada) deixava o Arauto SEM NENHUM ataque sempre que a rotina caísse
    em "pressionar"/"reduzir_cura" de novo -- que é o caminho mais
    comum quando o jogador não gasta muito recurso (ver chefe_ia.
    segurando_recurso). Um "chefe que só reforça a guarda e nunca
    ataca" não é o que o cartão pede ("perdida com frequência") -- a
    segunda vez em diante, em vez de não-fazer-nada, ele ataca com
    Chama Divina (a única fonte de dano do próprio kit)."""
    dado = game_data.HABILIDADES["voto_de_ferro"]
    if luta.chefe.get("_voto_de_ferro_usado"):
        _efeito_espelho_chama_divina(luta, jogador)
        return
    luta.chefe["_voto_de_ferro_usado"] = True
    luta.chefe["def"] = int(luta.chefe["def"] * 1.5)
    luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} conjura **{dado['nome']}** — a guarda dele fica mais dura.")


def _efeito_espelho_chama_divina(luta, jogador):
    """Graça Divina do espelho é SEMPRE Chama Divina -- a luta é sempre
    solo (um jogador só), nunca o Reerguer (não existe aliado caído pra
    levantar; nem faria sentido, o Arauto não se levanta). Dano puro,
    com defesa -- mesma base da versão do jogador."""
    dado = game_data.HABILIDADES["graca_divina"]
    dano_bruto = _rolar_dano_espelho(luta, 2.0)
    dano = _aplicar_dano_no_jogador(luta, jogador, at.aplicar_defesa(dano_bruto, jogador.s["def"]))
    luta.registrar(f"{dado['emoji']} {luta.chefe['nome']} conjura **Chama Divina** em {jogador.nome} — {dano} de dano.")


ROTINA_ORADOR = {
    "padrao": "graca_divina",
    "pressionar": "voto_de_ferro",
    "reduzir_cura": "voto_de_ferro",
    "priorizar_carregado": "graca_divina",
}


# ------------------------------------------------------------ motor comum

EFEITOS_ESPELHO = {
    "dardo_arcano": _efeito_espelho_dardo_arcano,
    "ruptura": _efeito_espelho_ruptura,
    "prisao_de_cristal": _efeito_espelho_prisao_de_cristal,
    "golpe_aberto": _efeito_espelho_golpe_aberto,
    "pancada_atordoante": _efeito_espelho_pancada_atordoante,
    "golpe_oportunista": _efeito_espelho_golpe_oportunista,
    "corte_rapido": _efeito_espelho_corte_rapido,
    "ponto_cego": _efeito_espelho_ponto_cego,
    "golpe_fatal": _efeito_espelho_golpe_fatal,
    "palavra_de_alento": _efeito_espelho_palavra_de_alento,
    "voto_de_ferro": _efeito_espelho_voto_de_ferro,
    "graca_divina": _efeito_espelho_chama_divina,
}

ROTINA_POR_CLASSE = {
    "mago": ROTINA_MAGO,
    "guerreiro": ROTINA_GUERREIRO,
    "ladino": ROTINA_LADINO,
    "orador": ROTINA_ORADOR,
}


def escolher_habilidade(luta, jogador_id):
    """Devolve (chave_habilidade, motivo) -- motivo é o texto de
    `chefe_ia.decidir_acao` (pode ser None, decisão "padrao")."""
    decisao = chefe_ia.decidir_acao(luta, jogador_id)
    rotina = ROTINA_POR_CLASSE[luta.chefe["classe"]]
    return rotina[decisao["acao"]], decisao["motivo"]


def turno_do_espelho(luta):
    """Chamado de combate.Luta.turno_do_chefe quando `luta.chefe.get(
    "e_espelho")` é verdadeiro -- a luta do espelho é SEMPRE solo (um
    jogador só), então o alvo é sempre `luta.participantes[0]`, nunca
    escolhido entre vários."""
    jogador = luta.participantes[0]
    if not jogador.ativo:
        return
    chave_habilidade, motivo = escolher_habilidade(luta, jogador.id)
    if motivo:
        luta.registrar(f"👁️ {luta.chefe['nome']} {motivo}")
    EFEITOS_ESPELHO[chave_habilidade](luta, jogador)
