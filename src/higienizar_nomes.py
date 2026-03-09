import os
import re
from pathlib import Path
from database import get_connection

def limpar_nome_filehistory(nome_arquivo):
    # Regex para capturar o padrão de data do FileHistory: " (2024_02_11 12_36_17 UTC)"
    padrao = r"\s\(\d{4}_\d{2}_\d{2}\s\d{2}_\d{2}_\d{2}\sUTC\)"
    return re.sub(padrao, "", nome_arquivo)

def higienizar_destino():
    base_f = Path("F:/")
    pastas = ["fotos", "videos", "documentos", "musica", "outros"]
    
    print("🧹 Iniciando higienização de nomes e remoção de timestamps...")

    for pasta in pastas:
        caminho_pasta = base_f / pasta
        if not caminho_pasta.exists(): continue

        for arquivo in caminho_pasta.rglob("*"):
            if not arquivo.is_file(): continue
            
            nome_limpo = limpar_nome_filehistory(arquivo.name)
            
            if nome_limpo != arquivo.name:
                novo_caminho = arquivo.parent / nome_limpo
                
                if not novo_caminho.exists():
                    try:
                        arquivo.rename(novo_caminho)
                        print(f"✅ Renomeado: {arquivo.name} -> {nome_limpo}")
                    except Exception as e:
                        print(f"❌ Erro ao renomear {arquivo.name}: {e}")
                else:
                    # Se o nome limpo já existe, o hash resolverá depois no script de duplicatas
                    print(f"⏭️  Já existe versão limpa de: {nome_limpo}, ignorando renomeação.")

if __name__ == "__main__":
    higienizar_destino()