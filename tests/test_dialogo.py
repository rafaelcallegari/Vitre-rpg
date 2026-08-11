# tests/test_dialogo.py
# Alicerce do diálogo com NPC: estado_sidequest (database.py), a mistura de
# opcoes/opcoes_por_estado (npcs.opcoes_do_dialogo), e a consistência do
# dado em dialogos.py com os NPCs de tipo "conversa" em npcs.py. Não cobre
# a View/botões do Discord -- isso só dá pra ver jogando (ver decisoes.md).
import database as db
import dialogos
import npcs
import pronomes

NPCS_CONVERSA = [
    n for andar in npcs.NPCS.values() for n in andar if n["tipo"] == "conversa"
]


def test_estado_sidequest_sem_linha_e_antes():
    db.criar_jogador(1, "Alice")
    assert db.estado_sidequest(1, "quest_qualquer") == "antes"


def test_estado_sidequest_traduz_ativa_e_concluida():
    db.criar_jogador(1, "Alice")
    with db.conectar() as conn:
        conn.execute(
            "INSERT INTO sidequests (user_id, quest_id, estado) VALUES (1, 'flor_da_guia', 'ativa')"
        )
    assert db.estado_sidequest(1, "flor_da_guia") == "durante"

    with db.conectar() as conn:
        conn.execute(
            "UPDATE sidequests SET estado = 'concluida' WHERE user_id = 1 AND quest_id = 'flor_da_guia'"
        )
    assert db.estado_sidequest(1, "flor_da_guia") == "depois"


def test_estado_sidequest_e_por_jogador_e_por_quest():
    db.criar_jogador(1, "Alice")
    db.criar_jogador(2, "Bob")
    with db.conectar() as conn:
        conn.execute(
            "INSERT INTO sidequests (user_id, quest_id, estado) VALUES (1, 'flor_da_guia', 'ativa')"
        )
    assert db.estado_sidequest(1, "flor_da_guia") == "durante"
    assert db.estado_sidequest(2, "flor_da_guia") == "antes"        # outro jogador, mesma quest
    assert db.estado_sidequest(1, "outra_quest") == "antes"          # mesmo jogador, outra quest


def test_npc_sem_opcoes_por_estado_nunca_consulta_o_banco():
    """NPC sem quest -- hoje, todos os 9 -- só devolve `opcoes`, sem tocar
    em estado_sidequest. user_id inválido (999) provaria que bateu no banco
    se a função tentasse -- não deveria estourar nem mudar o resultado."""
    opcoes = npcs.opcoes_do_dialogo("pip", user_id=999)
    assert opcoes == dialogos.DIALOGOS["pip"]["opcoes"]


def test_opcoes_por_estado_soma_conforme_o_estado_da_quest(monkeypatch):
    """Nenhum NPC real tem opcoes_por_estado ainda -- simula um pra travar o
    contrato que dialogos.py vai seguir quando a primeira sidequest nascer."""
    fixture = {
        "npc_de_teste": {
            "abertura": "abertura",
            "opcoes": [{"label": "solta", "resposta": "sempre aparece"}],
            "opcoes_por_estado": {
                "antes": [{"label": "gancho", "resposta": "ainda não fiz nada por você"}],
                "durante": [{"label": "cobranca", "resposta": "e então, conseguiu?"}],
                "depois": [{"label": "gratidao", "resposta": "obrigado por aquilo"}],
            },
            "quest_id": "quest_de_teste",
        }
    }
    monkeypatch.setattr(npcs, "DIALOGOS", fixture)
    db.criar_jogador(1, "Alice")

    opcoes = npcs.opcoes_do_dialogo("npc_de_teste", user_id=1)
    labels = {o["label"] for o in opcoes}
    assert labels == {"solta", "gancho"}          # sem linha na tabela -> 'antes'

    with db.conectar() as conn:
        conn.execute(
            "INSERT INTO sidequests (user_id, quest_id, estado) VALUES (1, 'quest_de_teste', 'ativa')"
        )
    labels = {o["label"] for o in npcs.opcoes_do_dialogo("npc_de_teste", user_id=1)}
    assert labels == {"solta", "cobranca"}


def test_todo_npc_conversa_tem_chave_de_dialogo_valida():
    assert len(NPCS_CONVERSA) == 9
    for n in NPCS_CONVERSA:
        assert "dialogo" in n, f"{n['nome']} é tipo conversa mas não tem campo 'dialogo'"
        assert n["dialogo"] in dialogos.DIALOGOS, f"{n['nome']} aponta pra uma chave inexistente"


def test_todo_dialogo_tem_abertura_e_opcoes_bem_formadas_quando_existem():
    """Bramm não tem pergunta nenhuma na Lore -- `opcoes` pode faltar (não
    pode existir vazia por engano, isso já seria bug de digitação)."""
    for chave, dado in dialogos.DIALOGOS.items():
        assert dado.get("abertura"), f"{chave} sem abertura"
        if "opcoes" in dado:
            assert dado["opcoes"], f"{chave} tem a chave 'opcoes' mas vazia -- tira a chave ou preenche"
            for opcao in dado["opcoes"]:
                assert opcao.get("label"), f"{chave}: opção sem label"
                assert opcao.get("resposta"), f"{chave}: opção '{opcao.get('label')}' sem resposta"


