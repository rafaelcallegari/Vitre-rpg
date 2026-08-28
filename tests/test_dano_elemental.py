# tests/test_dano_elemental.py
# Cartão "Dano elemental": ciclo de fraquezas das 24 armas elementais,
# tabela de condição arma->alvo (NOVA, não reusa CONDICOES_ELEMENTO — ver
# decisoes.md § Dano elemental) e o teto de uma aplicação por rodada. Corte
# via git stash confirma que cada teste aqui quebra sem a mudança
# correspondente.
import bot  # noqa: F401 -- popula combate.H (combate.instalar)
import combate
import condicoes
import database as db
import game_data

CHEFE_TESTE = {"nome": "Testinho", "hp": 999999, "atk": 1, "def": 0, "xp": 0, "moedas": 0}


def _combatente_com_arma(user_id, arma_chave):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    db.atualizar_jogador(user_id, arma=arma_chave)
    j = db.get_jogador(user_id)
    return combate.Combatente(j, bot.stats(j))


# ================================================================
# O ciclo: cada elemento tem exatamente 1 forte, 1 fraco, 4 neutros — e fecha
# ================================================================

def test_ciclo_de_elementos_tem_um_forte_um_fraco_e_quatro_neutros_para_cada():
    ciclo = game_data.CICLO_ELEMENTOS
    assert len(ciclo) == 6
    for elemento in ciclo:
        contagem = {"forte": 0, "fraco": 0, "neutro": 0}
        for alvo in ciclo:
            fator = game_data.multiplicador_elemento(elemento, alvo)
            if fator == game_data.MULTIPLICADOR_ELEMENTO_FORTE:
                contagem["forte"] += 1
            elif fator == game_data.MULTIPLICADOR_ELEMENTO_FRACO:
                contagem["fraco"] += 1
            else:
                contagem["neutro"] += 1
        assert contagem == {"forte": 1, "fraco": 1, "neutro": 4}, elemento


def test_ciclo_de_elementos_fecha_passando_pelos_seis_uma_vez_so():
    """Encadear "forte contra" 6 vezes a partir de qualquer elemento deve
    visitar os 6 elementos uma vez cada e voltar pro ponto de partida —
    prova que é um ciclo fechado, não 6 pares soltos."""
    ciclo = game_data.CICLO_ELEMENTOS
    inicio = ciclo[0]
    atual = inicio
    visitados = [atual]
    for _ in range(len(ciclo) - 1):
        seguinte = next(
            alvo for alvo in ciclo
            if game_data.multiplicador_elemento(atual, alvo) == game_data.MULTIPLICADOR_ELEMENTO_FORTE
        )
        assert seguinte not in visitados, "ciclo repetiu antes de passar pelos 6"
        visitados.append(seguinte)
        atual = seguinte
    assert set(visitados) == set(ciclo)
    assert game_data.multiplicador_elemento(atual, inicio) == game_data.MULTIPLICADOR_ELEMENTO_FORTE


# ================================================================
# Alvo sem elemento é neutro, nunca exceção
# ================================================================

def test_alvo_ou_arma_sem_elemento_e_neutro_sem_levantar_excecao():
    assert game_data.multiplicador_elemento("fogo", None) == 1.0
    assert game_data.multiplicador_elemento(None, "fogo") == 1.0
    assert game_data.multiplicador_elemento(None, None) == 1.0
    # "luz"/"sombra" são o elemento da Mortalha (outro sistema) -- fora do
    # ciclo de 6, deve cair em neutro também, não estourar KeyError/IndexError
    assert game_data.multiplicador_elemento("fogo", "luz") == 1.0
    assert game_data.multiplicador_elemento("luz", "fogo") == 1.0


# ================================================================
# Teto por rodada: uma aplicação por elemento, mesmo com golpes repetidos
# ================================================================

def test_teto_por_rodada_uma_aplicacao_por_elemento_mesmo_com_dois_golpes(monkeypatch):
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)  # sempre passa a chance de aplicar
    c1 = _combatente_com_arma(1, "espada_solario")   # fogo
    c2 = _combatente_com_arma(2, "espada_solario")   # fogo também
    luta = combate.Luta([c1, c2], CHEFE_TESTE, andar_num=1)

    combate._talvez_condicionar_chefe(luta, c1)
    combate._talvez_condicionar_chefe(luta, c2)   # mesmo elemento, mesma rodada

    brasas = [cond for cond in luta.condicoes if cond["nome"] == "Brasa"]
    assert len(brasas) == 1


def test_teto_por_rodada_nao_impede_elementos_diferentes_de_aplicarem_os_dois(monkeypatch):
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)
    c1 = _combatente_com_arma(1, "espada_solario")   # fogo
    c2 = _combatente_com_arma(2, "machado_raio")     # raio
    luta = combate.Luta([c1, c2], CHEFE_TESTE, andar_num=1)

    combate._talvez_condicionar_chefe(luta, c1)
    combate._talvez_condicionar_chefe(luta, c2)

    nomes = {cond["nome"] for cond in luta.condicoes}
    assert nomes == {"Brasa", "Curto"}


