# combate.py
# Combate por turnos dos chefes, solo ou em party, com botoes na mensagem.
# Nao importa bot.py (evita import circular): os helpers chegam por instalar().

import random

import discord

import atributos as at
import condicoes
import database as db
import espelhos
import habilidades as hab
import mundo
import passivas
import pronomes
import travas
import vilarejo
from andares_altos import ANDAR_ACIMA_DO_SELO, LIMITE_VIAJAR
from game_data import (
    ITENS, ANDARES, ANDAR_MAXIMO, HABILIDADES, CLASSES, CONDICOES_ELEMENTO,
    CONDICOES_ARMA_ELEMENTAL, multiplicador_elemento,
)
from npcs import ANDAR_DESBLOQUEIA_CARROCA

# helpers emprestados do bot.py, preenchidos por instalar()
H = {}

# ---------------------------------------------------------------- constantes

TIMEOUT_RODADA = 60          # segundos sem clicar = saiu da luta
TIMEOUT_SALA = 90            # janela da sala de espera
MAX_PARTY = 4
MAX_POCOES = 3                # poções por luta, por pessoa
MAX_ELIXIRES = 1              # elixires de Alquimia por luta, por pessoa — contador à parte
REDUCAO_DEFENDENDO = 0.50    # dano que sobra quando voce defende
CHANCE_CARREGAR = 0.30       # por rodada
MULTIPLICADOR_CARREGADO = 3.0
PENETRACAO_BASE = 0.30       # fracao da defesa que o chefe ignora
PENETRACAO_POR_ANDAR = 0.015
PENETRACAO_CARREGADO = 0.25  # somada a base no golpe pesado
FUGA_POR_DESFALQUE = 0.15    # cada companheiro perdido facilita a fuga
HP_MINIMO_PARA_ENTRAR = 0.40

# ajuda de veterano na party: quem entra num andar abaixo do próprio andar_max
# não é "dono" daquele andar. Isso só importa pro HP do chefe nos andares
# 1-10 (escala por nº de donos, não por participante) — recompensa, drop e
# progressão são iguais pra todo mundo que venceu. Ver decisoes.md § Ajuda
# de veterano na party.

# rodada 1 é só do jogador: chefe não ataca, não rola carregar, não rola
# telegraph de condição, e não abre a luta com o golpe de iniciativa por DES.
# Desliga voltando isso pra False — nenhuma outra lógica depende disso.
# Ver decisoes.md § Rodada 1 sem chefe.
RODADA_1_SEM_CHEFE = True

# andares 11+: telegraph de condição elemental, independente do golpe
# carregado (rolls separados, de propósito — ver decisoes.md § Condições)
CHANCE_TELEGRAFAR_CONDICAO = 0.25

# arma elemental (todo andar): chance por golpe que acerta o alvo de amarrar
# a condição de CONDICOES_ARMA_ELEMENTAL nele — teto de uma aplicação por
# elemento por rodada (Luta.elementos_aplicados_rodada), senão uma party de
# 4 elementais do mesmo elemento chega perto de 100% de uptime. Ver
# decisoes.md § Dano elemental.
CHANCE_CONDICAO_ELEMENTO_ARMA = 0.25
FASE2_LIMIAR = 0.5   # fração de hp_chefe_max que dispara o "fase2" do chefe
# ANDAR_ACIMA_DO_SELO vem de andares_altos.py: acima dele, material de chefe
# segue chefes_derrotados (100% primeira vez, 15% repetição) em vez da
# chance fixa no dict — ver decisoes.md § Morte e reconquista

# recursos de habilidade por luta (Fúria, Energia) — não persistem no banco,
# resetam toda vez que uma luta de chefe começa. Mana é o recurso de sempre
# (jogadores.mana), persistente e regenerado fora de combate.
FURIA_MAX = 100
FURIA_POR_GOLPE = 15          # + FOR/5; crítico dá +50%; Defender gera metade
ENERGIA_MAX = 100
ENERGIA_REGEN_POR_TURNO = 20

# números das 8 primeiras skills — ver decisoes.md § Primeira leva de skills
MAX_STACKS_SANGRAMENTO = 3
VALOR_SANGRAMENTO = 0.03          # fração do HP máximo do chefe, por rodada, por stack
TETO_STUN_ATORDOANTE = at.TETO_ESQUIVA   # 0.25 — mesmo teto de chance_esquiva
BONUS_CRITICO_CORTE_RAPIDO = 0.10
BONUS_CRITICO_PONTO_CEGO = 0.45
CURA_POR_RODADA_ALENTO = 0.08
VULNERAVEL_RUPTURA = 0.20
REDUCAO_VOTO_DE_FERRO = 0.20

# multiplicadores de dano de skill sobre a MESMA base do ataque normal
# (atributo + atk da arma, ver hab.poder_base) — o número já É a razão
# skill/ataque-básico, em qualquer nível e com qualquer arma. Regra:
# dano puro ~2 ataques, dano + efeito relevante ~1,3 ataque + o efeito.
# Ver decisoes.md § Dano de skill abaixo do ataque básico.
MULTIPLICADOR_DARDO_ARCANO = 2.0     # dano puro (+ ignora defesa, bônus à parte)
MULTIPLICADOR_GOLPE_ABERTO = 1.3     # dano + sangramento (o efeito)
MULTIPLICADOR_CORTE_RAPIDO = 1.35    # dano puro, por golpe — 2 golpes = 2.7 nominal (era 1.0/2.0 -- ver
                                      # decisoes.md § Ajustes do Ladino, assimetria de defesa com Dardo Arcano)

# skills de ascensão do Ladino (Step 2a) -- mesma base do ataque normal que
# as acima, ver decisoes.md § Dano de skill abaixo do ataque básico.
MULTIPLICADOR_GOLPE_FATAL_BASE = 1.2      # alvo com HP cheio
BONUS_GOLPE_FATAL_EXECUCAO = 2.0          # + até isso, conforme o alvo perde HP -- teto 3.2 com o alvo a 0
                                           # (era 1.3/teto 2.5 -- medido por Monte Carlo abaixo do Corte
                                           # Rápido em qualquer andar, ver decisoes.md § Ajustes do Ladino)
MULTIPLICADOR_FLECHA_PERFURANTE = 1.8     # dano puro, ignora defesa (igual Dardo Arcano) -- NÃO mudou:
                                           # medido já competitivo com o Corte Rápido a partir do andar 9 e
                                           # dominante no 15, subir mais viraria a skill mais forte do jogo

# skills de ascensão do Mago (Step 2b) -- calibragem ACIMA da régua de
# propósito: 2.0 (nominal igual ao Dardo Arcano) + o efeito, e as três
# passam por at.aplicar_defesa (Dardo Arcano continua sendo a única que
# ignora defesa -- é a identidade dele desde o nível 1). Ver decisoes.md §
# Step 2b pro porquê da exceção à régua de "~1,3 ataque + efeito".
MULTIPLICADOR_PRISAO_DE_CRISTAL = 2.0
TRAVAMENTO_PRISAO_DE_CRISTAL_RODADAS = 1   # N rodadas travado -- regra N+1 (ver comentário
                                            # "Duração de condições" logo acima de _multiplicador_afinidade)
MULTIPLICADOR_CONFLAGRACAO = 2.0
BONUS_CONFLAGRACAO_POR_STACK = 0.25        # por stack de Brasa já no alvo -- 3 stacks = 2.75
MAX_STACKS_BRASA = 3                       # só empilha com Combustão (Step 2b) -- sem a passiva, refresca
MULTIPLICADOR_INTERRUPCAO = 2.0            # dano igual às outras duas -- cancelar a carga é bônus condicional,
                                            # não vale mais nominal por isso (ver decisoes.md § Step 2b)

# skills de ascensão do Guerreiro (Step 2c) -- mesmo critério do Mago:
# 2.0 nominal + o efeito, COM at.aplicar_defesa. Ver decisoes.md § Step 2c.
MULTIPLICADOR_MURALHA_DE_ESCUDOS = 2.0
REDUCAO_MURALHA_DE_ESCUDOS = 0.20          # temporária, enquanto o redirecionamento durar -- soma com
                                            # Disciplina (permanente) e Voto de Ferro, teto 0.5 pro total
DURACAO_MURALHA_RODADAS = 2                # N rodadas de redirecionamento -- regra N+1 (ver comentário
                                            # "Duração de condições" logo acima de _multiplicador_afinidade)
MULTIPLICADOR_GOLPE_OPORTUNISTA = 2.0      # guerreiro com HP cheio
BONUS_GOLPE_OPORTUNISTA = 1.0              # + até isso, conforme O PRÓPRIO GUERREIRO perde HP -- teto 3.0
                                            # com c em 1 de HP. Espelho do Golpe Fatal (Step 2a): aquele pune
                                            # o alvo ferido, este recompensa o guerreiro ferido.
MULTIPLICADORES_SEQUENCIA = (0.5, 0.7, 0.8)   # 3 golpes, soma 2.0 -- cada um mais forte que o anterior,
                                               # cada um rola crítico separado (mesmo padrão do Corte Rápido)

# skills de ascensão do Orador (Step 2d) -- mesmo critério: 2.0 nominal +
# efeito, COM at.aplicar_defesa. Ver decisoes.md § Step 2d.
MULTIPLICADOR_PUNHO_DO_SILENCIO = 2.0
DURACAO_BLOQUEIA_SKILL_PUNHO_RODADAS = 2   # N rodadas silenciado -- regra N+1 (ver comentário
                                            # "Duração de condições" logo acima de _multiplicador_afinidade).
                                            # Hoje quase não faz nada (chefe não tem habilidade própria) --
                                            # intencional, ganha valor no step 3 (IA de combo). NÃO é no-op
                                            # por engano como Reflexos era (Step 2b correção): aqui o efeito
                                            # (bloqueia_skill) já existe e É consultado hoje
                                            # (condicoes.pode_lancar_habilidade), só o chefe ainda não tem
                                            # skill própria pra bloquear.
MULTIPLICADOR_CHAMA_DIVINA = 2.0           # versão solo de Graça Divina -- puro dano
FRACAO_HP_REERGUER = 0.6                   # versão party de Graça Divina -- HP de quem é levantado
LIMITE_REERGUER_POR_LUTA = 2               # total NA LUTA, não por aliado -- contador em Luta, não no jogador
FRACAO_HP_AUTO_RESSURREICAO = 0.6          # auto-ressurreição do clérigo, só luta SOLO, uma vez por luta
MULTIPLICADOR_REPRESALIA = 2.0             # skill do paladino -- dano puro + a condição abaixo
FRACAO_REFLEXAO_REPRESALIA = 0.3           # fração do dano que o CHEFE toma de volta enquanto ativa
DURACAO_REFLEXAO_REPRESALIA_RODADAS = 3    # N rodadas refletindo -- regra N+1 (ver comentário
                                            # "Duração de condições" logo acima de _multiplicador_afinidade)
FRACAO_ABSORCAO_JURAMENTO = 0.3            # passiva do paladino -- fração do dano de QUALQUER aliado
                                            # (nunca do próprio paladino) transferida pra ele; TRANSFERÊNCIA,
                                            # não redução -- não entra em _reducao_dano_total, não compete de
                                            # teto com Disciplina/Voto de Ferro/Muralha de Escudos

COR_DERROTA = 0x8B0000
COR_FUGA = 0x6C757D
COR_SALA = 0xA8DADC


def _reducao_dano_total(luta, combatente):
    """Some a redução de dano das condições temporárias (Muralha de
    Escudos, Voto de Ferro -- condicoes.reducao_dano_recebido) com a
    passiva PERMANENTE do soldado (Disciplina, passivas.bonus_reducao_
    dano) -- o teto de 0.5 vale pro TOTAL combinado, não só pras
    condições sozinhas. Ver decisoes.md § Step 2c."""
    return min(0.5, condicoes.reducao_dano_recebido(luta, combatente.id) + passivas.bonus_reducao_dano(combatente.jogador))


def _defesa_efetiva(luta, c, inimigo=None):
    """Fio da Lâmina (espadachim, Step 2c): reduz a defesa do inimigo
    ANTES de `at.aplicar_defesa` ver ela -- perfuração PARCIAL, nunca
    pula a função (ao contrário de Dardo Arcano/Flecha Perfurante, que
    ignoram defesa por inteiro e não chamam isto). 0.0 de passivas.
    fracao_defesa_ignorada reproduz a defesa do inimigo sem mudança
    nenhuma. `inimigo` -- Step E: qual inimigo defende; default None
    continua lendo `luta.chefe["def"]` (o principal), então todo
    chamador de antes deste cartão (ataque normal e toda skill que
    mira sempre `inimigos[0]`) funciona sem passar nada."""
    dados = inimigo.dados if inimigo is not None else luta.chefe
    return dados["def"] * (1 - passivas.fracao_defesa_ignorada(c.jogador))


def _recuperar_mana_por_golpe(c):
    """Corpo Desperto (monge, Step 2d): chamada quando um golpe de c
    ACERTA -- ataque normal ou skill. 0 de passivas.mana_recuperada_por_
    golpe reproduz o comportamento de sempre (nada muda) pra quem não é
    monge, então todo ponto de dano pode chamar isto sem risco."""
    c.mana = min(c.s["mana_max"], c.mana + passivas.mana_recuperada_por_golpe(c.jogador))


def _curar_por_critico(c, critico):
    """Fio Vermelho (efeito de acessório, Step D commit 3): cura uma
    fração do HP MÁXIMO quando um ataque NORMAL crítica. 0.0 de
    passivas.cura_fracao_ao_critico reproduz sempre igual pra quem não
    tem o efeito equipado -- mesmo padrão de segurança de
    `_recuperar_mana_por_golpe`."""
    if not critico:
        return
    fracao = passivas.cura_fracao_ao_critico(c.jogador)
    if fracao <= 0:
        return
    cura = max(1, int(c.s["hp_max"] * fracao))
    c.hp = min(c.s["hp_max"], c.hp + cura)


def _talvez_auto_ressuscitar(luta):
    """Auto-ressurreição (clérigo, SOLO, Step 2d): quando o único
    combatente cai e ainda não usou a auto-ressurreição desta luta, ele
    volta sozinho com FRACAO_HP_AUTO_RESSURREICAO do HP máximo --
    automático, não custa mana, dispara mesmo com mana vazia (ele está
    caído, não pode lançar nada).

    Chamado de Luta.fim_da_luta, ANTES de qualquer decisão de derrota --
    de propósito: é o único jeito de funcionar não importa qual dano
    derrubou o clérigo (golpe do chefe, golpe carregado, uma condição
    tickando dano), sem precisar patchar cada ponto do jogo que pode
    marcar `caiu = True`. `fim_da_luta` é sempre consultado logo depois
    de qualquer um desses, então interceptar ali cobre todos eles de
    uma vez."""
    if luta.em_party:
        return
    c = luta.participantes[0]
    if not c.caiu or luta.auto_ressurreicao_usada or not passivas.e_clerigo(c.jogador):
        return
    luta.auto_ressurreicao_usada = True
    c.caiu = False
    c.hp = int(FRACAO_HP_AUTO_RESSURREICAO * c.s["hp_max"])
    c.acao = "defender"
    c.defendendo = True
    c.salvar_estado()
    luta.registrar(f"✨ {c.nome} se recusa a cair -- volta à luta com {c.hp} HP!")


def _pode_lancar_graca_divina(luta, combatente):
    """Reerguer (versão party de Graça Divina) só pode ser lançada se
    existir alguém caído E o limite de LIMITE_REERGUER_POR_LUTA ainda não
    foi usado -- sem isso, não gasta mana à toa (ver decisoes.md § Step
    2d). Chama Divina (versão solo) não tem essa restrição -- é dano
    puro, sempre disponível."""
    if not luta.em_party:
        return True
    if luta.reergueres_usados >= LIMITE_REERGUER_POR_LUTA:
        return False
    return any(outro.caiu for outro in luta.participantes)