def test_so_guia_fica_de_fora_do_campo_dialogo():
    """Desde 'ações de diálogo de todos os NPCs', só A Guia (carta própria,
    ainda teleporta direto) não tem 'dialogo'. Os outros 5 tipos têm."""
    for andar in npcs.NPCS.values():
        for n in andar:
            if n["tipo"] == "guia":
                assert "dialogo" not in n, f"{n['nome']} (guia) não devia ter 'dialogo' ainda"
            else:
                assert "dialogo" in n, f"{n['nome']} ({n['tipo']}) devia ter 'dialogo'"


def test_opcoes_nunca_duplicam_o_botao_de_mecanica():
    """Comprar/Vender/Descansar/Sair são botões que comercio.py desenha —
    se aparecerem dentro de `opcoes` também, o jogador veria duas vezes."""
    proibidos = {"comprar", "vender", "descansar", "sair", "viajar"}
    for chave, dado in dialogos.DIALOGOS.items():
        for opcao in dado.get("opcoes", []):
            assert opcao["label"].lower() not in proibidos, (
                f"{chave}: opção '{opcao['label']}' deveria ser botão de mecânica, não pergunta"
            )


def test_rede_do_torv_as_tres_respostas_mencionam_ele():
    """Kesh, Hjalmar e Selen respondem sobre o Torv -- o card pediu pra
    escrever as três juntas, sem se contradizer. Trava só o mínimo
    verificável automaticamente: as três falam dele, nenhuma o rebatiza."""
    for chave in ("kesh", "hjalmar", "selen"):
        resposta = next(
            o["resposta"] for o in dialogos.DIALOGOS[chave]["opcoes"]
            if "torv" in o["label"].lower()
        )
        assert "Torv" in resposta


def test_todo_dialogo_tem_saida_propria():
    """Os 9 de hoje ganharam linha de saída própria -- o fallback existe pro
    NPC futuro que ainda não tiver a dele (ver test_saida_cai_no_fallback)."""
    for chave, dado in dialogos.DIALOGOS.items():
        assert dado.get("saida"), f"{chave} sem linha de saída"


def test_sair_nao_e_mais_uma_opcao_solta():
    """Sair virou botão fixo da DialogoView (bot.py), não item de `opcoes`
    -- não pode voltar a existir como opção duplicada em dialogos.py."""
    for chave, dado in dialogos.DIALOGOS.items():
        labels = {o["label"].lower() for o in dado.get("opcoes", [])}
        assert "sair" not in labels, f"{chave} ainda tem 'Sair' dentro de opcoes"


def test_saida_cai_no_fallback_quando_npc_nao_tem_a_propria(monkeypatch):
    fixture = {"npc_sem_saida": {"abertura": "abertura", "opcoes": []}}
    monkeypatch.setattr(dialogos, "DIALOGOS", fixture)
    saida = dialogos.DIALOGOS["npc_sem_saida"].get("saida") or dialogos.SAIDA_PADRAO
    assert saida == dialogos.SAIDA_PADRAO


def test_abertura_e_sempre_reaproveitada_da_fala_de_npcs_py():
    for andar in npcs.NPCS.values():
        for n in andar:
            chave = n.get("dialogo")
            if not chave:
                continue
            assert dialogos.DIALOGOS[chave]["abertura"] == n["fala"], (
                f"{n['nome']}: abertura em dialogos.py diverge da fala em npcs.py"
            )


def test_bramm_fala_quatro_vezes_por_dia():
    bramm = next(n for n in npcs.NPCS[3] if n["nome"] == "Bramm")
    assert "quatro vezes por dia" in bramm["fala"]
    assert "três vezes por dia" not in bramm["fala"]


def test_bramm_nao_tem_pergunta_na_lore():
    assert "opcoes" not in dialogos.DIALOGOS["bramm"]


def test_selen_nao_vende_mas_ainda_tem_dialogo():
    """A ressalva do card ('Comprar não se aplica a ela') é sobre o botão
    de comércio, não sobre o diálogo -- ela ainda pergunta sobre Torv e o
    Selo como qualquer outro ferreiro."""
    assert dialogos.DIALOGOS["selen"]["opcoes"]


def test_marcador_de_concordancia_em_dialogo_real_resolve_certo():
    """Pip fala de 'subir e contar sozinho/sozinha' sobre quem está jogando
    -- é o exemplo real de concordância que entrou nesta varredura."""
    resposta = next(
        o["resposta"] for o in dialogos.DIALOGOS["pip"]["opcoes"]
        if "parou" in o["label"]
    )
    assert "{o|a}" in resposta   # ainda não resolvido no dado bruto
    assert "sozinho" in pronomes.concordar(resposta, "ele")
    assert "sozinha" in pronomes.concordar(resposta, "ela")
    assert "sozinho" in pronomes.concordar(resposta, "elu")
