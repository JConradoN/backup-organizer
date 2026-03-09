import hashlib
from pathlib import Path
from tqdm import tqdm
from database import get_connection

def calcular_sha256(caminho):
    sha256 = hashlib.sha256()
    with open(caminho, "rb") as f:
        while bloco := f.read(1048576): # 1MB por vez
            sha256.update(bloco)
    return sha256.hexdigest()

def preencher_hashes():
    with get_connection() as conn:
        # Busca arquivos que estão no destino mas não têm hash real
        arquivos = conn.execute(
            "SELECT id, caminho_destino FROM files WHERE status='copiado' AND (hash_sha256 IS NULL OR hash_sha256='sem_hash')"
        ).fetchall()

        if not arquivos:
            print("✅ Todos os arquivos já possuem Hash.")
            return

        print(f"🧬 Gerando DNA (Hash) para {len(arquivos)} arquivos no destino...")
        
        for arq in tqdm(arquivos):
            caminho = Path(arq["caminho_destino"])
            if caminho.exists():
                hash_real = calcular_sha256(caminho)
                conn.execute("UPDATE files SET hash_sha256 = ? WHERE id = ?", (hash_real, arq["id"]))
        
        conn.commit()
    print("✅ Hashes atualizados com sucesso!")

if __name__ == "__main__":
    preencher_hashes()