# tests/test_dialogo.py
# Alicerce do diálogo com NPC: estado_sidequest (database.py), a mistura de
# opcoes/opcoes_por_estado (npcs.opcoes_do_dialogo), e a consistência do
# dado em dialogos.py com os NPCs de tipo "conversa" em npcs.py. Não cobre
# a View/botões do Discord -- isso só dá pra ver jogando (ver decisoes.md).
import database as db
import dialogos
import npcs

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


def test_todo_dialogo_tem_abertura_e_opcoes_com_label_e_resposta():
    for chave, dado in dialogos.DIALOGOS.items():
        assert dado.get("abertura"), f"{chave} sem abertura"
        assert dado.get("opcoes"), f"{chave} sem opcoes"
        for opcao in dado["opcoes"]:
            assert opcao.get("label"), f"{chave}: opção sem label"
            assert opcao.get("resposta"), f"{chave}: opção '{opcao.get('label')}' sem resposta"


def test_npc_nao_conversa_nao_ganhou_campo_dialogo():
    """Mercador, ferreiro, carroceiro, taverneiro e guia seguem exatamente
    como estavam -- este corte só tocou nos 9 de tipo conversa."""
    outros = [
        n for andar in npcs.NPCS.values() for n in andar if n["tipo"] != "conversa"
    ]
    assert outros
    for n in outros:
        assert "dialogo" not in n, f"{n['nome']} ({n['tipo']}) ganhou 'dialogo' fora do escopo"