# ================================================================
# Refresh de duração não empilha
# ================================================================

def test_condicao_ja_ativa_refresca_duracao_em_vez_de_empilhar(monkeypatch):
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)
    c = _combatente_com_arma(1, "espada_solario")   # fogo
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)

    combate._talvez_condicionar_chefe(luta, c)
    assert len(luta.condicoes) == 1
    luta.condicoes[0]["duracao"] = 1   # simula ter tickado quase até expirar

    luta.elementos_aplicados_rodada = set()   # nova rodada -- teto resetado
    combate._talvez_condicionar_chefe(luta, c)

    assert len(luta.condicoes) == 1   # não duplicou a entrada
    assert luta.condicoes[0]["duracao"] == game_data.CONDICOES_ARMA_ELEMENTAL["fogo"]["duracao"]


# ================================================================
# Sanguessuga (sombrio): drena devolve cura ao portador, respeitando hp_max
# ================================================================

def test_sanguessuga_devolve_cura_ao_portador_da_arma(monkeypatch):
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)  # sempre passa a chance de aplicar
    dados = game_data.CONDICOES_ARMA_ELEMENTAL["sombrio"]
    assert dados.get("drena")   # é a Sanguessuga -- se não tiver drena, o teste abaixo não prova nada
    chefe_pequeno = {**CHEFE_TESTE, "hp": 500}   # chefe pequeno o bastante pra cura não bater no teto de HP do jogador
    c = _combatente_com_arma(1, "machado_sombrio")   # sombrio
    luta = combate.Luta([c], chefe_pequeno, andar_num=1)
    c.hp = 1

    combate._talvez_condicionar_chefe(luta, c)   # amarra a Sanguessuga de verdade, pela arma
    condicoes.tick(luta)

    dano = max(1, int(luta.hp_chefe_max * dados["valor"]))
    cura_esperada = int(dano * dados["drena"])
    assert cura_esperada < c.s["hp_max"]   # a conta abaixo só vale se não bater no teto
    assert c.hp == 1 + cura_esperada


def test_sanguessuga_nao_ultrapassa_o_hp_max_do_portador(monkeypatch):
    monkeypatch.setattr(combate.random, "random", lambda: 0.0)
    c = _combatente_com_arma(1, "machado_sombrio")
    luta = combate.Luta([c], CHEFE_TESTE, andar_num=1)
    c.hp = c.s["hp_max"]   # já cheio

    combate._talvez_condicionar_chefe(luta, c)
    condicoes.tick(luta)

    assert c.hp == c.s["hp_max"]


# ================================================================
# Caçada/exploração: multiplicador presente, condição ausente
# ================================================================

def test_cacada_aplica_multiplicador_de_elemento_no_dano(monkeypatch):
    db.criar_jogador(1, "Jogador1")
    db.atualizar_jogador(1, arma="espada_solario")   # fogo -- forte contra sombrio no ciclo
    j = db.get_jogador(1)
    s = bot.stats(j)

    monkeypatch.setattr(bot.at, "chance_iniciativa", lambda *a, **k: 2.0)  # jogador sempre abre
    monkeypatch.setattr(bot.random, "uniform", lambda a, b: 1.0)
    monkeypatch.setattr(bot.random, "random", lambda: 1.0)   # nunca crítico, nunca esquiva

    dano_neutro = max(1, int(s["atk"]))   # def=0 do mob -> aplicar_defesa não reduz
    dano_esperado = max(1, int(dano_neutro * game_data.MULTIPLICADOR_ELEMENTO_FORTE))
    mob = {"hp": dano_esperado, "atk": 0, "def": 0, "elemento": "sombrio"}

    hp_final, venceu, log = bot.simular_combate(s, 999999, mob, andar_num=1)

    assert venceu is True
    assert f"**{dano_esperado}**" in log[-1]


def test_cacada_nao_aplica_condicao_nenhuma_no_monstro():
    """O loop de simular_combate não tem Luta nem condicoes.py — só o
    multiplicador de tipo entra na caçada/exploração (ver decisoes.md §
    Dano elemental). Não há estado de condição pra checar: só confirma que
    o monstro (um dict puro) não ganha nenhuma chave nova depois da luta."""
    db.criar_jogador(1, "Jogador1")
    db.atualizar_jogador(1, arma="espada_solario")
    j = db.get_jogador(1)
    s = bot.stats(j)
    mob = {"hp": 10, "atk": 5, "def": 0, "elemento": "sombrio"}
    chaves_antes = set(mob.keys())

    bot.simular_combate(s, 999, mob, andar_num=1)

    assert set(mob.keys()) == chaves_antes
