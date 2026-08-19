# tests/test_salao_guilda.py
# Tesouros de chefe (game_data) + Salão da Guilda (database.py/salao.py/
# guildas.py/raide.py). O teste que trava a decisão de desenho é
# test_tier_conta_total_nao_distintos -- ver decisoes.md § Salão da Guilda.
#
# Sem pytest-asyncio no projeto: funções async são exercitadas com
# asyncio.run(...) dentro de um `def test_` comum -- mesmo padrão de
# tests/test_avatar.py.
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import bot  # side effect: liga H de guildas.py/raide.py via instalar()
import database as db
import guildas
import profissoes
import salao
from game_data import ANDARES, ITENS, SALAO_TIERS


# ---------------------------------------------------------------- fakes
class FakeCtx:
    def __init__(self, user_id, mentions=None, display_name=None):
        self.author = SimpleNamespace(id=user_id, display_name=display_name or f"user{user_id}")
        self.message = SimpleNamespace(mentions=mentions or [])
        self.guild = None
        self.send = AsyncMock()


def _confirmar_cls(resultado):
    """Substitui admin.ConfirmarAcao nos testes -- salao.depositar() recebe a
    classe de confirmação por parâmetro exatamente pra isso: sem precisar de
    interaction/botão real de Discord pra testar confirmar/cancelar."""
    class _Fake:
        def __init__(self, autor_id):
            self.autor_id = autor_id
            self.confirmado = resultado
            self.mensagem = None

        async def wait(self):
            return None

    return _Fake


def _jogador(user_id=1, nome="Jogadora"):
    db.criar_jogador(user_id, nome)
    return db.get_jogador(user_id)


_CONTADOR_GUILDA = [0]


def _guilda(lider_id=1, andar_home=1, membros_extra=()):
    _CONTADOR_GUILDA[0] += 1
    nome = f"Ordem do Selo {_CONTADOR_GUILDA[0]}"  # nome de guilda é UNIQUE no schema
    guilda_id = db.criar_guilda(nome, lider_id, andar_home, cargo_id=10, canal_id=20)
    for uid in membros_extra:
        db.adicionar_membro_guilda(uid, guilda_id)
    return guilda_id


def _depositar(ctx, j, guilda_id, item, assinatura="", confirmado=True):
    guilda_dict = db.get_guilda(guilda_id)
    asyncio.run(salao.depositar(ctx, j, guilda_dict, item, assinatura, _confirmar_cls(confirmado)))


# ------------------------------------------------------- 1. drop dos chefes
def test_cada_chefe_de_1_a_10_solta_um_tesouro_distinto_100_por_cento():
    catalogo = set(salao.tesouros_do_catalogo())
    assert len(catalogo) == 10

    usados = set()
    for andar in range(1, 11):
        drops = dict(ANDARES[andar]["boss"]["drops"])
        assert "fragmento_selo" in drops and drops["fragmento_selo"] == 1.0

        tesouros_do_andar = [item for item in drops if salao.eh_tesouro(item)]
        assert len(tesouros_do_andar) == 1, f"andar {andar} deveria soltar exatamente 1 tesouro"
        item = tesouros_do_andar[0]
        assert drops[item] == 1.0
        assert item not in usados, "cada tesouro só pode pertencer a um andar"
        usados.add(item)

    assert usados == catalogo, "todo tesouro do catálogo precisa vir de algum andar 1-10"


def test_andares_11_a_15_nao_ganham_tesouro():
    for andar in range(11, 16):
        drops = dict(ANDARES[andar]["boss"]["drops"])
        assert not any(salao.eh_tesouro(item) for item in drops)


# --------------------------------------------------- 2. tesouro não é X, Y, Z
def test_tesouro_nao_e_vendavel_nem_de_loja():
    for chave in salao.tesouros_do_catalogo():
        dado = ITENS[chave]
        assert dado.get("vendavel", True) is False
        assert dado.get("loja", True) is False


def test_tesouro_nao_e_equipavel():
    tipos_equipaveis = ("arma", "armadura", "anel", "colar")
    for chave in salao.tesouros_do_catalogo():
        assert ITENS[chave]["tipo"] not in tipos_equipaveis


