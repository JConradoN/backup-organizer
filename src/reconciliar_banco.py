import sqlite3
from pathlib import Path
import sys
from tqdm import tqdm

# Configura o path para encontrar o database.py
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
from database import get_connection

def reconciliar():
    print("🔍 Iniciando reconciliação física (Banco vs HD)...")
    
    with get_connection() as conn:
        # Pega tudo que a IA processou mas não está marcado como copiado
        arquivos = conn.execute(
            "SELECT id, caminho_destino FROM files WHERE status = 'processado' AND caminho_destino IS NOT NULL"
        ).fetchall()
        
        if not arquivos:
            print("✅ Nada para reconciliar.")
            return

        print(f"📋 Analisando {len(arquivos)} arquivos pendentes...")
        atualizados = 0
        
        for arq in tqdm(arquivos):
            dest = Path(arq["caminho_destino"])
            
            # Checa se o arquivo existe fisicamente no destino
            if dest.exists() and dest.is_file():
                conn.execute(
                    "UPDATE files SET status = 'copiado' WHERE id = ?", (arq["id"],)
                )
                atualizados += 1
                
                # Commit em blocos para performance
                if atualizados % 500 == 0:
                    conn.commit()
                    
        conn.commit()
        print(f"\n✅ Sucesso! {atualizados} arquivos foram encontrados no HD e marcados como 'copiado'.")

if __name__ == "__main__":
    reconciliar()