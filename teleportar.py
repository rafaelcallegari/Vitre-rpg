# teleportar.py
# Script standalone pra mandar um jogador direto pra um andar. Roda no
# terminal (python teleportar.py), mesmo estilo do dar_moedas.py.
#
# Se o destino for maior que o andar_max atual, andar_max sobe junto —
# senao o jogador chega num andar que o jogo ainda trata como trancado
# (loja/ferreiro nao liberam o andar, e ate o Selo (andar 10) "dono do
# andar" no chefe exige andar == andar_max).

import sqlite3

import game_data

ANDAR_MAXIMO = game_data.ANDAR_MAXIMO

conn = sqlite3.connect("aincrad.db")
conn.execute("PRAGMA busy_timeout=5000")

jogadores = conn.execute(
    "SELECT user_id, nome, andar, andar_max FROM jogadores ORDER BY nome COLLATE NOCASE"
).fetchall()

if not jogadores:
    print("Nenhum jogador cadastrado.")
    raise SystemExit

print("Jogadores:")
for i, (user_id, nome, andar, andar_max) in enumerate(jogadores, start=1):
    print(f"  {i}. {nome} - andar {andar} (destrancado ate {andar_max})")

escolha = input("\nEscolha o jogador (numero): ").strip()
if not escolha.isdigit() or not (1 <= int(escolha) <= len(jogadores)):
    print("Numero invalido.")
    raise SystemExit

user_id, nome, andar_atual, andar_max_atual = jogadores[int(escolha) - 1]

destino = input(f"Teleportar {nome} para qual andar (1-{ANDAR_MAXIMO})? ").strip()
if not destino.isdigit() or not (1 <= int(destino) <= ANDAR_MAXIMO):
    print(f"Andar invalido. Tem que ser entre 1 e {ANDAR_MAXIMO}.")
    raise SystemExit
destino = int(destino)

nome_andar = game_data.ANDARES.get(destino, {}).get("nome", "?")
sobe_max = destino > andar_max_atual
aviso_max = f" (andar_max tambem sobe de {andar_max_atual} para {destino})" if sobe_max else ""

confirmacao = input(
    f"Confirma: {nome} vai do andar {andar_atual} para o andar {destino} "
    f"({nome_andar}){aviso_max}? (s/n) "
).strip().lower()
if confirmacao != "s":
    print("Cancelado.")
    raise SystemExit

novo_max = max(andar_max_atual, destino)
conn.execute(
    "UPDATE jogadores SET andar = ?, andar_max = ? WHERE user_id = ?",
    (destino, novo_max, user_id),
)
conn.commit()

print(f"OK - {nome} esta agora no andar {destino} ({nome_andar}), destrancado ate {novo_max}.")

conn.close()
