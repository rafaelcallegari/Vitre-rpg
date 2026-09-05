# tests/test_espelhos.py
# Cartão "Step 3 — os 4 espelhos e o motor de decisão de chefe", commit 3:
# as 12 habilidades revertidas (jogador ataca chefe -> espelho ataca
# jogador), a rotina por classe (chefe_ia.decidir_acao escolhendo qual
# habilidade do kit lançar) e o turno do espelho. Ver decisoes.md § Step 3
# pra escolha de design (funções PRÓPRIAS, não generalização das
# _efeito_* de combate.py).
import inspect

import bot
import chefe_ia
import combate
import condicoes
import database as db
import espelhos
import game_data

CHEFE_TESTE = {"nome": "Testinho", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0}


def _combatente(user_id, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


def _luta_espelho(chave_espelho, jogador, atk=50, hp=2000, defesa=0):
    dados = dict(game_data.DUNGEON_ESPELHOS_DADOS[chave_espelho])
    dados["e_espelho"] = True
    dados["atk"] = atk
    dados["hp"] = hp
    dados["def"] = defesa
    return combate.Luta([jogador], dados, andar_num=9)


def _sem_variancia(monkeypatch):
    monkeypatch.setattr(espelhos.random, "uniform", lambda a, b: 1.0)
    monkeypatch.setattr(espelhos.random, "random", lambda: 1.0)   # nunca crita, nunca atordoa/envenena


# ==================================================================
# Catálogo -- cada classe encontra sempre o próprio espelho
# ==================================================================

def test_cada_classe_tem_um_espelho_proprio_com_kit_de_tres():
    for classe, chave in game_data.DUNGEON_ESPELHOS.items():
        dados = game_data.DUNGEON_ESPELHOS_DADOS[chave]
        assert dados["classe"] == classe
        assert len(dados["kit"]) == 3


def test_arauto_nao_tem_reerguer_so_chama_divina():
    """"O Arauto NÃO se levanta" -- a rotina dele nunca aponta pra uma
    versão de party de graca_divina, e a função de efeito É sempre
    Chama Divina (a luta do espelho é sempre solo)."""
    rotina = espelhos.ROTINA_POR_CLASSE["orador"]
    assert set(rotina.values()) <= {"graca_divina", "voto_de_ferro"}
    assert espelhos.EFEITOS_ESPELHO["graca_divina"] is espelhos._efeito_espelho_chama_divina


# ==================================================================
# Dardo Arcano (mago) -- ignora defesa
# ==================================================================

def test_dardo_arcano_ignora_a_defesa_do_jogador(monkeypatch):
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="mago", inteligencia=20)
    luta_sem_def = _luta_espelho("espectro_do_lich", jogador, defesa=0)
    hp_antes = jogador.hp
    espelhos._efeito_espelho_dardo_arcano(luta_sem_def, jogador)
    dano_sem_def = hp_antes - jogador.hp

    jogador2 = _combatente(2, classe="mago", inteligencia=20)
    luta_com_def = _luta_espelho("espectro_do_lich", jogador2, defesa=500)
    hp_antes2 = jogador2.hp
    espelhos._efeito_espelho_dardo_arcano(luta_com_def, jogador2)
    dano_com_def = hp_antes2 - jogador2.hp

    assert dano_sem_def == dano_com_def   # defesa não muda nada -- ignora, igual o original


# ==================================================================
# Ruptura (mago) -- puro debuff, vulnerável no JOGADOR, sem dano
# ==================================================================

def test_ruptura_aplica_vulneravel_no_jogador_sem_causar_dano():
    jogador = _combatente(1, classe="mago", inteligencia=20)
    luta = _luta_espelho("espectro_do_lich", jogador)
    hp_antes = jogador.hp

    espelhos._efeito_espelho_ruptura(luta, jogador)

    assert jogador.hp == hp_antes   # sem dano
    cond = next(c for c in luta.condicoes if c["tipo"] == "vulneravel")
    assert cond["alvo"] == jogador.id
    assert condicoes.multiplicador_dano_causado(luta, jogador.id) > 1.0


