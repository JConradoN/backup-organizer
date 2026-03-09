"""Runner unico para automatizar o pipeline operacional.

Perfis:
- daily: sanitizacao dry-run + indexacao incremental sem OCR
- nightly-ocr: indexacao OCR com checkpoint + auditoria duplicatas
- cleanup-apply: sanitizacao apply + reindex sem OCR

Por padrao roda em modo plano (sem executar) para seguranca.
Use --execute para de fato rodar.
"""

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
LOG_DIR = ROOT / "logs" / "automation"


def _run(cmd: Sequence[str], execute: bool, log_lines: list[str]) -> int:
    line = " ".join(cmd)
    print(f"-> {line}")
    log_lines.append(f"[{datetime.now().isoformat()}] CMD: {line}")
    if not execute:
        return 0

    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout)
        log_lines.append(proc.stdout)
    if proc.stderr:
        print(proc.stderr)
        log_lines.append(proc.stderr)
    log_lines.append(f"RC={proc.returncode}")
    return proc.returncode


def profile_daily(execute: bool, log_lines: list[str]) -> int:
    steps = [
        [str(PYTHON), "src/sanitizar_pre_indexacao.py", "--fonte", "F:/"],
        [
            str(PYTHON),
            "src/indexacao_texto.py",
            "--fonte",
            "F:/",
            "--job-id",
            "daily_sem_ocr",
            "--max-video-mb",
            "50",
        ],
    ]
    for s in steps:
        rc = _run(s, execute, log_lines)
        if rc != 0:
            return rc
    return 0


def profile_nightly_ocr(execute: bool, log_lines: list[str]) -> int:
    steps = [
        [
            str(PYTHON),
            "src/indexacao_texto.py",
            "--fonte",
            "F:/",
            "--ocr-imagens",
            "--job-id",
            "ocr_noturno",
            "--max-video-mb",
            "50",
        ],
        [str(PYTHON), "src/auditoria_duplicatas_amigavel.py"],
    ]
    for s in steps:
        rc = _run(s, execute, log_lines)
        if rc != 0:
            return rc
    return 0


def profile_cleanup_apply(execute: bool, log_lines: list[str]) -> int:
    steps = [
        [str(PYTHON), "src/sanitizar_pre_indexacao.py", "--fonte", "F:/", "--apply"],
        [
            str(PYTHON),
            "src/indexacao_texto.py",
            "--fonte",
            "F:/",
            "--job-id",
            "daily_sem_ocr",
            "--max-video-mb",
            "50",
        ],
    ]
    for s in steps:
        rc = _run(s, execute, log_lines)
        if rc != 0:
            return rc
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Automation runner para scripts operacionais")
    parser.add_argument(
        "--profile",
        required=True,
        choices=["daily", "nightly-ocr", "cleanup-apply"],
        help="Perfil de automacao",
    )
    parser.add_argument("--execute", action="store_true", help="Executa comandos. Sem isso, apenas mostra plano")
    args = parser.parse_args()

    if not PYTHON.exists():
        raise FileNotFoundError(f"Python da venv nao encontrado: {PYTHON}")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_lines: list[str] = []
    log_lines.append(f"Profile={args.profile} execute={args.execute}")

    if args.profile == "daily":
        rc = profile_daily(args.execute, log_lines)
    elif args.profile == "nightly-ocr":
        rc = profile_nightly_ocr(args.execute, log_lines)
    else:
        rc = profile_cleanup_apply(args.execute, log_lines)

    log_path = LOG_DIR / f"pipeline_{args.profile}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path.write_text("\n".join(log_lines), encoding="utf-8")

    print(f"\nLog: {log_path}")
    if rc == 0:
        print("Pipeline finalizado com sucesso.")
    else:
        print(f"Pipeline terminou com erro. RC={rc}")
        raise SystemExit(rc)


if __name__ == "__main__":
    main()
