# tests/test_dungeon_cooldown.py
# Cartão "Exploração de Dungeon", commit 3: revoga parte da decisão de
# 28/08 -- "entrada gratuita" e "repetição infinita" continuam, só o "sem
# cooldown" cai. Por RUN, contado na ENTRADA (não por sala); morrer não
# reinicia o cooldown. Ver decisoes.md § Dungeon -- cooldown.
import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot
import database as db
import dungeon

SALAS_DE_TESTE = (
    "camara_dos_ecos", "salao_do_espelho_rachado", "piso_instavel",
    "bau_esquecido", "corrente_solta",
)


def _jogador(user_id=1, **campos):
    db.criar_jogador(user_id, f"Jogador{user_id}")
    padrao = dict(andar=9, nivel=15, classe="guerreiro", forca=20)
    padrao.update(campos)
    db.atualizar_jogador(user_id, **padrao)
    return db.get_jogador(user_id)


def _ctx(user_id=1):
    ctx = MagicMock()
    ctx.author.id = user_id
    ctx.send = AsyncMock()
    return ctx


def _msg(ctx):
    return ctx.send.call_args.args[0] if ctx.send.call_args.args else ctx.send.call_args.kwargs.get("content", "")


def _sempre_vitoria(monkeypatch):
    monkeypatch.setitem(dungeon.H, "simular_combate", lambda s, hp, mob, andar_num: (hp, True, ["vitória"]))


def test_entrar_na_dungeon_liga_o_cooldown():
    j = _jogador(1)
    ctx = _ctx(1)

    asyncio.run(dungeon._executar_entrar_ou_continuar(ctx, j))

    assert db.checar_cooldown(1, "dungeon") > 0


def test_segunda_entrada_com_cooldown_ativo_e_bloqueada_e_nao_cria_run():
    j = _jogador(1)
    db.set_cooldown(1, "dungeon", 900)

    asyncio.run(dungeon._executar_entrar_ou_continuar(_ctx(1), j))

    assert dungeon.obter_run(1) is None


def test_mensagem_de_cooldown_segue_o_padrao_do_resto_do_jogo():
    j = _jogador(1)
    db.set_cooldown(1, "dungeon", 900)
    ctx = _ctx(1)

    asyncio.run(dungeon._executar_entrar_ou_continuar(ctx, j))

    msg = _msg(ctx)
    assert msg.startswith("⏳ `rpg dungeon` volta em")


def test_cooldown_e_por_run_nao_por_sala_continuar_a_mesma_run_nao_mexe_nele(monkeypatch):
    """Resolver uma segunda sala da MESMA run (retomada) não reseta nem
    estica o cooldown -- só a ENTRADA (criar_run) grava."""
    _sempre_vitoria(monkeypatch)
    j = _jogador(1)
    asyncio.run(dungeon._executar_entrar_ou_continuar(_ctx(1), j))
    restante_apos_entrada = db.checar_cooldown(1, "dungeon")

    j2 = db.get_jogador(1)
    asyncio.run(dungeon._executar_entrar_ou_continuar(_ctx(1), j2))   # resolve a 2ª sala da mesma run

    assert db.checar_cooldown(1, "dungeon") <= restante_apos_entrada   # nunca aumentou


def test_morrer_na_dungeon_nao_reinicia_o_cooldown(monkeypatch):
    """Escolha do designer, não do Rafael -- ver decisoes.md. Morrer já
    custa a run inteira + a penalidade normal; a run cai antes do
    cooldown expirar, então o jogador ainda espera o resto do tempo.

    Cria a run com uma sala de COMBATE garantida na frente (`sortear_
    salas` é aleatório -- deixar a criação real escolher arriscaria pegar
    uma sala sem combate na 1ª posição e o teste não morrer de jeito
    nenhum) e grava o cooldown à mão, do jeito que `_executar_entrar_ou_
    continuar` já teria feito na entrada real."""
    j = _jogador(1, moedas=1000)
    db.set_cooldown(1, "dungeon", dungeon.COOLDOWN_DUNGEON)
    db.criar_dungeon_run(1, list(SALAS_DE_TESTE))   # índice 0 = "camara_dos_ecos", combate
    monkeypatch.setitem(dungeon.H, "simular_combate", lambda s, hp, mob, andar_num: (0, False, ["derrota"]))

    asyncio.run(dungeon.resolver_sala_atual(_ctx(1), j, dungeon.obter_run(1)))

    restante_apos_morte = db.checar_cooldown(1, "dungeon")
    assert dungeon.obter_run(1) is None   # a run morreu de verdade
    assert restante_apos_morte > 0   # o cooldown continua contando, não foi zerado nem reiniciado


def test_sair_da_dungeon_nao_reinicia_o_cooldown():
    j = _jogador(1)
    asyncio.run(dungeon._executar_entrar_ou_continuar(_ctx(1), j))
    restante_antes_de_sair = db.checar_cooldown(1, "dungeon")

    asyncio.run(dungeon._executar_sair(_ctx(1), j))

    assert db.checar_cooldown(1, "dungeon") <= restante_antes_de_sair
    assert db.checar_cooldown(1, "dungeon") > 0


def test_apos_o_cooldown_expirar_entrar_de_novo_funciona(monkeypatch):
    _sempre_vitoria(monkeypatch)   # sala de combate sorteada não pode derrubar o personagem por RNG real
    j = _jogador(1)
    db.set_cooldown(1, "dungeon", -1)   # já expirado

    asyncio.run(dungeon._executar_entrar_ou_continuar(_ctx(1), j))

    assert dungeon.obter_run(1) is not None


def test_repeticao_infinita_continua_nenhum_limite_de_quantas_runs(monkeypatch):
    """"Entrada gratuita" e "repetição infinita" continuam de pé -- só o
    "sem cooldown" caiu. Sem custo em moedas pra entrar -- `simular_
    combate` mockado pra vitória de propósito, senão a sala de combate
    sorteada na entrada poderia derrubar o personagem por RNG de verdade
    e confundir "custo de entrada" com "perda de uma luta"."""
    _sempre_vitoria(monkeypatch)
    j = _jogador(1, moedas=500)
    db.set_cooldown(1, "dungeon", -1)

    asyncio.run(dungeon._executar_entrar_ou_continuar(_ctx(1), j))

    assert db.get_jogador(1)["moedas"] >= 500   # nenhum custo de entrada -- só pode SUBIR (drop de vitória)