def test_ruptura_com_vulneravel_ja_ativo_ataca_em_vez_de_empilhar(monkeypatch):
    """Achado na calibragem: sem essa guarda, a rotina caindo em
    "pressionar" repetidas vezes empilharia "vulnerável" sem teto --
    uma escalada que o jogador fazendo a mesma coisa contra um chefe de
    verdade não tem (`condicoes.aplicar` nunca funde condições)."""
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="mago", inteligencia=20)
    luta = _luta_espelho("espectro_do_lich", jogador)
    espelhos._efeito_espelho_ruptura(luta, jogador)   # primeira vez -- aplica
    hp_antes = jogador.hp

    espelhos._efeito_espelho_ruptura(luta, jogador)   # segunda vez -- deveria atacar, não empilhar

    vulneraveis = [c for c in luta.condicoes if c["tipo"] == "vulneravel"]
    assert len(vulneraveis) == 1   # não virou 2
    assert jogador.hp < hp_antes   # atacou de verdade (Dardo Arcano)


def test_vulneravel_da_ruptura_de_verdade_aumenta_o_dano_que_o_jogador_toma(monkeypatch):
    """Achado durante a calibragem (commit 4): aplicar "vulneravel" no
    jogador sem NENHUM dano consultar `multiplicador_dano_causado(luta,
    jogador.id)` seria puro teatro -- a condição existiria mas nunca
    morderia. `_aplicar_dano_no_jogador` agora consulta essa multiplicação
    genérica (já existia em condicoes.py, só não estava plugada)."""
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="mago", inteligencia=20)
    luta = _luta_espelho("espectro_do_lich", jogador)
    hp_antes = jogador.hp
    espelhos._efeito_espelho_dardo_arcano(luta, jogador)
    dano_sem_vulneravel = hp_antes - jogador.hp

    jogador2 = _combatente(2, classe="mago", inteligencia=20)
    luta2 = _luta_espelho("espectro_do_lich", jogador2)
    condicoes.aplicar(luta2, jogador2.id, "vulneravel", "Marca", "✨", duracao=5, valor=0.20, origem="chefe")
    hp_antes2 = jogador2.hp
    espelhos._efeito_espelho_dardo_arcano(luta2, jogador2)
    dano_com_vulneravel = hp_antes2 - jogador2.hp

    assert dano_com_vulneravel == int(dano_sem_vulneravel * 1.20)


# ==================================================================
# Prisão de Cristal (mago_gelo) -- dano com defesa + trava ataque E skill
# ==================================================================

def test_prisao_de_cristal_aplica_defesa_e_trava_ataque_e_habilidade(monkeypatch):
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="mago", inteligencia=20)
    luta = _luta_espelho("espectro_do_lich", jogador)

    espelhos._efeito_espelho_prisao_de_cristal(luta, jogador)

    assert jogador.hp < jogador.s["hp_max"]
    assert condicoes.pode_agir(luta, jogador.id) is False
    assert condicoes.pode_lancar_habilidade(luta, jogador.id) is False


# ==================================================================
# Golpe Aberto (guerreiro) -- dano + sangramento empilhável até 3
# ==================================================================

def test_golpe_aberto_aplica_dano_com_defesa_e_sangramento(monkeypatch):
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta_espelho("campeao_da_arena", jogador)

    espelhos._efeito_espelho_golpe_aberto(luta, jogador)

    assert jogador.hp < jogador.s["hp_max"]
    sangramentos = [c for c in luta.condicoes if c["tipo"] == "dano_por_rodada" and c["nome"] == "Sangramento"]
    assert len(sangramentos) == 1
    assert sangramentos[0]["alvo"] == jogador.id


def test_golpe_aberto_empilha_ate_tres_depois_renova_em_vez_de_empilhar(monkeypatch):
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta_espelho("campeao_da_arena", jogador)

    for _ in range(4):
        espelhos._efeito_espelho_golpe_aberto(luta, jogador)

    sangramentos = [c for c in luta.condicoes if c["tipo"] == "dano_por_rodada" and c["nome"] == "Sangramento"]
    assert len(sangramentos) == 3   # nunca passa de 3 pilhas


# ==================================================================
# Pancada Atordoante (guerreiro) -- chance fixa, trava ataque E skill
# ==================================================================

def test_pancada_atordoante_acerta_trava_o_jogador_e_causa_dano(monkeypatch):
    monkeypatch.setattr(espelhos.random, "uniform", lambda a, b: 1.0)
    monkeypatch.setattr(espelhos.random, "random", lambda: 0.0)   # sempre acerta
    jogador = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta_espelho("campeao_da_arena", jogador)
    hp_antes = jogador.hp

    espelhos._efeito_espelho_pancada_atordoante(luta, jogador)

    assert condicoes.pode_agir(luta, jogador.id) is False
    assert condicoes.pode_lancar_habilidade(luta, jogador.id) is False
    assert jogador.hp < hp_antes


