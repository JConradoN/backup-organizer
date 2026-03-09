import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from database import DB_PATH

abs_path = Path(DB_PATH).resolve()
print(f"DB_PATH configurado : {DB_PATH}")
print(f"Caminho absoluto    : {abs_path}")
print(f"Arquivo existe?     : {abs_path.exists()}")
if abs_path.exists():
    print(f"Tamanho             : {abs_path.stat().st_size / 1024**2:.1f} MB")

# Verifica se existe outro banco no diretório pai
parent_db = Path(__file__).parent.parent / "backup_organizer.db"
print(f"\nBanco na raiz do projeto: {parent_db}")
print(f"Existe?                 : {parent_db.exists()}")
if parent_db.exists():
    print(f"Tamanho                 : {parent_db.stat().st_size / 1024**2:.1f} MB")
