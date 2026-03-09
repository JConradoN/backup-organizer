"""Entry point v2 enxuto.

Foco: executar somente o fluxo que se mostrou util e estavel.
- scan
- classify
- copy
- index (opcional)

Nao inclui scripts experimentais/diagnosticos.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Reusa os modulos maduros de src sem quebrar a versao atual.
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

load_dotenv(dotenv_path=ROOT / ".env")

from database import init_db, resumo  # noqa: E402
from scanner import scan  # noqa: E402
from classifier import classificar_todos  # noqa: E402
from mover import executar_copia  # noqa: E402
from indexacao_texto import indexar_texto  # noqa: E402


def print_resumo() -> None:
    rows = resumo()
    if not rows:
        print("Banco vazio.")
        return
    print("\nResumo do banco")
    print("-" * 48)
    for r in rows:
        print(f"decisao={r.get('decisao')} status={r.get('status')} total={r.get('total')}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Backup Organizer v2 (fluxo enxuto)")
    p.add_argument("--fonte", help="Diretorio de origem (ex: G:\\)")
    p.add_argument("--destino", help="Diretorio de destino (ex: F:\\)")
    p.add_argument("--dry-run", action="store_true", help="Simula sem copiar")

    p.add_argument("--skip-scan", action="store_true")
    p.add_argument("--skip-classify", action="store_true")
    p.add_argument("--skip-copy", action="store_true")

    p.add_argument("--indexar", action="store_true", help="Roda indexacao apos a copia")
    p.add_argument("--ocr", action="store_true", help="Ativa OCR na indexacao")
    p.add_argument("--max-video-mb", type=int, default=50)

    p.add_argument("--resumo", action="store_true", help="Mostra resumo e sai")
    return p


def main() -> None:
    args = build_parser().parse_args()

    init_db()

    if args.resumo:
        print_resumo()
        return

    if not args.fonte or not args.destino:
        print("Erro: --fonte e --destino sao obrigatorios (ou use --resumo)")
        raise SystemExit(1)

    started = datetime.now()
    print(f"Inicio: {started.isoformat(timespec='seconds')}")
    print(f"Fonte: {args.fonte}")
    print(f"Destino: {args.destino}")
    print(f"Dry-run: {args.dry_run}")

    if not args.skip_scan:
        print("\n[1/4] Scan")
        scan(args.fonte, dry_run=args.dry_run)

    if not args.skip_classify:
        print("\n[2/4] Classify")
        classificar_todos(args.destino, dry_run=args.dry_run)

    if not args.skip_copy:
        print("\n[3/4] Copy")
        executar_copia(dry_run=args.dry_run)

    if args.indexar:
        print("\n[4/4] Indexacao")
        indexar_texto(
            fonte=Path(args.destino),
            incluir_duplicatas=False,
            usar_ocr=args.ocr,
            max_video_mb=args.max_video_mb,
        )

    print("\nConcluido.")
    print_resumo()


if __name__ == "__main__":
    main()