def _paladino_ativo(luta):
    """Paladino ATIVO com Juramento -- None se não há paladino na luta ou
    se o único já caiu (quem caiu não absorve nada). `passivas.
    fracao_absorcao_aliado` só volta > 0 pra quem tem a passiva, então
    isto nunca pega um combatente qualquer por engano."""
    return next(
        (c for c in luta.ativos if passivas.fracao_absorcao_aliado(c.jogador) > 0),
        None,
    )


def _transferir_para_paladino(luta, alvo, dano):
    """Juramento (paladino, passiva, Step 2d): fração FIXA do dano que
    QUALQUER aliado -- nunca o próprio paladino -- vai tomar do chefe é
    paga pelo paladino em vez da vítima original. TRANSFERÊNCIA, não
    redução: não entra em `_reducao_dano_total`/`reducao_dano_recebida`,
    não compete de teto com Disciplina/Voto de Ferro/Muralha de
    Escudos. Também não é a Muralha (que redireciona o ALVO que o chefe
    escolhe) -- aqui o chefe continua acertando quem quiser, só quem
    PAGA parte da conta muda. Devolve (dano_que_o_alvo_toma,
    dano_que_o_paladino_toma, paladino_ou_None)."""
    paladino = _paladino_ativo(luta)
    if paladino is None or paladino.id == alvo.id:
        return dano, 0, None
    fracao = passivas.fracao_absorcao_aliado(paladino.jogador)
    absorvido = int(dano * fracao)
    return dano - absorvido, absorvido, paladino


def _refletir_se_paladino(luta, combatente, dano_recebido, inimigo_id="chefe"):
    """Represália (paladino, skill, Step 2d): devolve a QUEM CAUSOU o
    dano uma fração do que `combatente` acabou de tomar, se ele estiver
    sob `reflete_dano`. `inimigo_id` -- Step E: antes disto, o reflexo
    sempre saía de `luta.hp_chefe` (o inimigo PRINCIPAL), certo enquanto
    só existia um inimigo por luta; com grupos de bandidos, o inimigo
    que bateu pode não ser `inimigos[0]`, e devolver nele bateria no
    alvo errado. Default "chefe" preserva every chamador antigo (raide,
    dungeon, os testes de `test_paladino.py`) sem mudar uma linha. O
    dano refletido sai do HP do inimigo DIRETO -- não volta a passar por
    `_aplicar_dano_do_chefe` nem por esta função -- então reflexão nunca
    dispara reflexão de novo, mesmo se o paladino tomar dano transferido
    de Juramento (que também chama isto)."""
    fracao = condicoes.fracao_reflexao(luta, combatente.id)
    if fracao <= 0 or dano_recebido <= 0:
        return
    refletido = max(1, int(dano_recebido * fracao))
    inimigo = luta.inimigo_por_id(inimigo_id) or luta.inimigos[0]
    inimigo.hp -= refletido
    luta.verificar_fase2()
    luta.registrar(f"🔥 **Represália** devolve **{refletido}** de dano a {inimigo.nome}.")


def _aplicar_dano_do_chefe(luta, alvo, dano, inimigo_id="chefe"):
    """Ponto único onde o dano que um inimigo causa realmente toca o HP
    de um combatente -- os dois lugares que causam esse dano (ataque
    normal, golpe carregado, dentro de `_turno_de_um_inimigo`) chamam
    isto em vez de mexer em `c.hp` direto. `inimigo_id` -- Step E: quem
    causou ESTE dano, só usado hoje pra saber pra quem a Represália
    reflete (ver `_refletir_se_paladino`); default "chefe" preserva os
    chamadores que não passam nada (todos antes deste cartão). Devolve
    o dano que `alvo` de fato tomou (depois de Juramento), pro chamador
    logar a mensagem certa. Marca `caiu` normalmente pros dois lados
    (alvo original e paladino, se ele absorveu parte)."""
    dano_alvo, dano_paladino, paladino = _transferir_para_paladino(luta, alvo, dano)
    alvo.hp -= dano_alvo
    if alvo.hp <= 0:
        alvo.caiu = True
    _ganhar_furia_por_efeito_ao_apanhar(alvo, dano_alvo)
    _refletir_se_paladino(luta, alvo, dano_alvo, inimigo_id)
    if paladino is not None and dano_paladino > 0:
        paladino.hp -= dano_paladino
        luta.registrar(f"🛡️ {paladino.nome} absorve **{dano_paladino}** de dano por **Juramento**.")
        if paladino.hp <= 0:
            paladino.caiu = True
        _ganhar_furia_por_efeito_ao_apanhar(paladino, dano_paladino)
        _refletir_se_paladino(luta, paladino, dano_paladino, inimigo_id)
    return dano_alvo


def penetracao_do_andar(andar_num, carregado=False):
    pen = PENETRACAO_BASE + PENETRACAO_POR_ANDAR * (andar_num - 1)
    if carregado:
        pen += PENETRACAO_CARREGADO
    return min(0.85, pen)


def dano_do_chefe(chefe, s, andar_num, defendendo=False, carregado=False):
    """Defender anula a penetracao e ainda corta o dano pela metade."""
    pen = 0.0 if defendendo else penetracao_do_andar(andar_num, carregado)
    bruto = chefe["atk"] * random.uniform(0.85, 1.15)
    if carregado:
        bruto *= MULTIPLICADOR_CARREGADO
    if random.random() < at.CRITICO_BASE:
        bruto *= at.MULTIPLICADOR_CRITICO
    valor = at.aplicar_defesa(bruto, s["def"] * (1 - pen))
    if defendendo:
        valor = max(1, int(valor * REDUCAO_DEFENDENDO))
    return valor


def _aplicar_sombra(luta, c, dano):
    """Mortalha de Sombra: dobra todo dano que o jogador causar ao chefe
    nessa rodada -- golpe normal (chamado do loop de ataque) e as três
    habilidades que causam dano direto (Dardo Arcano, Golpe Aberto, Corte
    Rápido — chamado de dentro de cada `_efeito_*`). NUNCA entra em efeito
    que não é dano em si: condição (Ruptura/Voto de Ferro), cura (Palavra
    de Alento) ou o DoT que Golpe Aberto deixa (Sangramento tica no valor
    fixo de sempre, só o golpe que o aplica dobra) -- cada um desses só
    chamaria isto se alguém adicionasse a chamada, o que não é o caso.
    Também não mexe no golpe do chefe. `c.sombra_ativa` já é zerado
    incondicionalmente no fim da rodada (Luta.turno_do_chefe), então não
    precisa desligar aqui -- inclusive quando chamado duas vezes na mesma
    ativação (Corte Rápido atinge duas vezes, as duas dobram)."""
    if not c.sombra_ativa:
        return dano
    luta.registrar(f"🌑 Mortalha de Sombra: o golpe de {c.nome} sai em dobro.")
    return dano * 2


def pocoes_na_mochila(user_id):
    itens = db.get_inventario(user_id)
    return [
        i for i in itens
        if i["item"] in ITENS and ITENS[i["item"]]["tipo"] == "consumivel"
    ][:5]


async def responder(interaction, embed, view):
    """Confirma a interacao antes de qualquer trabalho pesado e depois edita.

    Sem o defer, o token vence em 3 segundos — e gravar HP, drop e XP no
    SQLite passa disso com facilidade quando tem gente jogando junto.
    """
    if not interaction.response.is_done():
        await interaction.response.defer()
    await interaction.edit_original_response(embed=embed, view=view)


def eh_elixir(chave):
    """Poção/mana comum tem valor fixo; a versão de Alquimia é por porcentagem."""
    dado = ITENS[chave]
    return "cura_pct" in dado or "mana_pct" in dado


def pode_usar(combatente, chave):
    if eh_elixir(chave):
        return combatente.elixires_usados < MAX_ELIXIRES
    return combatente.pocoes_usadas < MAX_POCOES


def ganhar_furia(c, critico=False):
    """Só o Guerreiro acumula Fúria, e só atacando — golpe crítico dá +50%.
    Desespero (mercenário, Step 2c): mais rápido abaixo de metade do HP --
    ver passivas.multiplicador_furia_desespero."""
    if c.jogador["classe"] != "guerreiro":
        return
    ganho = FURIA_POR_GOLPE + int(c.jogador["forca"] or 0) / 5
    if critico:
        ganho *= 1.5
    ganho *= passivas.multiplicador_furia_desespero(c.jogador, c.hp / c.s["hp_max"])
    c.furia = min(FURIA_MAX, c.furia + ganho)


def ganhar_furia_defesa(c):
    """Defender também gera Fúria pro Guerreiro, metade do golpe normal.
    Desespero também vale aqui -- é o caso que a passiva mais precisa
    valer: o guerreiro apanhando é quem está abaixo de metade do HP."""
    if c.jogador["classe"] != "guerreiro":
        return
    ganho = 0.5 * (FURIA_POR_GOLPE + int(c.jogador["forca"] or 0) / 5)
    ganho *= passivas.multiplicador_furia_desespero(c.jogador, c.hp / c.s["hp_max"])
    c.furia = min(FURIA_MAX, c.furia + ganho)


def _ganhar_furia_por_efeito_ao_apanhar(c, dano_recebido):
    """Fervor Contido (efeito de acessório, Step D commit 3): Fúria
    fixa extra sempre que dano de verdade chega no jogador -- 0 de
    passivas.bonus_furia_ao_apanhar reproduz sempre igual pra quem não
    tem o efeito. Independente de `ganhar_furia_defesa` (que só dispara
    ao ESCOLHER Defender): este dispara em qualquer dano recebido,
    defendendo ou não -- é o que "ao apanhar" pede."""
    if c.jogador["classe"] != "guerreiro" or dano_recebido <= 0:
        return
    bonus = passivas.bonus_furia_ao_apanhar(c.jogador)
    if bonus:
        c.furia = min(FURIA_MAX, c.furia + bonus)


def regenerar_energia(luta):
    """Energia do Ladino sobe todo turno, agindo ou não."""
    for c in luta.ativos:
        if c.jogador["classe"] == "ladino":
            c.energia = min(ENERGIA_MAX, c.energia + ENERGIA_REGEN_POR_TURNO)


# ------------------------------------------------------------- combatente

class Combatente:
    """Um jogador dentro da luta. Solo e' uma party de um."""

    def __init__(self, jogador, s):
        self.id = jogador["user_id"]
        self.nome = jogador["nome"]
        self.jogador = jogador
        self.s = s
        self.hp = max(0, jogador["hp"])
        self.mana = max(0, jogador["mana"])
        self.furia = 0             # Guerreiro: começa zerada, só sobe com dano causado
        self.energia = ENERGIA_MAX  # Ladino: começa cheia, regenera por turno
        self.acao = None            # o que ele escolheu nesta rodada
        self.defendendo = False
        self.pocoes_usadas = 0
        self.elixires_usados = 0
        self.mortalha_usada = False   # uma vez por luta -- ver BotaoMortalha
        self.sombra_ativa = False     # Mortalha de Sombra: dobra o próximo golpe NESTA rodada
        self.sangue_frio_disparado = False   # Sangue Frio (assassino): só uma vez por luta, por combatente
        self.caiu = False
        self.fugiu = False
        self.saiu = False
        self.dono = True   # Luta.__init__ ajusta pra quem entrou só de ajuda
        self._estado_final_salvo = False   # ver salvar_estado()

    @property
    def ativo(self):
        return not (self.caiu or self.fugiu or self.saiu)

    def recurso_atual(self):
        """Mana, Fúria ou Energia — o que a classe do jogador usa pra lançar."""
        recurso = CLASSES.get(self.jogador["classe"], {}).get("recurso")
        return {"mana": self.mana, "furia": self.furia, "energia": self.energia}.get(recurso, 0)

    def salvar_estado(self):
        """Grava HP/mana no banco -- exceto se o combatente já saiu da luta
        (fugiu/saiu/caiu) e essa saída já foi salva uma vez. Os laços que
        rodam por cima de `Luta.participantes` (fim de rodada, timeout)
        continuam chamando isso pra TODO MUNDO a cada rodada, inclusive
        quem já não está mais lutando -- sem a guarda, cada chamada
        seguinte regravava o HP CONGELADO no momento da saída por cima de
        qualquer cura que acontecesse depois (poção fora da luta, por
        exemplo), porque `self.hp` nunca mais muda depois que a pessoa sai.
        Uma vez que o estado final foi salvo, mais nenhuma escrita acontece
        pra esse combatente. Ver decisoes.md § HP final é congelado ao sair
        da luta."""
        if not self.ativo:
            if self._estado_final_salvo:
                return
            self._estado_final_salvo = True
        db.atualizar_jogador(self.id, hp=max(0, self.hp), mana=max(0, self.mana))

    def barra(self):
        estado = ""
        if self.caiu:
            estado = " — caiu"
        elif self.fugiu:
            estado = " — fugiu"
        elif self.saiu:
            estado = " — saiu da luta"
        elif self.acao:
            estado = pronomes.concordar(" — pront{o|a}", self.jogador["pronome"])
        linha = (f"{H['barra_hp'](self.hp, self.s['hp_max'])} "
                 f"{max(0, self.hp)}/{self.s['hp_max']}{estado}")
        classe = self.jogador["classe"]
        if classe:
            recurso = CLASSES[classe]["recurso"]
            emoji, valor, teto = {
                "mana": ("🔷", self.mana, self.s["mana_max"]),
                "furia": ("🔥", self.furia, FURIA_MAX),
                "energia": ("⚡", self.energia, ENERGIA_MAX),
            }[recurso]
            linha += f" · {emoji} {max(0, valor)}/{teto}"
        return linha


# ---------------------------------------------------------------- inimigo

class Inimigo:
    """Um inimigo dentro da luta -- Step A (multi-inimigo no motor):
    `self.hp_chefe`/`self.hp_chefe_max`/`self.carregando`/
    `self.preparando_condicao`, que até aqui eram estado da `Luta`
    inteira, viram estado PRÓPRIO de cada inimigo. `dados` é o dict de
    definição do inimigo (nome/atk/def/elemento/hp/etc — o mesmo shape
    que sempre foi `Luta.chefe`). Ver Luta.__init__ e decisoes.md § Step
    A."""

    def __init__(self, id, dados, hp):
        self.id = id
        self.dados = dados
        self.hp = hp
        self.hp_max = hp
        self.carregando = False
        self.preparando_condicao = None   # telegraph independente — ver Luta._talvez_telegrafar_condicao

    @property
    def nome(self):
        return self.dados["nome"]

    @property
    def ativo(self):
        return self.hp > 0


# ------------------------------------------------------------ estado da luta

