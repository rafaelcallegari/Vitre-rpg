# tests/test_efeitos_acessorio.py
# Step D, commit 3: efeitos em acessório. Reaproveita passivas.py (o motor
# das ascensões) -- um efeito de acessório é uma passiva cuja origem é a
# peça equipada (instancias.efeito) em vez da ascensão. `passivas.py` passa
# a somar as duas fontes; anel e colar com o MESMO efeito somam entre si.
# Ver decisoes.md § Step D.
import bot
import combate
import database as db
import game_data
import passivas

CHEFE_TESTE = {"nome": "Testinho", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0}
CHEFE_ELEMENTAL = {"nome": "Testinho do Vento", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0, "elemento": "ar"}


def _jogador(user_id=1, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    if campos:
        db.atualizar_jogador(user_id, **campos)
    return db.get_jogador(user_id)


def _equipar_efeito(user_id, campo_instancia, efeito, item="anel_forca"):
    """Cria uma instância de anel/colar com o `efeito` dado e equipa no
    jogador -- `campo_instancia` é 'anel_instancia_id' ou
    'colar_instancia_id'. Item base é irrelevante pra passivas.py (só o
    campo `efeito` da instância importa), mas equipa um de verdade
    (mesmo padrão de com_instancia) pra ficar realista."""
    slot = "anel" if "anel" in campo_instancia else "colar"
    instancia_id = db.criar_instancia(user_id, item)
    db.definir_efeito_instancia(instancia_id, efeito)
    db.atualizar_jogador(user_id, **{slot: item, campo_instancia: instancia_id})
    return instancia_id


# ==================================================================
# database.py -- a instância passa a poder carregar um efeito
# ==================================================================

def test_instancia_nasce_sem_efeito():
    iid = db.criar_instancia(1, "anel_forca")
    assert db.get_instancia(iid)["efeito"] is None


def test_definir_efeito_instancia_grava_e_le():
    iid = db.criar_instancia(1, "anel_forca")
    db.definir_efeito_instancia(iid, "cura_ao_critico")
    assert db.get_instancia(iid)["efeito"] == "cura_ao_critico"


def test_definir_efeito_convive_com_encantamento_e_melhoria():
    """As três camadas (melhoria do Forjador, encantamento do
    Encantador, efeito da Entidade Sombria) são independentes na mesma
    linha -- mesmo padrão de joia_*/encantamento_*."""
    iid = db.criar_instancia(1, "anel_forca")
    db.set_nivel_melhoria(iid, 2)
    db.definir_encantamento(iid, "forca", 5)
    db.definir_efeito_instancia(iid, "furia_extra_ao_apanhar")
    instancia = db.get_instancia(iid)
    assert instancia["nivel_melhoria"] == 2
    assert instancia["encantamento_atributo"] == "forca"
    assert instancia["efeito"] == "furia_extra_ao_apanhar"


# ==================================================================
# bot.com_instancia -- propaga o efeito pro dict resolvido
# ==================================================================

def test_com_instancia_propaga_efeito():
    iid = db.criar_instancia(1, "anel_forca")
    db.definir_efeito_instancia(iid, "ignora_condicao")
    resolvido = bot.com_instancia(dict(game_data.ITENS["anel_forca"]), iid)
    assert resolvido["_efeito"] == "ignora_condicao"


def test_com_instancia_sem_efeito_nao_cria_a_chave():
    iid = db.criar_instancia(1, "anel_forca")
    resolvido = bot.com_instancia(dict(game_data.ITENS["anel_forca"]), iid)
    assert "_efeito" not in resolvido


# ==================================================================
# passivas.py -- soma acessório + ascensão, por fonte
# ==================================================================

def test_sem_ascensao_e_sem_acessorio_os_tres_efeitos_sao_neutros():
    j = _jogador(1)
    assert passivas.cura_fracao_ao_critico(j) == 0.0
    assert passivas.chance_ignora_condicao(j) == 0.0
    assert passivas.bonus_furia_ao_apanhar(j) == 0


def test_um_acessorio_com_efeito_conta_como_uma_fonte():
    j = _jogador(1)
    _equipar_efeito(1, "anel_instancia_id", "cura_ao_critico")
    j = db.get_jogador(1)
    assert passivas.cura_fracao_ao_critico(j) == game_data.PASSIVAS["cura_ao_critico"]["valor"]


def test_anel_e_colar_com_o_mesmo_efeito_somam_as_duas_fontes():
    _jogador(1)
    _equipar_efeito(1, "anel_instancia_id", "ignora_condicao")
    _equipar_efeito(1, "colar_instancia_id", "ignora_condicao", item="colar_forca")
    j = db.get_jogador(1)
    esperado = game_data.PASSIVAS["ignora_condicao"]["valor"] * 2
    assert passivas.chance_ignora_condicao(j) == esperado


def test_ascensao_e_acessorio_juntos_somam_tres_fontes_no_maximo_pratico():
    """O cartão: 'ascensão e dois acessórios pode somar três fontes' --
    aqui simulado com uma ascensão real (assassino, sangue_frio) mais
    dois acessórios com o MESMO efeito novo -- os dois tipos de fonte
    (ascensão + acessório) convivem na mesma consulta sem se atropelar."""
    _jogador(1, classe="ladino", ascensao="assassino")
    _equipar_efeito(1, "anel_instancia_id", "furia_extra_ao_apanhar")
    _equipar_efeito(1, "colar_instancia_id", "furia_extra_ao_apanhar", item="colar_forca")
    j = db.get_jogador(1)
    # a ascensão (assassino) não concede furia_extra_ao_apanhar -- só os
    # dois acessórios contam, então são 2 fontes, não 3, aqui.
    esperado = game_data.PASSIVAS["furia_extra_ao_apanhar"]["valor"] * 2
    assert passivas.bonus_furia_ao_apanhar(j) == esperado
    # mas a ascensão AINDA concede sangue_frio normalmente -- as fontes
    # de efeitos diferentes não se confundem.
    assert passivas._fontes_do_efeito(j, "sangue_frio") == 1


def test_efeito_de_acessorio_nao_vaza_pra_quem_nao_equipou():
    _jogador(1)
    _jogador(2)
    _equipar_efeito(1, "anel_instancia_id", "cura_ao_critico")
    assert passivas.cura_fracao_ao_critico(db.get_jogador(1)) > 0
    assert passivas.cura_fracao_ao_critico(db.get_jogador(2)) == 0.0


def test_tem_passiva_de_ascensao_continua_funcionando_sem_acessorio(monkeypatch):
    """Regressão: o refactor de _tem_passiva pra contagem de fontes não
    pode quebrar as passivas de ascensão já existentes (bool simples)."""
    j = _jogador(1, classe="ladino", ascensao="assassino")
    assert passivas._tem_passiva(j, "sangue_frio") is True
    assert passivas._tem_passiva(j, "instinto_ladino") is True
    assert passivas._tem_passiva(j, "bencao") is False


def test_bonus_reducao_dano_continua_bool_simples_pra_disciplina():
    """Disciplina (soldado) não é um dos três efeitos de acessório --
    nunca chega via instancias.efeito -- então continua valendo uma vez
    só, exatamente como antes do commit 3."""
    j = _jogador(1, classe="guerreiro", ascensao="soldado")
    assert passivas.bonus_reducao_dano(j) == game_data.PASSIVAS["disciplina"]["valor"]


# ==================================================================
# combate.py -- os três efeitos de verdade, dentro de uma luta
# ==================================================================

def test_cura_ao_critico_cura_o_jogador_num_golpe_critico():
    j = _jogador(1, classe="guerreiro", forca=20, hp=1)
    _equipar_efeito(1, "anel_instancia_id", "cura_ao_critico")
    j = db.get_jogador(1)
    c = combate.Combatente(j, bot.stats(j))
    combate._curar_por_critico(c, critico=True)
    assert c.hp > 1


def test_cura_ao_critico_nao_cura_sem_critico():
    j = _jogador(1, classe="guerreiro", forca=20, hp=1)
    _equipar_efeito(1, "anel_instancia_id", "cura_ao_critico")
    j = db.get_jogador(1)
    c = combate.Combatente(j, bot.stats(j))
    combate._curar_por_critico(c, critico=False)
    assert c.hp == 1


def test_cura_ao_critico_nao_cura_sem_o_efeito():
    j = _jogador(1, classe="guerreiro", forca=20, hp=1)
    c = combate.Combatente(j, bot.stats(j))
    combate._curar_por_critico(c, critico=True)
    assert c.hp == 1


def test_furia_extra_ao_apanhar_soma_na_furia_do_guerreiro():
    j = _jogador(1, classe="guerreiro", forca=20)
    _equipar_efeito(1, "anel_instancia_id", "furia_extra_ao_apanhar")
    j = db.get_jogador(1)
    c = combate.Combatente(j, bot.stats(j))
    furia_antes = c.furia
    combate._ganhar_furia_por_efeito_ao_apanhar(c, dano_recebido=10)
    assert c.furia == furia_antes + game_data.PASSIVAS["furia_extra_ao_apanhar"]["valor"]


def test_furia_extra_ao_apanhar_nao_dispara_sem_dano():
    j = _jogador(1, classe="guerreiro", forca=20)
    _equipar_efeito(1, "anel_instancia_id", "furia_extra_ao_apanhar")
    j = db.get_jogador(1)
    c = combate.Combatente(j, bot.stats(j))
    furia_antes = c.furia
    combate._ganhar_furia_por_efeito_ao_apanhar(c, dano_recebido=0)
    assert c.furia == furia_antes


def test_furia_extra_ao_apanhar_nao_dispara_pra_quem_nao_e_guerreiro():
    j = _jogador(1, classe="mago", inteligencia=20)
    _equipar_efeito(1, "anel_instancia_id", "furia_extra_ao_apanhar")
    j = db.get_jogador(1)
    c = combate.Combatente(j, bot.stats(j))
    combate._ganhar_furia_por_efeito_ao_apanhar(c, dano_recebido=10)
    assert c.furia == 0


def test_veu_cinza_pode_ignorar_a_condicao_telegrafada(monkeypatch):
    j = _jogador(1, classe="guerreiro", forca=20)
    _equipar_efeito(1, "anel_instancia_id", "ignora_condicao")
    j = db.get_jogador(1)
    c = combate.Combatente(j, bot.stats(j))
    luta = combate.Luta([c], CHEFE_ELEMENTAL, andar_num=11)
    inimigo = luta.inimigos[0]
    inimigo.preparando_condicao = {**game_data.CONDICOES_ELEMENTO["ar"], "alvo_id": c.id}
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)   # sempre "rola baixo" -- ignora se a chance > 0
    luta._resolver_condicao_pendente(inimigo)
    assert luta.condicoes == []


