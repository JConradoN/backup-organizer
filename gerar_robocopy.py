import sys
import os
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv

# Garante que o script encontre o database.py
sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from database import get_connection

def gerar():
    with get_connection() as conn:
        # Só pega o que está processado mas NÃO marcado como copiado
        arquivos = conn.execute(
            """SELECT caminho_original, caminho_destino, tamanho
               FROM files
               WHERE status = 'processado'
               AND decisao IN ('util', 'ambiguo')
               AND caminho_destino IS NOT NULL"""
        ).fetchall()

    if not arquivos:
        print("✅ Tudo atualizado! Nenhum arquivo novo para copiar.")
        # Cria um bat vazio para não dar erro no próximo passo
        (Path(__file__).parent / "robocopy_run.bat").write_text("@echo off\necho Nada novo para copiar.", encoding="cp1252")
        return

    print(f"📊 {len(arquivos):,} arquivos pendentes de cópia física...")

    grupos = defaultdict(list)
    for arq in arquivos:
        origem  = Path(arq["caminho_original"])
        destino = Path(arq["caminho_destino"])
        # O segredo para caracteres especiais e caminhos longos no Windows: prefixo \\?\
        chave   = (str(origem.parent), str(destino.parent))
        grupos[chave].append(origem.name)

    linhas = ["@echo off", "chcp 1252 > nul", "echo Iniciando Robocopy Incremental...", ""]

    for (pasta_orig, pasta_dest), arquivos_grupo in grupos.items():
        CHUNK = 50 # Menor para evitar erro de limite de caracteres no CMD
        for i in range(0, len(arquivos_grupo), CHUNK):
            chunk = arquivos_grupo[i:i+CHUNK]
            nomes = " ".join(f'"{n}"' for n in chunk)
            # /XO pula arquivos mais antigos, /V gera log, /NP remove progresso poluído
            linha = f'robocopy "{pasta_orig}" "{pasta_dest}" {nomes} /COPY:DAT /XO /R:2 /W:2 /NP /V'
            linhas.append(linha)

    linhas.append("\necho ✅ Fim do Robocopy.")
    
    # Salva na pasta src para o .bat encontrar
    bat_path = Path(__file__).parent / "robocopy_run.bat"
    bat_path.write_text("\n".join(linhas), encoding="cp1252")
    print(f"🚀 Script de cópia gerado em: {bat_path}")

if __name__ == "__main__":
    gerar()