class Luta:
    def __init__(self, combatentes, chefe, andar_num, donos_ids=None):
        """donos_ids: quem conta como "dono do andar" pra escalar o HP do
        chefe (andares 1-10). None = todo mundo é dono (luta solo,
        raide.py) — só a party de `combate.py` passa um subconjunto de
        propósito, pra quem entrou só de ajuda (andar_max diferente do
        andar do chefe) não inflar o chefe. Recompensa, drop e progressão
        não olham `dono` — vitória é igual pra todo mundo que estava na
        luta. Ver decisoes.md § Ajuda de veterano na party."""
        self.participantes = combatentes
        self.andar_num = andar_num
        donos_ids = set(donos_ids) if donos_ids is not None else {c.id for c in combatentes}
        for c in combatentes:
            c.dono = c.id in donos_ids
        num_donos = sum(1 for c in combatentes if c.dono)
        # acima do Selo (andar 11+) o HP do chefe é fixo, igual ao solo,
        # não importa quantos donos entraram -- decisão do Rafael: 11-15 é
        # conteúdo de grupo, e é esperado que a party fique bem mais forte
        # lá em cima. Do 1 ao 10 continua escalando por dono (raide.py usa
        # esse mesmo caminho com andar_num=ANDAR_REFERENCIA_RAIDE=7, sempre
        # abaixo do limiar, então a raide não muda). Ver decisoes.md § HP
        # de chefe fixo acima do Selo.
        escala = 1 if andar_num > ANDAR_ACIMA_DO_SELO else max(1, num_donos)

        # Step A: `chefe` sempre vira uma LISTA de inimigos -- um dict
        # sozinho (todo chamador de hoje: raide.py, dungeon.py,
        # iniciar_luta abaixo) vira lista de um, de propósito ("chefe
        # sozinho vira lista de um", ver decisoes.md § Step A). Cada
        # inimigo escala o PRÓPRIO hp por dono, de forma independente --
        # a extensão mais fiel ao que já valia pra um chefe só (decisão
        # registrada em decisoes.md § Step A -- escala de HP por
        # inimigo). inimigos[0] SEMPRE recebe o id "chefe": é a ponte
        # explícita e temporária pra todo código (e a suíte inteira) que
        # ainda pensa em "o chefe", singular -- ver as propriedades
        # chefe/hp_chefe/hp_chefe_max/carregando/preparando_condicao
        # logo abaixo. Os inimigos seguintes (sem nenhum conteúdo usando
        # ainda) ganham "chefe_1", "chefe_2"... -- nunca colide com
        # user_id de jogador (sempre int).
        dados_inimigos = chefe if isinstance(chefe, list) else [chefe]
        self.inimigos = [
            Inimigo("chefe" if i == 0 else f"chefe_{i}", dados, dados["hp"] * escala)
            for i, dados in enumerate(dados_inimigos)
        ]

        self.rodada = 1
        self.materiais_extras = []        # material da fase 1 quando o chefe troca de fase (andar 15)
        self.encerrada = False
        self.condicoes = []   # ver condicoes.py — sangramento, confusão, elementos etc.
        self.elementos_aplicados_rodada = set()  # teto de 1 aplicação por elemento, por rodada
        self.log = []
        # solo vs party é decidido AQUI, uma vez, e nunca mais reconsultado --
        # ver decisoes.md § Step 2d (motor de solo vs party). Antes era uma
        # @property recalculada de `len(self.participantes)` a cada leitura;
        # `self.participantes` nunca muda depois do __init__ (ninguém dá
        # append/remove nele -- só `self.ativos`, abaixo, encolhe), então o
        # VALOR já era fixo na prática -- virou atributo congelado pra ficar
        # fixo por CONSTRUÇÃO, não por coincidência de ninguém ter mutado a
        # lista errada ainda. Uma party que perde todo mundo menos um
        # continua party (o combatente que sobrou vê `em_party` True o jogo
        # inteiro); uma luta solo nunca vira party no meio.
        self.em_party = len(combatentes) > 1
        # Step 2d, clérigo: contadores presos à LUTA, não ao jogador --
        # "somem quando a luta acaba" só porque a Luta em si não sobrevive
        # além disso (não é persistido em banco). Reerguer: total NA
        # LUTA, não por aliado. Auto-ressurreição: só luta solo, ver
        # _talvez_auto_ressuscitar.
        self.reergueres_usados = 0
        self.auto_ressurreicao_usada = False
        # Step 3, commit 1: registro pro motor GERAL de decisão de chefe
        # (chefe_ia.py) -- só o que aconteceu NESTA luta, nunca persiste.
        # Vazio e nunca consultado pelos chefes da torre nesta passada
        # (ver decisoes.md § Step 3) -- só os espelhos (commit 3) leem.
        self.historico_ia = {}

        # Step C, commit 2: a cerveja da taverna do vilarejo aplica o
        # próprio efeito assim que a luta começa, não importa qual luta
        # seja (boss/party/dungeon-espelho/raide -- toda Luta de verdade
        # passa por aqui; cacar/explorar/dungeon de sala usam
        # simular_combate, que recebe o valor à parte, ver bot.py).
        # Reaproveita duas condições que já existiam: vulneravel no chefe
        # (mais dano causado) e chance_erro no próprio jogador (mais
        # chance de errar) -- "coragem líquida". Duração fixa e grande
        # porque condicoes.py só entende rodadas, não "a luta inteira".
        for c in self.participantes:
            mult, erro = vilarejo.consumir_cerveja_pendente(c.id)
            if mult > 1.0:
                condicoes.aplicar(
                    self, "chefe", "vulneravel", "Coragem de Taverna", "🍺",
                    vilarejo.DURACAO_CERVEJA_RODADAS, mult - 1.0,
                )
            if erro > 0.0:
                condicoes.aplicar(
                    self, c.id, "chance_erro", "Cerveja na Cabeça", "🍺",
                    vilarejo.DURACAO_CERVEJA_RODADAS, erro,
                )

    # -------- ponte pro inimigo principal (Step A) --------
    # Explícita e temporária: todo código escrito antes do Step A (e a
    # suíte inteira) fala de "o chefe" no singular, lendo/escrevendo
    # `luta.chefe`/`luta.hp_chefe`/`luta.hp_chefe_max`/`luta.carregando`/
    # `luta.preparando_condicao` direto. As cinco propriedades abaixo só
    # espelham `self.inimigos[0]` -- sempre o mesmo objeto que tem id
    # "chefe" (ver __init__). Nada aqui decide comportamento: é
    # encanamento pra não ter que reescrever ~15 pontos de combate.py e
    # ~15 arquivos de teste que já assumem um chefe só. Código NOVO que
    # pensa em múltiplos inimigos usa `self.inimigos`/`self.inimigo_por_id`
    # direto, nunca esta ponte. Ver decisoes.md § Step A.
    @property
    def chefe(self):
        return self.inimigos[0].dados

    @chefe.setter
    def chefe(self, valor):
        self.inimigos[0].dados = valor

    @property
    def hp_chefe(self):
        return self.inimigos[0].hp

    @hp_chefe.setter
    def hp_chefe(self, valor):
        self.inimigos[0].hp = valor

    @property
    def hp_chefe_max(self):
        return self.inimigos[0].hp_max

    @hp_chefe_max.setter
    def hp_chefe_max(self, valor):
        self.inimigos[0].hp_max = valor

    @property
    def carregando(self):
        return self.inimigos[0].carregando

    @carregando.setter
    def carregando(self, valor):
        self.inimigos[0].carregando = valor

    @property
    def preparando_condicao(self):
        return self.inimigos[0].preparando_condicao

    @preparando_condicao.setter
    def preparando_condicao(self, valor):
        self.inimigos[0].preparando_condicao = valor

    def inimigo_por_id(self, id_inimigo):
        return next((i for i in self.inimigos if i.id == id_inimigo), None)

    @property
    def inimigos_ativos(self):
        return [i for i in self.inimigos if i.ativo]

    @property
    def ativos(self):
        return [c for c in self.participantes if c.ativo]

    @property
    def desfalque(self):
        """Quantos companheiros a party perdeu — facilita a fuga de quem ficou."""
        return len(self.participantes) - len(self.ativos)

    def por_id(self, user_id):
        return next((c for c in self.participantes if c.id == user_id), None)

    def registrar(self, linha):
        self.log.append(linha)

    def chance_de_fuga(self, combatente):
        base = at.chance_fuga(
            combatente.s["atribs"]["destreza"],
            at.destreza_monstro(self.andar_num),
            eh_chefe=True,
        )
        return min(0.90, base + FUGA_POR_DESFALQUE * self.desfalque)

    def embed(self, titulo=None, cor=None, rodape=None):
        andar = ANDARES[self.andar_num]
        e = discord.Embed(
            title=titulo or f"Chefe do andar {self.andar_num} — {self.chefe['nome']}",
            color=cor if cor is not None else andar["cor"],
        )
        # Step E: um field por inimigo, não só o principal -- antes disto,
        # bandidos 2-4 de um grupo de estrada ficavam com o HP invisível
        # pro jogador (a única linha mostrada era sempre `self.chefe`, a
        # ponte pro inimigo[0]). Pra qualquer luta de hoje (sempre um
        # inimigo só), o resultado é idêntico ao de antes -- só muda
        # quando `self.inimigos` tem mais de um de verdade. Ver
        # decisoes.md § Step E.
        for inimigo in self.inimigos:
            nome_campo = inimigo.nome if inimigo.ativo else f"{inimigo.nome} — derrotado"
            e.add_field(
                name=nome_campo,
                value=f"{H['barra_hp'](inimigo.hp, inimigo.hp_max)} {max(0, inimigo.hp)}/{inimigo.hp_max}",
                inline=False,
            )
        for c in self.participantes:
            nome = c.nome if c.dono else f"{c.nome} (ajuda)"
            e.add_field(name=nome, value=c.barra(), inline=False)
        if RODADA_1_SEM_CHEFE and self.rodada == 1 and not self.encerrada:
            e.add_field(
                name="🕯️ O chefe ainda não reagiu",
                value=f"*{self.chefe['nome']} observa. A primeira rodada é toda sua.*",
                inline=False,
            )
        if self.log:
            limite = 4 if self.em_party else 2
            e.add_field(
                name=f"── Rodada {self.rodada} ──",
                value="\n".join(self.log[-limite:]),
                inline=False,
            )
        if self.carregando and not self.encerrada:
            e.add_field(
                name="⚠️ Alguma coisa vai acontecer",
                value=f"*{self.chefe['nome']} está preparando um golpe.* "
                      f"Ele acerta **todo mundo** — Defender anula a penetração de armadura.",
                inline=False,
            )
        if self.preparando_condicao and not self.encerrada:
            pend = self.preparando_condicao
            alvo = self.por_id(pend["alvo_id"])
            nome_alvo = alvo.nome if alvo else "alguém que já saiu"
            e.add_field(
                name=f"{pend['emoji']} {pend['nome']} sendo reunido",
                value=f"*{self.chefe['nome']} mira em **{nome_alvo}**.* "
                      f"Defender reduz a duração pela metade se acertar.",
                inline=False,
            )
        if rodape:
            e.set_footer(text=rodape)
        elif not self.encerrada:
            faltam = [c.nome for c in self.ativos if not c.acao]
            espera = ("Sua vez" if not self.em_party
                      else "Esperando: " + ", ".join(faltam) if faltam else "Resolvendo…")
            e.set_footer(text=f"{espera} · {TIMEOUT_RODADA}s para agir")
        return e

    # -------- resolucao da rodada
    def turno_do_chefe(self):
        """Cada inimigo vivo age uma vez por rodada, contra a party inteira
        — exceto na rodada 1, que é só do jogador (RODADA_1_SEM_CHEFE).
        Step A: o corpo que decidia a ação de UM chefe virou
        `_turno_de_um_inimigo`, chamado uma vez por inimigo — hoje sempre
        um só, então o resultado é idêntico ao de antes. Inimigo com
        "elemento" (andares 11+) também rola, de forma independente do
        golpe carregado, pra telegrafar/aplicar uma condição elemental —
        os dois podem acontecer na mesma rodada. Corrente (chance_erro) e
        Curto (bloqueia_skill) são as condições que a ARMA elemental do
        jogador pode ter amarrado no inimigo (qualquer andar) — ver
        decisoes.md § Dano elemental pros pontos de consulta novos que
        esses dois tipos precisaram aqui (os outros quatro já eram
        consultados em pontos que já existiam)."""
        alvos = self.ativos
        if not alvos:
            return

        if RODADA_1_SEM_CHEFE and self.rodada == 1:
            self.registrar(f"{self.chefe['nome']} ainda não reagiu à entrada de vocês.")
        else:
            for inimigo in self.inimigos:
                if inimigo.ativo:
                    self._turno_de_um_inimigo(inimigo, alvos)

        for c in self.participantes:
            c.defendendo = False
            c.acao = None
            c.sombra_ativa = False   # "nessa rodada" -- some no fim dela, usada ou não
            c.salvar_estado()
        self.rodada += 1
        self.elementos_aplicados_rodada = set()

    def _turno_de_um_inimigo(self, inimigo, alvos):
        """O turno de UM inimigo -- Step A. Usa o estado PRÓPRIO dele
        (`inimigo.carregando`/`inimigo.preparando_condicao`/`inimigo.
        dados`), nunca a ponte `self.chefe`/`self.carregando` -- exceto o
        despacho pro espelho (`espelhos.turno_do_espelho` só sabe operar
        em `self.chefe`/`self.hp_chefe`, correto hoje porque só
        `inimigos[0]` pode ser espelho). A Represália (Step E) passou a
        receber `inimigo.id` explícito em `_aplicar_dano_do_chefe` --
        deixou de ser uma fronteira presa a `inimigos[0]`, ver
        decisoes.md § Step E."""
        if not condicoes.pode_agir(self, inimigo.id):
            self.registrar(f"{inimigo.nome} está sob efeito e perde a rodada.")
            return

        self._resolver_condicao_pendente(inimigo)
        if inimigo.dados.get("e_espelho"):
            # Step 3, commit 3: os espelhos não carregam golpe nem
            # atacam por RNG puro -- toda a lógica de carregado/
            # ataque normal abaixo é só pra chefe da torre, e
            # continua intocada pra eles. Ver espelhos.py.
            espelhos.turno_do_espelho(self)
        elif random.random() < condicoes.chance_de_erro(self, inimigo.id):
            self.registrar(f"🌬️ Corrente desvia o golpe de {inimigo.nome} — ele erra a rodada.")
        elif inimigo.carregando:
            inimigo.carregando = False
            self.registrar(f"💥 **Golpe carregado** — {inimigo.nome} acerta todo mundo:")
            for c in alvos:
                # Reflexos (mago de raio, Step 2b correção): chance
                # INDIVIDUAL de escapar ileso só deste golpe carregado
                # -- não cancela a carga, não protege os outros alvos
                # do laço, não vale pro ataque normal (ramo abaixo).
                if random.random() < passivas.chance_erro_carregado(c.jogador):
                    self.registrar(f"⚡ {c.nome} lê o movimento e escapa do golpe carregado.")
                    continue
                dano = dano_do_chefe(
                    inimigo.dados, c.s, self.andar_num,
                    defendendo=c.defendendo, carregado=True,
                )
                dano = int(dano * condicoes.multiplicador_dano_causado(self, c.id))
                dano = max(1, int(dano * (1 - _reducao_dano_total(self, c))))
                dano_no_alvo = _aplicar_dano_do_chefe(self, c, dano, inimigo.id)
                aparou = " (aparou)" if c.defendendo else ""
                self.registrar(f"· {c.nome} toma **{dano_no_alvo}**{aparou}")
        # Curto (bloqueia_skill) só impede COMEÇAR a carregar -- um golpe
        # já em preparo (ramo acima) resolve normal, ver decisoes.md
        elif condicoes.pode_lancar_habilidade(self, inimigo.id) and random.random() < CHANCE_CARREGAR:
            inimigo.carregando = True
            self.registrar(f"{inimigo.nome} recua e começa a se preparar.")
        else:
            alvo = condicoes.alvo_forcado(self, inimigo.id) or random.choice(alvos)
            des = alvo.s["atribs"]["destreza"]
            if random.random() < at.chance_esquiva(des, at.destreza_monstro(self.andar_num)):
                self.registrar(f"{alvo.nome} esquivou do ataque.")
            else:
                dano = dano_do_chefe(
                    inimigo.dados, alvo.s, self.andar_num, defendendo=alvo.defendendo
                )
                dano = int(dano * condicoes.multiplicador_dano_causado(self, alvo.id))
                dano = max(1, int(dano * (1 - _reducao_dano_total(self, alvo))))
                dano_no_alvo = _aplicar_dano_do_chefe(self, alvo, dano, inimigo.id)
                self.registrar(f"{inimigo.nome} ataca **{alvo.nome}** — {dano_no_alvo} de dano")

        self._talvez_telegrafar_condicao(inimigo)

    def _resolver_condicao_pendente(self, inimigo):
        """Aplica a condição que ESTE inimigo telegrafou na rodada
        anterior. Se o alvo defendeu, a duração é cortada pela metade —
        é isso que faz Defender virar decisão, não sorte. Véu Cinza
        (efeito de acessório, Step D commit 3) rola ANTES de tudo isso —
        ignorar cancela a aplicação inteira, não só encurta a duração."""
        pend = inimigo.preparando_condicao
        if not pend:
            return
        inimigo.preparando_condicao = None
        alvo = self.por_id(pend["alvo_id"])
        if not alvo or not alvo.ativo:
            self.registrar(f"{pend['emoji']} O alvo de {inimigo.nome} já não está mais na luta.")
            return
        if random.random() < passivas.chance_ignora_condicao(alvo.jogador):
            self.registrar(f"{pend['emoji']} {alvo.nome} ignora **{pend['nome']}** por completo.")
            return
        duracao = pend["duracao"]
        if alvo.defendendo:
            duracao = max(1, duracao // 2)
        condicoes.aplicar(
            self, alvo.id, pend["tipo"], pend["nome"], pend["emoji"],
            duracao, pend["valor"], origem=inimigo.id,
        )

    def _talvez_telegrafar_condicao(self, inimigo):
        """Roll independente do golpe carregado — só inimigos com
        "elemento" (andares 11+) participam."""
        elemento = inimigo.dados.get("elemento")
        if not elemento or inimigo.preparando_condicao is not None:
            return
        if random.random() >= CHANCE_TELEGRAFAR_CONDICAO:
            return
        dados = CONDICOES_ELEMENTO[elemento]
        alvo = random.choice(self.ativos)
        inimigo.preparando_condicao = {**dados, "alvo_id": alvo.id}
        self.registrar(
            f"{dados['emoji']} {inimigo.nome} está reunindo **{dados['nome']}** contra {alvo.nome}."
        )

    def verificar_fase2(self):
        """Chamado sempre que o jogador causa dano ao chefe. Troca ATK/DEF/
        elemento sem resetar nada da luta (fúria, energia, poções,
        condições ativas continuam) — só o andar 15 tem "fase2" no dict."""
        fase2 = self.chefe.get("fase2")
        if not fase2 or self.hp_chefe > self.hp_chefe_max * FASE2_LIMIAR:
            return
        self.materiais_extras.extend(self.chefe.get("drops", []))
        novo_chefe = dict(self.chefe)
        novo_chefe.update(fase2)
        novo_chefe.pop("fase2", None)
        self.chefe = novo_chefe
        self.registrar(
            f"⚡ **{self.chefe['nome']}** — a postura muda por completo. "
            f"Elemento agora é {fase2['elemento']}."
        )


# ---------------------------------------------------------- fim de combate

async def recompensar(luta, combatente):
    """Paga um participante de uma luta vencida — caído ou não, tenha
    aberto a party ou descido só de ajuda. Ninguém leva menos: XP, moedas,
    drop e progressão de andar são cheios pra todo mundo que chega aqui
    (só quem fugiu ou saiu de vez fica fora da lista de quem recebe — ver
    `finalizar_vitoria`). Acima do andar 10 o material de chefe usa
    `chefes_derrotados` por jogador em vez da chance fixa do dict: 100% na
    primeira vitória da conta contra aquele chefe, 15% nas repetições —
    senão entrar só de ajuda (ou morrer de propósito) virava o jeito mais
    eficiente de farmar material (ver decisoes.md). Morte acima do andar
    10 continua resetando andar/andar_max pro 10 (processar_morte, bot.py)
    -- só a VITÓRIA no andar 15 parou de fazer isso (Step B): o jogador
    fica parado lá em cima, e a porta atrás do trono (ver
    `_talvez_oferecer_porta`) é quem decide se ele desce (`rpg viajar`,
    livre) ou atravessa. `chefes_derrotados` não reseta nunca -- os 100%
    de chance são únicos na vida da conta, por chefe; sem isso os 15% de
    repetição nunca seriam alcançados (ver decisoes.md § Roguelike acima
    do Selo)."""
    j, s, chefe = combatente.jogador, combatente.s, luta.chefe

    itens_dropados = []
    if luta.andar_num > ANDAR_ACIMA_DO_SELO:
        vezes = await db.a_vezes_derrotado_chefe(j["user_id"], luta.andar_num)
        chance_material = 1.0 if vezes == 0 else 0.15
        chance_material = min(1.0, chance_material + passivas.bonus_material(j))
        for item, _chance_original in list(chefe.get("drops", [])) + luta.materiais_extras:
            if random.random() < chance_material:
                await db.a_add_item(j["user_id"], item)
                itens_dropados.append(item)
        await db.a_registrar_vitoria_chefe(j["user_id"], luta.andar_num)
    else:
        itens_dropados = H["rolar_drops"](chefe, passivas.bonus_material(j))
        for item in itens_dropados:
            await db.a_add_item(j["user_id"], item)

    xp_ganho = int(chefe["xp"])
    moedas_base = int(chefe["moedas"])
    moedas_ganho = moedas_base + int(moedas_base * passivas.bonus_moedas(j))
    nivel, xp, subiu = H["aplicar_xp"](j, xp_ganho)
    hp_cheio = at.hp_maximo(nivel, s["atribs"]["constituicao"])

    novo_andar = min(luta.andar_num + 1, ANDAR_MAXIMO)
    novo_max = max(j["andar_max"], novo_andar)

    await db.a_atualizar_jogador(
        j["user_id"], hp=hp_cheio, mana=s["mana_max"], xp=xp, nivel=nivel,
        pontos=H["pontos_por_subir"](j, subiu),
        moedas=j["moedas"] + moedas_ganho, andar=novo_andar, andar_max=novo_max,
    )
    return nivel, subiu, xp_ganho, moedas_ganho, itens_dropados


def _texto_item_dropado(item):
    """Nome+emoji pro embed de vitória, puxado de ITENS (constante de
    domínio) com `.get()` em vez de subscript direto -- a chave já foi
    validada contra ITENS na autoria de `game_data.ANDARES`, mas um typo num
    drop novo vira texto degradado aqui, não crash da embed de vitória
    inteira (ver decisoes.md § Padrão — mapa de domínio nunca é subscript
    direto)."""
    dado = ITENS.get(item)
    if not dado:
        return item
    return f"{dado.get('emoji', '')} {dado.get('nome', item)}".strip()


def _texto_contexto_tesouro(andar_num):
    """Linha extra pro embed de vitória quando o drop dessa rodada inclui um
    tesouro de chefe -- diz o que ele é agora: chave de sidequest do
    próprio andar (o Salão da Guilda, destino antigo, foi cortado; ver
    decisoes.md § Corte do Salão da Guilda). Sem número, sem guilda: o
    tesouro é de quem venceu."""
    return (
        "🗝️ Isso é chave, não troféu — não vende, não equipa, não vai pro baú. "
        f"Guarda: alguém no andar {andar_num} vai pedir por ele."
    )


async def finalizar_vitoria(luta):
    """Vitória: todo mundo que estava na luta e não fugiu/saiu recebe igual,
    tenha caído ou não (só fuga e saída por timeout ficam de fora — ver
    decisoes.md § Ajuda de veterano na party)."""
    luta.encerrada = True
    vencedores = [c for c in luta.participantes if not (c.fugiu or c.saiu)]
    novo_andar = min(luta.andar_num + 1, ANDAR_MAXIMO)
    linhas = []
    for c in vencedores:
        nivel, subiu, xp_ganho, moedas_ganho, itens_dropados = await recompensar(luta, c)
        linha = f"**{c.nome}** — +{xp_ganho} XP · +{moedas_ganho} 🪙"
        if itens_dropados:
            linha += " · " + " · ".join(_texto_item_dropado(item) for item in itens_dropados)
        if any(ITENS.get(item, {}).get("tipo") == "tesouro" for item in itens_dropados):
            linha += f"\n· {_texto_contexto_tesouro(luta.andar_num)}"
        if subiu:
            linha += f"\n· subiu para o **nível {nivel}** (+{at.PONTOS_POR_NIVEL * subiu} pontos)"
        linhas.append(linha)

    e = luta.embed(
        titulo=f"Chefe derrotado — {luta.chefe['nome']}",
        rodape=f"Luta encerrada na rodada {luta.rodada}. Quem estava na luta recuperou todo o HP.",
    )
    e.add_field(name="Recompensas", value="\n".join(linhas) or "Ninguém sobrou de pé.", inline=False)
    if luta.chefe.get("fala_derrota"):
        e.add_field(name="🗡️ Últimas palavras", value=f"*{luta.chefe['fala_derrota']}*", inline=False)
    if luta.andar_num == ANDAR_MAXIMO:
        e.add_field(
            name="🌌 O topo, outra vez",
            value=(
                f"Vocês bateram o último andar. A torre guarda cada chefe que já caiu — não é "
                f"a primeira vez pra nenhum deles, então o material de todos agora cai na "
                f"chance baixa, não garantido. Atrás do trono vazio, uma porta que não estava "
                f"lá antes."
            ),
            inline=False,
        )
    elif vencedores:
        e.add_field(
            name=f"⬆️ Andar {novo_andar} destrancado",
            value=f"**{ANDARES[novo_andar]['nome']}**\n{ANDARES[novo_andar]['descricao']}",
            inline=False,
        )
        if novo_andar == ANDAR_DESBLOQUEIA_CARROCA:
            e.add_field(
                name="🐎 Vocês conheceram Bramm",
                value="O carroceiro passa por aqui três vezes por dia e não cobra. `rpg carroca`",
                inline=False,
            )
    return e


# ---------------------------------------------------------- a porta (Step B)
# Fala da Guia, só na PRIMEIRA vitória de cada jogador contra o chefe do
# andar 15 (`db.vezes_derrotado_chefe` -- ver decisoes.md § Step B, "o
# gatilho é ter vencido, não estar vencendo"). Ela era escudeira do Herói;
# ele saiu por aquela porta e não voltou -- ver andares_altos.
# FALA_SOBRE_VOCE[7] pro resto da história.
# Reescrito no cartão "reescrita dos diálogos de fora da torre" -- texto do
# Rafael, substitui a versão anterior ao pé da letra. Batida curta, uma
# linha por vez ("Pare." sozinho é o requisito) -- ver dialogos.linhas()
# pro mesmo mecanismo aplicado a `abertura`/`resposta` em dialogos.py; aqui
# é só um "\n".join() direto porque este texto nunca passa por
# pronomes.concordar() nem pelo resto do pipeline de DIALOGOS.
TEXTO_PLEA_GUIA = "\n".join([
    "Pare.",
    "Eu esperei por essa porta muito antes de você sequer saber que ela existia.",
    "Ele me pediu para esperar. Eu esperei.",
    "Você chegou até aqui porque conseguiu subir a torre.",
    "Eu cheguei porque tinha uma promessa para cumprir.",
    "Então, por tudo o que eu esperei...",
    "Essa porta é minha primeiro.",
])


class BotaoEscolhaPorta(discord.ui.Button):
    """Um par (Ficar/Sair) por vencedor -- botão em View compartilhada
    precisa de estado por jogador (mesma lição da Mortalha, ver
    decisoes.md § Step B): só o dono do par pode clicar, e clicar só
    desabilita OS DOIS BOTÕES DELE, nunca a view inteira -- o resto da
    party continua livre pra escolher, mesmo depois."""

    def __init__(self, vencedor_id, nome, sair):
        estilo = discord.ButtonStyle.primary if sair else discord.ButtonStyle.secondary
        label = f"Sair — {nome}" if sair else f"Ficar — {nome}"
        super().__init__(label=label, style=estilo)
        self.vencedor_id = vencedor_id
        self.sair = sair

    async def callback(self, interaction):
        if interaction.user.id != self.vencedor_id:
            await interaction.response.send_message("Essa escolha não é sua.", ephemeral=True)
            return
        for item in self.view.children:
            if getattr(item, "vencedor_id", None) == self.vencedor_id:
                item.disabled = True
        await interaction.response.edit_message(view=self.view)
        if self.sair:
            mundo.sair_pela_porta(self.vencedor_id)
            e = discord.Embed(
                title=mundo.TITULO_MIRANTE, description=mundo.DESCRICAO_MIRANTE,
                color=discord.Color.blue(),
            )
            e.set_footer(text="`rpg viajar 15` sobe de volta pra torre, sempre de graça.")
            await interaction.followup.send(embed=e, ephemeral=True)
        else:
            mundo.ficar_na_torre(self.vencedor_id)
            texto = f"Você dá as costas pra porta e desce. De volta ao andar {ANDAR_ACIMA_DO_SELO}."
            await interaction.followup.send(texto, ephemeral=True)


class ViewEscolhaPorta(discord.ui.View):
    """Um par de botões por jogador -- cada um escolhe por si, mesmo tendo
    matado o chefe em party (ver decisoes.md § Step B). Timeout comprido
    (é decisão narrativa, não rodada de combate); ninguém escolher não
    trava nada -- dá pra decidir depois, `rpg falar` na porta (ver
    npcs.py, "porta": True -- reaproveita esta mesma view fora de
    qualquer luta, só com um jogador)."""

    def __init__(self, jogadores):
        """`jogadores`: lista de (user_id, nome) -- não precisa ser
        Combatente/luta de verdade."""
        super().__init__(timeout=300)
        self.mensagem = None
        for user_id, nome in jogadores:
            self.add_item(BotaoEscolhaPorta(user_id, nome, sair=False))
            self.add_item(BotaoEscolhaPorta(user_id, nome, sair=True))

    async def on_timeout(self):
        if self.mensagem is None:
            return
        for item in self.children:
            item.disabled = True
        await self.mensagem.edit(view=self)


async def _talvez_oferecer_porta(luta, enviar):
    """Depois de vencer o chefe do andar 15 (nunca antes -- só chamada
    quando a luta já terminou em vitória de verdade), cada vencedor
    escolhe: ficar (desce pro andar 10, o mesmo destino que a vitória
    fazia sozinha antes deste cartão) ou sair pela porta atrás do trono.
    `enviar` é quem manda a mensagem nova -- `interaction.followup.send`
    (clique) ou `self.mensagem.channel.send` (timeout, sem interaction).
    Nunca dispara em raide (andar de referência 7) nem no espelho da
    dungeon (andar 9) -- os dois ficam abaixo do andar 15 sempre.

    A fala da Guia é sobre VER a porta, não vencer o chefe (conserto,
    ver decisoes.md § Step B) -- `mundo.ja_viu_a_porta`/`marcar_porta_
    vista`, não `vezes_derrotado_chefe` (esse já estava gasto pra quem
    tinha zerado a torre antes deste pacote)."""
    if luta.andar_num != ANDAR_MAXIMO or luta.inimigos_ativos:
        return
    vencedores = [c for c in luta.participantes if not (c.fugiu or c.saiu)]
    if not vencedores:
        return

    primeiros = []
    for c in vencedores:
        if not mundo.ja_viu_a_porta(c.jogador):
            mundo.marcar_porta_vista(c.id)
            primeiros.append(c.nome)

    e = discord.Embed(
        title="Atrás do trono, uma porta",
        description=(
            "O trono está vazio, como sempre esteve. A porta que não devia estar ali "
            "continua ali. Cada um decide por si."
        ),
        color=discord.Color.dark_gold(),
    )
    for nome in primeiros:
        e.add_field(name=f"🕯️ A Guia detém {nome}", value=TEXTO_PLEA_GUIA, inline=False)

    view = ViewEscolhaPorta([(c.id, c.nome) for c in vencedores])
    view.mensagem = await enviar(embed=e, view=view)


async def finalizar_derrota(luta):
    """Ninguem sobrou: cada um que caiu paga a penalidade."""
    luta.encerrada = True
    perdas = []
    for c in luta.participantes:
        if c.caiu:
            perda, salvo_conduto = await H["a_processar_morte"](c.jogador, c.s)
            texto = "usou o Salvo-Conduto" if salvo_conduto else f"perdeu {perda} 🪙"
            perdas.append(f"**{c.nome}** {texto}")
    e = luta.embed(
        titulo=f"A party caiu — {luta.chefe['nome']}",
        cor=COR_DERROTA,
        rodape=f"Caíram na rodada {luta.rodada}. O chefe volta com o HP cheio.",
    )
    e.add_field(
        name="Derrota",
        value="\n".join(perdas) or "Ninguém sobrou.",
        inline=False,
    )
    return e


async def encerrar_por_abandono(luta):
    """Todo mundo fugiu ou sumiu — a luta acaba sem vencedor."""
    luta.encerrada = True
    fugiram = [c.nome for c in luta.participantes if c.fugiu]
    sumiram = [c.nome for c in luta.participantes if c.saiu]
    partes = []
    if fugiram:
        partes.append("Fugiram: " + ", ".join(fugiram))
    if sumiram:
        partes.append("Sumiram no meio: " + ", ".join(sumiram))
    e = luta.embed(
        titulo=f"A luta acabou — {luta.chefe['nome']}",
        cor=COR_FUGA,
        rodape="Quem fugiu não gastou o cooldown. Quem sumiu, gastou.",
    )
    e.add_field(name="Sem vencedor", value="\n".join(partes) or "—", inline=False)
    for c in luta.participantes:
        if c.fugiu:
            await db.a_set_cooldown(c.id, "boss", 0)
    return e


# ------------------------------------------------------------------- views

class MenuPocoes(discord.ui.View):
    def __init__(self, painel, combatente):
        super().__init__(timeout=TIMEOUT_RODADA)
        self.painel = painel
        self.combatente = combatente
        for linha in pocoes_na_mochila(combatente.id):
            if pode_usar(combatente, linha["item"]):
                self.add_item(BotaoPocao(linha["item"], ITENS[linha["item"]], linha["qtd"]))
        self.add_item(BotaoVoltar())

    async def interaction_check(self, interaction):
        if interaction.user.id != self.combatente.id:
            await interaction.response.send_message("Essa mochila não é sua.", ephemeral=True)
            return False
        return True


class BotaoPocao(discord.ui.Button):
    def __init__(self, chave, dados, qtd):
        super().__init__(
            label=f"{dados['nome']} ({qtd})",
            emoji=dados["emoji"],
            style=discord.ButtonStyle.success,
        )
        self.chave = chave

    async def callback(self, interaction):
        await interaction.response.defer()
        painel = self.view.painel
        c = self.view.combatente
        if not await db.a_remove_item(c.id, self.chave, 1):
            await responder(interaction, painel.luta.embed(), painel)
            return
        dado = ITENS[self.chave]
        campo, valor = at.restauracao_do_item(dado, c.s["hp_max"], c.s["mana_max"])
        if campo == "mana":
            antes = max(0, c.mana)
            c.mana = min(c.s["mana_max"], antes + valor)
            ganho, rotulo = c.mana - antes, "mana"
        else:
            valor = int(valor * (1 - condicoes.reducao_cura_recebida(painel.luta, c.id)))
            antes = max(0, c.hp)
            c.hp = min(c.s["hp_max"], antes + valor)
            ganho, rotulo = c.hp - antes, "HP"
        if eh_elixir(self.chave):
            c.elixires_usados += 1
        else:
            c.pocoes_usadas += 1
        painel.luta.registrar(
            f"{dado['emoji']} {c.nome} bebe **{dado['nome']}** — +{ganho} {rotulo}"
        )
        await painel.registrar_acao(interaction, c, "pocao")


class BotaoVoltar(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Voltar", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction):
        await interaction.response.defer()
        painel = self.view.painel
        await responder(interaction, painel.luta.embed(), painel)


# --------------------------------------------------------- efeitos de habilidade
# Uma função por skill, disparada por _lancar_habilidade(). O efeito acontece
# no clique do botão, antes da rodada resolver de verdade — mesmo timing das
# poções (BotaoPocao).
#
# Duração de condições tipo "buff consultado depois" (vulneravel, reduz_dano,
# bonus_critico, pula_turno): condicoes.tick() já desconta 1 rodada na MESMA
# chamada em que a skill foi lançada, antes de qualquer ataque ou turno do
# chefe dessa rodada ser resolvido. Pra sobreviver a esse desconto e ainda
# valer pelas N rodadas prometidas na descrição da skill, a duração passada
# pra condicoes.aplicar() precisa ser N+1. Isso NÃO vale pra dano_por_rodada/
# cura_por_rodada (sangramento, regeneração) — esses já aplicam o efeito
# dentro do próprio tick(), então duração ali é literal (N = N aplicações).

def _multiplicador_afinidade(c):
    arma = ITENS.get(c.jogador["arma"], {})
    return hab.fator_afinidade(c.jogador["classe"], arma)


def _bonus_arma_de(c):
    return ITENS.get(c.jogador["arma"], {}).get("atk", 0)


def _elemento_arma_de(c):
    return ITENS.get(c.jogador["arma"], {}).get("elemento")


def _fator_elemento_arma(luta, c):
    """Multiplicador de dano da arma elemental de c contra o elemento do
    chefe (1.0 se qualquer um dos dois não tiver elemento)."""
    return multiplicador_elemento(_elemento_arma_de(c), luta.chefe.get("elemento"))


def _aplicar_ou_renovar_condicao_arma(luta, c, dados, duracao):
    """Condição já ativa no chefe refresca a duração em vez de duplicar --
    nunca ENCOLHE uma duração já ativa (max, não overwrite). Isso importa
    pro Travamento (gelo): quando Prisão de Cristal (skill) já setou uma
    duração mais longa (regra N+1 + Inverno Constante) e o MESMO golpe
    também rola a arma elemental por cima, sem o max() a rolagem da arma
    sobrescreveria com o valor cru, mais curto, desfazendo o bônus da
    skill. origem=c.id é o que faz `drena` (Sanguessuga) devolver cura pra
    c em condicoes._tick_dano."""
    existente = next(
        (cond for cond in luta.condicoes if cond["alvo"] == "chefe" and cond["nome"] == dados["nome"]),
        None,
    )
    if existente:
        existente["duracao"] = max(existente["duracao"], duracao)
        luta.registrar(f"{dados['emoji']} **{dados['nome']}** renovado em {luta.chefe['nome']}.")
        return
    condicoes.aplicar(
        luta, "chefe", dados["tipo"], dados["nome"], dados["emoji"],
        duracao, dados["valor"], origem=c.id, drena=dados.get("drena"),
    )


def _empilhar_condicao_arma(luta, c, dados, max_stacks):
    """Combustão (mago de fogo, Step 2b): a Brasa que o jogador aplica
    empilha até max_stacks em vez de refrescar -- mesma lógica de
    Sangramento em _efeito_golpe_aberto (já testada em
    tests/test_condicoes.py), generalizada aqui pra qualquer condição
    dano_por_rodada da arma elemental que precise empilhar."""
    stacks = [
        cond for cond in luta.condicoes
        if cond["tipo"] == "dano_por_rodada" and cond["nome"] == dados["nome"] and cond["alvo"] == "chefe"
    ]
    if len(stacks) >= max_stacks:
        stacks[0]["duracao"] = dados["duracao"]
        luta.registrar(f"{dados['emoji']} **{dados['nome']}** renovado ({len(stacks)}/{max_stacks} pilhas).")
        return
    condicoes.aplicar(
        luta, "chefe", dados["tipo"], dados["nome"], dados["emoji"],
        dados["duracao"], dados["valor"], origem=c.id, drena=dados.get("drena"),
    )


def _talvez_condicionar_chefe(luta, c):
    """25% de chance por golpe que acerta o chefe de amarrar a condição da
    arma elemental de c nele (CONDICOES_ARMA_ELEMENTAL) -- teto de uma
    aplicação por elemento por rodada (senão uma party de 4 elementais do
    mesmo elemento chega perto de 100% de uptime, ver decisoes.md § Dano
    elemental).

    Brasa (fogo) com Combustão (Step 2b) empilha em vez de refrescar --
    passivas.empilha_brasa(c.jogador) decide. Travamento (gelo) consulta
    passivas.bonus_duracao_travamento (Inverno Constante) -- é bônus de
    quem APLICA (c), não de quem sofre."""
    elemento = _elemento_arma_de(c)
    dados = CONDICOES_ARMA_ELEMENTAL.get(elemento)
    if not dados or elemento in luta.elementos_aplicados_rodada:
        return
    if random.random() >= CHANCE_CONDICAO_ELEMENTO_ARMA:
        return
    luta.elementos_aplicados_rodada.add(elemento)
    if elemento == "fogo" and passivas.empilha_brasa(c.jogador):
        _empilhar_condicao_arma(luta, c, dados, MAX_STACKS_BRASA)
        return
    duracao = dados["duracao"]
    if dados["tipo"] == "pula_turno":
        duracao += passivas.bonus_duracao_travamento(c.jogador)
    _aplicar_ou_renovar_condicao_arma(luta, c, dados, duracao)


def _rolar_critico(luta, c):
    """True se o Sangue Frio (assassino) força este golpe a critar --
    consome o "uma vez por luta" do combatente na hora, mesmo golpe de
    skill com múltiplos hits (Corte Rápido) só deixa o PRIMEIRO sair
    garantido. Ver passivas.critico_garantido -- essa função stateless não
    sabe (nem pode saber) se o combatente já usou o dele nesta luta."""
    forcado = passivas.critico_garantido(c.jogador, luta.rodada) and not c.sangue_frio_disparado
    if forcado:
        c.sangue_frio_disparado = True
    return forcado


def _rolar_ataque_normal(luta, c, atk, defesa, critico):
    """Mesmo golpe normal de sempre (H["calcular_dano"]), só que passando
    as duas passivas de crítico do Ladino -- Sangue Frio força o primeiro
    golpe da rodada 1, Olho de Águia aumenta o multiplicador quando critica.
    Duplicado como dois pontos de chamada em Luta (rodada normal e
    on_timeout) -- ver decisoes.md § Step 2a pra não deixar só um mudado."""
    forcado = _rolar_critico(luta, c)
    return H["calcular_dano"](
        atk, defesa, critico,
        critico_forcado=forcado,
        multiplicador_critico_extra=passivas.multiplicador_critico(c.jogador),
    )


def _rolar_dano_habilidade(luta, c, multiplicador, critico_extra=0.0, atributo=None):
    """Dano bruto de uma skill: mesma variação (±15%) e crítico de um golpe
    normal, sobre a MESMA base do ataque normal (atributo + atk da arma) —
    é isso que faz o multiplicador ser literalmente "quantos ataques
    básicos essa skill vale", em qualquer nível e com qualquer arma. Ver
    decisoes.md § Dano de skill abaixo do ataque básico.

    `atributo`: só Punho do Silêncio (Step 2d) passa isso -- escala em DES
    em vez do atributo_habilidade normal do Orador (INT). Ver hab.poder_base."""
    base = hab.poder_base(c.jogador, _bonus_arma_de(c), atributo) * multiplicador * _multiplicador_afinidade(c)
    bruto = base * random.uniform(0.85, 1.15)
    foi_critico = _rolar_critico(luta, c) or random.random() < (c.s["critico"] + critico_extra)
    if foi_critico:
        bruto *= at.MULTIPLICADOR_CRITICO * passivas.multiplicador_critico(c.jogador)
    return bruto


def _efeito_dardo_arcano(luta, c, dados):
    dano = max(1, int(_rolar_dano_habilidade(luta, c, MULTIPLICADOR_DARDO_ARCANO) * _fator_elemento_arma(luta, c)))
    dano = _aplicar_sombra(luta, c, dano)
    luta.hp_chefe -= dano
    luta.verificar_fase2()
    luta.registrar(
        f"{dados['emoji']} {c.nome} crava **{dados['nome']}** — {dano} de dano, ignorando a defesa."
    )
    _talvez_condicionar_chefe(luta, c)


def _efeito_ruptura(luta, c, dados):
    condicoes.aplicar(
        luta, "chefe", "vulneravel", dados["nome"], dados["emoji"],
        duracao=4, valor=VULNERAVEL_RUPTURA, origem=c.id,
    )


def _efeito_golpe_aberto(luta, c, dados):
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, MULTIPLICADOR_GOLPE_ABERTO), _defesa_efetiva(luta, c))
    dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
    dano = _aplicar_sombra(luta, c, dano)
    luta.hp_chefe -= dano
    luta.verificar_fase2()
    luta.registrar(f"{dados['emoji']} {c.nome} abre **{dados['nome']}** — {dano} de dano.")
    # o sangramento aplicado abaixo usa VALOR_SANGRAMENTO fixo, nunca o
    # `dano` do golpe que abriu -- Sombra dobra o golpe, não o DoT que ele
    # deixa, e as rodadas seguintes tickam no valor normal (ver decisoes.md).
    stacks = [
        cond for cond in luta.condicoes
        if cond["tipo"] == "dano_por_rodada" and cond["nome"] == "Sangramento" and cond["alvo"] == "chefe"
    ]
    if len(stacks) >= MAX_STACKS_SANGRAMENTO:
        stacks[0]["duracao"] = 3
        luta.registrar(f"🩸 Sangramento renovado ({len(stacks)}/{MAX_STACKS_SANGRAMENTO} pilhas).")
    else:
        condicoes.aplicar(
            luta, "chefe", "dano_por_rodada", "Sangramento", "🩸",
            duracao=3, valor=VALOR_SANGRAMENTO, origem=c.id,
        )
    _talvez_condicionar_chefe(luta, c)