def test_tesouro_nao_entra_em_receita_de_profissao():
    catalogo = set(salao.tesouros_do_catalogo())
    assert not (catalogo & set(profissoes.RECEITAS))
    for receita in profissoes.RECEITAS.values():
        assert not (catalogo & set(receita["materiais"]))


# --------------------------------------------------------- 3. tier por total
def test_tier_conta_total_nao_distintos():
    """A decisão central do desenho: 3 cópias do MESMO tesouro valem tier
    igual a 3 tesouros DISTINTOS -- se alguém trocar `contar_tesouros_salao`
    pra COUNT(DISTINCT item), este teste quebra."""
    g_repetido = _guilda(lider_id=1)
    for uid in (101, 102, 103):
        db.depositar_tesouro_salao(g_repetido, "coroa_velha", uid, None)

    g_distinto = _guilda(lider_id=2)
    for item in ("coroa_velha", "novelo_da_rainha", "lasca_do_guardiao"):
        db.depositar_tesouro_salao(g_distinto, item, 201, None)

    total_repetido = db.contar_tesouros_salao(g_repetido)
    total_distinto = db.contar_tesouros_salao(g_distinto)
    assert total_repetido == total_distinto == 3
    assert salao.tier_por_total(total_repetido) == salao.tier_por_total(total_distinto)


def test_tiers_sao_crescentes_e_cooldown_nunca_abaixo_de_1h():
    minimos = [t["min_tesouros"] for t in SALAO_TIERS]
    assert minimos == sorted(minimos)
    assert all(t["cooldown_raide"] >= 3600 for t in SALAO_TIERS)
    assert min(t["cooldown_raide"] for t in SALAO_TIERS) == 3600


def test_proximo_tier_none_no_teto():
    maior = SALAO_TIERS[-1]["min_tesouros"]
    assert salao.proximo_tier(maior) is None
    assert salao.proximo_tier(maior - 1)["min_tesouros"] == maior


# --------------------------------------------------- 6. piso de membros
def test_tier_efetivo_ignora_tesouro_com_menos_de_3_membros():
    tier = salao.tier_efetivo(total=40, membros_count=2, membros_minimo=guildas.MEMBROS_PARA_VALER)
    assert tier["tier"] == 0
    tier_com_membros = salao.tier_efetivo(total=40, membros_count=3, membros_minimo=guildas.MEMBROS_PARA_VALER)
    assert tier_com_membros["tier"] == 3


# --------------------------------------------------------------- depósito
def test_deposito_confirmado_sai_da_mochila_e_entra_no_salao_com_credito():
    j = _jogador(1)
    guilda_id = _guilda(lider_id=1, membros_extra=(2, 3))
    db.add_item(1, "coroa_velha", 1)
    ctx = FakeCtx(1)

    _depositar(ctx, j, guilda_id, "coroa_velha", assinatura="Cheguei até aqui sozinho.")

    assert db.tem_item(1, "coroa_velha", 1) is False
    linhas = db.tesouros_do_salao(guilda_id)
    assert len(linhas) == 1
    assert linhas[0]["user_id"] == 1
    assert linhas[0]["item"] == "coroa_velha"
    assert linhas[0]["mensagem"] == "Cheguei até aqui sozinho."


def test_deposito_cancelado_nao_move_nada():
    j = _jogador(1)
    guilda_id = _guilda(lider_id=1, membros_extra=(2, 3))
    db.add_item(1, "coroa_velha", 1)
    ctx = FakeCtx(1)

    _depositar(ctx, j, guilda_id, "coroa_velha", confirmado=False)

    assert db.tem_item(1, "coroa_velha", 1) is True
    assert db.contar_tesouros_salao(guilda_id) == 0


def test_deposito_sem_item_na_mochila_nao_deposita():
    j = _jogador(1)
    guilda_id = _guilda(lider_id=1)
    ctx = FakeCtx(1)

    _depositar(ctx, j, guilda_id, "coroa_velha")

    assert db.contar_tesouros_salao(guilda_id) == 0
    ctx.send.assert_awaited()


