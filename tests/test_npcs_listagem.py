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
import mundo
import npcs

TIPOS_NO_BANCO = {n["tipo"] for lista in npcs.NPCS.values() for n in lista}


def _jogador(chave):
    """`chave` é um andar da torre (int) ou um lugar de fora (string,
    Step C) -- `npcs.NPCS` mistura os dois tipos de chave desde que o
    vilarejo entrou. Pra chave de fora, `andar` fica congelado em 15
    (como qualquer jogador que já saiu pela porta) e é `mundo` quem
    aponta pro lugar de verdade -- ver mundo.chave_do_lugar."""
    db.criar_jogador(1, "Alice")
    if isinstance(chave, int):
        db.atualizar_jogador(1, andar=chave, andar_max=chave, pronome="elu")
    else:
        db.atualizar_jogador(1, andar=15, andar_max=15, mundo=chave, pronome="elu")
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