def test_pancada_atordoante_erra_o_atordoamento_mas_ainda_causa_dano(monkeypatch):
    """DIFERENÇA DELIBERADA do original (que nunca causa dano, nem
    acertando nem errando o atordoamento) -- ver decisoes.md § Step 3,
    achado calibrando o commit 4: sem dano nenhum, o Campeão da Arena
    passava rodadas inteiras sem ameaçar nada."""
    monkeypatch.setattr(espelhos.random, "uniform", lambda a, b: 1.0)
    monkeypatch.setattr(espelhos.random, "random", lambda: 0.99)   # sempre falha o atordoamento
    jogador = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta_espelho("campeao_da_arena", jogador)
    hp_antes = jogador.hp

    espelhos._efeito_espelho_pancada_atordoante(luta, jogador)

    assert condicoes.pode_agir(luta, jogador.id) is True   # não travou
    assert jogador.hp < hp_antes   # mas causou dano mesmo assim


# ==================================================================
# Golpe Oportunista (mercenário) -- escala com o quanto O ESPELHO perdeu
# ==================================================================

def test_golpe_oportunista_cresce_conforme_o_espelho_perde_hp(monkeypatch):
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="guerreiro", forca=20, constituicao=50)
    luta_cheio = _luta_espelho("campeao_da_arena", jogador, hp=2000)
    hp_antes = jogador.hp
    espelhos._efeito_espelho_golpe_oportunista(luta_cheio, jogador)
    dano_cheio = hp_antes - jogador.hp

    jogador2 = _combatente(2, classe="guerreiro", forca=20, constituicao=50)
    luta_baixo = _luta_espelho("campeao_da_arena", jogador2, hp=2000)
    luta_baixo.hp_chefe = 1   # quase morto
    hp_antes2 = jogador2.hp
    espelhos._efeito_espelho_golpe_oportunista(luta_baixo, jogador2)
    dano_baixo = hp_antes2 - jogador2.hp

    assert dano_baixo > dano_cheio


# ==================================================================
# Corte Rápido (ladino) -- dois golpes com defesa
# ==================================================================

def test_corte_rapido_desfere_dois_golpes(monkeypatch):
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="ladino", destreza=20)
    luta = _luta_espelho("assassino_do_vento", jogador)
    hp_antes = jogador.hp

    espelhos._efeito_espelho_corte_rapido(luta, jogador)

    assert jogador.hp < hp_antes
    assert luta.log[-1].count("+") == 1   # "X + Y = total" -- exatamente dois golpes somados


# ==================================================================
# Ponto Cego (ladino) -- auto-buff, sem dano, afeta golpes seguintes
# ==================================================================

def test_ponto_cego_e_um_auto_buff_sem_dano_que_vale_pro_proximo_golpe():
    jogador = _combatente(1, classe="ladino", destreza=20)
    luta = _luta_espelho("assassino_do_vento", jogador)
    hp_antes = jogador.hp

    espelhos._efeito_espelho_ponto_cego(luta, jogador)

    assert jogador.hp == hp_antes
    assert condicoes.bonus_critico(luta, "chefe") == 0.45


def test_ponto_cego_com_buff_ja_ativo_ataca_em_vez_de_empilhar(monkeypatch):
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="ladino", destreza=20)
    luta = _luta_espelho("assassino_do_vento", jogador)
    espelhos._efeito_espelho_ponto_cego(luta, jogador)
    hp_antes = jogador.hp

    espelhos._efeito_espelho_ponto_cego(luta, jogador)

    buffs = [c for c in luta.condicoes if c["tipo"] == "bonus_critico"]
    assert len(buffs) == 1
    assert jogador.hp < hp_antes   # atacou (Corte Rápido) em vez de empilhar o buff


# ==================================================================
# Golpe Fatal (assassino) -- escala com o quanto O JOGADOR já perdeu
# ==================================================================

