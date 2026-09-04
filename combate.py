# combate.py
# Combate por turnos dos chefes, solo ou em party, com botoes na mensagem.
# Nao importa bot.py (evita import circular): os helpers chegam por instalar().

import random

import discord

import atributos as at
import condicoes
import database as db
import habilidades as hab
import passivas
import pronomes
import travas
from andares_altos import ANDAR_ACIMA_DO_SELO, LIMITE_VIAJAR
from game_data import (
    ITENS, ANDARES, ANDAR_MAXIMO, HABILIDADES, CLASSES, CONDICOES_ELEMENTO,
    CONDICOES_ARMA_ELEMENTAL, SALAO_TIERS, multiplicador_elemento,
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
BONUS_GOLPE_FATAL_EXECUCAO = 1.3          # + até isso, conforme o alvo perde HP -- teto 2.5 com o alvo a 0
MULTIPLICADOR_FLECHA_PERFURANTE = 1.8     # dano puro, ignora defesa (igual Dardo Arcano)

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
    """Só o Guerreiro acumula Fúria, e só atacando — golpe crítico dá +50%."""
    if c.jogador["classe"] != "guerreiro":
        return
    ganho = FURIA_POR_GOLPE + int(c.jogador["forca"] or 0) / 5
    if critico:
        ganho *= 1.5
    c.furia = min(FURIA_MAX, c.furia + ganho)


def ganhar_furia_defesa(c):
    """Defender também gera Fúria pro Guerreiro, metade do golpe normal."""
    if c.jogador["classe"] != "guerreiro":
        return
    ganho = 0.5 * (FURIA_POR_GOLPE + int(c.jogador["forca"] or 0) / 5)
    c.furia = min(FURIA_MAX, c.furia + ganho)


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
        self.chefe = chefe
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
        if andar_num > ANDAR_ACIMA_DO_SELO:
            self.hp_chefe = chefe["hp"]
        else:
            self.hp_chefe = chefe["hp"] * max(1, num_donos)
        self.hp_chefe_max = self.hp_chefe
        self.rodada = 1
        self.carregando = False
        self.preparando_condicao = None   # telegraph independente — ver _talvez_telegrafar_condicao
        self.materiais_extras = []        # material da fase 1 quando o chefe troca de fase (andar 15)
        self.encerrada = False
        self.condicoes = []   # ver condicoes.py — sangramento, confusão, elementos etc.
        self.elementos_aplicados_rodada = set()  # teto de 1 aplicação por elemento, por rodada
        self.log = []

    @property
    def ativos(self):
        return [c for c in self.participantes if c.ativo]

    @property
    def desfalque(self):
        """Quantos companheiros a party perdeu — facilita a fuga de quem ficou."""
        return len(self.participantes) - len(self.ativos)

    @property
    def em_party(self):
        return len(self.participantes) > 1

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
        e.add_field(
            name=self.chefe["nome"],
            value=f"{H['barra_hp'](self.hp_chefe, self.hp_chefe_max)} "
                  f"{max(0, self.hp_chefe)}/{self.hp_chefe_max}",
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
        """O chefe age uma vez por rodada, contra a party inteira — exceto
        na rodada 1, que é só do jogador (RODADA_1_SEM_CHEFE). Chefe com
        "elemento" (andares 11+) também rola, de forma independente do golpe
        carregado, pra telegrafar/aplicar uma condição elemental — os dois
        podem acontecer na mesma rodada. Corrente (chance_erro) e Curto
        (bloqueia_skill) são as condições que a ARMA elemental do jogador
        pode ter amarrado no chefe (qualquer andar) — ver decisoes.md §
        Dano elemental pros pontos de consulta novos que esses dois tipos
        precisaram aqui (os outros quatro já eram consultados em pontos que
        já existiam)."""
        alvos = self.ativos
        if not alvos:
            return

        if RODADA_1_SEM_CHEFE and self.rodada == 1:
            self.registrar(f"{self.chefe['nome']} ainda não reagiu à entrada de vocês.")
        elif not condicoes.pode_agir(self, "chefe"):
            self.registrar(f"{self.chefe['nome']} está sob efeito e perde a rodada.")
        else:
            self._resolver_condicao_pendente()
            if random.random() < condicoes.chance_de_erro(self, "chefe"):
                self.registrar(f"🌬️ Corrente desvia o golpe de {self.chefe['nome']} — ele erra a rodada.")
            elif self.carregando:
                self.carregando = False
                self.registrar(f"💥 **Golpe carregado** — {self.chefe['nome']} acerta todo mundo:")
                for c in alvos:
                    # Reflexos (mago de raio, Step 2b correção): chance
                    # INDIVIDUAL de escapar ileso só deste golpe carregado
                    # -- não cancela a carga, não protege os outros alvos
                    # do laço, não vale pro ataque normal (ramo abaixo).
                    if random.random() < passivas.chance_erro_carregado(c.jogador):
                        self.registrar(f"⚡ {c.nome} lê o movimento e escapa do golpe carregado.")
                        continue
                    dano = dano_do_chefe(
                        self.chefe, c.s, self.andar_num,
                        defendendo=c.defendendo, carregado=True,
                    )
                    dano = int(dano * condicoes.multiplicador_dano_causado(self, c.id))
                    dano = max(1, int(dano * (1 - _reducao_dano_total(self, c))))
                    c.hp -= dano
                    aparou = " (aparou)" if c.defendendo else ""
                    self.registrar(f"· {c.nome} toma **{dano}**{aparou}")
                    if c.hp <= 0:
                        c.caiu = True
            # Curto (bloqueia_skill) só impede COMEÇAR a carregar -- um golpe
            # já em preparo (ramo acima) resolve normal, ver decisoes.md
            elif condicoes.pode_lancar_habilidade(self, "chefe") and random.random() < CHANCE_CARREGAR:
                self.carregando = True
                self.registrar(f"{self.chefe['nome']} recua e começa a se preparar.")
            else:
                alvo = condicoes.alvo_forcado(self) or random.choice(alvos)
                des = alvo.s["atribs"]["destreza"]
                if random.random() < at.chance_esquiva(des, at.destreza_monstro(self.andar_num)):
                    self.registrar(f"{alvo.nome} esquivou do ataque.")
                else:
                    dano = dano_do_chefe(
                        self.chefe, alvo.s, self.andar_num, defendendo=alvo.defendendo
                    )
                    dano = int(dano * condicoes.multiplicador_dano_causado(self, alvo.id))
                    dano = max(1, int(dano * (1 - _reducao_dano_total(self, alvo))))
                    alvo.hp -= dano
                    self.registrar(f"{self.chefe['nome']} ataca **{alvo.nome}** — {dano} de dano")
                    if alvo.hp <= 0:
                        alvo.caiu = True

            self._talvez_telegrafar_condicao()

        for c in self.participantes:
            c.defendendo = False
            c.acao = None
            c.sombra_ativa = False   # "nessa rodada" -- some no fim dela, usada ou não
            c.salvar_estado()
        self.rodada += 1
        self.elementos_aplicados_rodada = set()

    def _resolver_condicao_pendente(self):
        """Aplica a condição que foi telegrafada na rodada anterior. Se o
        alvo defendeu, a duração é cortada pela metade — é isso que faz
        Defender virar decisão, não sorte."""
        pend = self.preparando_condicao
        if not pend:
            return
        self.preparando_condicao = None
        alvo = self.por_id(pend["alvo_id"])
        if not alvo or not alvo.ativo:
            self.registrar(f"{pend['emoji']} O alvo de {self.chefe['nome']} já não está mais na luta.")
            return
        duracao = pend["duracao"]
        if alvo.defendendo:
            duracao = max(1, duracao // 2)
        condicoes.aplicar(
            self, alvo.id, pend["tipo"], pend["nome"], pend["emoji"],
            duracao, pend["valor"], origem="chefe",
        )

    def _talvez_telegrafar_condicao(self):
        """Roll independente do golpe carregado — só chefes com "elemento"
        (andares 11+) participam."""
        elemento = self.chefe.get("elemento")
        if not elemento or self.preparando_condicao is not None:
            return
        if random.random() >= CHANCE_TELEGRAFAR_CONDICAO:
            return
        dados = CONDICOES_ELEMENTO[elemento]
        alvo = random.choice(self.ativos)
        self.preparando_condicao = {**dados, "alvo_id": alvo.id}
        self.registrar(
            f"{dados['emoji']} {self.chefe['nome']} está reunindo **{dados['nome']}** contra {alvo.nome}."
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
    eficiente de farmar material (ver decisoes.md). Derrotar o chefe do
    andar 15 é roguelike: reseta andar/andar_max pro 10 pra todo mundo que
    recebe, igual à morte lá em cima. `chefes_derrotados` NÃO reseta em
    nenhum dos dois casos — os 100% de chance são únicos na vida da conta,
    por chefe; sem isso os 15% de repetição nunca seriam alcançados (ver
    decisoes.md § Roguelike acima do Selo)."""
    j, s, chefe = combatente.jogador, combatente.s, luta.chefe
    completou_torre = luta.andar_num == ANDAR_MAXIMO

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

    if completou_torre:
        novo_andar = ANDAR_ACIMA_DO_SELO
        novo_max = ANDAR_ACIMA_DO_SELO
    else:
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


def _progresso_salao_previsto(total_atual):
    """(total projetado, tier alvo) supondo o tesouro que acabou de cair
    depositado no Salão -- é só uma projeção pro texto do embed de vitória,
    não deposita nada de verdade (isso continua sendo `rpg guilda depositar`,
    ato manual e irreversível). None se essa projeção já bateria o tier
    máximo. Lê SALAO_TIERS direto (dado puro de game_data.py) em vez de
    chamar salao.py -- combate.py não depende de módulo de feature, mesma
    regra que já vale pra guildas.py não depender de bot.py (ver
    decisoes.md § nota de arquitetura do Salão)."""
    projetado = total_atual + 1
    for tier in SALAO_TIERS:
        if projetado < tier["min_tesouros"]:
            return projetado, tier
    return None


def _texto_contexto_tesouro(user_id):
    """Linha extra pro embed de vitória quando o drop dessa rodada inclui um
    tesouro de chefe. Lê o estado de guilda/Salão via database.py (não via
    guildas.py) -- mesma nota de arquitetura acima."""
    guilda = db.guilda_do_membro(user_id)
    if not guilda:
        return (
            "🏛️ Isso é tesouro de guilda — não vende, só serve pro Salão. Vale guardar: "
            "funda uma (`rpg guilda criar <nome>`) ou entra numa que já te convidou "
            "(`rpg guilda convites` · `rpg guilda aceitar <nome>`)."
        )
    total = db.contar_tesouros_salao(guilda["id"])
    projecao = _progresso_salao_previsto(total)
    if not projecao:
        return f"🏛️ `rpg guilda depositar` pro Salão de **{guilda['nome']}** — já no tier máximo."
    projetado, alvo = projecao
    return (
        f"🏛️ `rpg guilda depositar` pro Salão de **{guilda['nome']}** — **{projetado}/{alvo['min_tesouros']}** "
        f"pro tier {alvo['tier']} ({alvo['nome']})."
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
            linha += f"\n· {_texto_contexto_tesouro(c.jogador['user_id'])}"
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
                f"chance baixa, não garantido. O que ela não guarda é onde vocês pararam: quem "
                f"estava na luta volta pro andar {ANDAR_ACIMA_DO_SELO}. Pra tentar de novo, "
                f"começa pelo `rpg viajar {ANDAR_ACIMA_DO_SELO + 1}`."
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


async def finalizar_derrota(luta):
    """Ninguem sobrou: cada um que caiu paga a penalidade."""
    luta.encerrada = True
    perdas = []
    for c in luta.participantes:
        if c.caiu:
            perda = await H["a_processar_morte"](c.jogador, c.s)
            perdas.append(f"**{c.nome}** perdeu {perda} 🪙")
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


def _rolar_dano_habilidade(luta, c, multiplicador, critico_extra=0.0):
    """Dano bruto de uma skill: mesma variação (±15%) e crítico de um golpe
    normal, sobre a MESMA base do ataque normal (atributo + atk da arma) —
    é isso que faz o multiplicador ser literalmente "quantos ataques
    básicos essa skill vale", em qualquer nível e com qualquer arma. Ver
    decisoes.md § Dano de skill abaixo do ataque básico."""
    base = hab.poder_base(c.jogador, _bonus_arma_de(c)) * multiplicador * _multiplicador_afinidade(c)
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
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, MULTIPLICADOR_GOLPE_ABERTO), luta.chefe["def"])
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
            luta.chefe["def"],
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
    )


def _efeito_voto_de_ferro(luta, c, dados):
    for alvo in luta.ativos:
        condicoes.aplicar(
            luta, alvo.id, "reduz_dano", dados["nome"], dados["emoji"],
            duracao=3, valor=REDUCAO_VOTO_DE_FERRO, origem=c.id,
        )


def _efeito_golpe_fatal(luta, c, dados):
    """Assassino: escala com o quanto o CHEFE já perdeu de HP -- 1.2x com
    o alvo cheio, até 2.5x (MULTIPLICADOR_GOLPE_FATAL_BASE +
    BONUS_GOLPE_FATAL_EXECUCAO) com o alvo perto de 0. Aplica defesa
    normalmente, ao contrário de Flecha Perfurante logo abaixo."""
    fracao_perdida = 1 - max(0, luta.hp_chefe) / luta.hp_chefe_max
    multiplicador = MULTIPLICADOR_GOLPE_FATAL_BASE + BONUS_GOLPE_FATAL_EXECUCAO * fracao_perdida
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, multiplicador), luta.chefe["def"])
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
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, MULTIPLICADOR_PRISAO_DE_CRISTAL), luta.chefe["def"])
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
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, multiplicador), luta.chefe["def"])
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


def _efeito_interrupcao(luta, c, dados):
    """Mago de Raio: dano em cima da MESMA base do ataque normal (com
    defesa, ver decisoes.md § Step 2b) e, se o chefe estiver CARREGANDO um
    golpe (`luta.carregando`), cancela a carga.

    FRONTEIRA DURA, NÃO GENERALIZAR: isto cancela especificamente
    `luta.carregando` -- o golpe pesado que o chefe prepara em
    `Luta.turno_do_chefe` (ver `CHANCE_CARREGAR`). NUNCA uma habilidade de
    chefe -- o chefe ainda não tem nenhuma (a IA de combo entra no step 3),
    mas quando entrar, Interrupção não cancela ela por acidente só porque
    alguém generalizou isto pra "ação do chefe" no genérico. Se uma
    habilidade de chefe precisar ser interrompível um dia, é uma consulta
    NOVA, não a reutilização deste `if luta.carregando`. Ver
    tests/test_mago_raio.py, teste que trava exatamente essa fronteira.

    Contra chefe que não está carregando, a skill é só dano -- reativa de
    propósito, sem efeito de consolação."""
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, MULTIPLICADOR_INTERRUPCAO), luta.chefe["def"])
    dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
    dano = _aplicar_sombra(luta, c, dano)
    luta.hp_chefe -= dano
    luta.verificar_fase2()
    if luta.carregando:
        luta.carregando = False
        luta.registrar(
            f"{dados['emoji']} {c.nome} conjura **{dados['nome']}** — {dano} de dano e interrompe a carga de {luta.chefe['nome']}!"
        )
    else:
        luta.registrar(f"{dados['emoji']} {c.nome} conjura **{dados['nome']}** — {dano} de dano.")
    _talvez_condicionar_chefe(luta, c)


def _efeito_muralha_de_escudos(luta, c, dados):
    """Soldado: dano em cima da MESMA base do ataque normal (com defesa,
    ver decisoes.md § Step 2c) + `redireciona` (o chefe é obrigado a
    atacar c -- condicoes.alvo_forcado já existe e não tinha usuário
    nenhum no jogo) + `reduz_dano` em c, os dois por
    DURACAO_MURALHA_RODADAS (2), regra N+1 (duracao=3)."""
    dano = at.aplicar_defesa(_rolar_dano_habilidade(luta, c, MULTIPLICADOR_MURALHA_DE_ESCUDOS), luta.chefe["def"])
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
}


def _lancar_habilidade(luta, c, chave, dados, alvo_id=None):
    if dados["recurso"] == "mana":
        c.mana -= dados["custo"]
    elif dados["recurso"] == "furia":
        c.furia -= dados["custo"]
    else:
        c.energia -= dados["custo"]
    efeito = EFEITOS_HABILIDADE[chave]
    if dados.get("alvo") == "aliado_escolhido":
        efeito(luta, c, dados, alvo_id)
    else:
        efeito(luta, c, dados)


class MenuHabilidades(discord.ui.View):
    def __init__(self, painel, combatente):
        super().__init__(timeout=TIMEOUT_RODADA)
        self.painel = painel
        self.combatente = combatente
        for chave, dados in hab.lancaveis(combatente.jogador, combatente.recurso_atual()).items():
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

        if dados.get("alvo") == "aliado_escolhido" and len(painel.luta.ativos) > 1:
            await responder(interaction, painel.luta.embed(), MenuAlvoHabilidade(painel, c, self.chave))
            return

        # luta solo ou skill sem alvo escolhido: alvo é sempre quem lançou
        alvo_id = c.id if dados.get("alvo") == "aliado_escolhido" else None
        _lancar_habilidade(painel.luta, c, self.chave, dados, alvo_id)
        await painel.registrar_acao(interaction, c, "habilidade")


class MenuAlvoHabilidade(discord.ui.View):
    """Seletor de alvo pra skills que miram um aliado escolhido (Palavra de Alento)."""

    def __init__(self, painel, combatente, chave):
        super().__init__(timeout=TIMEOUT_RODADA)
        self.painel = painel
        self.combatente = combatente
        for alvo in painel.luta.ativos:
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

    def _continuar(self, luta):
        """Painel novo pra quando sobra gente depois de um timeout — método
        à parte (não só `PainelLuta(luta)` direto) pra uma subclasse como
        PainelRaide (raide.py) poder continuar sendo ela mesma, com os
        argumentos extras que precisa (guilda_id, iniciador_id)."""
        return PainelLuta(luta)

    async def fim_da_luta(self, interaction=None):
        """Devolve o embed final se a luta acabou, ou None se continua."""
        luta = self.luta
        if luta.hp_chefe <= 0:
            return await finalizar_vitoria(luta)
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
                    luta, c, c.s["atk"], luta.chefe["def"], c.s["critico"] + critico_extra
                )
                dano = int(dano * condicoes.multiplicador_dano_causado(luta, "chefe"))
                dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
                dano = _aplicar_sombra(luta, c, dano)
                luta.hp_chefe -= dano
                luta.verificar_fase2()
                luta.registrar(f"{c.nome} acerta **{dano}**")
                ganhar_furia(c, critico)
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
                            luta, c, c.s["atk"], luta.chefe["def"], c.s["critico"] + critico_extra
                        )
                        dano = int(dano * condicoes.multiplicador_dano_causado(luta, "chefe"))
                        dano = max(1, int(dano * _fator_elemento_arma(luta, c)))
                        dano = _aplicar_sombra(luta, c, dano)
                        luta.hp_chefe -= dano
                        luta.verificar_fase2()
                        luta.registrar(f"{c.nome} acerta **{dano}**")
                        ganhar_furia(c, critico)
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