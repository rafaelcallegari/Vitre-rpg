# passivas.py
# Motor de passivas de ascensão -- espelha condicoes.py na forma: uma
# função de consulta por efeito, cada uma recebendo o jogador (dict) e
# devolvendo um número ou bool. combate.py e os pontos de recompensa
# (cacar/explorar/chefe, ver bot.py/combate.py) NUNCA fazem
# `if jogador["ascensao"] == "assassino"` espalhado -- só chamam estas
# funções, que sabem ler ASCENSOES/PASSIVAS (game_data.py) por baixo.
# Nenhum número mora aqui: quem carrega o valor de cada passiva é
# game_data.PASSIVAS. Ver decisoes.md § Step 2a.
#
# Ao contrário de condicoes.py (estado por LUTA, em luta.condicoes), isto
# aqui é estado PERSISTENTE do jogador (coluna jogadores.ascensao) -- não
# tem tick(), não expira, não nasce nem morre dentro de uma luta.
#
# Todas as consultas devolvem o valor NEUTRO (o que não muda nada) quando
# `ascensao` é NULL (jogador não ascendeu), não é mais uma chave válida em
# ASCENSOES (ramo que existiu e foi removido do jogo -- ver decisoes.md §
# Step 2a, Batedor de Carteira), ou é um ramo válido que ainda não tem essa
# passiva específica. Nunca `ASCENSOES[jogador["ascensao"]]` direto --
# sempre confirma que a chave existe antes de indexar.
import atributos as at
import database as db
from game_data import ASCENSOES, PASSIVAS


def _ramo(jogador):
    ascensao = (jogador or {}).get("ascensao")
    return ascensao if ascensao in ASCENSOES else None


def _efeitos_acessorios(jogador):
    """Chaves de efeito equipadas em anel/colar (Step D, commit 3) -- lê
    a instância DIRETO do banco (não passa por bot.com_instancia, que é
    de bot.py e resolveria bônus de atributo que não interessam aqui; só
    o campo `efeito` importa). Uma entrada por peça que tiver -- se
    anel E colar carregarem o MESMO efeito, a chave aparece duas vezes,
    de propósito (é o que faz as duas fontes somarem, ver
    _fontes_do_efeito)."""
    jogador = jogador or {}
    chaves = []
    for campo in ("anel_instancia_id", "colar_instancia_id"):
        instancia_id = jogador.get(campo)
        if not instancia_id:
            continue
        instancia = db.get_instancia(instancia_id)
        if instancia and instancia.get("efeito"):
            chaves.append(instancia["efeito"])
    return chaves


def _fontes_do_efeito(jogador, chave):
    """Quantas fontes concedem esta passiva a este jogador -- a ascensão
    conta no máximo 1 (um jogador só tem um ramo), cada acessório
    equipado com o efeito conta mais 1. Efeitos NUMÉRICOS somam por
    fonte (o cartão foi explícito: "um jogador com ascensão e dois
    acessórios pode somar três fontes" -- os tetos que já existem no
    motor, cura reduzida em 0.8/dano reduzido em 0.5, continuam valendo
    pro TOTAL, não por fonte). Efeitos booleanos (`_tem_passiva`) só
    perguntam se o total é > 0."""
    ramo = _ramo(jogador)
    contagem = 1 if (ramo is not None and chave in ASCENSOES[ramo]["passivas"]) else 0
    contagem += _efeitos_acessorios(jogador).count(chave)
    return contagem


def _tem_passiva(jogador, chave):
    return _fontes_do_efeito(jogador, chave) > 0


def critico_garantido(jogador, rodada):
    """Sangue Frio (assassino): o primeiro golpe da luta (rodada 1) é
    crítico garantido. Só isso -- combate.py ainda precisa garantir que não
    dispara de novo pra quem já usou o golpe garantido nesta luta (ex.: o
    segundo hit de Corte Rápido, no mesmo clique), e isso é estado por
    COMBATENTE, não cabe numa consulta stateless como esta."""
    return rodada == 1 and _tem_passiva(jogador, "sangue_frio")


def multiplicador_critico(jogador):
    """Fator extra sobre at.MULTIPLICADOR_CRITICO quando o golpe critica --
    1.0 = nenhuma passiva mexe nisso. Olho de Águia (arqueiro) soma um
    bônus fixo ao multiplicador base (PASSIVAS["olho_de_aguia"]["valor"]),
    reexpresso aqui como razão pra caber num motor sempre multiplicativo --
    é recalculado a cada chamada, então continua somando exatamente esse
    bônus mesmo se at.MULTIPLICADOR_CRITICO for rebalanceado depois."""
    if _tem_passiva(jogador, "olho_de_aguia"):
        bonus = PASSIVAS["olho_de_aguia"]["valor"]
        return (at.MULTIPLICADOR_CRITICO + bonus) / at.MULTIPLICADOR_CRITICO
    return 1.0