def test_golpe_fatal_cresce_conforme_o_jogador_perde_hp(monkeypatch):
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="ladino", destreza=20, constituicao=50)
    luta = _luta_espelho("assassino_do_vento", jogador)
    hp_max = jogador.s["hp_max"]
    jogador.hp = hp_max
    hp_antes = jogador.hp
    espelhos._efeito_espelho_golpe_fatal(luta, jogador)
    dano_cheio = hp_antes - jogador.hp

    jogador2 = _combatente(2, classe="ladino", destreza=20, constituicao=50)
    luta2 = _luta_espelho("assassino_do_vento", jogador2)
    jogador2.hp = 1
    espelhos._efeito_espelho_golpe_fatal(luta2, jogador2)
    dano_baixo = 1 - jogador2.hp   # quanto ele ainda perdeu, mesmo já quase morto (pode passar de 1 negativo)

    assert dano_baixo >= dano_cheio


# ==================================================================
# Palavra de Alento / Voto de Ferro (orador) -- espelho cuida de si
# ==================================================================

def test_palavra_de_alento_cura_o_proprio_espelho_sem_tocar_no_jogador():
    jogador = _combatente(1, classe="orador", inteligencia=20)
    luta = _luta_espelho("arauto_dos_deuses", jogador, hp=2000)
    luta.hp_chefe = 1000
    hp_jogador_antes = jogador.hp

    espelhos._efeito_espelho_palavra_de_alento(luta, jogador)

    assert luta.hp_chefe > 1000
    assert luta.hp_chefe <= luta.hp_chefe_max
    assert jogador.hp == hp_jogador_antes


def test_voto_de_ferro_aumenta_a_defesa_do_espelho_permanentemente_uma_vez():
    jogador = _combatente(1, classe="orador", inteligencia=20)
    luta = _luta_espelho("arauto_dos_deuses", jogador, defesa=20)

    espelhos._efeito_espelho_voto_de_ferro(luta, jogador)
    assert luta.chefe["def"] == 30   # 20 * 1.5

    espelhos._efeito_espelho_voto_de_ferro(luta, jogador)   # segunda vez -- não aplica de novo
    assert luta.chefe["def"] == 30


def test_voto_de_ferro_ja_usado_ataca_em_vez_de_nao_fazer_nada(monkeypatch):
    """Achado na calibragem: um Arauto que só reforça a guarda e nunca
    ataca de novo nunca perde a luta -- a segunda vez em diante, Voto
    de Ferro vira Chama Divina (a única fonte de dano do kit)."""
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="orador", inteligencia=20)
    luta = _luta_espelho("arauto_dos_deuses", jogador, defesa=20)
    espelhos._efeito_espelho_voto_de_ferro(luta, jogador)   # gasta o único uso
    hp_antes = jogador.hp

    espelhos._efeito_espelho_voto_de_ferro(luta, jogador)   # de novo -- agora ataca

    assert jogador.hp < hp_antes


def test_chama_divina_e_dano_puro_com_defesa(monkeypatch):
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="orador", inteligencia=20)
    luta = _luta_espelho("arauto_dos_deuses", jogador)
    hp_antes = jogador.hp

    espelhos._efeito_espelho_chama_divina(luta, jogador)

    assert jogador.hp < hp_antes


# ==================================================================
# _rolar_dano_espelho -- crit consulta condicoes.bonus_critico("chefe")
# ==================================================================

def test_rolar_dano_espelho_usa_o_atk_do_proprio_chefe():
    import atributos as at
    jogador = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta_espelho("campeao_da_arena", jogador, atk=100)
    teto = 100 * 1.15 * at.MULTIPLICADOR_CRITICO * 1.01   # folga pro crítico eventual

    valores = [espelhos._rolar_dano_espelho(luta, 1.0) for _ in range(200)]

    assert all(100 * 0.85 * 0.99 <= v <= teto for v in valores)


def test_rolar_dano_espelho_bonus_critico_de_chefe_aumenta_a_chance(monkeypatch):
    """`condicoes.bonus_critico(luta, "chefe")` -- consulta genérica que
    já existia -- é o que faz o auto-buff do Ponto Cego valer nos
    golpes seguintes do espelho."""
    jogador = _combatente(1, classe="ladino", destreza=20)
    luta = _luta_espelho("assassino_do_vento", jogador, atk=100)
    monkeypatch.setattr(espelhos.random, "uniform", lambda a, b: 1.0)
    condicoes.aplicar(luta, "chefe", "bonus_critico", "Foco", "🎯", duracao=5, valor=1.0)   # 100% de crítico
    monkeypatch.setattr(espelhos.random, "random", lambda: 0.5)   # só passa se a chance somar >= 0.5

    import atributos as at
    valor = espelhos._rolar_dano_espelho(luta, 1.0)

    assert valor == 100 * at.MULTIPLICADOR_CRITICO   # criticou -- a chance somada bateu o roll de 0.5


