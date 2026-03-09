"""
diagnostico.py
Mostra as extensões que estão indo para a IA, ordenadas por frequência.
Roda em segundos — apenas consulta o banco, sem processar arquivos.
"""

from database import get_connection

def main():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT extensao, COUNT(*) as total
            FROM files
            WHERE status = 'pendente'
            GROUP BY extensao
            ORDER BY total DESC
            LIMIT 60
        """).fetchall()

    total_ia = sum(r["total"] for r in rows)
    print(f"\n📊 Extensões pendentes para IA ({total_ia:,} arquivos)\n")
    print(f"  {'EXTENSÃO':<15} {'QTDE':>8}  {'%':>6}")
    print("  " + "-" * 35)
    for r in rows:
        ext   = r["extensao"] or "(sem extensão)"
        total = r["total"]
        pct   = total / total_ia * 100
        print(f"  {ext:<15} {total:>8,}  {pct:>5.1f}%")

if __name__ == "__main__":
    main()
