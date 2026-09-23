# entidade_sombria.py
# Step D, commit 4: a Essência das Trevas e a Entidade Sombria. Ela chegou
# com a incursão -- é coerente com a lore que ela também tenha vindo de fora
# -- e muda de lugar junto: só aparece no andar corrompido do dia (ver
# npcs.npcs_do_andar, que soma ENTIDADE_SOMBRIA à lista quando
# incursao.andar_esta_corrompido(andar) é True). Módulo novo, mesmo padrão
# de vilarejo.py/incursao.py -- o conceito (uma loja de token com regra
# própria, sem moeda nenhuma) é grande o bastante pra não emendar em
# npcs.py/bot.py.
import database as db
import game_data
import incursao

# ---------------- o que ela vende ----------------
# Regra geral do cartão: loja de token vende o que os outros sistemas NÃO
# vendem -- sem redução de cooldown (torneira fechada na dungeon) e sem arma
# pronta (Selen/as 24 elementais são o coração do endgame). Os dois itens
# abaixo não existem em mais lugar nenhum.
EFEITOS_VENDIDOS = ("cura_ao_critico", "ignora_condicao", "furia_extra_ao_apanhar")

# Preço/taxa calibrados juntos por Monte Carlo (scratchpad, não faz parte do
# repo) -- ~15-20 caçadas/dia é o "farm moderado" assumido (cooldown de
# rpg cacar é 60s, mas ninguém joga sem parar; é um bot de 5-10 amigos, não
# um MMO). A 20% de chance por criatura de sombra, isso dá ~3-4 Essência por
# dia de incursão. Ver decisoes.md § Step D pro raciocínio completo.
CHANCE_ESSENCIA_DROP = 0.20   # 20% por criatura de sombra derrotada
PRECO_SELO = 10               # ~3 dias de incursão de farm moderado
PRECO_SALVO_CONDUTO = 45    # ~4.5x o Selo -- "mais caro que o resto", de propósito

ENTIDADE_SOMBRIA = {
    "nome": "A Entidade Sombria", "titulo": "", "tipo": "entidade_sombria", "dialogo": "entidade_sombria",
    "fala": (
        "Vocês trancaram a porta de dentro. Eu vim pela fresta que ficou depois que "
        "destrancaram de novo. Não vim pra ficar — só pra negociar antes de ir."
    ),
}


def npc_presente(andar, momento=None):
    return incursao.andar_esta_corrompido(andar, momento)


def encontrar_efeito(texto):
    """Casa `texto` (nome livre ou chave) contra os TRÊS efeitos que a
    Entidade Sombria vende -- nunca os outros de game_data.PASSIVAS (as
    passivas de ascensão não são um Selo que se compra). None se não
    achar."""
    alvo = (texto or "").strip().lower()
    if not alvo:
        return None
    for chave in EFEITOS_VENDIDOS:
        dado = game_data.PASSIVAS[chave]
        if alvo == chave or alvo == dado["nome"].lower():
            return chave
    for chave in EFEITOS_VENDIDOS:
        dado = game_data.PASSIVAS[chave]
        if alvo in dado["nome"].lower():
            return chave
    return None


def comprar_selo(user_id, slot, efeito):
    """`slot`: "anel" ou "colar" -- de qual campo de instância ler.
    Devolve (ok, motivo) -- motivo é a chave do erro quando ok é False,
    ou None quando deu certo. Quem chama (bot.py) traduz motivo -> frase;
    esta função não sabe de Discord."""
    if slot not in ("anel", "colar"):
        return False, "slot_invalido"
    j = db.get_jogador(user_id)
    if not j:
        return False, "sem_jogador"
    instancia_id = j[f"{slot}_instancia_id"]
    if not instancia_id:
        return False, "sem_peca"
    if not db.tem_item(user_id, "essencia_das_trevas", PRECO_SELO):
        return False, "sem_essencia"
    db.remove_item(user_id, "essencia_das_trevas", PRECO_SELO)
    db.definir_efeito_instancia(instancia_id, efeito)
    return True, None


def comprar_salvo_conduto(user_id):
    """Um por jogador por vez -- sem esse limite, a torre acima do Selo
    perde o dente (o cartão foi explícito). Devolve (ok, motivo)."""
    if db.tem_item(user_id, "salvo_conduto", 1):
        return False, "ja_tem"
    if not db.tem_item(user_id, "essencia_das_trevas", PRECO_SALVO_CONDUTO):
        return False, "sem_essencia"
    db.remove_item(user_id, "essencia_das_trevas", PRECO_SALVO_CONDUTO)
    db.add_item(user_id, "salvo_conduto", 1)
    return True, None