def _efeito_pancada_atordoante(luta, c, dados):
    forca = int(c.jogador["forca"] or 0)
    chance = min(TETO_STUN_ATORDOANTE, 0.05 + 0.01 * forca)
    if random.random() < chance:
        condicoes.aplicar(
            luta, "chefe", "pula_turno", dados["nome"], dados["emoji"],
            duracao=2, valor=0, origem=c.id,
        )
        luta.registrar(f"{dados['emoji']} {c.nome} atordoa {luta.chefe['nome']}!")
    else:
        luta.registrar(
            f"{dados['emoji']} {c.nome} tenta atordoar {luta.chefe['nome']} "
            f"e falha ({chance * 100:.0f}%)."
        )


def _efeito_corte_rapido(luta, c, dados):
    golpes = []
    total = 0
    for _ in range(2):
        dano = at.aplicar_defesa(
            _rolar_dano_habilidade(luta, c, MULTIPLICADOR_CORTE_RAPIDO, critico_extra=BONUS_CRITICO_CORTE_RAPIDO),
            _defesa_efetiva(luta, c),
        )
        dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
        dano = _aplicar_sombra(luta, c, dano)
        luta.hp_chefe -= dano
        luta.verificar_fase2()
        total += dano
        golpes.append(str(dano))
        _talvez_condicionar_chefe(luta, c)
    luta.registrar(
        f"{dados['emoji']} {c.nome} desfere **{dados['nome']}** — "
        f"{' + '.join(golpes)} = {total} de dano."
    )