def test_deposito_e_irreversivel_nao_existe_saque():
    """Não existe função de banco que tire uma linha de guilda_salao de
    volta pro inventário -- só a mensagem (assinatura) pode ser reescrita."""
    funcoes = {nome for nome in dir(db) if "salao" in nome}
    assert not any("sacar" in f or "remover" in f or "excluir" in f for f in funcoes)


# ---------------------------------------------------- sanitização de assinatura
def test_assinatura_com_everyone_e_recusada_e_nao_deposita():
    j = _jogador(1)
    guilda_id = _guilda(lider_id=1, membros_extra=(2, 3))
    db.add_item(1, "coroa_velha", 1)
    ctx = FakeCtx(1)

    _depositar(ctx, j, guilda_id, "coroa_velha", assinatura="valeu a pena @everyone")

    assert db.tem_item(1, "coroa_velha", 1) is True
    assert db.contar_tesouros_salao(guilda_id) == 0
    texto_enviado = " ".join(str(c) for c in ctx.send.call_args_list)
    assert "everyone" in texto_enviado.lower() or "menç" in texto_enviado.lower()


def test_assinatura_com_here_e_recusada():
    j = _jogador(1)
    guilda_id = _guilda(lider_id=1, membros_extra=(2, 3))
    db.add_item(1, "coroa_velha", 1)
    ctx = FakeCtx(1)

    _depositar(ctx, j, guilda_id, "coroa_velha", assinatura="oi @here")

    assert db.contar_tesouros_salao(guilda_id) == 0


def test_mencao_em_massa_nao_bloqueia_mencao_individual():
    assert salao.mencao_em_massa("valeu <@123456789012345678>") is False
    assert salao.mencao_em_massa("@everyone") is True
    assert salao.mencao_em_massa("@Everyone") is True
    assert salao.mencao_em_massa("@here") is True


def test_assinatura_longa_e_recusada():
    j = _jogador(1)
    guilda_id = _guilda(lider_id=1, membros_extra=(2, 3))
    db.add_item(1, "coroa_velha", 1)
    ctx = FakeCtx(1)

    _depositar(ctx, j, guilda_id, "coroa_velha", assinatura="x" * 200)

    assert db.contar_tesouros_salao(guilda_id) == 0


# ------------------------------------------------------------ editar/apagar
def test_editar_e_apagar_assinatura_nao_muda_contagem_nem_tier():
    guilda_id = _guilda(lider_id=1)
    tesouro_id = db.depositar_tesouro_salao(guilda_id, "coroa_velha", 1, "original")
    total_antes = db.contar_tesouros_salao(guilda_id)

    db.definir_mensagem_tesouro_salao(tesouro_id, "editada")
    assert db.tesouros_do_salao(guilda_id)[0]["mensagem"] == "editada"
    assert db.contar_tesouros_salao(guilda_id) == total_antes

    db.definir_mensagem_tesouro_salao(tesouro_id, None)
    assert db.tesouros_do_salao(guilda_id)[0]["mensagem"] is None
    assert db.contar_tesouros_salao(guilda_id) == total_antes


def test_autor_edita_a_propria_assinatura_via_comando():
    j = _jogador(1)
    guilda_id = _guilda(lider_id=1)
    guilda = db.get_guilda(guilda_id)
    db.depositar_tesouro_salao(guilda_id, "coroa_velha", 1, "original")
    ctx = FakeCtx(1)

    asyncio.run(salao.acao_assinar(ctx, j, guilda, "coroa velha nova assinatura"))

    linha = db.tesouro_salao_do_membro(guilda_id, "coroa_velha", 1, db.temporada_atual())
    assert linha["mensagem"] == "nova assinatura"


def test_lider_limpa_assinatura_de_outro_membro():
    lider = _jogador(1, "Lider")
    membro = SimpleNamespace(id=2, display_name="Membro")
    guilda_id = _guilda(lider_id=1, membros_extra=(2,))
    guilda = db.get_guilda(guilda_id)
    db.depositar_tesouro_salao(guilda_id, "coroa_velha", 2, "assinatura do membro")
    ctx = FakeCtx(1, mentions=[membro])

    asyncio.run(salao.acao_limpar_assinatura(ctx, lider, guilda, f"<@{membro.id}> coroa velha"))

    linha = db.tesouro_salao_do_membro(guilda_id, "coroa_velha", 2, db.temporada_atual())
    assert linha["mensagem"] is None


