# dar_moedas.py
# Script standalone pra dar moedas de graça pra um jogador. Roda direto no
# terminal (python dar_moedas.py), nao depende do bot estar online — mesma
# ideia do reset_boss.py, so que interativo.

import sqlite3

conn = sqlite3.connect("aincrad.db")
conn.execute("PRAGMA busy_timeout=5000")

jogadores = conn.execute(
    "SELECT user_id, nome, moedas FROM jogadores ORDER BY nome COLLATE NOCASE"
).fetchall()

if not jogadores:
    print("Nenhum jogador cadastrado.")
    raise SystemExit

print("Jogadores:")
for i, (user_id, nome, moedas) in enumerate(jogadores, start=1):
    print(f"  {i}. {nome} - {moedas} moedas")

escolha = input("\nEscolha o jogador (numero): ").strip()
if not escolha.isdigit() or not (1 <= int(escolha) <= len(jogadores)):
    print("Numero invalido.")
    raise SystemExit

user_id, nome, moedas_atuais = jogadores[int(escolha) - 1]

valor = input(f"Quantas moedas adicionar para {nome}? ").strip()
if not valor.lstrip("-").isdigit():
    print("Valor invalido.")
    raise SystemExit
valor = int(valor)

confirmacao = input(f"Confirma: {nome} vai de {moedas_atuais} para {moedas_atuais + valor} moedas? (s/n) ").strip().lower()
if confirmacao != "s":
    print("Cancelado.")
    raise SystemExit

conn.execute("UPDATE jogadores SET moedas = moedas + ? WHERE user_id = ?", (valor, user_id))
conn.commit()

nova_quantia = conn.execute("SELECT moedas FROM jogadores WHERE user_id = ?", (user_id,)).fetchone()[0]
print(f"OK - {nome} agora tem {nova_quantia} moedas.")

conn.close()
