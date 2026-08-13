# tests/test_trocas.py
# _commitar_troca é o único ponto onde item e moeda passam de um jogador
# para outro — o teste mais importante da suíte (ver decisoes.md).
import database as db
import trocas


def _criar_par(moedas_a=500, moedas_b=200, andar=1):
    db.criar_jogador(1, "Alice")
    db.criar_jogador(2, "Bob")
    db.atualizar_jogador(1, moedas=moedas_a, andar=andar)
    db.atualizar_jogador(2, moedas=moedas_b, andar=andar)


def _inventario(user_id):
    return {i["item"]: i["qtd"] for i in db.get_inventario(user_id)}


def test_caminho_feliz_troca_exatamente_o_ofertado_sem_duplicar_nem_sumir():
    _criar_par(moedas_a=500, moedas_b=200)
    db.add_item(1, "pocao_p", 3)
    db.add_item(2, "pocao_m", 1)

    troca = trocas.Troca(1, 2, andar=1)
    troca.ofertas[1] = {"itens": {"pocao_p": 2}, "moedas": 300}
    troca.ofertas[2] = {"itens": {"pocao_m": 1}, "moedas": 50}

    sucesso, motivo = trocas._commitar_troca(troca)
    assert (sucesso, motivo) == (True, None)

    a, b = db.get_jogador(1), db.get_jogador(2)
    assert a["moedas"] == 500 - 300 + 50
    assert b["moedas"] == 200 - 50 + 300

    inv_a, inv_b = _inventario(1), _inventario(2)
    assert inv_a == {"pocao_p": 1, "pocao_m": 1}   # ficou com 1, recebeu 1
    assert inv_b == {"pocao_p": 2}                  # deu a única poção média, recebeu 2 pequenas


def test_condicao_de_corrida_moeda_gasta_por_fora_falha_e_nao_move_nada():
    _criar_par(moedas_a=500, moedas_b=200)
    db.add_item(1, "pocao_p", 2)

    troca = trocas.Troca(1, 2, andar=1)
    troca.ofertas[1] = {"itens": {"pocao_p": 2}, "moedas": 300}
    troca.ofertas[2] = {"itens": {}, "moedas": 50}

    # por fora: jogador 1 gasta moeda em outra coisa antes do commit rodar
    db.atualizar_jogador(1, moedas=100)

    sucesso, motivo = trocas._commitar_troca(troca)
    assert sucesso is False
    assert motivo is not None

    a, b = db.get_jogador(1), db.get_jogador(2)
    assert a["moedas"] == 100   # não descontou os 300 que não tinha mais
    assert b["moedas"] == 200   # não recebeu nada
    assert _inventario(1) == {"pocao_p": 2}   # item intacto, nada moveu


def test_condicao_de_corrida_item_removido_por_fora_falha_e_nao_move_nada():
    _criar_par()
    db.add_item(1, "pocao_p", 2)

    troca = trocas.Troca(1, 2, andar=1)
    troca.ofertas[1] = {"itens": {"pocao_p": 2}, "moedas": 0}
    troca.ofertas[2] = {"itens": {}, "moedas": 0}

    # por fora: item consumido em outro lugar antes do commit
    db.remove_item(1, "pocao_p", 2)

    sucesso, motivo = trocas._commitar_troca(troca)
    assert sucesso is False
    assert _inventario(2) == {}


def test_peca_melhorada_pode_ser_trocada_e_o_bonus_viaja_junto():
    """O bloqueio de peça melhorada saiu -- agora ela é uma instância, e
    trocar só muda o `dono`. Ver decisoes.md § Instâncias de item."""
    _criar_par()
    instancia_id = db.criar_instancia(1, "espada_ferro", nivel_melhoria=2)
    db.atualizar_jogador(1, arma="espada_ferro", arma_instancia_id=instancia_id)
    db.atualizar_jogador(1, arma=None, arma_instancia_id=None)  # desequipa: agora "na mochila"

    troca = trocas.Troca(1, 2, andar=1)
    troca.ofertas[1] = {"itens": {}, "instancias": {"espada_ferro": instancia_id}, "moedas": 0}
    troca.ofertas[2] = {"itens": {}, "instancias": {}, "moedas": 0}

    sucesso, motivo = trocas._commitar_troca(troca)
    assert (sucesso, motivo) == (True, None)

    instancia = db.get_instancia(instancia_id)
    assert instancia["dono"] == 2
    assert instancia["nivel_melhoria"] == 2   # o bônus viajou junto


def test_estado_invalido_instancia_equipada_por_fora_devolve_false_sem_excecao():
    _criar_par()
    instancia_id = db.criar_instancia(1, "espada_ferro", nivel_melhoria=1)

    troca = trocas.Troca(1, 2, andar=1)
    troca.ofertas[1] = {"itens": {}, "instancias": {"espada_ferro": instancia_id}, "moedas": 0}
    troca.ofertas[2] = {"itens": {}, "instancias": {}, "moedas": 0}

    # por fora: a peça foi equipada depois que a oferta foi montada
    db.atualizar_jogador(1, arma="espada_ferro", arma_instancia_id=instancia_id)

    sucesso, motivo = trocas._commitar_troca(troca)
    assert sucesso is False
    assert isinstance(motivo, str) and motivo
    assert db.get_instancia(instancia_id)["dono"] == 1   # nada moveu


def test_estado_invalido_instancia_nao_e_mais_do_ofertante_devolve_false():
    _criar_par()
    instancia_id = db.criar_instancia(1, "espada_ferro", nivel_melhoria=1)

    troca = trocas.Troca(1, 2, andar=1)
    troca.ofertas[1] = {"itens": {}, "instancias": {"espada_ferro": instancia_id}, "moedas": 0}
    troca.ofertas[2] = {"itens": {}, "instancias": {}, "moedas": 0}

    # por fora: a instância já tinha ido pra outro jogador (ex: outra troca)
    with db.conectar() as conn:
        conn.execute("UPDATE instancias SET dono = 3 WHERE id = ?", (instancia_id,))

    sucesso, motivo = trocas._commitar_troca(troca)
    assert sucesso is False
    assert isinstance(motivo, str) and motivo


def test_estado_invalido_jogador_sem_personagem_devolve_false_sem_excecao():
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, moedas=100)

    troca = trocas.Troca(1, 999, andar=1)   # 999 nunca rodou "rpg comecar"
    troca.ofertas[1] = {"itens": {}, "moedas": 10}
    troca.ofertas[999] = {"itens": {}, "moedas": 0}

    sucesso, motivo = trocas._commitar_troca(troca)
    assert sucesso is False
    assert isinstance(motivo, str) and motivo
    assert db.get_jogador(1)["moedas"] == 100   # nada moveu
