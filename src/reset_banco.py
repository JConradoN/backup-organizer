from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from database import get_connection, init_db

# Garante que as tabelas existam antes de tentar dar o comando UPDATE
init_db()

with get_connection() as conn:
    try:
        cur = conn.execute("UPDATE files SET status='pendente', decisao=NULL, caminho_destino=NULL WHERE status='processado'")
        conn.commit()
        print(f"✅ Reset concluído — {cur.rowcount:,} arquivos voltaram para pendente")
    except Exception as e:
        print(f"ℹ️ O banco já estava limpo ou vazio: {e}")