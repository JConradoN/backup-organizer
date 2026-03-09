"""
marcar_copiados.py
Após o robocopy_run.bat terminar, este script verifica quais arquivos
foram copiados com sucesso (compara tamanho) e atualiza o banco.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from tqdm import tqdm
from database import get_connection, marcar_copiado, marcar_erro

def marcar():
    with get_connection() as conn:
        arquivos = conn.execute(
            """SELECT caminho_original, caminho_destino, tamanho
               FROM files
               WHERE status = 'processado'
               AND decisao IN ('util', 'ambiguo')
               AND caminho_destino IS NOT NULL"""
        ).fetchall()

    total = len(arquivos)
    print(f"🔍 Verificando {total:,} arquivos copiados...")

    stats = {"ok": 0, "faltando": 0, "tamanho_errado": 0}

    for arq in tqdm(arquivos, desc="Verificando", unit="arq"):
        destino = Path(arq["caminho_destino"])
        
        # Arquivo pode ter sido renomeado com _1, _2 etc pelo mover.py original
        # Tenta encontrar qualquer variante
        encontrado = None
        if destino.exists():
            encontrado = destino
        else:
            # Tenta variantes com sufixo numérico
            for i in range(1, 5):
                variante = destino.parent / f"{destino.stem}_{i}{destino.suffix}"
                if variante.exists():
                    encontrado = variante
                    break

        if encontrado is None:
            stats["faltando"] += 1
            marcar_erro(arq["caminho_original"], "Arquivo não encontrado no destino após robocopy")
            continue

        # Verifica tamanho
        tamanho_dest = encontrado.stat().st_size
        tamanho_orig = arq["tamanho"] or 0

        if tamanho_orig > 0 and abs(tamanho_dest - tamanho_orig) > 1024:
            stats["tamanho_errado"] += 1
            marcar_erro(arq["caminho_original"], f"Tamanho divergente: orig={tamanho_orig} dest={tamanho_dest}")
        else:
            marcar_copiado(arq["caminho_original"])
            stats["ok"] += 1

    print(f"\n✅ Verificação concluída:")
    print(f"   Copiados OK      : {stats['ok']:,}")
    print(f"   Faltando         : {stats['faltando']:,}")
    print(f"   Tamanho errado   : {stats['tamanho_errado']:,}")

if __name__ == "__main__":
    marcar()