# ==================================================================
# A rotina -- chefe_ia.decidir_acao escolhe qual habilidade do kit
# ==================================================================

def test_escolher_habilidade_padrao_e_o_primeiro_do_kit():
    jogador = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta_espelho("campeao_da_arena", jogador)
    jogador.hp = jogador.s["hp_max"]
    chefe_ia.registrar_fracao_recurso(luta, jogador.id, 0.3)   # não segurando recurso

    chave, motivo = espelhos.escolher_habilidade(luta, jogador.id)

    assert chave == "golpe_aberto"
    assert motivo is None


def test_escolher_habilidade_prioriza_carregado_com_jogador_em_pouco_hp():
    jogador = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta_espelho("campeao_da_arena", jogador)
    jogador.hp = 1

    chave, motivo = espelhos.escolher_habilidade(luta, jogador.id)

    assert chave == "golpe_oportunista"   # a habilidade de ascensão -- a "carregada" do kit
    assert motivo


def test_escolher_habilidade_pressionar_ou_reduzir_cura_escolhe_a_skill_de_utilidade():
    jogador = _combatente(1, classe="mago", inteligencia=20)
    luta = _luta_espelho("espectro_do_lich", jogador)
    jogador.hp = jogador.s["hp_max"]
    chefe_ia.registrar_fracao_recurso(luta, jogador.id, 1.0)

    chave, motivo = espelhos.escolher_habilidade(luta, jogador.id)

    assert chave == "ruptura"
    assert motivo


# ==================================================================
# turno_do_espelho -- alvo é sempre o único jogador, chama o efeito certo
# ==================================================================

def test_turno_do_espelho_ataca_o_unico_jogador_da_luta(monkeypatch):
    _sem_variancia(monkeypatch)
    jogador = _combatente(1, classe="ladino", destreza=20)
    luta = _luta_espelho("assassino_do_vento", jogador)
    jogador.hp = jogador.s["hp_max"]
    chefe_ia.registrar_fracao_recurso(luta, jogador.id, 0.3)
    hp_antes = jogador.hp

    espelhos.turno_do_espelho(luta)

    assert jogador.hp < hp_antes   # corte_rapido (padrao) causou dano


def test_turno_do_espelho_nao_faz_nada_se_jogador_ja_nao_esta_ativo():
    jogador = _combatente(1, classe="ladino", destreza=20)
    luta = _luta_espelho("assassino_do_vento", jogador)
    jogador.caiu = True
    hp_antes = jogador.hp

    espelhos.turno_do_espelho(luta)   # não deveria levantar nem mudar nada

    assert jogador.hp == hp_antes


def test_turno_do_espelho_registra_o_motivo_quando_ha_um():
    jogador = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta_espelho("campeao_da_arena", jogador)
    jogador.hp = 1   # dispara "priorizar_carregado", que tem motivo

    espelhos.turno_do_espelho(luta)

    assert any("👁️" in linha for linha in luta.log)


# ==================================================================
# Fronteira -- combate.Luta.turno_do_chefe só desvia pra espelhos.py
# quando `chefe.get("e_espelho")`; chefe de torre normal continua
# exatamente igual (mesmo espírito do teste de chefe_ia.py)
# ==================================================================

def test_chefe_de_torre_normal_nunca_chama_espelhos(monkeypatch):
    jogador = _combatente(1, classe="guerreiro", forca=20)
    luta = combate.Luta([jogador], CHEFE_TESTE, andar_num=1)
    luta.rodada = 2   # RODADA_1_SEM_CHEFE -- precisa avançar a rodada (armadilha do e687f27)
    chamou = {"sim": False}

    def _explode(*a, **k):
        chamou["sim"] = True
    monkeypatch.setattr(espelhos, "turno_do_espelho", _explode)

    luta.turno_do_chefe()

    assert chamou["sim"] is False


def test_chefe_marcado_como_espelho_chama_espelhos_turno(monkeypatch):
    jogador = _combatente(1, classe="guerreiro", forca=20)
    luta = _luta_espelho("campeao_da_arena", jogador)
    luta.rodada = 2
    chamou = {"sim": False}

    def _marca(luta_arg):
        chamou["sim"] = True
    monkeypatch.setattr(espelhos, "turno_do_espelho", _marca)

    luta.turno_do_chefe()

    assert chamou["sim"] is True
