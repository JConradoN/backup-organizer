import sqlite3
import os
from pathlib import Path

# Caminho com 'r' para evitar erro de unicode no Windows
DB_PATH = r"C:\Users\morph\dev-tools\backup-organizer\src\backup_organizer.db"

def consultar_progresso():
    if not os.path.exists(DB_PATH):
        print(f"❌ Erro: O arquivo {DB_PATH} não foi encontrado!")
        return

    conn = sqlite3.connect(DB_PATH)
    # Configura para acessar colunas pelo nome se precisar
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT COUNT(*), SUM(tamanho) FROM files WHERE status='copiado';"

    try:
        row = cursor.execute(query).fetchone()
        count = row[0] or 0
        total_bytes = row[1] or 0
        total_gb = total_bytes / (1024**3)

        print("\n" + "="*40)
        print("📊 RELATÓRIO DE TRANSFERÊNCIA (BANCO)")
        print("="*40)
        print(f"✅ Arquivos confirmados : {count:,}")
        print(f"📦 Tamanho total        : {total_gb:.2f} GB")
        print("="*40)

    except Exception as e:
        print(f"❌ Erro ao consultar o banco: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    consultar_progresso()