def bonus_moedas(jogador):
    """Fração ADICIONAL de moedas -- 0.0 = nenhuma passiva mexe nisso."""
    if _tem_passiva(jogador, "instinto_ladino"):
        return PASSIVAS["instinto_ladino"]["valor_moedas"]
    return 0.0


def bonus_material(jogador):
    """Fração ADICIONAL de CHANCE de material por item -- 0.0 = nenhuma
    passiva mexe nisso. Mexe na chance, não na quantidade -- ver
    decisoes.md § Step 2a (chance, não quantidade)."""
    if _tem_passiva(jogador, "instinto_ladino"):
        return PASSIVAS["instinto_ladino"]["valor_material"]
    return 0.0


def bonus_duracao_travamento(jogador):
    """Rodadas ADICIONAIS em todo Travamento (pula_turno) que o JOGADOR
    aplica no chefe -- Prisão de Cristal (skill) e o Travamento da arma
    elemental (gelo) os dois consultam isto. 0 = nenhuma passiva mexe
    nisso. É bônus de quem APLICA, não de quem sofre -- por isso o
    parâmetro é sempre o jogador que deu o golpe, nunca o alvo."""
    if _tem_passiva(jogador, "inverno_constante"):
        return PASSIVAS["inverno_constante"]["valor"]
    return 0


def empilha_brasa(jogador):
    """Combustão (mago de fogo): True se a Brasa que o JOGADOR aplica no
    chefe deve empilhar (até MAX_STACKS_BRASA, ver combate.py) em vez de
    só renovar a duração. False = nenhuma passiva mexe nisso -- Brasa
    continua se comportando como sempre (refresh)."""
    return _tem_passiva(jogador, "combustao")


def chance_erro_carregado(jogador):
    """Reflexos (mago de raio): chance ADICIONAL de o jogador escapar
    ILESO quando o chefe SOLTA o golpe carregado (não vale pro ataque
    normal) -- 0.0 = nenhuma passiva mexe nisso. Consultada por
    combatente, dentro do laço que resolve o golpe carregado em
    Luta.turno_do_chefe -- erra só quem tem a passiva, nunca cancela a
    carga nem afeta o dano dos outros alvos."""
    if _tem_passiva(jogador, "reflexos"):
        return PASSIVAS["reflexos"]["valor"]
    return 0.0


def bonus_reducao_dano(jogador):
    """Disciplina (soldado): fração ADICIONAL e PERMANENTE de redução de
    dano recebido -- soma com as condições temporárias (Muralha de
    Escudos, Voto de Ferro), teto de 0.5 pro total combinado (ver
    combate._reducao_dano_total). 0.0 = nenhuma passiva mexe nisso."""
    if _tem_passiva(jogador, "disciplina"):
        return PASSIVAS["disciplina"]["valor"]
    return 0.0


def multiplicador_furia_desespero(jogador, fracao_hp):
    """Desespero (mercenário): multiplicador sobre o ganho de Fúria
    (`combate.ganhar_furia`/`ganhar_furia_defesa`) quando o guerreiro está
    com `fracao_hp` (hp atual / hp máximo) abaixo de METADE -- 1.0 = acima
    da metade, ou nenhuma passiva mexe nisso. `fracao_hp` é estado de
    combate (não mora no jogador persistido), por isso entra como
    parâmetro -- mesmo padrão de `critico_garantido(jogador, rodada)`."""
    if _tem_passiva(jogador, "desespero") and fracao_hp <= 0.5:
        return PASSIVAS["desespero"]["valor"]
    return 1.0


def fracao_defesa_ignorada(jogador):
    """Fio da Lâmina (espadachim): fração da defesa do chefe que os
    ataques do jogador ignoram -- 0.0 = nenhuma passiva mexe nisso. Vale
    no ataque normal E em toda skill (ver combate._defesa_efetiva);
    perfuração parcial, nunca pula `at.aplicar_defesa`, só reduz a defesa
    ANTES dela. Ver decisoes.md § Ajustes do Ladino (Corte Rápido) pro
    registro de que esse caminho foi reservado pro espadachim, não pro
    ladino."""
    if _tem_passiva(jogador, "fio_da_lamina"):
        return PASSIVAS["fio_da_lamina"]["valor"]
    return 0.0


