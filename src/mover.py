"""
mover.py
Fase 3 — Movimentação Copy-First.
Versão otimizada:
- Verificação usa hash do banco (sem reler o HD de origem)
- Calcula hash apenas do destino e compara com SQLite
- NUNCA deleta automaticamente
"""

import hashlib
import os
import shutil
from pathlib import Path
from datetime import datetime

from tqdm import tqdm

from database import get_connection, marcar_copiado, marcar_erro


BLOCK_SIZE = 1_048_576  # 1MB — consistente com o scanner


def _hash_arquivo(caminho: Path) -> str | None:
    """Hash SHA-256 do arquivo de destino para verificação."""
    sha256 = hashlib.sha256()
    try:
        with open(caminho, "rb") as f:
            while bloco := f.read(BLOCK_SIZE):
                sha256.update(bloco)
        return sha256.hexdigest()
    except (PermissionError, OSError):
        return None


def _verificar_copia(destino: Path, hash_origem: str | None, tamanho_origem: int) -> bool:
    """
    Verifica a cópia sem reler o HD de origem.
    - Se temos hash do scan: compara hash do destino com o banco
    - Se não temos hash (fotos/vídeos sem hash): verifica só o tamanho
    """
    if not destino.exists():
        return False

    # Verificação por tamanho (fotos/vídeos — sem hash no banco)
    if hash_origem is None:
        return destino.stat().st_size == tamanho_origem

    # Verificação por hash (documentos/código — hash no banco)
    hash_destino = _hash_arquivo(destino)
    return hash_destino == hash_origem


def _copiar_arquivo(origem: Path, destino: Path) -> bool:
    """
    Copia com renomeação automática em conflito de nome.
    Retorna True se cópia foi bem sucedida.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)

    # Evita sobrescrever arquivo existente
    if destino.exists():
        stem, suffix = destino.stem, destino.suffix
        contador = 1
        while destino.exists():
            destino = destino.parent / f"{stem}_{contador}{suffix}"
            contador += 1

    shutil.copy2(str(origem), str(destino))
    return destino.exists()


def executar_copia(dry_run: bool = False) -> dict:
    """
    Executa cópia de todos os arquivos classificados.
    Verificação usa hash do banco — sem reler o HD de origem.
    """
    with get_connection() as conn:
        arquivos = conn.execute(
            """SELECT caminho_original, caminho_destino, decisao,
                      hash_sha256, tamanho
               FROM files
               WHERE status = 'processado'
               AND decisao IN ('util', 'ambiguo')
               AND caminho_destino IS NOT NULL"""
        ).fetchall()

    total = len(arquivos)
    if total == 0:
        print("Nenhum arquivo pronto para cópia.")
        return {}

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Iniciando cópia de {total:,} arquivos...\n")

    stats     = {"copiados": 0, "erros": 0, "simulados": 0, "verificados": 0}
    log_lines = []

    for arq in tqdm(arquivos, desc="Copiando", unit="arq"):
        origem  = Path(arq["caminho_original"])
        destino = Path(arq["caminho_destino"])

        if dry_run:
            log_lines.append(f"[SIMULADO] {origem} → {destino}")
            stats["simulados"] += 1
            continue

        try:
            if not origem.exists():
                raise FileNotFoundError(f"Origem não encontrada: {origem}")

            sucesso_copia = _copiar_arquivo(origem, destino)

            if not sucesso_copia:
                raise IOError("Falha na cópia — arquivo de destino não criado")

            # Verifica usando hash do banco (sem reler origem)
            verificado = _verificar_copia(
                destino,
                arq["hash_sha256"],
                arq["tamanho"] or 0
            )

            if verificado:
                marcar_copiado(str(origem))
                stats["copiados"] += 1
                stats["verificados"] += 1
                log_lines.append(f"[OK] {origem} → {destino}")
            else:
                # Hash divergiu — remove cópia corrompida
                destino.unlink(missing_ok=True)
                raise ValueError("Verificação falhou — cópia removida, original intacto")

        except Exception as e:
            marcar_erro(str(origem), str(e))
            stats["erros"] += 1
            log_lines.append(f"[ERRO] {origem} — {e}")

    _salvar_log(log_lines, dry_run)

    print(f"\n✅ Cópia concluída:")
    if dry_run:
        print(f"   Simulados        : {stats['simulados']:,}")
    else:
        print(f"   Copiados         : {stats['copiados']:,}")
        print(f"   Verificados (OK) : {stats['verificados']:,}")
        print(f"   Erros            : {stats['erros']:,}")

    print("\n⚠️  NENHUM ARQUIVO FOI DELETADO.")
    print("   Revise o HD de destino e exclua os originais manualmente.")

    return stats


def _salvar_log(linhas: list, dry_run: bool) -> None:
    pasta = Path("logs")
    pasta.mkdir(exist_ok=True)
    prefixo = "dry_run" if dry_run else "copia"
    nome    = f"{prefixo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    with open(pasta / nome, "w", encoding="utf-8") as f:
        f.write(f"Backup Organizer — {'Simulação' if dry_run else 'Cópia'}\n")
        f.write(f"Data: {datetime.now().isoformat()}\n")
        f.write("=" * 60 + "\n\n")
        f.write("\n".join(linhas))

    print(f"\n📄 Log salvo em: logs/{nome}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    executar_copia(dry_run=args.dry_run)