def _efeito_ponto_cego(luta, c, dados):
    condicoes.aplicar(
        luta, c.id, "bonus_critico", dados["nome"], dados["emoji"],
        duracao=4, valor=BONUS_CRITICO_PONTO_CEGO, origem=c.id,
    )


def _efeito_palavra_de_alento(luta, c, dados, alvo_id):
    condicoes.aplicar(
        luta, alvo_id, "cura_por_rodada", dados["nome"], dados["emoji"],
        duracao=2, valor=CURA_POR_RODADA_ALENTO, origem=c.id,
        bonus_cura_ignorado=passivas.fracao_reducao_cura_ignorada(c.jogador),   # Bênção, Step 2d
    )


def _efeito_voto_de_ferro(luta, c, dados):
    for alvo in luta.ativos:
        condicoes.aplicar(
            luta, alvo.id, "reduz_dano", dados["nome"], dados["emoji"],
            duracao=3, valor=REDUCAO_VOTO_DE_FERRO, origem=c.id,
        )


def _efeito_golpe_fatal(luta, c, dados):
    """Assassino: escala com o quanto o CHEFE já perdeu de HP -- 1.2x com
    o alvo cheio, até 3.2x (MULTIPLICADOR_GOLPE_FATAL_BASE +
    BONUS_GOLPE_FATAL_EXECUCAO) com o alvo perto de 0. Aplica defesa
    normalmente, ao contrário de Flecha Perfurante logo abaixo."""
    fracao_perdida = 1 - max(0, luta.hp_chefe) / luta.hp_chefe_max
    multiplicador = MULTIPLICADOR_GOLPE_FATAL_BASE + BONUS_GOLPE_FATAL_EXECUCAO * fracao_perdida
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, multiplicador), _defesa_efetiva(luta, c))
    dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
    dano = _aplicar_sombra(luta, c, dano)
    luta.hp_chefe -= dano
    luta.verificar_fase2()
    luta.registrar(f"{dados['emoji']} {c.nome} crava **{dados['nome']}** — {dano} de dano.")
    _talvez_condicionar_chefe(luta, c)