def mana_recuperada_por_golpe(jogador):
    """Corpo Desperto (monge): mana ADICIONAL recuperada a cada golpe que
    acerta -- ataque normal ou skill (mana não regenera em combate por
    conta própria, então isto é o que sustenta o monge numa luta longa).
    0 = nenhuma passiva mexe nisso."""
    if _tem_passiva(jogador, "corpo_desperto"):
        return PASSIVAS["corpo_desperto"]["valor"]
    return 0


def e_clerigo(jogador):
    """Chama Divina/Reerguer e a auto-ressurreição (Step 2d) são
    inerentes à ascensão clérigo, não uma passiva separada -- o clérigo
    só tem UMA passiva de verdade (Bênção, "três ramos, uma passiva
    cada"). Consulta direta ao ramo, não à lista de passivas -- por isso
    mora aqui e não usa _tem_passiva."""
    return _ramo(jogador) == "clerigo"


def fracao_reducao_cura_ignorada(jogador):
    """Bênção (clérigo): fração da `reducao_cura_recebida` do ALVO que as
    curas DESTE jogador ignoram -- 0.0 = nenhuma passiva mexe nisso. NÃO
    muda o teto de 0.8 de `condicoes.reducao_cura_recebida` -- só reduz o
    valor CONSULTADO na hora de aplicar uma cura vinda deste clérigo (ver
    condicoes._tick_cura, campo "bonus_cura_ignorado")."""
    if _tem_passiva(jogador, "bencao"):
        return PASSIVAS["bencao"]["valor"]
    return 0.0


def fracao_absorcao_aliado(jogador):
    """Juramento (paladino): fração do dano que QUALQUER aliado (nunca o
    próprio paladino) tomaria do chefe, transferida pro paladino em vez
    disso -- 0.0 = nenhuma passiva mexe nisso. TRANSFERÊNCIA, não
    redução: quem decide se o dano é transferido e debita o HP do
    paladino é combate.py (_transferir_para_paladino) -- esta função só
    devolve a fração, igual toda consulta deste motor."""
    if _tem_passiva(jogador, "juramento"):
        return PASSIVAS["juramento"]["valor"]
    return 0.0


# ---------------- efeitos de acessório (Step D, commit 3) ----------------
# Mesmas regras do resto do motor, só que a fonte pode ser anel/colar em vez
# de ascensão -- e por isso os três somam por FONTE (_fontes_do_efeito), não
# só "tem ou não tem": dois acessórios com o mesmo efeito valem o dobro.

def cura_fracao_ao_critico(jogador):
    """Fio Vermelho: fração do HP MÁXIMO curada quando um ataque NORMAL
    do jogador critica -- 0.0 = nenhuma fonte concede isto. Só ataque
    normal (não skill) -- mesmo escopo de `ganhar_furia`/`_recuperar_
    mana_por_golpe` nos dois call sites de `_rolar_ataque_normal`."""
    return PASSIVAS["cura_ao_critico"]["valor"] * _fontes_do_efeito(jogador, "cura_ao_critico")


def chance_ignora_condicao(jogador):
    """Véu Cinza: chance de ignorar por completo uma condição que o
    chefe telegrafar (Vendaval/Choque/Congelamento/Queimadura/Ferida
    Sombria/Marca, andares 11+) -- 0.0 = nenhuma fonte concede isto.
    Consultada em `combate.Luta._resolver_condicao_pendente`, antes de
    `condicoes.aplicar` -- ignorar cancela a aplicação inteira, não
    reduz duração nem valor."""
    return PASSIVAS["ignora_condicao"]["valor"] * _fontes_do_efeito(jogador, "ignora_condicao")


def bonus_furia_ao_apanhar(jogador):
    """Fervor Contido: Fúria FIXA adicional sempre que o jogador toma
    dano de verdade do chefe -- 0 = nenhuma fonte concede isto. Só
    Guerreiro tem Fúria (quem chama já filtra a classe, mesmo padrão de
    `ganhar_furia`/`ganhar_furia_defesa`); diferente dos dois, este
    dispara em QUALQUER dano recebido, não só ao escolher Defender."""
    return PASSIVAS["furia_extra_ao_apanhar"]["valor"] * _fontes_do_efeito(jogador, "furia_extra_ao_apanhar")
