from database import get_connection
with get_connection() as conn:
    rows = conn.execute("""
        SELECT extensao, COUNT(*) as total
        FROM files
        WHERE decisao = 'lixo' AND status = 'processado'
        GROUP BY extensao
        ORDER BY total DESC
        LIMIT 30
    """).fetchall()
    print(f"\n{'EXTENSÃO':<20} {'QTDE':>6}")
    print("-" * 28)
    for r in rows:
        print(f"{r['extensao'] or '(sem extensao)':<20} {r['total']:>6}")
