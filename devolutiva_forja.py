# devolutiva_forja.py
# Script one-off: paga a diferenca de moedas pra quem subiu a Forja no custo
# antigo, depois do rebalanceamento das quatro receitas em profissoes.py.
# Sem flag so mostra o preview -- so' credita moedas de verdade com --aplicar.
# Rodar --aplicar duas vezes paga duas vezes: uma unica execucao, depois de
# backup do aincrad.db. Ver decisoes.md § Rebalancear a escada da Forja.
import sqlite3
import sys

DB_PATH = "aincrad.db"
DIFERENCA_POR_XP = 12   # custo por XP: 25 moedas no modelo velho, 13 no novo


def xp_acumulado(prof_nivel, prof_xp):
    """XP total que o jogador ja' pagou no preco antigo: 25*N*(N-1) e' o XP
    das levas ja' completadas ate' o nivel atual, prof_xp e' o progresso
    dentro do nivel corrente."""
    return 25 * prof_nivel * (prof_nivel - 1) + prof_xp


def main():
    aplicar = "--aplicar" in sys.argv

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    forjadores = conn.execute(
        "SELECT user_id, nome, prof_nivel, prof_xp, moedas FROM jogadores WHERE profissao = 'forja'"
    ).fetchall()

    print(f"{'jogador':20} {'nivel':>5} {'xp':>6} {'devolucao':>10}")
    total = 0
    for j in forjadores:
        devolucao = xp_acumulado(j["prof_nivel"], j["prof_xp"]) * DIFERENCA_POR_XP
        total += devolucao
        print(f"{j['nome']:20} {j['prof_nivel']:>5} {j['prof_xp']:>6} {devolucao:>10}")
        if aplicar:
            conn.execute(
                "UPDATE jogadores SET moedas = moedas + ? WHERE user_id = ?",
                (devolucao, j["user_id"]),
            )

    print(f"\nTOTAL: {total}")
    if aplicar:
        conn.commit()
        print("Aplicado -- moedas creditadas. Registra data + total no decisoes.md.")
    else:
        print("Preview apenas -- confere os valores, faz backup do aincrad.db, "
              "e roda de novo com --aplicar.")
    conn.close()


if __name__ == "__main__":
    main()