def test_nao_lider_nao_limpa_assinatura_de_outro():
    membro_obj = SimpleNamespace(id=2, display_name="Membro")
    guilda_id = _guilda(lider_id=1, membros_extra=(2,))
    guilda = db.get_guilda(guilda_id)
    db.depositar_tesouro_salao(guilda_id, "coroa_velha", 2, "assinatura do membro")
    membro_jogador = _jogador(2, "Membro")
    ctx = FakeCtx(2, mentions=[membro_obj])  # o próprio "membro" tentando, não o líder

    asyncio.run(salao.acao_limpar_assinatura(ctx, membro_jogador, guilda, "<@2> coroa velha"))

    linha = db.tesouro_salao_do_membro(guilda_id, "coroa_velha", 2, db.temporada_atual())
    assert linha["mensagem"] == "assinatura do membro"


# -------------------------------------------------------- extrair_tesouro
def test_extrair_tesouro_por_nome_e_por_chave():
    chave, resto = salao.extrair_tesouro("Coroa Velha uma mensagem qualquer")
    assert chave == "coroa_velha"
    assert resto == "uma mensagem qualquer"

    chave2, resto2 = salao.extrair_tesouro("coroa_velha")
    assert chave2 == "coroa_velha"
    assert resto2 == ""

    chave3, _ = salao.extrair_tesouro("poção pequena")
    assert chave3 is None


# ------------------------------------------------------- home / migração
def test_home_acima_do_tier_e_recusada_com_tesouros_faltando():
    j = _jogador(1)
    db.atualizar_jogador(1, andar_max=10)
    guilda_id = _guilda(lider_id=1, membros_extra=(2, 3))
    ctx = FakeCtx(1)

    asyncio.run(guildas.acao_home(ctx, j, "10"))

    guilda = db.get_guilda(guilda_id)
    assert guilda["andar_home"] == 1  # não mudou
    ctx.send.assert_awaited()


def test_guilda_com_home_pre_existente_acima_do_tier_nao_e_rebaixada_pela_migracao():
    """Grandfather: uma guilda com home 10 (de antes deste cartão) mantém a
    home -- só a PRÓXIMA troca é que passa pelo gate novo."""
    j = _jogador(1)
    db.atualizar_jogador(1, andar_max=10)
    guilda_id = db.criar_guilda("Antiga", lider_id=1, andar_home=10, cargo_id=10, canal_id=20)
    db.adicionar_membro_guilda(2, guilda_id)
    db.adicionar_membro_guilda(3, guilda_id)

    # nada além de init_db()/criar_guilda rodou -- home continua 10
    assert db.get_guilda(guilda_id)["andar_home"] == 10

    ctx = FakeCtx(1)
    asyncio.run(guildas.acao_home(ctx, j, "10"))  # tentar TROCAR é recusado (tier 0 só libera até 3)
    assert db.get_guilda(guilda_id)["andar_home"] == 10  # segue 10 -- não foi rebaixada nem "reconfirmada"


def test_home_liberada_apos_tier_suficiente():
    _jogador(1)
    db.atualizar_jogador(1, andar_max=10)
    j = db.get_jogador(1)  # relê depois do atualizar_jogador -- senão fica com andar_max velho
    guilda_id = _guilda(lider_id=1, membros_extra=(2, 3))
    for i in range(6):
        db.depositar_tesouro_salao(guilda_id, "coroa_velha", 100 + i, None)
    ctx = FakeCtx(1)

    asyncio.run(guildas.acao_home(ctx, j, "5"))  # tier 1 libera até o andar 5

    assert db.get_guilda(guilda_id)["andar_home"] == 5


