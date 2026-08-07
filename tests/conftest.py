# tests/conftest.py
# Isolamento de banco para toda a suíte — nenhum teste pode tocar o
# aincrad.db de produção. Ver decisoes.md § Suíte de testes (isolamento).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database as db

CAMINHO_PRODUCAO = os.path.abspath("aincrad.db")


def _garantir_nao_e_producao():
    if db.DB_PATH != ":memory:" and os.path.abspath(db.DB_PATH) == CAMINHO_PRODUCAO:
        raise RuntimeError(
            "db.DB_PATH aponta para o banco de produção (aincrad.db) — "
            "teste abortado antes de tocar nele."
        )


@pytest.fixture(autouse=True)
def banco_de_teste():
    """Roda antes de CADA teste: descarta qualquer conexão anterior, aponta
    DB_PATH para um banco em memória isolado e recria o schema do zero. Sem
    isso, um teste herdaria dados do teste anterior — a conexão de módulo
    agora é longa (ver decisoes.md § Conexão longa), então sem fechar e
    reapontar explicitamente todos os testes compartilhariam a mesma
    conexão/arquivo.

    ":memory:" só passou a funcionar depois do cartão da conexão longa: com
    conexão-por-chamada, cada `conectar()` abria um banco em memória NOVO e
    vazio — o banco em memória não sobrevivia entre chamadas. Agora que a
    conexão é uma só, reaberta preguiçosamente e nunca fechada em uso
    normal, o banco em memória persiste durante o teste inteiro."""
    db.fechar_conexao()
    db.DB_PATH = ":memory:"
    _garantir_nao_e_producao()
    db.init_db()
    yield
    db.fechar_conexao()
