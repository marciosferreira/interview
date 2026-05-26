"""
reset_week_limit.py
-------------------
Recua o created_at das job_sessions da última semana para 8 dias atrás,
zerando o contador de entrevistas semanais sem apagar dados.

Uso:
    py reset_week_limit.py              # mostra o que vai mudar (dry-run)
    py reset_week_limit.py --apply      # aplica a mudança
    py reset_week_limit.py --email x@y  # filtra por usuário específico
"""

import sqlite3
import time
import argparse
from pathlib import Path

DB_PATH = Path(__file__).parent / "sessions.db"

def now_ms() -> int:
    return int(time.time() * 1000)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Aplica a mudança (sem isso é dry-run)")
    parser.add_argument("--email", help="Filtra por email de usuário (opcional)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    week_ago_ms   = now_ms() - 7  * 24 * 3_600_000
    eight_days_ms = now_ms() - 8  * 24 * 3_600_000  # destino: fora da janela

    # Monta query de busca
    if args.email:
        user_row = conn.execute(
            "SELECT id, email FROM users WHERE email = ?", (args.email,)
        ).fetchone()
        if not user_row:
            print(f"Usuário não encontrado: {args.email}")
            return
        user_filter = f"AND js.user_id = '{user_row['id']}'"
        print(f"Filtrando por: {user_row['email']} (id={user_row['id']})")
    else:
        user_filter = ""

    rows = conn.execute(f"""
        SELECT js.id, js.user_id, js.job_title, js.company, js.created_at,
               u.email
        FROM job_sessions js
        LEFT JOIN users u ON js.user_id = u.id
        WHERE js.created_at >= ?
        {user_filter}
        ORDER BY js.created_at DESC
    """, (week_ago_ms,)).fetchall()

    if not rows:
        print("Nenhuma job_session na última semana. Nada a fazer.")
        return

    print(f"\n{'DRY-RUN — use --apply para confirmar' if not args.apply else 'APLICANDO'}")
    print(f"{'─'*60}")
    print(f"{'ID':<36}  {'Email':<28}  {'Título'}")
    print(f"{'─'*60}")
    for r in rows:
        print(f"{r['id']:<36}  {(r['email'] or '?'):<28}  {r['job_title'] or '?'}")
    print(f"{'─'*60}")
    print(f"Total: {len(rows)} sessão(ões) serão recuadas para fora da janela de 7 dias.\n")

    if args.apply:
        ids = [r["id"] for r in rows]
        conn.executemany(
            "UPDATE job_sessions SET created_at = ? WHERE id = ?",
            [(eight_days_ms, id_) for id_ in ids],
        )
        conn.commit()
        print("✓ created_at recuado para 8 dias atrás. Limite semanal zerado.")
    else:
        print("Nenhuma mudança feita. Rode com --apply para confirmar.")

    conn.close()

if __name__ == "__main__":
    main()
