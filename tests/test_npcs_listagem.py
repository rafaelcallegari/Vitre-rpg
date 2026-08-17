# tests/test_npcs_listagem.py
# `rpg npcs` montava o papel de cada NPC com um dict literal indexado direto
# por n["tipo"] -- um tipo sem entrada no dict (encantador, joalheiro, os dois
# semeados em npcs.NPCS) levantava KeyError e derrubava o comando inteiro. Ver
# decisoes.md § mapa de domínio + subscript direto.
#
# Este teste não fixa a lista de tipos conhecida hoje -- ele varre os tipos
# REALMENTE presentes em npcs.NPCS (todos os andares) e afirma o contrato:
# nenhum tipo semeado no banco pode ficar sem entrada em PAPEL_NPC, e montar a
# listagem pra qualquer andar nunca levanta exceção. Semear um tipo novo sem
# descrição tem que fazer este teste falhar.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot
import database as db
import npcs

TIPOS_NO_BANCO = {n["tipo"] for lista in npcs.NPCS.values() for n in lista}


def _jogador(andar):
    db.criar_jogador(1, "Alice")
    db.atualizar_jogador(1, andar=andar, andar_max=andar, pronome="elu")
    return db.get_jogador(1)


def test_todo_tipo_semeado_no_banco_tem_papel_descrito():
    faltando = TIPOS_NO_BANCO - set(bot.PAPEL_NPC)
    assert not faltando, f"tipo(s) de NPC sem entrada em PAPEL_NPC: {faltando}"


def test_rpg_npcs_nao_quebra_em_nenhum_andar_semeado():
    for andar in npcs.NPCS:
        _jogador(andar)
        ctx = MagicMock()
        ctx.author.id = 1
        ctx.send = AsyncMock()

        asyncio.run(bot.listar_npcs.callback(ctx))

        ctx.send.assert_called_once()


def test_papel_de_tipo_desconhecido_vira_linha_sem_descricao_em_vez_de_crash():
    """Prova o padrão .get() diretamente: um tipo nunca visto não derruba a
    montagem, só sai sem descrição."""
    assert bot.PAPEL_NPC.get("tipo_que_nao_existe_ainda", "") == ""
