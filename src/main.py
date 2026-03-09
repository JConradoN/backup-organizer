"""
main.py
Ponto de entrada do Backup Organizer.
Orquestra as 3 fases: Scan → Classify → Copy.

Uso:
    python main.py --fonte D:\\ --destino E:\\ --dry-run
    python main.py --fonte D:\\ --destino E:\\
    python main.py --resumo
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

# Carrega .env ANTES de qualquer import local — garante DB_PATH correto
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from database import init_db, resumo, iniciar_run, finalizar_run
from scanner import scan
from classifier import classificar_todos
from mover import executar_copia


BANNER = """
╔══════════════════════════════════════════════╗
║       🗂️  BACKUP ORGANIZER v1.0              ║
║   Organização inteligente de HDs antigos     ║
║   Copy-First | Heurísticas | IA Local        ║
╚══════════════════════════════════════════════╝
"""


def exibir_resumo():
    """Exibe o estado atual do banco de dados."""
    print("\n📊 Resumo do banco de dados:\n")
    dados = resumo()
    if not dados:
        print("   Banco vazio — execute o scan primeiro.")
        return

    print(f"  {'DECISÃO':<12} {'STATUS':<14} {'TOTAL':>8}")
    print("  " + "-" * 36)
    for row in dados:
        decisao = row.get("decisao") or "—"
        status = row.get("status") or "—"
        total = row.get("total", 0)
        print(f"  {decisao:<12} {status:<14} {total:>8,}")


def main():
    print(BANNER)

    parser = argparse.ArgumentParser(
        description="Backup Organizer — Organização inteligente de HDs antigos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  Simulação completa:
    python main.py --fonte D:\\ --destino E:\\ --dry-run

  Execução real (scan + classify + copy):
    python main.py --fonte D:\\ --destino E:\\

  Só scan (fase 1):
    python main.py --fonte D:\\ --destino E:\\ --apenas-scan

  Ver progresso atual:
    python main.py --resumo
        """
    )

    parser.add_argument("--fonte",   help="HD de origem (ex: D:\\)")
    parser.add_argument("--destino", help="HD de destino (ex: E:\\)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula todas as operações sem mover arquivos")
    parser.add_argument("--apenas-scan", action="store_true",
                        help="Executa apenas a fase de varredura")
    parser.add_argument("--apenas-classify", action="store_true",
                        help="Executa apenas a fase de classificação")
    parser.add_argument("--apenas-copy", action="store_true",
                        help="Executa apenas a fase de cópia")
    parser.add_argument("--resumo", action="store_true",
                        help="Exibe resumo do banco e sai")

    args = parser.parse_args()

    # Resumo do banco
    if args.resumo:
        init_db()
        exibir_resumo()
        return

    # Valida argumentos obrigatórios
    if not args.fonte or not args.destino:
        parser.print_help()
        print("\n❌ Erro: --fonte e --destino são obrigatórios.")
        sys.exit(1)

    # Inicializa banco
    init_db()

    dry_run = args.dry_run
    inicio = datetime.now()

    if dry_run:
        print("⚠️  MODO DRY RUN — Nenhum arquivo será movido\n")

    print(f"📂 Fonte  : {args.fonte}")
    print(f"📂 Destino: {args.destino}")
    print(f"🕐 Início : {inicio.strftime('%d/%m/%Y %H:%M:%S')}\n")

    total = 0
    stats = {}

    # FASE 1 — Scan
    if not args.apenas_classify and not args.apenas_copy:
        print("=" * 50)
        print("FASE 1 — VARREDURA")
        print("=" * 50)
        total = scan(args.fonte, dry_run=dry_run)

    if args.apenas_scan:
        print("\n✅ Scan concluído. Use --apenas-classify para continuar.")
        return

    # FASE 2 — Classify
    if not args.apenas_copy:
        print("\n" + "=" * 50)
        print("FASE 2 — CLASSIFICAÇÃO")
        print("=" * 50)
        stats = classificar_todos(args.destino, dry_run=dry_run)

    if args.apenas_classify:
        print("\n✅ Classificação concluída. Use --apenas-copy para continuar.")
        return

    # FASE 3 — Copy
    print("\n" + "=" * 50)
    print("FASE 3 — CÓPIA (COPY-FIRST)")
    print("=" * 50)
    executar_copia(dry_run=dry_run)

    # Resumo final
    fim = datetime.now()
    duracao = fim - inicio
    print(f"\n{'='*50}")
    print(f"✅ PROCESSO CONCLUÍDO")
    print(f"   Duração: {str(duracao).split('.')[0]}")
    print(f"{'='*50}")
    exibir_resumo()


if __name__ == "__main__":
    main()
