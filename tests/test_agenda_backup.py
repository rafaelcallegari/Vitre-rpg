# tests/test_agenda_backup.py
# _rotacionar_backups não importa discord.py de verdade nem precisa de bot —
# testável direto com tmp_path/os.utime forjando mtime. Ver decisoes.md §
# Guarda contra restart consumindo os backups recentes.
import os
import time

import pytest

import agenda
import database as db


@pytest.fixture(autouse=True)
def backups_em_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "BACKUP_DIR", str(tmp_path))


def _forjar_mtime(caminho, ha_quantos_segundos):
    with open(caminho, "w"):
        pass
    quando = time.time() - ha_quantos_segundos
    os.utime(caminho, (quando, quando))


def _recentes():
    return [os.path.join(db.BACKUP_DIR, f"recente_{i}.db") for i in (1, 2, 3)]


def test_pasta_vazia_cria_recente_1_mesmo_com_a_guarda():
    agenda._rotacionar_backups()

    assert os.path.exists(_recentes()[0])
    assert not os.path.exists(_recentes()[1])
    assert not os.path.exists(_recentes()[2])


def test_recente_com_10_minutos_bloqueia_a_rotacao_dos_tres():
    recente_1, recente_2, recente_3 = _recentes()
    _forjar_mtime(recente_1, ha_quantos_segundos=10 * 60)
    antes = os.path.getmtime(recente_1)

    agenda._rotacionar_backups()

    assert os.path.getmtime(recente_1) == antes
    assert not os.path.exists(recente_2)
    assert not os.path.exists(recente_3)


def test_recente_com_2_horas_rotaciona_o_mais_antigo():
    recente_1, recente_2, recente_3 = _recentes()
    _forjar_mtime(recente_1, ha_quantos_segundos=3 * 3600)
    _forjar_mtime(recente_2, ha_quantos_segundos=2 * 3600)
    _forjar_mtime(recente_3, ha_quantos_segundos=1.5 * 3600)
    antes_2 = os.path.getmtime(recente_2)
    antes_3 = os.path.getmtime(recente_3)

    agenda._rotacionar_backups()

    # o mais novo dos três (recente_3, 1,5h) já passou da guarda de 1h, então
    # a rotação acontece — e o alvo é o de mtime mais antigo (recente_1),
    # não recente_2 nem recente_3.
    assert os.path.getmtime(recente_1) == pytest.approx(time.time(), abs=5)
    assert os.path.getmtime(recente_2) == antes_2
    assert os.path.getmtime(recente_3) == antes_3


def test_guarda_dos_recentes_nao_impede_diario_nem_semanal():
    recente_1, _, _ = _recentes()
    _forjar_mtime(recente_1, ha_quantos_segundos=10 * 60)

    agenda._rotacionar_backups()

    diario = os.path.join(db.BACKUP_DIR, "diario.db")
    semanal = os.path.join(db.BACKUP_DIR, "semanal.db")
    assert os.path.exists(diario)
    assert os.path.exists(semanal)


def test_round_robin_espacado_escreve_nos_tres_slots_sem_repetir():
    recente_1, recente_2, recente_3 = _recentes()

    agenda._rotacionar_backups()
    assert os.path.exists(recente_1)
    assert not os.path.exists(recente_2)

    _forjar_mtime(recente_1, ha_quantos_segundos=agenda.GUARDA_RECENTE_SEG + 60)
    agenda._rotacionar_backups()
    assert os.path.exists(recente_2)
    assert not os.path.exists(recente_3)

    _forjar_mtime(recente_1, ha_quantos_segundos=2 * agenda.GUARDA_RECENTE_SEG)
    _forjar_mtime(recente_2, ha_quantos_segundos=agenda.GUARDA_RECENTE_SEG + 60)
    agenda._rotacionar_backups()
    assert os.path.exists(recente_3)