def _efeito_flecha_perfurante(luta, c, dados):
    """Arqueiro: mesmo caminho do Dardo Arcano -- ignora a defesa do chefe."""
    dano = max(1, int(_rolar_dano_habilidade(luta, c, MULTIPLICADOR_FLECHA_PERFURANTE) * _fator_elemento_arma(luta, c)))
    dano = _aplicar_sombra(luta, c, dano)
    luta.hp_chefe -= dano
    luta.verificar_fase2()
    luta.registrar(
        f"{dados['emoji']} {c.nome} crava **{dados['nome']}** — {dano} de dano, ignorando a defesa."
    )
    _talvez_condicionar_chefe(luta, c)


def _efeito_prisao_de_cristal(luta, c, dados):
    """Mago de Gelo: dano em cima da MESMA base do ataque normal (com
    defesa, ao contrário do Dardo Arcano) + Travamento no chefe --
    TRAVAMENTO_PRISAO_DE_CRISTAL_RODADAS (1) rodada, regra N+1 (duracao=2)
    +passivas.bonus_duracao_travamento (Inverno Constante)."""
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, MULTIPLICADOR_PRISAO_DE_CRISTAL), _defesa_efetiva(luta, c))
    dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
    dano = _aplicar_sombra(luta, c, dano)
    luta.hp_chefe -= dano
    luta.verificar_fase2()
    luta.registrar(f"{dados['emoji']} {c.nome} conjura **{dados['nome']}** — {dano} de dano.")
    duracao = TRAVAMENTO_PRISAO_DE_CRISTAL_RODADAS + 1 + passivas.bonus_duracao_travamento(c.jogador)
    condicoes.aplicar(
        luta, "chefe", "pula_turno", "Travamento", "🔒",
        duracao=duracao, valor=0, origem=c.id,
    )
    _talvez_condicionar_chefe(luta, c)


def _efeito_conflagracao(luta, c, dados):
    """Mago de Fogo: dano em cima da MESMA base do ataque normal (com
    defesa, ver decisoes.md § Step 2b) que CRESCE com a Brasa já
    acumulada no alvo -- conta as pilhas ANTES de aplicar a Brasa deste
    golpe (a que ele está prestes a acrescentar não conta pra si mesma).
    Sempre aplica Brasa -- empilha com Combustão, refresca sem ela (mesmo
    caminho da arma elemental, ver _talvez_condicionar_chefe)."""
    stacks_brasa = len([
        cond for cond in luta.condicoes
        if cond["tipo"] == "dano_por_rodada" and cond["nome"] == "Brasa" and cond["alvo"] == "chefe"
    ])
    multiplicador = MULTIPLICADOR_CONFLAGRACAO + BONUS_CONFLAGRACAO_POR_STACK * stacks_brasa
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, multiplicador), _defesa_efetiva(luta, c))
    dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
    dano = _aplicar_sombra(luta, c, dano)
    luta.hp_chefe -= dano
    luta.verificar_fase2()
    luta.registrar(f"{dados['emoji']} {c.nome} conjura **{dados['nome']}** — {dano} de dano.")
    dados_brasa = CONDICOES_ARMA_ELEMENTAL["fogo"]
    if passivas.empilha_brasa(c.jogador):
        _empilhar_condicao_arma(luta, c, dados_brasa, MAX_STACKS_BRASA)
    else:
        _aplicar_ou_renovar_condicao_arma(luta, c, dados_brasa, dados_brasa["duracao"])
    # a skill já garantiu Brasa nesta rodada -- não deixa o proc da arma
    # elemental (chamado logo abaixo) aplicar ou empilhar de novo em cima
    luta.elementos_aplicados_rodada.add("fogo")
    _talvez_condicionar_chefe(luta, c)


def _efeito_interrupcao(luta, c, dados, alvo_id):
    """Mago de Raio: dano em cima da MESMA base do ataque normal (com
    defesa, ver decisoes.md § Step 2b) contra o inimigo ESCOLHIDO e, se
    ELE estiver CARREGANDO um golpe, cancela a carga dele.

    Step E generalizou o alvo (`dados["alvo"] = "inimigo_escolhido"`,
    infra que existia desde o Step A sem nenhuma skill usando) porque
    um bandido de estrada carregando não é sempre `inimigos[0]` --
    antes disto, Interrupção sempre batia no primeiro inimigo da luta,
    não importa qual o jogador escolhesse (ver decisoes.md § Step E).
    `alvo_id` vem de `MenuAlvoHabilidade`/`BotaoHabilidade` (resolve
    direto quando só existe um inimigo -- luta solo contra a torre,
    hoje sempre; abre o menu com dois ou mais).

    FRONTEIRA DURA, NÃO GENERALIZAR: isto cancela especificamente
    `inimigo.carregando` -- o golpe pesado que qualquer inimigo prepara
    em `_turno_de_um_inimigo` (ver `CHANCE_CARREGAR`). NUNCA uma
    habilidade de chefe -- nenhum chefe tem uma ainda. Se uma
    habilidade de chefe precisar ser interrompível um dia, é uma
    consulta NOVA, não a reutilização deste `if inimigo.carregando`.
    Ver tests/test_mago_raio.py, teste que trava exatamente essa
    fronteira.

    Contra inimigo que não está carregando, a skill é só dano -- reativa
    de propósito, sem efeito de consolação."""
    inimigo = luta.inimigo_por_id(alvo_id) or luta.inimigos[0]
    dano = at.aplicar_defesa(
        _rolar_dano_habilidade(luta, c, MULTIPLICADOR_INTERRUPCAO), _defesa_efetiva(luta, c, inimigo),
    )
    dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
    dano = _aplicar_sombra(luta, c, dano)
    inimigo.hp -= dano
    luta.verificar_fase2()
    if inimigo.carregando:
        inimigo.carregando = False
        luta.registrar(
            f"{dados['emoji']} {c.nome} conjura **{dados['nome']}** — {dano} de dano e interrompe a carga de {inimigo.nome}!"
        )
    else:
        luta.registrar(f"{dados['emoji']} {c.nome} conjura **{dados['nome']}** — {dano} de dano em {inimigo.nome}.")
    _talvez_condicionar_chefe(luta, c)


def _efeito_muralha_de_escudos(luta, c, dados):
    """Soldado: dano em cima da MESMA base do ataque normal (com defesa,
    ver decisoes.md § Step 2c) + `redireciona` (o chefe é obrigado a
    atacar c -- condicoes.alvo_forcado já existe e não tinha usuário
    nenhum no jogo) + `reduz_dano` em c, os dois por
    DURACAO_MURALHA_RODADAS (2), regra N+1 (duracao=3)."""
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, MULTIPLICADOR_MURALHA_DE_ESCUDOS), _defesa_efetiva(luta, c))
    dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
    dano = _aplicar_sombra(luta, c, dano)
    luta.hp_chefe -= dano
    luta.verificar_fase2()
    luta.registrar(f"{dados['emoji']} {c.nome} ergue **{dados['nome']}** — {dano} de dano.")
    duracao = DURACAO_MURALHA_RODADAS + 1
    condicoes.aplicar(
        luta, "chefe", "redireciona", dados["nome"], dados["emoji"],
        duracao=duracao, valor=c.id, origem=c.id,
    )
    condicoes.aplicar(
        luta, c.id, "reduz_dano", dados["nome"], dados["emoji"],
        duracao=duracao, valor=REDUCAO_MURALHA_DE_ESCUDOS, origem=c.id,
    )
    _talvez_condicionar_chefe(luta, c)


def _efeito_golpe_oportunista(luta, c, dados):
    """Mercenário: espelho do Golpe Fatal (Step 2a) -- em vez de escalar
    com o quanto o CHEFE já perdeu de HP, escala com o quanto O PRÓPRIO
    GUERREIRO (c.hp / c.s["hp_max"], nunca o HP do chefe) já perdeu --
    2.0x com HP cheio, até 3.0x (MULTIPLICADOR_GOLPE_OPORTUNISTA +
    BONUS_GOLPE_OPORTUNISTA) com c perto de 0. Aplica defesa normalmente."""
    fracao_perdida = 1 - max(0, c.hp) / c.s["hp_max"]
    multiplicador = MULTIPLICADOR_GOLPE_OPORTUNISTA + BONUS_GOLPE_OPORTUNISTA * fracao_perdida
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, multiplicador), _defesa_efetiva(luta, c))
    dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
    dano = _aplicar_sombra(luta, c, dano)
    luta.hp_chefe -= dano
    luta.verificar_fase2()
    luta.registrar(f"{dados['emoji']} {c.nome} crava **{dados['nome']}** — {dano} de dano.")
    _talvez_condicionar_chefe(luta, c)


def _efeito_sequencia(luta, c, dados):
    """Espadachim: três golpes em cima da MESMA base do ataque normal (com
    defesa), cada um mais forte que o anterior -- MULTIPLICADORES_
    SEQUENCIA (0.5, 0.7, 0.8), soma 2.0. Cada golpe rola crítico separado,
    mesmo padrão do Corte Rápido (_rolar_dano_habilidade chamada uma vez
    por golpe, não uma vez só pra todos)."""
    golpes = []
    total = 0
    for multiplicador in MULTIPLICADORES_SEQUENCIA:
        dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, multiplicador), _defesa_efetiva(luta, c))
        dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
        dano = _aplicar_sombra(luta, c, dano)
        luta.hp_chefe -= dano
        luta.verificar_fase2()
        total += dano
        golpes.append(str(dano))
        _talvez_condicionar_chefe(luta, c)
    luta.registrar(
        f"{dados['emoji']} {c.nome} encadeia **{dados['nome']}** — "
        f"{' + '.join(golpes)} = {total} de dano."
    )


def _efeito_punho_do_silencio(luta, c, dados):
    """Monge: única skill do jogo que escala em DES em vez do
    atributo_habilidade normal da classe (INT pro Orador) --
    `_rolar_dano_habilidade(..., atributo="destreza")`. Aplica defesa
    normalmente + `bloqueia_skill` no chefe (mesma condição de Choque,
    andares 11+) por DURACAO_BLOQUEIA_SKILL_PUNHO_RODADAS (2), regra N+1
    (duracao=3). Recupera mana por Corpo Desperto -- o único jeito do
    monge sustentar mais de um golpe numa luta longa."""
    dano = at.aplicar_defesa(
        _rolar_dano_habilidade(luta, c, MULTIPLICADOR_PUNHO_DO_SILENCIO, atributo="destreza"),
        _defesa_efetiva(luta, c),
    )
    dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
    dano = _aplicar_sombra(luta, c, dano)
    luta.hp_chefe -= dano
    luta.verificar_fase2()
    luta.registrar(f"{dados['emoji']} {c.nome} crava **{dados['nome']}** — {dano} de dano.")
    duracao = DURACAO_BLOQUEIA_SKILL_PUNHO_RODADAS + 1
    condicoes.aplicar(
        luta, "chefe", "bloqueia_skill", dados["nome"], dados["emoji"],
        duracao=duracao, valor=0, origem=c.id,
    )
    _recuperar_mana_por_golpe(c)
    _talvez_condicionar_chefe(luta, c)


def _efeito_graca_divina(luta, c, dados):
    """Clérigo: duas versões no MESMO slot de skill, decidido por
    `luta.em_party` (congelado na criação da luta, Step 2d commit 1).

    PARTY (Reerguer): levanta o primeiro aliado caído que encontrar (não
    há seletor de alvo -- ponto de partida pra playtest, escolha
    simplificada) com FRACAO_HP_REERGUER do HP máximo. Marca `acao` e
    `defendendo` pra ele não travar o "esperando todo mundo escolher" e
    ganhar a proteção de Defender nesta rodada -- ele acabou de ser
    puxado de volta, não vai atacar no mesmo golpe. Limite de 2 por LUTA
    é checado DE NOVO aqui (não só em `_pode_lancar_graca_divina`, que só
    filtra o menu no INÍCIO da rodada): com dois clérigos na mesma party,
    os dois podem ver o botão disponível e escolher Reerguer na mesma
    rodada -- sem essa segunda checagem, os dois resolveriam e o limite
    seria furado.

    SOLO (Chama Divina): dano puro em cima da MESMA base do ataque normal
    (com defesa)."""
    if luta.em_party:
        if luta.reergueres_usados >= LIMITE_REERGUER_POR_LUTA:
            luta.registrar(f"{dados['emoji']} {c.nome} conjura **{dados['nome']}**, mas o limite da luta já foi atingido.")
            return
        caido = next((outro for outro in luta.participantes if outro.caiu), None)
        if caido is None:
            luta.registrar(f"{dados['emoji']} {c.nome} conjura **{dados['nome']}**, mas ninguém precisava.")
            return
        caido.caiu = False
        caido.hp = int(FRACAO_HP_REERGUER * caido.s["hp_max"])
        caido.acao = "defender"
        caido.defendendo = True
        caido.salvar_estado()
        luta.reergueres_usados += 1
        luta.registrar(
            f"{dados['emoji']} {c.nome} ergue **{caido.nome}** de volta à luta com "
            f"{caido.hp} HP! ({luta.reergueres_usados}/{LIMITE_REERGUER_POR_LUTA})"
        )
    else:
        dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, MULTIPLICADOR_CHAMA_DIVINA), _defesa_efetiva(luta, c))
        dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
        dano = _aplicar_sombra(luta, c, dano)
        luta.hp_chefe -= dano
        luta.verificar_fase2()
        luta.registrar(f"{dados['emoji']} {c.nome} conjura **Chama Divina** — {dano} de dano.")
        _talvez_condicionar_chefe(luta, c)


