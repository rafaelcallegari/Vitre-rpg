# tests/test_status_equipamento.py
# `rpg status` ganhou um campo mostrando o que está equipado -- lendo o que
# `stats()` já resolve (bônus de melhoria incluso), sem recalcular nada.
# Ver decisoes.md § Equipamento no rpg status.
import atributos as at
import bot
import database as db


def _jogador(**campos):
    db.criar_jogador(1, "Alice")
    if campos:
        db.atualizar_jogador(1, **campos)
    return db.get_jogador(1)


def test_stats_expoe_none_pros_quatro_slots_vazios():
    j = _jogador()
    s = bot.stats(j)
    assert s["equipamento"] == {"arma": None, "armadura": None, "anel": None, "colar": None}


def test_stats_expoe_a_peca_resolvida_quando_equipada():
    j = _jogador(arma="espada_ferro")
    s = bot.stats(j)
    chave, dado = s["equipamento"]["arma"]
    assert chave == "espada_ferro"
    assert dado["nome"] == "Espada de Ferro"
    assert dado["atk"] == 8   # sem melhoria, é o valor cru do item


def _melhorar(user_id, slot, item, nivel):
    """Simula uma peça equipada e melhorada -- cria a instância e aponta o
    slot pra ela, mesmo caminho que `rpg melhorar` usa na primeira melhoria."""
    instancia_id = db.criar_instancia(user_id, item, nivel)
    db.atualizar_jogador(user_id, **{f"{slot}_instancia_id": instancia_id})
    return instancia_id


def test_stats_expoe_o_bonus_de_melhoria_ja_aplicado_na_arma():
    j = _jogador(arma="espada_ferro")
    _melhorar(1, "arma", "espada_ferro", 2)
    j = db.get_jogador(1)
    s = bot.stats(j)
    _, dado = s["equipamento"]["arma"]
    assert dado["atk"] == int(8 * (1 + 0.12 * 2))   # mesma conta de com_bonus_upgrade


def test_texto_equipamento_marca_slot_vazio():
    j = _jogador()
    s = bot.stats(j)
    texto = bot.texto_equipamento(s)
    assert texto.count("*vazio*") == 4   # arma, armadura, anel e colar


def test_texto_equipamento_mostra_nome_e_bonus_de_cada_peca():
    j = _jogador(arma="espada_ferro", armadura="couro_batido",
                  anel="anel_forca", colar="colar_inteligencia")
    s = bot.stats(j)
    texto = bot.texto_equipamento(s)
    assert "Espada de Ferro" in texto and "+8 ATK" in texto
    assert "Couro Batido" in texto and "+8 DEF" in texto
    assert "Anel do Punho Firme" in texto and "+4 FOR" in texto
    assert "Colar do Eco Arcano" in texto and "+2 INT" in texto
    assert "*vazio*" not in texto


def test_texto_equipamento_mostra_o_nivel_de_melhoria():
    j = _jogador(arma="espada_ferro")
    _melhorar(1, "arma", "espada_ferro", 2)
    j = db.get_jogador(1)
    s = bot.stats(j)
    texto = bot.texto_equipamento(s)
    assert "+2" in texto


def test_texto_equipamento_sem_melhoria_nao_mostra_nivel():
    j = _jogador(arma="espada_ferro")
    s = bot.stats(j)
    texto = bot.texto_equipamento(s)
    linha_arma = next(l for l in texto.splitlines() if "Espada de Ferro" in l)
    assert "+8 ATK (FOR)" in linha_arma   # nada de "+0" ou "+None" sobrando


def test_soma_dos_bonus_bate_com_ataque_e_defesa_mostrados():
    """O mesmo cenário do smoke test manual: arma +2, anel de FOR, colar de
    INT -- confere a fórmula pública de atributos.ataque()/defesa() bate
    com o valor final que `rpg status` mostra."""
    j = _jogador(arma="espada_ferro", armadura="couro_batido",
                  anel="anel_forca", colar="colar_inteligencia")
    _melhorar(1, "arma", "espada_ferro", 2)
    j = db.get_jogador(1)
    s = bot.stats(j)

    atk_arma = s["equipamento"]["arma"][1]["atk"]
    def_armadura = s["equipamento"]["armadura"][1]["def"]
    bonus_for = s["equipamento"]["anel"][1]["bonus"]

    for_total = at.BASE + bonus_for
    assert s["atk"] == at.ataque(for_total, atk_arma)
    assert s["def"] == at.defesa(def_armadura)
