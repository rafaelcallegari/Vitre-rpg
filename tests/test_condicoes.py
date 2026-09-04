# tests/test_condicoes.py
# Cartão "Testes do motor de condições": condicoes.py é puro (não importa
# discord), então blocos 1-5 usam LutaFake/CombatenteFake -- não vale a pena
# subir bot.py/database pra testar uma função pura. Bloco 6 (os 8 efeitos)
# precisa de combate.Combatente/Luta de verdade porque as skills lêem
# jogador/stats -- mesmo padrão de tests/test_mortalha_luz_sombra.py.
#
# Não duplica tests/test_dano_elemental.py: a Sanguessuga (drena) e o clamp
# de hp_max em condição de dano já estão cobertos lá, inclusive com a origem
# amarrada por _talvez_condicionar_chefe. Aqui o drena é testado direto via
# condicoes.aplicar(), sem passar pela arma elemental.
import pytest

import bot  # noqa: F401 -- popula combate.H via bot.instalar()
import combate
import condicoes
import database as db
import game_data

CHEFE_TESTE = {"nome": "Testinho", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0}


def _combatente(user_id, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


def _sem_variancia(monkeypatch):
    """Trava ±15%/crítico de `_rolar_dano_habilidade` num valor fixo, pra
    comparar dano entre lutas sem depender de RNG -- mesmo truque de
    test_mortalha_luz_sombra.py."""
    monkeypatch.setattr(combate.random, "uniform", lambda a, b: 1.0)
    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita, nunca atordoa, nunca condiciona


# ==================================================================
# Fakes pra blocos 1-5: condicoes.py não importa discord, não vale subir o
# bot inteiro só pra testar dict-in, dict-out.
# ==================================================================

class CombatenteFake:
    def __init__(self, id, hp, hp_max, ativo=True):
        self.id = id
        self.nome = f"Combatente{id}"
        self.hp = hp
        self.s = {"hp_max": hp_max}
        self.ativo = ativo
        self.caiu = False


class LutaFake:
    def __init__(self, combatentes=(), hp_chefe=1000, hp_chefe_max=1000):
        self.condicoes = []
        self.log = []
        self.chefe = {"nome": "Chefe Teste"}
        self.hp_chefe = hp_chefe
        self.hp_chefe_max = hp_chefe_max
        self._combatentes = list(combatentes)

    def por_id(self, user_id):
        return next((c for c in self._combatentes if c.id == user_id), None)

    def registrar(self, texto):
        self.log.append(texto)


# ==================================================================
# Bloco 1 — _valor_absoluto, a fronteira em 1
# ==================================================================

def test_valor_absoluto_fracao_do_hp_max():
    assert condicoes._valor_absoluto(0.3, 10) == 3


def test_valor_absoluto_literal_quando_maior_ou_igual_a_1_ignora_hp_max():
    assert condicoes._valor_absoluto(5.9, 10) == 5
    assert condicoes._valor_absoluto(5.9, 999999) == 5   # não escala com hp_max -- é fixo


def test_valor_absoluto_1_0_exato_cai_no_ramo_literal_nao_no_de_fracao():
    # se caísse no ramo de fração, hp_max=3 daria max(1, int(3*1.0)) == 3
    assert condicoes._valor_absoluto(1.0, 3) == 1


def test_valor_absoluto_fracao_pequena_demais_ainda_da_piso_1():
    assert condicoes._valor_absoluto(0.01, 10) == 1   # int(0.1) == 0, max(1, 0) == 1


# ==================================================================
# Bloco 2 — dano_por_rodada e cura_por_rodada, os dois com tick próprio
# ==================================================================

def test_dano_por_rodada_no_chefe_usa_hp_chefe_max():
    luta = LutaFake(hp_chefe=200, hp_chefe_max=200)
    condicoes.aplicar(luta, "chefe", "dano_por_rodada", "Queimadura", "🔥", duracao=1, valor=0.25)

    condicoes.tick(luta)

    assert luta.hp_chefe == 150   # 25% de 200


def test_dano_por_rodada_no_jogador_usa_hp_max_do_combatente_nao_do_chefe():
    alvo = CombatenteFake(id=1, hp=40, hp_max=40)
    luta = LutaFake(combatentes=[alvo], hp_chefe=999999, hp_chefe_max=999999)
    condicoes.aplicar(luta, alvo.id, "dano_por_rodada", "Sangramento", "🩸", duracao=1, valor=0.25)

    condicoes.tick(luta)

    assert alvo.hp == 30   # 25% de 40 (hp_max do combatente), não do chefe


def test_dano_por_rodada_derruba_o_jogador_quando_hp_chega_a_zero_ou_menos():
    alvo = CombatenteFake(id=1, hp=10, hp_max=100)
    luta = LutaFake(combatentes=[alvo])
    condicoes.aplicar(luta, alvo.id, "dano_por_rodada", "Sangramento", "🩸", duracao=1, valor=15)

    condicoes.tick(luta)

    assert alvo.caiu is True
    assert alvo.hp == -5


def test_dano_por_rodada_em_alvo_inativo_e_no_op():
    alvo = CombatenteFake(id=1, hp=50, hp_max=100, ativo=False)
    luta = LutaFake(combatentes=[alvo])
    condicoes.aplicar(luta, alvo.id, "dano_por_rodada", "Sangramento", "🩸", duracao=1, valor=20)

    condicoes.tick(luta)

    assert alvo.hp == 50


def test_dano_por_rodada_em_alvo_inexistente_nao_estoura():
    luta = LutaFake()
    condicoes.aplicar(luta, 999, "dano_por_rodada", "Sangramento", "🩸", duracao=1, valor=20)

    condicoes.tick(luta)   # não pode lançar exceção

    assert luta.condicoes == []


def test_drena_cura_a_origem_max_1_int_dano_vezes_drena():
    alvo = CombatenteFake(id=1, hp=100, hp_max=100)
    curador = CombatenteFake(id=2, hp=10, hp_max=100)
    luta = LutaFake(combatentes=[alvo, curador])
    condicoes.aplicar(
        luta, alvo.id, "dano_por_rodada", "Sanguessuga", "🩸", duracao=1, valor=40,
        origem=curador.id, drena=0.5,
    )

    condicoes.tick(luta)

    assert alvo.hp == 60      # 100 - 40
    assert curador.hp == 30   # 10 + max(1, int(40 * 0.5))


def test_drena_clampa_no_hp_max_do_curador():
    alvo = CombatenteFake(id=1, hp=100, hp_max=100)
    curador = CombatenteFake(id=2, hp=95, hp_max=100)
    luta = LutaFake(combatentes=[alvo, curador])
    condicoes.aplicar(
        luta, alvo.id, "dano_por_rodada", "Sanguessuga", "🩸", duracao=1, valor=40,
        origem=curador.id, drena=0.5,
    )

    condicoes.tick(luta)

    assert curador.hp == 100   # 95 + 20 estouraria pra 115, clampado


def test_curador_inativo_nao_recebe_drena_mas_o_dano_continua_tickando():
    alvo = CombatenteFake(id=1, hp=100, hp_max=100)
    curador = CombatenteFake(id=2, hp=10, hp_max=100, ativo=False)
    luta = LutaFake(combatentes=[alvo, curador])
    condicoes.aplicar(
        luta, alvo.id, "dano_por_rodada", "Sanguessuga", "🩸", duracao=1, valor=40,
        origem=curador.id, drena=0.5,
    )

    condicoes.tick(luta)

    assert alvo.hp == 60      # dano aconteceu normalmente
    assert curador.hp == 10   # cura não foi entregue a quem já não está mais ativo


def test_cura_por_rodada_nunca_passa_do_hp_max():
    alvo = CombatenteFake(id=1, hp=95, hp_max=100)
    luta = LutaFake(combatentes=[alvo])
    condicoes.aplicar(luta, alvo.id, "cura_por_rodada", "Regeneração", "💚", duracao=1, valor=20)

    condicoes.tick(luta)

    assert alvo.hp == 100


def test_cura_por_rodada_nao_cura_alvo_inativo_nao_ressuscita():
    alvo = CombatenteFake(id=1, hp=0, hp_max=100, ativo=False)
    luta = LutaFake(combatentes=[alvo])
    condicoes.aplicar(luta, alvo.id, "cura_por_rodada", "Regeneração", "💚", duracao=1, valor=20)

    condicoes.tick(luta)

    assert alvo.hp == 0


def test_cura_por_rodada_no_chefe_e_no_op():
    luta = LutaFake(hp_chefe=100, hp_chefe_max=200)
    condicoes.aplicar(luta, "chefe", "cura_por_rodada", "Regeneração", "💚", duracao=1, valor=20)

    condicoes.tick(luta)

    assert luta.hp_chefe == 100


def test_reduz_cura_entra_antes_do_clamp_de_hp_max():
    alvo = CombatenteFake(id=1, hp=50, hp_max=100)
    luta = LutaFake(combatentes=[alvo])
    # duracao=5 de propósito -- duracao=1 acopla esse teste ao bug de ordem
    # do tick() (ver bloco "bug de ordem" mais abaixo), o que não é o que
    # este teste quer travar.
    condicoes.aplicar(luta, alvo.id, "reduz_cura", "Ferida Sombria", "🌑", duracao=5, valor=0.5)
    condicoes.aplicar(luta, alvo.id, "cura_por_rodada", "Regeneração", "💚", duracao=1, valor=60)

    condicoes.tick(luta)

    # sem a redução, 60 de cura estouraria o hp_max (50+60=110 -> clampado
    # em 100, ganho 50). Com os 50% de reducao_cura entrando ANTES do
    # clamp, o ganho é 30 (60*0.5=30, 50+30=80) -- diferente do que a ordem
    # errada (clampar primeiro, reduzir o ganho depois) daria (25).
    assert alvo.hp == 80


# ==================================================================
# Bloco 3 — os seis tipos consultados (+ alvo_forcado), com os tetos
# ==================================================================

def test_multiplicador_dano_causado_soma_sem_teto_duas_rupturas_empilham():
    luta = LutaFake()
    condicoes.aplicar(luta, "chefe", "vulneravel", "Ruptura", "💠", duracao=5, valor=0.20)
    condicoes.aplicar(luta, "chefe", "vulneravel", "Ruptura", "💠", duracao=5, valor=0.20)

    assert condicoes.multiplicador_dano_causado(luta, "chefe") == 1.0 + 0.20 + 0.20


def test_reducao_dano_recebido_tem_teto_de_50_por_cento():
    alvo = CombatenteFake(id=1, hp=100, hp_max=100)
    luta = LutaFake(combatentes=[alvo])
    condicoes.aplicar(luta, alvo.id, "reduz_dano", "Voto de Ferro", "🛡️", duracao=5, valor=0.40)
    condicoes.aplicar(luta, alvo.id, "reduz_dano", "Voto de Ferro", "🛡️", duracao=5, valor=0.40)

    assert condicoes.reducao_dano_recebido(luta, alvo.id) == 0.5   # 0.8 somado, capado em 0.5


def test_chance_de_erro_tem_teto_de_60_por_cento():
    luta = LutaFake()
    condicoes.aplicar(luta, "chefe", "chance_erro", "Corrente", "🌬️", duracao=5, valor=0.5)
    condicoes.aplicar(luta, "chefe", "chance_erro", "Corrente", "🌬️", duracao=5, valor=0.5)

    assert condicoes.chance_de_erro(luta, "chefe") == 0.6   # 1.0 somado, capado em 0.6


def test_reducao_cura_recebida_tem_teto_de_80_por_cento_nunca_zera_a_cura():
    alvo = CombatenteFake(id=1, hp=0, hp_max=100)
    luta = LutaFake(combatentes=[alvo])
    condicoes.aplicar(luta, alvo.id, "reduz_cura", "Ferida Sombria", "🌑", duracao=5, valor=0.5)
    condicoes.aplicar(luta, alvo.id, "reduz_cura", "Ferida Sombria", "🌑", duracao=5, valor=0.5)

    assert condicoes.reducao_cura_recebida(luta, alvo.id) == 0.8   # 1.0 somado, capado em 0.8, não em 1.0


def test_fracao_reflexao_soma_e_tem_teto_de_1_0():
    """Represália (paladino, Step 2d): mesmo padrão de reducao_cura_
    recebida -- soma aditiva, com teto (aqui em 1.0, nunca devolve mais
    dano do que o paladino recebeu)."""
    alvo = CombatenteFake(id=1, hp=100, hp_max=100)
    luta = LutaFake(combatentes=[alvo])
    condicoes.aplicar(luta, alvo.id, "reflete_dano", "Represália", "🔥", duracao=4, valor=0.6)
    condicoes.aplicar(luta, alvo.id, "reflete_dano", "Represália", "🔥", duracao=4, valor=0.6)

    assert condicoes.fracao_reflexao(luta, alvo.id) == 1.0   # 1.2 somado, capado em 1.0


def test_fracao_reflexao_e_zero_sem_condicao_ativa():
    alvo = CombatenteFake(id=1, hp=100, hp_max=100)
    luta = LutaFake(combatentes=[alvo])

    assert condicoes.fracao_reflexao(luta, alvo.id) == 0.0


def test_fracao_reflexao_ignora_condicao_ja_expirada():
    alvo = CombatenteFake(id=1, hp=100, hp_max=100)
    luta = LutaFake(combatentes=[alvo])
    condicoes.aplicar(luta, alvo.id, "reflete_dano", "Represália", "🔥", duracao=4, valor=0.3)
    luta.condicoes[0]["duracao"] = 0

    assert condicoes.fracao_reflexao(luta, alvo.id) == 0.0


def test_fracao_reflexao_nao_conta_condicao_de_outro_alvo():
    alvo = CombatenteFake(id=1, hp=100, hp_max=100)
    outro = CombatenteFake(id=2, hp=100, hp_max=100)
    luta = LutaFake(combatentes=[alvo, outro])
    condicoes.aplicar(luta, outro.id, "reflete_dano", "Represália", "🔥", duracao=4, valor=0.3)

    assert condicoes.fracao_reflexao(luta, alvo.id) == 0.0


def test_bonus_critico_e_soma_aditiva_sem_teto():
    alvo = CombatenteFake(id=1, hp=100, hp_max=100)
    luta = LutaFake(combatentes=[alvo])
    condicoes.aplicar(luta, alvo.id, "bonus_critico", "Ponto Cego", "🎯", duracao=5, valor=0.20)
    condicoes.aplicar(luta, alvo.id, "bonus_critico", "Ponto Cego", "🎯", duracao=5, valor=0.25)

    assert condicoes.bonus_critico(luta, alvo.id) == 0.45


def test_pode_agir_false_com_pula_turno_ativo_true_sem_condicao():
    alvo = CombatenteFake(id=1, hp=100, hp_max=100)
    luta = LutaFake(combatentes=[alvo])
    assert condicoes.pode_agir(luta, alvo.id) is True

    condicoes.aplicar(luta, alvo.id, "pula_turno", "Atordoado", "💥", duracao=1, valor=0)

    assert condicoes.pode_agir(luta, alvo.id) is False


def test_pode_lancar_habilidade_false_com_bloqueia_skill_ativo_true_sem_condicao():
    luta = LutaFake()
    assert condicoes.pode_lancar_habilidade(luta, "chefe") is True

    condicoes.aplicar(luta, "chefe", "bloqueia_skill", "Choque", "⚡", duracao=1, valor=0)

    assert condicoes.pode_lancar_habilidade(luta, "chefe") is False


def test_alvo_forcado_none_sem_redireciona_ativo():
    luta = LutaFake()
    assert condicoes.alvo_forcado(luta) is None


def test_alvo_forcado_retorna_o_combatente_quando_ativo():
    alvo = CombatenteFake(id=1, hp=100, hp_max=100)
    luta = LutaFake(combatentes=[alvo])
    condicoes.aplicar(luta, "chefe", "redireciona", "Provocação", "📣", duracao=1, valor=alvo.id)

    assert condicoes.alvo_forcado(luta) is alvo


def test_alvo_forcado_ignora_combatente_com_ativo_falso_e_cai_no_none():
    alvo = CombatenteFake(id=1, hp=100, hp_max=100, ativo=False)
    luta = LutaFake(combatentes=[alvo])
    condicoes.aplicar(luta, "chefe", "redireciona", "Provocação", "📣", duracao=1, valor=alvo.id)

    assert condicoes.alvo_forcado(luta) is None


# ==================================================================
# Bloco 4 — o contrato de duração (N+1), combate.py:788-795
# ==================================================================

def _sobrevive_n_ticks_e_expira_no_seguinte(luta, nome, n):
    """Confirma a regra N+1 CONTANDO TICKS, não lendo cond['duracao']: a
    condição precisa continuar aparecendo em luta.condicoes pelos N ticks
    prometidos na descrição da skill, e sumir só no tick N+1."""
    for i in range(n):
        condicoes.tick(luta)
        assert any(c["nome"] == nome for c in luta.condicoes), f"'{nome}' sumiu cedo demais, tick {i + 1}/{n}"
    condicoes.tick(luta)
    assert not any(c["nome"] == nome for c in luta.condicoes), f"'{nome}' deveria ter expirado no tick {n + 1}"


def test_ruptura_dura_as_3_rodadas_prometidas_apesar_da_duracao_guardada_ser_4():
    c = _combatente(1, classe="mago", inteligencia=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    combate._efeito_ruptura(luta, c, game_data.HABILIDADES["ruptura"])

    _sobrevive_n_ticks_e_expira_no_seguinte(luta, "Ruptura", 3)


def test_ponto_cego_dura_as_3_rodadas_prometidas_apesar_da_duracao_guardada_ser_4():
    c = _combatente(1, classe="ladino", destreza=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    combate._efeito_ponto_cego(luta, c, game_data.HABILIDADES["ponto_cego"])

    _sobrevive_n_ticks_e_expira_no_seguinte(luta, "Ponto Cego", 3)


def test_voto_de_ferro_dura_as_2_rodadas_prometidas_apesar_da_duracao_guardada_ser_3():
    c = _combatente(1, classe="orador", inteligencia=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    combate._efeito_voto_de_ferro(luta, c, game_data.HABILIDADES["voto_de_ferro"])

    _sobrevive_n_ticks_e_expira_no_seguinte(luta, "Voto de Ferro", 2)


def test_pancada_atordoante_dura_a_1_rodada_prometida_apesar_da_duracao_guardada_ser_2(monkeypatch):
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)   # garante o stun
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    combate._efeito_pancada_atordoante(luta, c, game_data.HABILIDADES["pancada_atordoante"])

    _sobrevive_n_ticks_e_expira_no_seguinte(luta, "Pancada Atordoante", 1)


def test_sangramento_de_golpe_aberto_e_duracao_literal_3_aplicacoes(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    combate._efeito_golpe_aberto(luta, c, game_data.HABILIDADES["golpe_aberto"])
    esperado_por_tick = condicoes._valor_absoluto(combate.VALOR_SANGRAMENTO, luta.hp_chefe_max)

    for i in range(3):
        antes = luta.hp_chefe
        condicoes.tick(luta)
        assert luta.hp_chefe == antes - esperado_por_tick, f"tick {i + 1}/3"

    assert not any(c2["nome"] == "Sangramento" for c2 in luta.condicoes)
    antes = luta.hp_chefe
    condicoes.tick(luta)   # 4ª chamada -- já expirou, não aplica mais nada
    assert luta.hp_chefe == antes


def test_palavra_de_alento_e_duracao_literal_2_aplicacoes():
    c = _combatente(1, classe="orador", inteligencia=20, hp=1)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    combate._efeito_palavra_de_alento(luta, c, game_data.HABILIDADES["palavra_de_alento"], alvo_id=c.id)
    esperado_por_tick = condicoes._valor_absoluto(combate.CURA_POR_RODADA_ALENTO, c.s["hp_max"])

    for i in range(2):
        antes = c.hp
        condicoes.tick(luta)
        assert c.hp == min(c.s["hp_max"], antes + esperado_por_tick), f"tick {i + 1}/2"

    assert not any(cc["nome"] == "Palavra de Alento" for cc in luta.condicoes)
    antes = c.hp
    condicoes.tick(luta)
    assert c.hp == antes


# ==================================================================
# Bloco 5 — a invariante que segura as consultas sem filtro de duracao > 0
# ==================================================================

def test_nenhuma_condicao_com_duracao_zero_ou_negativa_sobrevive_a_um_tick():
    luta = LutaFake()
    condicoes.aplicar(luta, "chefe", "vulneravel", "Ruptura", "💠", duracao=1, valor=0.1)
    condicoes.aplicar(luta, "chefe", "reduz_dano", "Voto de Ferro", "🛡️", duracao=1, valor=0.1)
    condicoes.aplicar(luta, "chefe", "bonus_critico", "Ponto Cego", "🎯", duracao=1, valor=0.1)

    condicoes.tick(luta)

    assert luta.condicoes == []


def test_condicao_com_duracao_maior_sobrevive_e_a_expirada_some_no_mesmo_tick():
    luta = LutaFake()
    condicoes.aplicar(luta, "chefe", "vulneravel", "Expira", "💠", duracao=1, valor=0.1)
    condicoes.aplicar(luta, "chefe", "vulneravel", "Sobrevive", "💠", duracao=3, valor=0.1)

    condicoes.tick(luta)

    nomes = {c["nome"] for c in luta.condicoes}
    assert nomes == {"Sobrevive"}
    assert all(c["duracao"] > 0 for c in luta.condicoes)


# ==================================================================
# Bloco 6 — os 8 efeitos de habilidade
# ==================================================================

def test_dardo_arcano_ignora_a_defesa_do_chefe(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="mago", inteligencia=20)
    dados = game_data.HABILIDADES["dardo_arcano"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    combate._efeito_dardo_arcano(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    luta_com_def = combate.Luta([c], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_dardo_arcano(luta_com_def, c, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def == dano_sem_def


def test_golpe_aberto_aplica_a_defesa_do_chefe_ao_contrario_do_dardo_arcano(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20)
    dados = game_data.HABILIDADES["golpe_aberto"]

    luta_sem_def = combate.Luta([c], {**CHEFE_TESTE, "def": 0}, andar_num=1)
    combate._efeito_golpe_aberto(luta_sem_def, c, dados)
    dano_sem_def = luta_sem_def.hp_chefe_max - luta_sem_def.hp_chefe

    luta_com_def = combate.Luta([c], {**CHEFE_TESTE, "def": 500}, andar_num=1)
    combate._efeito_golpe_aberto(luta_com_def, c, dados)
    dano_com_def = luta_com_def.hp_chefe_max - luta_com_def.hp_chefe

    assert dano_com_def < dano_sem_def


def test_ruptura_aplica_vulneravel_no_chefe_sem_causar_dano():
    c = _combatente(1, classe="mago", inteligencia=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["ruptura"]

    combate._efeito_ruptura(luta, c, dados)

    assert luta.hp_chefe == luta.hp_chefe_max
    cond = luta.condicoes[-1]
    assert cond["tipo"] == "vulneravel"
    assert cond["alvo"] == "chefe"
    assert cond["valor"] == combate.VULNERAVEL_RUPTURA


def test_golpe_aberto_empilha_sangramento_ate_o_teto_de_3(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["golpe_aberto"]

    for _ in range(3):
        combate._efeito_golpe_aberto(luta, c, dados)

    stacks = [cc for cc in luta.condicoes if cc["nome"] == "Sangramento"]
    assert len(stacks) == 3


def test_golpe_aberto_no_quarto_uso_renova_a_primeira_pilha_em_vez_de_criar_a_quarta(monkeypatch):
    _sem_variancia(monkeypatch)
    c = _combatente(1, classe="guerreiro", forca=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["golpe_aberto"]

    for _ in range(3):
        combate._efeito_golpe_aberto(luta, c, dados)
    stacks_antes = [cc for cc in luta.condicoes if cc["nome"] == "Sangramento"]
    stacks_antes[0]["duracao"] = 1   # simula a primeira pilha quase expirando

    combate._efeito_golpe_aberto(luta, c, dados)   # 4º uso

    stacks_depois = [cc for cc in luta.condicoes if cc["nome"] == "Sangramento"]
    assert len(stacks_depois) == 3          # não virou 4
    assert stacks_depois[0]["duracao"] == 3   # a primeira pilha foi renovada, não criada de novo


def test_pancada_atordoante_chance_tem_teto_de_25_por_cento_com_forca_alta(monkeypatch):
    monkeypatch.setattr(combate.random, "random", lambda: 0.24999)   # abaixo do teto de 25%
    c = _combatente(1, classe="guerreiro", forca=999)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["pancada_atordoante"]

    combate._efeito_pancada_atordoante(luta, c, dados)

    assert any(cc["tipo"] == "pula_turno" for cc in luta.condicoes)


def test_pancada_atordoante_chance_no_piso_de_5_por_cento_com_forca_zero(monkeypatch):
    c = _combatente(1, classe="guerreiro", forca=0)
    dados = game_data.HABILIDADES["pancada_atordoante"]

    luta_acerta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    monkeypatch.setattr(combate.random, "random", lambda: 0.049)   # abaixo do piso de 5%
    combate._efeito_pancada_atordoante(luta_acerta, c, dados)
    assert any(cc["tipo"] == "pula_turno" for cc in luta_acerta.condicoes)

    luta_erra = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    monkeypatch.setattr(combate.random, "random", lambda: 0.05)   # no piso -- 0.05 < 0.05 é falso
    combate._efeito_pancada_atordoante(luta_erra, c, dados)
    assert not any(cc["tipo"] == "pula_turno" for cc in luta_erra.condicoes)


def test_corte_rapido_da_bonus_de_10_de_critico_por_golpe(monkeypatch):
    c = _combatente(1, classe="ladino", destreza=20)
    monkeypatch.setattr(combate.random, "uniform", lambda a, b: 1.0)
    dados = game_data.HABILIDADES["corte_rapido"]

    # limiar entre o crítico base e o crítico + bônus -- só crita com o bônus
    limiar = c.s["critico"] + combate.BONUS_CRITICO_CORTE_RAPIDO - 0.01
    assert limiar > c.s["critico"]   # sanity: o teste realmente depende do bônus

    monkeypatch.setattr(combate.random, "random", lambda: limiar)
    luta_com_bonus = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    combate._efeito_corte_rapido(luta_com_bonus, c, dados)
    dano_com_bonus = luta_com_bonus.hp_chefe_max - luta_com_bonus.hp_chefe

    monkeypatch.setattr(combate.random, "random", lambda: 1.0)   # nunca crita
    luta_sem_critico = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    combate._efeito_corte_rapido(luta_sem_critico, c, dados)
    dano_sem_critico = luta_sem_critico.hp_chefe_max - luta_sem_critico.hp_chefe

    assert dano_com_bonus > dano_sem_critico   # os dois golpes se beneficiaram do +0.10


def test_ponto_cego_aplica_no_combatente_nao_no_chefe():
    c = _combatente(1, classe="ladino", destreza=20)
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["ponto_cego"]

    combate._efeito_ponto_cego(luta, c, dados)

    cond = luta.condicoes[-1]
    assert cond["tipo"] == "bonus_critico"
    assert cond["alvo"] == c.id


def test_palavra_de_alento_aplica_no_alvo_recebido_nao_no_caster():
    c = _combatente(1, classe="orador", inteligencia=20)
    alvo = _combatente(2)
    luta = combate.Luta([c, alvo], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["palavra_de_alento"]

    combate._efeito_palavra_de_alento(luta, c, dados, alvo_id=alvo.id)

    cond = luta.condicoes[-1]
    assert cond["alvo"] == alvo.id
    assert cond["alvo"] != c.id


def test_voto_de_ferro_aplica_em_todos_os_ativos_um_por_combatente_e_ignora_quem_caiu():
    c1 = _combatente(1, classe="orador", inteligencia=20)
    c2 = _combatente(2)
    c3 = _combatente(3)
    c3.caiu = True   # já não está mais na luta -- não deveria receber o buff
    luta = combate.Luta([c1, c2, c3], CHEFE_TESTE, andar_num=1)
    dados = game_data.HABILIDADES["voto_de_ferro"]

    combate._efeito_voto_de_ferro(luta, c1, dados)

    buffados = [cc["alvo"] for cc in luta.condicoes if cc["tipo"] == "reduz_dano"]
    assert set(buffados) == {c1.id, c2.id}   # inclui o próprio orador, exclui quem caiu
    assert len(buffados) == 2                # um por combatente, sem duplicar


# ==================================================================
# BUG NOVO — tick() decrementa cada condição no MESMO laço em que aplica o
# efeito dela. Quando cura_por_rodada consulta reducao_cura_recebida()
# durante o próprio tick(), uma Ferida Sombria em duracao==1 já foi
# decrementada se estiver ANTES dela em luta.condicoes (então não conta,
# como a docstring promete), mas AINDA NÃO se estiver DEPOIS (conta, contra
# a docstring). xfail na ordem que quebra a promessa -- ver decisoes.md.
# ==================================================================

def _luta_ferida_sombria_expirando_com_cura_por_rodada(ordem):
    alvo = CombatenteFake(id=1, hp=50, hp_max=100)
    luta = LutaFake(combatentes=[alvo])
    if ordem == "reduz_cura_primeiro":
        condicoes.aplicar(luta, alvo.id, "reduz_cura", "Ferida Sombria", "🌑", duracao=1, valor=0.5)
        condicoes.aplicar(luta, alvo.id, "cura_por_rodada", "Regeneração", "💚", duracao=1, valor=20)
    else:
        condicoes.aplicar(luta, alvo.id, "cura_por_rodada", "Regeneração", "💚", duracao=1, valor=20)
        condicoes.aplicar(luta, alvo.id, "reduz_cura", "Ferida Sombria", "🌑", duracao=1, valor=0.5)
    return luta, alvo


def test_ferida_sombria_expirando_na_mesma_rodada_nao_reduz_a_cura_quando_vem_antes_na_lista():
    """A ordem que a docstring de reducao_cura_recebida pressupõe: Ferida
    Sombria processada (e decrementada) ANTES da cura_por_rodada que a
    consulta -- ela já não conta mais quando a cura tica."""
    luta, alvo = _luta_ferida_sombria_expirando_com_cura_por_rodada("reduz_cura_primeiro")

    condicoes.tick(luta)

    assert alvo.hp == 70   # cura cheia (20) -- Ferida Sombria expirando não contou


@pytest.mark.xfail(reason=(
    "condicoes.tick() decrementa cada condição no mesmo laço em que aplica "
    "seu efeito. Se a cura_por_rodada vem ANTES da reduz_cura em "
    "luta.condicoes, a Ferida Sombria ainda tem duracao==1 (não decrementada) "
    "quando a cura consulta reducao_cura_recebida() -- ela CONTA mesmo "
    "expirando nesta rodada, contra o que a docstring promete. A promessa só "
    "se sustenta numa das duas ordens de inserção. Ver decisoes.md § Bug de "
    "ordem no tick() de condições."
))
def test_ferida_sombria_expirando_na_mesma_rodada_nao_deveria_reduzir_a_cura_quando_vem_depois_na_lista():
    luta, alvo = _luta_ferida_sombria_expirando_com_cura_por_rodada("cura_por_rodada_primeiro")

    condicoes.tick(luta)

    assert alvo.hp == 70   # deveria ser cura cheia (mesma promessa da docstring) -- na prática dá 60
