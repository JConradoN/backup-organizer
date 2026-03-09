import sys
import os
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv

# Garante que o script encontre o database.py e configurações
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
load_dotenv(dotenv_path=BASE_DIR / ".env")

from database import get_connection

def gerar():
    print("🔍 Analisando banco de dados para cópia incremental...")
    
    with get_connection() as conn:
        # Busca apenas arquivos úteis que ainda não foram confirmados como copiados
        arquivos = conn.execute(
            """SELECT caminho_original, caminho_destino, tamanho 
               FROM files 
               WHERE status = 'processado' 
               AND decisao IN ('util', 'ambiguo') 
               AND caminho_destino IS NOT NULL"""
        ).fetchall()

    if not arquivos:
        print("✅ Nada novo para copiar no banco de dados.")
        return

    grupos = defaultdict(list)
    cont_pulados = 0
    
    for arq in arquivos:
        origem = Path(arq["caminho_original"])
        destino = Path(arq["caminho_destino"])
        
        # Checagem física rápida: se já existe com o mesmo tamanho, pula a geração do comando
        if destino.exists() and destino.stat().st_size == arq["tamanho"]:
            cont_pulados += 1
            continue
            
        chave = (str(origem.parent), str(destino.parent))
        grupos[chave].append(origem.name)

    if not grupos:
        print(f"✅ {cont_pulados} arquivos já estão no destino. Tudo atualizado!")
        if (Path(__file__).parent / "robocopy_run.bat").exists():
            os.remove(Path(__file__).parent / "robocopy_run.bat")
        return

    print(f"📦 {len(arquivos) - cont_pulados} arquivos pendentes adicionados à lista.")
    
    # Montagem do BAT com suporte a UTF-8 (65001) e Log de Auditoria
    log_path = BASE_DIR / "logs" / "robocopy_detalhado.log"
    linhas = [
        "@echo off",
        "chcp 65001 > nul",
        f"echo === INICIANDO TRANSFERENCIA: {len(arquivos) - cont_pulados} ARQUIVOS ===",
        f"echo Log sendo gerado em: {log_path}",
        ""
    ]

    for (pasta_orig, pasta_dest), nomes in grupos.items():
        # Blocos de 40 arquivos para não exceder o limite de linha do CMD
        CHUNK = 40 
        for i in range(0, len(nomes), CHUNK):
            bloco = nomes[i:i+CHUNK]
            lista_nomes = " ".join(f'"{n}"' for n in bloco)
            # /XO: Pula se o destino for igual/mais novo | /V: Detalhado | /TEE: Tela + Log
            linha = f'robocopy "{pasta_orig}" "{pasta_dest}" {lista_nomes} /COPY:DAT /XO /R:1 /W:1 /NP /V /TEE /LOG+:"{log_path}"'
            linhas.append(linha)

    linhas.append("\necho. \necho ✅ Processo finalizado com sucesso.")
    
    caminho_bat = Path(__file__).parent / "robocopy_run.bat"
    caminho_bat.write_text("\n".join(linhas), encoding="utf-8")
    print(f"🚀 Script BAT gerado: {caminho_bat}")

if __name__ == "__main__":
    gerar()