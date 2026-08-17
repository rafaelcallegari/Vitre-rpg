# tests/test_andar15.py
# Rename do chefe do andar 15 (nome do andar continua "Trono Vazio", só o
# chefe muda) + a fala de derrota que entrega a revelação da lore. Ver
# decisoes.md § Rename do chefe do andar 15.
import asyncio

import bot  # noqa: F401 -- importar popula combate.H (combate.instalar), sem conectar em nada
import combate
import game_data

ANDAR_15 = game_data.ANDARES[15]
BOSS = ANDAR_15["boss"]


def test_nome_do_andar_continua_trono_vazio():
    assert ANDAR_15["nome"] == "Trono Vazio"


def test_chefe_fase1_tem_nome_novo_e_stats_intactos():
    assert BOSS["nome"] == "«Espectro do rei»"
    assert BOSS["hp"] == 5580
    assert BOSS["atk"] == 275  # 335 - 60, ver decisoes.md § ATK dos chefes 11-15 reduzido em 60
    assert BOSS["def"] == 59
    assert BOSS["xp"] == 2420
    assert BOSS["moedas"] == 4050
    assert BOSS["elemento"] == "sombrio"
    assert BOSS["drops"] == [("sombra_dobrada", 1.0)]


def test_fase2_troca_nome_mantem_stats_e_carrega_fala_derrota():
    # mesmo padrão de Luta.verificar_fase2(): copia o dict da fase 1 e
    # aplica o override da fase 2 por cima -- não é só ler o dict estático.
    chefe = dict(BOSS)
    luta = combate.Luta(combatentes=[], chefe=chefe, andar_num=15)
    luta.hp_chefe = luta.hp_chefe_max * 0.4   # abaixo do limiar de 50% (FASE2_LIMIAR)

    luta.verificar_fase2()

    assert luta.chefe["nome"] == "«A Ruína do Rei»"
    assert luta.chefe["hp"] == 5580            # hp máximo herda da fase 1, não muda
    assert luta.chefe["atk"] == 315  # 375 - 60, ver decisoes.md § ATK dos chefes 11-15 reduzido em 60
    assert luta.chefe["def"] == 65
    assert luta.chefe["elemento"] == "divino"
    assert luta.chefe["drops"] == [("prego_de_luz", 1.0)]
    assert luta.chefe["fala_derrota"] == (
        "De novo não, como você está aqui, se já subiu essa torre"
    )
    assert "fase2" not in luta.chefe           # não fica pendurado depois da troca


def _campo(embed, nome):
    return next((f for f in embed.fields if f.name == nome), None)


def test_finalizar_vitoria_mostra_a_fala_derrota_quando_o_chefe_tem_uma():
    """Genérico -- funciona pra qualquer chefe com `fala_derrota`, não só o
    do andar 15. Zero participantes = `recompensar()` nunca roda, então dá
    pra testar o embed sem tocar no banco."""
    chefe_pos_fase2 = {**BOSS, **BOSS["fase2"]}   # mesmo merge de verificar_fase2()
    del chefe_pos_fase2["fase2"]
    luta = combate.Luta(combatentes=[], chefe=chefe_pos_fase2, andar_num=15)

    e = asyncio.run(combate.finalizar_vitoria(luta))

    campo = _campo(e, "🗡️ Últimas palavras")
    assert campo is not None
    assert BOSS["fase2"]["fala_derrota"] in campo.value


def test_finalizar_vitoria_nao_mostra_o_campo_quando_o_chefe_nao_tem_fala_derrota():
    chefe_sem_fala = {k: v for k, v in BOSS.items() if k != "fase2"}
    luta = combate.Luta(combatentes=[], chefe=chefe_sem_fala, andar_num=1)
    e = asyncio.run(combate.finalizar_vitoria(luta))
    assert _campo(e, "🗡️ Últimas palavras") is None


def test_apenas_o_cajado_divino_mudou_de_nome_entre_as_oito_armas_do_andar():
    armas_15 = {
        k: v["nome"] for k, v in game_data.ITENS.items()
        if v.get("tipo") == "arma" and v.get("andar_min") == 15
    }
    assert len(armas_15) == 8
    assert armas_15["cajado_divino"] == "«Cajado da Ruína»"
    assert armas_15["adaga_sombria"] == "«Adaga do Trono Vazio»"   # decisão do Rafael: mantida
    inalteradas = {
        "machado_sombrio": "«Machado da Sombra Dobrada»",
        "cajado_sombrio": "«Cajado da Ferida Sombria»",
        "manopla_sombria": "«Manoplas do Silêncio Ajoelhado»",
        "martelo_divino": "«Martelo do Prego de Luz»",
        "foice_divina": "«Foice do Juízo Suspenso»",
        "manopla_divina": "«Manoplas da Marca»",
    }
    for chave, nome in inalteradas.items():
        assert armas_15[chave] == nome