def _efeito_represalia(luta, c, dados):
    """Paladino: dano em cima da MESMA base do ataque normal (com
    defesa) + aplica `reflete_dano` em SI MESMO (`c.id`, não no chefe) --
    por DURACAO_REFLEXAO_REPRESALIA_RODADAS (3) rodadas, regra N+1
    (duracao=4), qualquer dano que o paladino tomar do chefe nesse
    período (direto ou absorvido de um aliado por Juramento) devolve
    FRACAO_REFLEXAO_REPRESALIA de volta ao chefe -- ver `_refletir_se_
    paladino`/`_aplicar_dano_do_chefe`, que é quem de fato consulta essa
    condição."""
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, MULTIPLICADOR_REPRESALIA), _defesa_efetiva(luta, c))
    dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
    dano = _aplicar_sombra(luta, c, dano)
    luta.hp_chefe -= dano
    luta.verificar_fase2()
    luta.registrar(f"{dados['emoji']} {c.nome} conjura **{dados['nome']}** — {dano} de dano.")
    condicoes.aplicar(
        luta, c.id, "reflete_dano", dados["nome"], dados["emoji"],
        duracao=DURACAO_REFLEXAO_REPRESALIA_RODADAS + 1, valor=FRACAO_REFLEXAO_REPRESALIA, origem=c.id,
    )
    _talvez_condicionar_chefe(luta, c)


EFEITOS_HABILIDADE = {
    "dardo_arcano": _efeito_dardo_arcano,
    "ruptura": _efeito_ruptura,
    "golpe_aberto": _efeito_golpe_aberto,
    "pancada_atordoante": _efeito_pancada_atordoante,
    "corte_rapido": _efeito_corte_rapido,
    "ponto_cego": _efeito_ponto_cego,
    "palavra_de_alento": _efeito_palavra_de_alento,
    "voto_de_ferro": _efeito_voto_de_ferro,
    "golpe_fatal": _efeito_golpe_fatal,
    "flecha_perfurante": _efeito_flecha_perfurante,
    "prisao_de_cristal": _efeito_prisao_de_cristal,
    "conflagracao": _efeito_conflagracao,
    "interrupcao": _efeito_interrupcao,
    "muralha_de_escudos": _efeito_muralha_de_escudos,
    "golpe_oportunista": _efeito_golpe_oportunista,
    "sequencia": _efeito_sequencia,
    "punho_do_silencio": _efeito_punho_do_silencio,
    "graca_divina": _efeito_graca_divina,
    "represalia": _efeito_represalia,
}


# Step A, commit 3: os dois tipos de "alvo escolhido pelo jogador" que
# BotaoAlvoHabilidade/MenuAlvoHabilidade sabem listar -- "aliado_escolhido"
# é o único usado hoje (Palavra de Alento); "inimigo_escolhido" é infra
# pura, sem nenhuma skill usando ainda (nenhum chefe tem companhia, ver
# decisoes.md § Step A). Generalizar o widget existente em vez de escrever
# um novo -- é o que o cartão pede.
TIPOS_ALVO_ESCOLHIDO = {"aliado_escolhido", "inimigo_escolhido"}


def _alvos_possiveis(luta, dados):
    """Quem pode ser alvo de uma skill "aliado_escolhido"/
    "inimigo_escolhido" -- cada item tem `.id`/`.nome` (Combatente ou
    Inimigo, os dois já têm os dois), então BotaoAlvoHabilidade nem
    precisa saber qual dos dois recebeu."""
    tipo = dados.get("alvo")
    if tipo == "aliado_escolhido":
        return luta.ativos
    if tipo == "inimigo_escolhido":
        return luta.inimigos_ativos
    return []


def _lancar_habilidade(luta, c, chave, dados, alvo_id=None):
    if dados["recurso"] == "mana":
        c.mana -= dados["custo"]
    elif dados["recurso"] == "furia":
        c.furia -= dados["custo"]
    else:
        c.energia -= dados["custo"]
    efeito = EFEITOS_HABILIDADE[chave]
    if dados.get("alvo") in TIPOS_ALVO_ESCOLHIDO:
        efeito(luta, c, dados, alvo_id)
    else:
        efeito(luta, c, dados)


class MenuHabilidades(discord.ui.View):
    def __init__(self, painel, combatente):
        super().__init__(timeout=TIMEOUT_RODADA)
        self.painel = painel
        self.combatente = combatente
        for chave, dados in hab.lancaveis(combatente.jogador, combatente.recurso_atual()).items():
            # Graça Divina (clérigo, Step 2d): em party, Reerguer só some
            # do menu se não tiver caído pra levantar ou já tiver usado os
            # 2 da luta -- ver _pode_lancar_graca_divina. Único caso hoje
            # em que uma skill lançável (custo cabe) ainda assim pode
            # ficar indisponível por causa de estado da LUTA, não do
            # jogador -- por isso é um `if` aqui, não algo em hab.py
            # (que não sabe nada sobre `luta`).
            if chave == "graca_divina" and not _pode_lancar_graca_divina(painel.luta, combatente):
                continue
            self.add_item(BotaoHabilidade(chave, dados))
        self.add_item(BotaoVoltar())

    async def interaction_check(self, interaction):
        if interaction.user.id != self.combatente.id:
            await interaction.response.send_message("Essas não são suas habilidades.", ephemeral=True)
            return False
        return True


class BotaoHabilidade(discord.ui.Button):
    def __init__(self, chave, dados):
        super().__init__(
            label=f"{dados['nome']} ({dados['custo']} {hab.NOME_RECURSO[dados['recurso']]})",
            emoji=dados.get("emoji"),
            style=discord.ButtonStyle.primary,
        )
        self.chave = chave

    async def callback(self, interaction):
        await interaction.response.defer()
        painel = self.view.painel
        c = self.view.combatente
        dados = HABILIDADES[self.chave]

        tipo_alvo = dados.get("alvo")
        if tipo_alvo in TIPOS_ALVO_ESCOLHIDO:
            alvos = _alvos_possiveis(painel.luta, dados)
            # regra de interface: com um alvo só (luta solo, ou hoje
            # sempre pra inimigo_escolhido -- nenhum chefe tem companhia
            # ainda), nada muda na tela -- resolve direto, sem mostrar
            # uma escolha que não existe. Só abre o menu com mais de uma
            # opção de verdade.
            if len(alvos) > 1:
                await responder(interaction, painel.luta.embed(), MenuAlvoHabilidade(painel, c, self.chave))
                return
            alvo_id = alvos[0].id if alvos else (c.id if tipo_alvo == "aliado_escolhido" else None)
        else:
            alvo_id = None
        _lancar_habilidade(painel.luta, c, self.chave, dados, alvo_id)
        await painel.registrar_acao(interaction, c, "habilidade")


class MenuAlvoHabilidade(discord.ui.View):
    """Seletor de alvo pra skills que miram um aliado OU inimigo escolhido
    -- Step A generalizou o widget pra inimigo também. "Aliado escolhido"
    continua sendo o único caso com skill de verdade usando (Palavra de
    Alento); "inimigo escolhido" é infra pura, ver decisoes.md § Step A."""

    def __init__(self, painel, combatente, chave):
        super().__init__(timeout=TIMEOUT_RODADA)
        self.painel = painel
        self.combatente = combatente
        for alvo in _alvos_possiveis(painel.luta, HABILIDADES[chave]):
            self.add_item(BotaoAlvoHabilidade(alvo, chave))
        self.add_item(BotaoVoltar())

    async def interaction_check(self, interaction):
        if interaction.user.id != self.combatente.id:
            await interaction.response.send_message("Essa não é sua habilidade.", ephemeral=True)
            return False
        return True


class BotaoAlvoHabilidade(discord.ui.Button):
    def __init__(self, alvo, chave):
        super().__init__(label=alvo.nome, emoji="🎯", style=discord.ButtonStyle.success)
        self.alvo_id = alvo.id
        self.chave = chave

    async def callback(self, interaction):
        await interaction.response.defer()
        painel = self.view.painel
        c = self.view.combatente
        dados = HABILIDADES[self.chave]
        _lancar_habilidade(painel.luta, c, self.chave, dados, self.alvo_id)
        await painel.registrar_acao(interaction, c, "habilidade")


def _mortalha_disponivel(c):
    """A skill da mortalha só existe pra quem tem a peça equipada e ainda
    não usou nesta luta -- ver decisoes.md § Mortalha de Luz/Sombra."""
    return bool(c.jogador.get("mortalha")) and not c.mortalha_usada