def test_sem_veu_cinza_a_condicao_aplica_normalmente(monkeypatch):
    j = _jogador(1, classe="guerreiro", forca=20)
    c = combate.Combatente(j, bot.stats(j))
    luta = combate.Luta([c], CHEFE_ELEMENTAL, andar_num=11)
    inimigo = luta.inimigos[0]
    inimigo.preparando_condicao = {**game_data.CONDICOES_ELEMENTO["ar"], "alvo_id": c.id}
    monkeypatch.setattr(combate.random, "random", lambda: 0.99)   # nunca ignora (chance == 0 de qualquer jeito)
    luta._resolver_condicao_pendente(inimigo)
    assert len(luta.condicoes) == 1
    assert luta.condicoes[0]["nome"] == "Vendaval"


def test_veu_cinza_nao_ignora_quando_o_dado_nao_favorece(monkeypatch):
    """20% de chance (uma fonte) -- com random() sempre alto, nunca cai
    dentro da chance, então a condição aplica normalmente mesmo com o
    efeito equipado."""
    j = _jogador(1, classe="guerreiro", forca=20)
    _equipar_efeito(1, "anel_instancia_id", "ignora_condicao")
    j = db.get_jogador(1)
    c = combate.Combatente(j, bot.stats(j))
    luta = combate.Luta([c], CHEFE_ELEMENTAL, andar_num=11)
    inimigo = luta.inimigos[0]
    inimigo.preparando_condicao = {**game_data.CONDICOES_ELEMENTO["ar"], "alvo_id": c.id}
    monkeypatch.setattr(combate.random, "random", lambda: 0.99)
    luta._resolver_condicao_pendente(inimigo)
    assert len(luta.condicoes) == 1


# ==================================================================
# regressão -- sem efeito de acessório equipado, nada muda
# ==================================================================

def test_luta_sem_nenhum_efeito_de_acessorio_se_comporta_como_sempre():
    j = _jogador(1, classe="guerreiro", forca=20, hp=50)
    c = combate.Combatente(j, bot.stats(j))
    combate._curar_por_critico(c, critico=True)
    assert c.hp == 50
    combate._ganhar_furia_por_efeito_ao_apanhar(c, dano_recebido=10)
    assert c.furia == 0
