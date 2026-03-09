import hashlib
import os
import re
import shutil
import sys
from pathlib import Path
from tqdm import tqdm

# Configura o path para encontrar o database.py
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
from database import get_connection

def limpar_nome_filehistory(nome):
    """Remove o sufixo de data do FileHistory: 'arquivo (2024_01_01 UTC).ext'"""
    padrao = r"\s\(\d{4}_\d{2}_\d{2}\s\d{2}_\d{2}_\d{2}\sUTC\)"
    return re.sub(padrao, "", nome)

def calcular_sha256(caminho):
    """Gera o hash real do arquivo para comparação de conteúdo (DNA)."""
    sha256 = hashlib.sha256()
    try:
        with open(caminho, "rb") as f:
            while bloco := f.read(1048576): # 1MB por vez
                sha256.update(bloco)
        return sha256.hexdigest()
    except Exception:
        return None

def purificar():
    base_f = Path("F:/")
    dup_dir = base_f / "duplicatas_detectadas"
    
    if not base_f.exists():
        print(f"❌ Erro: Unidade {base_f} não encontrada.")
        return

    dup_dir.mkdir(exist_ok=True)

    print("\n--- 1. HIGIENIZANDO NOMES (FileHistory) ---")
    arquivos_no_disco = list(base_f.rglob("*"))
    for arq in tqdm(arquivos_no_disco, desc="Limpando nomes"):
        if arq.is_file() and not str(arq).startswith(str(dup_dir)):
            nome_limpo = limpar_nome_filehistory(arq.name)
            if nome_limpo != arq.name:
                novo_path = arq.parent / nome_limpo
                if not novo_path.exists():
                    try:
                        arq.rename(novo_path)
                    except Exception:
                        pass

    print("\n--- 2. SINCRONIZANDO CAMINHOS E HASHES (BANCO vs DISCO) ---")
    with get_connection() as conn:
        # Pega TODOS os arquivos copiados para verificar se o caminho mudou após a limpeza da Fase 1
        # e para gerar hashes que ainda não foram gerados.
        arquivos_para_sincronizar = conn.execute(
            "SELECT id, caminho_destino, hash_sha256 FROM files WHERE status='copiado'"
        ).fetchall()
        
        for arq in tqdm(arquivos_para_sincronizar, desc="Sincronizando Banco"):
            if arq["caminho_destino"] is None:
                continue
                
            path_db = Path(arq["caminho_destino"])
            nome_limpo = limpar_nome_filehistory(path_db.name)
            path_limpo = path_db.parent / nome_limpo
            
            # Checa qual versão do caminho existe fisicamente no disco
            path_real_no_disco = None
            if path_limpo.exists():
                path_real_no_disco = path_limpo
            elif path_db.exists():
                path_real_no_disco = path_db

            if path_real_no_disco:
                needs_update = False
                # Pega o hash do DB para não recalcular
                hash_atual = arq["hash_sha256"]
                caminho_atual_str = str(path_real_no_disco)

                # 1. Gera hash se não existir
                if hash_atual is None or hash_atual == 'sem_hash':
                    novo_hash = calcular_sha256(path_real_no_disco)
                    if novo_hash:
                        hash_atual = novo_hash
                        needs_update = True

                # 2. Verifica se o caminho no banco de dados precisa ser atualizado
                if caminho_atual_str != arq["caminho_destino"]:
                    needs_update = True
                
                if needs_update:
                    conn.execute(
                        "UPDATE files SET hash_sha256 = ?, caminho_destino = ? WHERE id = ?", 
                        (hash_atual, caminho_atual_str, arq["id"])
                    )
            # else: o arquivo não foi encontrado no disco, pode ter sido movido/deletado manualmente
            # Nenhuma ação é tomada para preservar o registro.
        conn.commit()

    print("\n--- 3. REMOVENDO DUPLICATAS REAIS (Baseado em Hash) ---")
    with get_connection() as conn:
        dups = conn.execute("""
            SELECT hash_sha256, COUNT(*) FROM files 
            WHERE status='copiado' AND hash_sha256 IS NOT NULL AND hash_sha256 != 'sem_hash'
            GROUP BY hash_sha256 HAVING COUNT(*) > 1
        """).fetchall()

        espaco_recuperado = 0
        total_movidos = 0

        for d in tqdm(dups, desc="Movendo duplicatas"):
            h_val = d[0]
            items = conn.execute(
                "SELECT id, caminho_destino, tamanho FROM files WHERE hash_sha256 = ? AND status='copiado' ORDER BY length(caminho_destino) ASC", 
                (h_val,)
            ).fetchall()
            
            if len(items) > 1:
                # Mantemos o primeiro (caminho mais curto) e movemos os outros
                for repetido in items[1:]:
                    if repetido["caminho_destino"]:
                        p_old = Path(repetido["caminho_destino"])
                        if p_old.exists():
                            try:
                                destino_final = dup_dir / f"{h_val[:10]}_{p_old.name}"
                                shutil.move(str(p_old), str(destino_final))
                                # O schema atual só permite status: pendente/processado/erro/copiado.
                                # Registramos a remoção da duplicata em `motivo` para manter compatibilidade.
                                conn.execute(
                                    "UPDATE files SET motivo='duplicata_removida' WHERE id = ?",
                                    (repetido["id"],)
                                )
                                espaco_recuperado += (repetido["tamanho"] or 0)
                                total_movidos += 1
                            except Exception:
                                pass
        conn.commit()

    print("\n" + "="*50)
    print("🏁 PURIFICAÇÃO CONCLUÍDA!")
    print(f"📦 Arquivos duplicatas movidos: {total_movidos}")
    print(f"💾 Espaço aproximado liberado: {espaco_recuperado / (1024**3):.2f} GB")
    print("="*50)

if __name__ == "__main__":
    purificar()