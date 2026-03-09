"""
Auditoria amigavel de duplicatas no F:\n
Gera um relatorio ligando cada arquivo em F:/duplicatas_detectadas a uma copia
equivalente fora dessa pasta, usando hash SHA-256 real (nao depende de nome).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


F_BASE = Path("F:/")
F_DUP = F_BASE / "duplicatas_detectadas"
OUT_CSV = Path("logs/relatorio_duplicatas_amigavel.csv")


def sha256_file(path: Path) -> str | None:
    sha = hashlib.sha256()
    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest()
    except OSError:
        return None


def indexar_fora_duplicatas() -> dict[int, list[Path]]:
    by_size: dict[int, list[Path]] = {}
    for p in F_BASE.rglob("*"):
        if not p.is_file():
            continue
        if "\\duplicatas_detectadas\\" in str(p).lower():
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        by_size.setdefault(size, []).append(p)
    return by_size


def main() -> None:
    parser = argparse.ArgumentParser(description="Audita duplicatas e acha copia equivalente fora da pasta duplicatas_detectadas")
    parser.add_argument("--somente-faltantes", action="store_true", help="Escreve no CSV apenas casos sem equivalente fora")
    args = parser.parse_args()

    if not F_DUP.exists():
        raise FileNotFoundError(f"Diretorio nao encontrado: {F_DUP}")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    print("Indexando arquivos fora de duplicatas...")
    by_size = indexar_fora_duplicatas()
    hash_cache: dict[Path, str | None] = {}

    arquivos_dup = [p for p in F_DUP.rglob("*") if p.is_file()]
    total = len(arquivos_dup)
    encontrados = 0
    faltantes = 0
    erros = 0

    rows: list[dict[str, str]] = []

    for i, dup in enumerate(arquivos_dup, start=1):
        try:
            size = dup.stat().st_size
            hdup = sha256_file(dup)
            if not hdup:
                erros += 1
                status = "erro_hash"
                match = ""
            else:
                candidates = by_size.get(size, [])
                match_path = ""
                for c in candidates:
                    if c not in hash_cache:
                        hash_cache[c] = sha256_file(c)
                    if hash_cache[c] == hdup:
                        match_path = str(c)
                        break

                if match_path:
                    encontrados += 1
                    status = "encontrada"
                    match = match_path
                else:
                    faltantes += 1
                    status = "nao_encontrada"
                    match = ""

            if (not args.somente_faltantes) or status == "nao_encontrada":
                rows.append(
                    {
                        "arquivo_duplicata": str(dup),
                        "hash_sha256": hdup or "",
                        "arquivo_equivalente_f": match,
                        "status": status,
                    }
                )

        except Exception:
            erros += 1
            if not args.somente_faltantes:
                rows.append(
                    {
                        "arquivo_duplicata": str(dup),
                        "hash_sha256": "",
                        "arquivo_equivalente_f": "",
                        "status": "erro",
                    }
                )

        if i % 2000 == 0:
            print(f"Processados: {i}/{total}")

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["arquivo_duplicata", "hash_sha256", "arquivo_equivalente_f", "status"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print("=" * 60)
    print("Auditoria amigavel concluida")
    print(f"Total em duplicatas_detectadas : {total}")
    print(f"Com equivalente fora           : {encontrados}")
    print(f"Sem equivalente fora           : {faltantes}")
    print(f"Erros                          : {erros}")
    print(f"CSV                            : {OUT_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    main()