class BotaoMortalha(discord.ui.Button):
    """Botão compartilhado, igual Atacar/Defender/Fugir -- só existe no
    painel se ALGUÉM ativo qualifica (ver PainelLuta.__init__), mas o efeito
    é sempre do combatente que clicou; quem não tem mortalha ou já usou a
    dele leva recusa ephemeral, duas mensagens diferentes (ver callback),
    mesmo padrão do botão Habilidade pra quem não tem classe. NÃO chama
    registrar_acao — é a diferença central desta skill: ativa e ainda ataca
    na mesma rodada, não gasta o turno (decidido duas vezes, ver
    decisoes.md). `PainelLuta.interaction_check` já barra quem não está na
    luta, já saiu dela, ou já tem `c.acao` definido nesta rodada -- nenhuma
    checagem extra precisa disso aqui.

    NUNCA seta `self.disabled` aqui -- este botão é uma instância ÚNICA
    compartilhada pela view inteira da party (não um por jogador), então
    desabilitar `self` apaga o botão pra todo mundo depois do primeiro uso,
    mesmo que `mortalha_usada` seja por combatente. Foi bug real (ver
    decisoes.md § Mortalha de Luz/Sombra): trava geral onde deveria ser só
    a checagem por jogador. Regra vale pra qualquer botão futuro que
    apareça uma vez só no painel mas precise de estado por combatente."""

    def __init__(self):
        super().__init__(label="Mortalha", emoji="🕯️", style=discord.ButtonStyle.success, row=1)

    async def callback(self, interaction):
        painel = self.view
        luta = painel.luta
        c = painel.combatente_de(interaction)
        if not c.jogador.get("mortalha"):
            await interaction.response.send_message(
                "Você não tem uma Mortalha equipada. Ela é forjada pela Selen (andar 9), "
                "com as quatro peças da Guia — e precisa estar equipada pra ativar.",
                ephemeral=True,
            )
            return
        if c.mortalha_usada:
            await interaction.response.send_message(
                "Você já ativou a sua Mortalha nesta luta — é um uso por jogador, por luta. "
                "O resto da party ainda pode usar a deles.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        dados = ITENS[c.jogador["mortalha"]]
        c.mortalha_usada = True
        if dados.get("elemento") == "luz":
            ganho = c.s["hp_max"] - max(0, c.hp)
            c.hp = c.s["hp_max"]
            luta.registrar(
                f"{dados['emoji']} {c.nome} ativa **{dados['nome']}** — cura completa (+{ganho} HP)."
            )
        else:
            c.sombra_ativa = True
            luta.registrar(
                f"{dados['emoji']} {c.nome} ativa **{dados['nome']}** — o próximo golpe vem em dobro."
            )
        await responder(interaction, luta.embed(), painel)


class PainelLuta(discord.ui.View):
    def __init__(self, luta):
        super().__init__(timeout=TIMEOUT_RODADA)
        if any(_mortalha_disponivel(c) for c in luta.ativos):
            self.add_item(BotaoMortalha())
        self.luta = luta
        self.mensagem = None

    # -------- utilidades
    def combatente_de(self, interaction):
        return self.luta.por_id(interaction.user.id)

    async def interaction_check(self, interaction):
        c = self.combatente_de(interaction)
        if c is None:
            await interaction.response.send_message(
                "Você não está nesta luta. Abra a sua com `rpg boss` ou `rpg party`.",
                ephemeral=True,
            )
            return False
        if not c.ativo:
            await interaction.response.send_message(
                "Você já saiu desta luta.", ephemeral=True
            )
            return False
        if c.acao:
            await interaction.response.send_message(
                "Você já agiu nesta rodada. Esperando o resto da party.", ephemeral=True
            )
            return False
        return True

    def travar(self):
        for item in self.children:
            item.disabled = True
        self.stop()

    async def encerrar(self, interaction, embed):
        self.travar()
        travas.destravar_todos([c.id for c in self.luta.participantes])
        await responder(interaction, embed, self)
        await _talvez_oferecer_porta(self.luta, interaction.followup.send)

    def _continuar(self, luta):
        """Painel novo pra quando sobra gente depois de um timeout — método
        à parte (não só `PainelLuta(luta)` direto) pra uma subclasse como
        PainelRaide (raide.py) poder continuar sendo ela mesma, com os
        argumentos extras que precisa (guilda_id, iniciador_id)."""
        return PainelLuta(luta)

    async def fim_da_luta(self, interaction=None):
        """Devolve o embed final se a luta acabou, ou None se continua.
        Vitória exige TODOS os inimigos mortos, não só o principal --
        Step A: "matar um não encerra a luta; matar todos encerra". Hoje
        `luta.inimigos` tem sempre um só, então equivale a `hp_chefe <=
        0` de antes."""
        luta = self.luta
        if not luta.inimigos_ativos:
            return await finalizar_vitoria(luta)
        if not luta.ativos:
            _talvez_auto_ressuscitar(luta)   # clérigo solo, Step 2d -- ANTES de decidir derrota
            if not luta.ativos:
                if any(c.caiu for c in luta.participantes) and not any(
                    c.fugiu or c.saiu for c in luta.participantes
                ):
                    return await finalizar_derrota(luta)
                return await encerrar_por_abandono(luta)
        return None

    # -------- fluxo da rodada
    async def registrar_acao(self, interaction, combatente, acao):
        """Guarda a escolha e resolve a rodada quando todos ja escolheram."""
        combatente.acao = acao
        if acao == "defender":
            combatente.defendendo = True
            ganhar_furia_defesa(combatente)

        luta = self.luta
        if any(c.acao is None for c in luta.ativos):
            await responder(interaction, luta.embed(), self)
            return

        # começo da rodada: condições contínuas (sangramento, elementos etc.) primeiro
        condicoes.tick(luta)
        regenerar_energia(luta)
        fim = await self.fim_da_luta()
        if fim:
            await self.encerrar(interaction, fim)
            return

        # depois, ataques, e por fim o chefe
        for c in luta.ativos:
            if c.acao == "atacar" and condicoes.pode_agir(luta, c.id):
                if random.random() < condicoes.chance_de_erro(luta, c.id):
                    luta.registrar(f"🌪️ {c.nome} erra o golpe — o vento desvia.")
                    continue
                critico_extra = condicoes.bonus_critico(luta, c.id)
                dano, critico = _rolar_ataque_normal(
                    luta, c, c.s["atk"], _defesa_efetiva(luta, c), c.s["critico"] + critico_extra
                )
                dano = int(dano * condicoes.multiplicador_dano_causado(luta, "chefe"))
                dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
                dano = _aplicar_sombra(luta, c, dano)
                luta.hp_chefe -= dano
                luta.verificar_fase2()
                luta.registrar(f"{c.nome} acerta **{dano}**")
                ganhar_furia(c, critico)
                _recuperar_mana_por_golpe(c)
                _curar_por_critico(c, critico)
                _talvez_condicionar_chefe(luta, c)
        fim = await self.fim_da_luta()
        if fim:
            await self.encerrar(interaction, fim)
            return

        luta.turno_do_chefe()
        fim = await self.fim_da_luta()
        if fim:
            await self.encerrar(interaction, fim)
            return
        await responder(interaction, luta.embed(), self)

    @discord.ui.button(label="Atacar", emoji="⚔️", style=discord.ButtonStyle.danger)
    async def atacar(self, interaction, button):
        await interaction.response.defer()
        c = self.combatente_de(interaction)
        await self.registrar_acao(interaction, c, "atacar")

    @discord.ui.button(label="Defender", emoji="🛡️", style=discord.ButtonStyle.primary)
    async def defender(self, interaction, button):
        await interaction.response.defer()
        c = self.combatente_de(interaction)
        self.luta.registrar(f"{c.nome} firma a guarda.")
        await self.registrar_acao(interaction, c, "defender")

    @discord.ui.button(label="Mochila", emoji="🎒", style=discord.ButtonStyle.success)
    async def mochila(self, interaction, button):
        c = self.combatente_de(interaction)
        disponiveis = [i for i in pocoes_na_mochila(c.id) if pode_usar(c, i["item"])]
        if not disponiveis:
            await interaction.response.send_message(
                f"Você já usou o limite nesta luta ({MAX_POCOES} poções, "
                f"{MAX_ELIXIRES} elixir). Agora é no talento.",
                ephemeral=True,
            )
            return
        await responder(interaction, self.luta.embed(), MenuPocoes(self, c))

    @discord.ui.button(label="Habilidade", emoji="🔮", style=discord.ButtonStyle.primary)
    async def habilidade(self, interaction, button):
        c = self.combatente_de(interaction)
        if not c.jogador["classe"]:
            await interaction.response.send_message(
                "Você não tem classe — `rpg classe` primeiro.", ephemeral=True
            )
            return
        if not condicoes.pode_lancar_habilidade(self.luta, c.id):
            await interaction.response.send_message(
                "⚡ Você está sob Choque — não consegue canalizar nada agora.", ephemeral=True
            )
            return
        if not hab.lancaveis(c.jogador, c.recurso_atual()):
            await interaction.response.send_message(
                "Nenhuma habilidade disponível agora — sem recurso pra nenhuma "
                "que você já destravou.",
                ephemeral=True,
            )
            return
        await responder(interaction, self.luta.embed(), MenuHabilidades(self, c))

    @discord.ui.button(label="Fugir", emoji="🏃", style=discord.ButtonStyle.secondary)
    async def fugir(self, interaction, button):
        await interaction.response.defer()
        c = self.combatente_de(interaction)
        chance = self.luta.chance_de_fuga(c)
        if random.random() < chance:
            c.fugiu = True
            c.salvar_estado()
            travas.destravar(c.id)
            self.luta.registrar(f"🏃 {c.nome} escapou da sala.")
            fim = await self.fim_da_luta()
            if fim:
                await self.encerrar(interaction, fim)
                return
            await responder(interaction, self.luta.embed(), self)
            return
        self.luta.registrar(f"{c.nome} tentou fugir e falhou ({chance * 100:.0f}%).")
        await self.registrar_acao(interaction, c, "fugir")

    async def on_timeout(self):
        """Quem nao clicou sai da luta. Se sobrar gente, a rodada resolve sem ele."""
        luta = self.luta
        if luta.encerrada or self.mensagem is None:
            return
        for c in luta.ativos:
            if c.acao is None:
                c.saiu = True
                c.salvar_estado()
                travas.destravar(c.id)
                luta.registrar(f"⏱️ {c.nome} sumiu e saiu da luta.")

        if luta.ativos:
            condicoes.tick(luta)
            regenerar_energia(luta)
            if luta.hp_chefe > 0:
                for c in luta.ativos:
                    if c.acao == "atacar" and condicoes.pode_agir(luta, c.id):
                        if random.random() < condicoes.chance_de_erro(luta, c.id):
                            luta.registrar(f"🌪️ {c.nome} erra o golpe — o vento desvia.")
                            continue
                        critico_extra = condicoes.bonus_critico(luta, c.id)
                        dano, critico = _rolar_ataque_normal(
                            luta, c, c.s["atk"], _defesa_efetiva(luta, c), c.s["critico"] + critico_extra
                        )
                        dano = int(dano * condicoes.multiplicador_dano_causado(luta, "chefe"))
                        dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
                        dano = _aplicar_sombra(luta, c, dano)
                        luta.hp_chefe -= dano
                        luta.verificar_fase2()
                        luta.registrar(f"{c.nome} acerta **{dano}**")
                        ganhar_furia(c, critico)
                        _recuperar_mana_por_golpe(c)
                        _curar_por_critico(c, critico)
                        _talvez_condicionar_chefe(luta, c)
            if luta.hp_chefe > 0:
                luta.turno_do_chefe()

        embed = await self.fim_da_luta()
        if embed is None:
            # sobrou gente: a luta continua num painel novo — _continuar() é
            # overridável, pra subclasses (PainelRaide) continuarem sendo
            # elas mesmas em vez de virar um PainelLuta genérico
            novo = self._continuar(luta)
            novo.mensagem = self.mensagem
            self.stop()
            await self.mensagem.edit(embed=luta.embed(), view=novo)
            return

        self.travar()
        travas.destravar_todos([c.id for c in luta.participantes])
        await self.mensagem.edit(embed=embed, view=self)
        await _talvez_oferecer_porta(luta, self.mensagem.channel.send)


# ------------------------------------------------------------ sala de espera

def texto_regra_hp_chefe(andar_num, chefe):
    """Frase da sala de party sobre como o HP do chefe escala -- tem que
    bater com a conta de `Luta.__init__` pra não anunciar uma regra que o
    andar não segue mais. Ver decisoes.md § HP de chefe fixo acima do Selo."""
    if andar_num > ANDAR_ACIMA_DO_SELO:
        return f"**{chefe['hp']} HP fixo, não escala com o tamanho da party** (andar de grupo)"
    return f"**{chefe['hp']} HP por dono do andar**"


class SalaDeEspera(discord.ui.View):
    def __init__(self, anfitriao, jogador, andar_num):
        super().__init__(timeout=TIMEOUT_SALA)
        self.anfitriao = anfitriao
        self.andar_num = andar_num
        self.inscritos = [jogador["user_id"]]
        self.mensagem = None
        self.comecou = False

    def embed(self):
        chefe = ANDARES[self.andar_num]["boss"]
        nomes = []
        for uid in self.inscritos:
            j = db.get_jogador(uid)
            tag = "" if j["andar_max"] == self.andar_num else " — ajuda (não infla o chefe)"
            nomes.append(f"• **{j['nome']}** — nível {j['nivel']}{tag}")
        e = discord.Embed(
            title=f"Party para {chefe['nome']}",
            description=(
                f"Andar {self.andar_num}. O chefe entra com "
                f"{texto_regra_hp_chefe(self.andar_num, chefe)} — quem só está ajudando não infla "
                f"o chefe.\n\n"
                f"Precisa estar fisicamente no andar {self.andar_num} (`rpg viajar {self.andar_num}`) "
                f"e com pelo menos {int(HP_MINIMO_PARA_ENTRAR * 100)}% de HP."
            ),
            color=COR_SALA,
        )
        e.add_field(name=f"Na sala ({len(self.inscritos)}/{MAX_PARTY})",
                    value="\n".join(nomes), inline=False)
        e.set_footer(text=f"{TIMEOUT_SALA}s para fechar · só {db.get_jogador(self.anfitriao)['nome']} pode começar")
        return e

    async def validar(self, interaction, j):
        if j["andar"] != self.andar_num:
            await interaction.response.send_message(
                f"Você está no andar {j['andar']}, e essa sala é do andar {self.andar_num}. "
                f"Precisa estar fisicamente lá — `rpg viajar {self.andar_num}` primeiro. "
                f"Seu andar_max não importa pra entrar, só pra abrir a sala.",
                ephemeral=True,
            )
            return False
        s = H["stats"](j)
        if j["hp"] < s["hp_max"] * HP_MINIMO_PARA_ENTRAR:
            await interaction.response.send_message(
                f"Você está com {max(0, j['hp'])}/{s['hp_max']}. Cure antes de entrar.",
                ephemeral=True,
            )
            return False
        if await db.a_checar_cooldown(j["user_id"], "boss") > 0:
            await interaction.response.send_message(
                "Seu cooldown de chefe ainda não voltou.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Entrar", emoji="🤝", style=discord.ButtonStyle.success)
    async def entrar(self, interaction, button):
        if self.comecou:
            await interaction.response.send_message("A luta já começou.", ephemeral=True)
            return
        if interaction.user.id in self.inscritos:
            await interaction.response.send_message("Você já está na sala.", ephemeral=True)
            return
        if len(self.inscritos) >= MAX_PARTY:
            await interaction.response.send_message("A sala está cheia.", ephemeral=True)
            return
        j = await db.a_get_jogador(interaction.user.id)
        if not j:
            await interaction.response.send_message(
                "Você ainda não entrou na torre. Manda `rpg comecar`.", ephemeral=True
            )
            return
        if not await self.validar(interaction, j):
            return
        self.inscritos.append(j["user_id"])
        await responder(interaction, self.embed(), self)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.secondary)
    async def sair(self, interaction, button):
        if interaction.user.id == self.anfitriao:
            await interaction.response.send_message(
                "Quem abriu a sala não pode sair — cancele deixando o tempo acabar.",
                ephemeral=True,
            )
            return
        if interaction.user.id not in self.inscritos:
            await interaction.response.send_message("Você não está na sala.", ephemeral=True)
            return
        self.inscritos.remove(interaction.user.id)
        await responder(interaction, self.embed(), self)

    @discord.ui.button(label="Começar", emoji="⚔️", style=discord.ButtonStyle.danger)
    async def comecar(self, interaction, button):
        if interaction.user.id != self.anfitriao:
            await interaction.response.send_message(
                "Só quem abriu a sala pode começar.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self.comecou = True
        self.stop()
        await iniciar_luta(interaction, self.inscritos, self.andar_num, editar=True)

    async def on_timeout(self):
        if self.comecou or self.mensagem is None:
            return
        for item in self.children:
            item.disabled = True
        e = self.embed()
        e.title = "A sala fechou sem começar"
        e.color = COR_FUGA
        await self.mensagem.edit(embed=e, view=self)


# --------------------------------------------------------------- inicio

async def montar_combatentes(ids):
    combatentes = []
    for uid in ids:
        j = await db.a_get_jogador(uid)
        if not j:
            continue
        combatentes.append(Combatente(j, H["stats"](j)))
    return combatentes


def _resolver_abertura_do_chefe(luta, combatentes, andar_num):
    """Rola se o chefe abre a luta batendo em alguém antes da rodada 1
    resolver de verdade -- só roda se RODADA_1_SEM_CHEFE estiver desligado
    (ver decisoes.md § Rodada 1 sem chefe). Hoje a flag é sempre True, e
    `self.rodada == 1` já retorna antes de qualquer coisa aqui dentro
    poder rodar (ver Luta.turno_do_chefe) -- isto é código morto, do
    mesmo jeito que já era antes do Step 2b, ver decisoes.md § Step 2b
    (correção)."""
    if RODADA_1_SEM_CHEFE:
        return
    mais_rapido = max(c.s["atribs"]["destreza"] for c in combatentes)
    if random.random() >= at.chance_iniciativa(mais_rapido, at.destreza_monstro(andar_num)):
        alvo = random.choice(combatentes)
        dano = dano_do_chefe(luta.chefe, alvo.s, andar_num)
        alvo.hp -= dano
        luta.registrar(f"{luta.chefe['nome']} foi mais rápido e acerta {alvo.nome} — **{dano}**")
        if alvo.hp <= 0:
            alvo.caiu = True
        alvo.salvar_estado()


async def iniciar_luta(destino, ids, andar_num, editar=False):
    """destino e' um ctx (comando) ou uma interaction (botao Começar)."""
    combatentes = await montar_combatentes(ids)
    travas.travar_todos([c.id for c in combatentes])
    chefe = ANDARES[andar_num]["boss"]
    donos_ids = [c.id for c in combatentes if c.jogador["andar_max"] == andar_num]
    luta = Luta(combatentes, chefe, andar_num, donos_ids=donos_ids)

    for c in combatentes:
        await db.a_set_cooldown(c.id, "boss", H["COOLDOWN_BOSS"])
        await db.a_marcar_combate(c.id)

    _resolver_abertura_do_chefe(luta, combatentes, andar_num)

    painel = PainelLuta(luta)
    if not luta.ativos:
        painel.travar()
        embed = await finalizar_derrota(luta)
        travas.destravar_todos([c.id for c in combatentes])
        if editar:
            await responder(destino, embed, painel)
        else:
            await destino.send(embed=embed, view=painel)
        return

    if editar:
        await responder(destino, luta.embed(), painel)
        painel.mensagem = await destino.original_response()
    else:
        painel.mensagem = await destino.send(embed=luta.embed(), view=painel)


# ---------------------------------------------------------------- instalacao

def instalar(bot, contexto):
    """Substitui o comando `boss` do bot.py e adiciona o `party`."""
    H.update(contexto)
    bot.remove_command("boss")

    async def checar_sala_do_chefe(ctx, j, party=False):
        """Regras comuns ao boss solo e a' party. Do andar 1 ao 10 (Selo)
        exige andar == andar_max — sem isso dava pra farmar chefe fácil sem
        risco. Acima do Selo isso travava sem saída: `rpg viajar` nunca passa
        do andar 11 (LIMITE_VIAJAR), então quem descia de volta pro 11+ com
        andar_max mais alto (viagem pra baixo, teleporte da Guia, ajuda de
        party em andar menor) ficava sem hospedar em andar nenhum. Acima do
        Selo relaxa pra andar <= andar_max: quem está abaixo do próprio
        andar_max ainda hospeda e refaz a subida lutando, andar por andar.
        Em `rpg party`, quem não bate o requisito ainda pode ajudar a luta de
        outro andar, então a mensagem ensina isso em vez de só mandar voltar
        pro topo."""
        if not await mundo.exigir_torre(ctx, j):
            return False
        if j["andar"] <= ANDAR_ACIMA_DO_SELO and j["andar"] < j["andar_max"]:
            destino_sugerido = min(j["andar_max"], LIMITE_VIAJAR)
            acima = (
                f" A partir do {LIMITE_VIAJAR} não tem mais teleporte — sobe lutando, andar "
                f"por andar, até o {j['andar_max']}."
                if j["andar_max"] > LIMITE_VIAJAR else ""
            )
            extra = (
                f" Se é pra ajudar em vez de hospedar, não precisa fazer nada — você já está "
                f"no andar {j['andar']}: espera alguém de lá abrir a sala e entra com **Entrar**."
                if party else ""
            )
            await ctx.send(
                f"A sala do chefe do andar {j['andar']} não é sua pra abrir — só quem tem "
                f"andar_max {j['andar']} hospeda aqui. Manda `rpg viajar {destino_sugerido}` "
                f"pra abrir a sua lá em cima.{acima}{extra}"
            )
            return False
        s = H["stats"](j)
        if j["hp"] < s["hp_max"] * HP_MINIMO_PARA_ENTRAR:
            machucado = pronomes.concordar("Você está machucad{o|a} demais", j["pronome"])
            await ctx.send(
                f"{machucado} ({max(0, j['hp'])}/{s['hp_max']}). "
                f"Manda `rpg usar pocao pequena` antes."
            )
            return False
        return True

    @bot.command(name="boss", aliases=["chefe"])
    @travas.fora_de_luta()
    @travas.fora_de_manutencao()
    async def boss(ctx):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not await checar_sala_do_chefe(ctx, j):
            return
        restante = await db.a_checar_cooldown(ctx.author.id, "boss")
        if restante > 0:
            await ctx.send(f"⏳ `rpg boss` volta em **{H['fmt_tempo'](restante)}**.")
            return
        await iniciar_luta(ctx, [j["user_id"]], j["andar"])

    @bot.command(name="party", aliases=["grupo"])
    @travas.fora_de_manutencao()
    async def party(ctx):
        j = await H["pegar_jogador"](ctx)
        if not j:
            return
        if not await checar_sala_do_chefe(ctx, j, party=True):
            return
        restante = await db.a_checar_cooldown(ctx.author.id, "boss")
        if restante > 0:
            await ctx.send(f"⏳ Seu cooldown de chefe volta em **{H['fmt_tempo'](restante)}**.")
            return
        sala = SalaDeEspera(j["user_id"], j, j["andar"])
        sala.mensagem = await ctx.send(embed=sala.embed(), view=sala)

    print("combate.py carregado — chefe por turnos, solo e em party.")