# ------------------------------------------------------------------ raide
def test_cooldown_de_raide_muda_com_tier_da_guilda():
    guilda_id = _guilda(lider_id=1, membros_extra=(2, 3))
    assert salao.tier_efetivo(0, 3, guildas.MEMBROS_PARA_VALER)["cooldown_raide"] == 2 * 3600

    for i in range(36):
        db.depositar_tesouro_salao(guilda_id, "coroa_velha", 1000 + i, None)
    total = db.contar_tesouros_salao(guilda_id)
    assert salao.tier_efetivo(total, 3, guildas.MEMBROS_PARA_VALER)["cooldown_raide"] == 3600


# --------------------------------------------------------- reset de temporada
def test_reset_zera_salao_ativo_e_preserva_historico():
    guilda_id = _guilda(lider_id=1)
    temporada_1 = db.temporada_atual()
    db.depositar_tesouro_salao(guilda_id, "coroa_velha", 1, "primeira temporada")
    db.depositar_tesouro_salao(guilda_id, "novelo_da_rainha", 2, None)
    assert db.contar_tesouros_salao(guilda_id) == 2

    db.resetar_temporada()

    assert db.temporada_atual() == temporada_1 + 1
    assert db.contar_tesouros_salao(guilda_id) == 0  # temporada ativa zerada
    assert salao.tier_por_total(db.contar_tesouros_salao(guilda_id))["tier"] == 0

    historico = db.tesouros_do_salao(guilda_id, temporada=temporada_1)
    assert len(historico) == 2
    assinatura_preservada = next(r for r in historico if r["item"] == "coroa_velha")
    assert assinatura_preservada["mensagem"] == "primeira temporada"


def test_avancar_temporada_isolado():
    inicial = db.temporada_atual()
    novo = db.avancar_temporada()
    assert novo == inicial + 1
    assert db.temporada_atual() == novo


# ------------------------------------------------------------------ vitrine
def test_vitrine_36_tesouros_assinados_nao_estoura_embed():
    """Pior caso de propósito: 36 tesouros (tier máximo), cada um com
    assinatura no limite de 140 caracteres -- se a paginação não estiver
    ligada corretamente, isso passa dos limites de embed do Discord."""
    guilda_id = _guilda(lider_id=1, membros_extra=(2, 3))
    catalogo = salao.tesouros_do_catalogo()
    for i in range(36):
        item = catalogo[i % len(catalogo)]
        db.depositar_tesouro_salao(guilda_id, item, 2000 + i, "x" * salao.LIMITE_ASSINATURA)

    guilda = db.get_guilda(guilda_id)
    ctx = FakeCtx(1)

    asyncio.run(salao.acao_vitrine(ctx, guilda))  # não pode levantar exceção

    linhas = db.tesouros_do_salao(guilda_id)
    entradas = [salao._entrada_tesouro(r) for r in linhas]
    import paginacao
    paginas = paginacao.paginar(entradas, titulo="Salão", descricao="x" * 50)
    assert len(paginas) >= 2
    for pagina in paginas:
        assert len(pagina) <= paginacao.MAX_FIELDS_POR_EMBED
        assert all(len(nome) <= 256 and len(valor) <= paginacao.MAX_CHARS_POR_FIELD for nome, valor in pagina)
        assert sum(len(n) + len(v) for n, v in pagina) + 90 <= paginacao.MAX_CHARS_POR_EMBED


def test_vitrine_vazia_nao_estoura():
    guilda_id = _guilda(lider_id=1)
    guilda = db.get_guilda(guilda_id)
    ctx = FakeCtx(1)

    asyncio.run(salao.acao_vitrine(ctx, guilda))

    ctx.send.assert_awaited()


def test_assinatura_sobrevive_ao_reset_no_arquivo_da_temporada_anterior():
    guilda_id = _guilda(lider_id=1)
    temporada_1 = db.temporada_atual()
    db.depositar_tesouro_salao(guilda_id, "elmo_de_ignar", 1, "não esqueçam de mim")

    db.resetar_temporada()

    guilda = db.get_guilda(guilda_id)
    ctx = FakeCtx(1)
    asyncio.run(salao.acao_historico(ctx, guilda, str(temporada_1)))
    ctx.send.assert_awaited()

    linha = db.tesouro_salao_do_membro(guilda_id, "elmo_de_ignar", 1, temporada_1)
    assert linha["mensagem"] == "não esqueçam de mim"
