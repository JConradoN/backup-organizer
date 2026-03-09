"""
purger.py
Apaga da ORIGEM todos os arquivos classificados como lixo.
Roda ANTES da cópia para liberar espaço e simplificar o processo.

Segurança:
- Dry run por padrão (--confirmar para apagar de verdade)
- Log completo de tudo que foi apagado
- Nunca apaga arquivos úteis ou ambíguos
"""

import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from tqdm import tqdm

from database import get_connection


def apagar_lixo(confirmar: bool = False) -> dict:
    with get_connection() as conn:
        arquivos = conn.execute(
            """SELECT caminho_original, nome, extensao, tamanho
               FROM files
               WHERE decisao = 'lixo'
               AND status = 'processado'"""
        ).fetchall()

    total = len(arquivos)

    if total == 0:
        print("Nenhum arquivo de lixo encontrado.")
        print("Execute a Fase 2 (classify) primeiro.")
        return {}

    tamanho_total = sum(a["tamanho"] or 0 for a in arquivos)
    print(f"\n{'='*55}")
    print(f"  PURGER — Limpeza de lixo da origem")
    print(f"{'='*55}")
    print(f"  Arquivos para apagar : {total:,}")
    print(f"  Espaço a liberar     : {tamanho_total / 1024**3:.2f} GB")
    print(f"  Modo                 : {'REAL — APAGANDO' if confirmar else 'SIMULAÇÃO (use --confirmar)'}")
    print(f"{'='*55}\n")

    if not confirmar:
        print("⚠️  Modo simulação. Nenhum arquivo será apagado.")
        print("    Use: python purger.py --confirmar\n")

    stats = {"apagados": 0, "nao_encontrados": 0, "erros": 0, "simulados": 0}
    log_linhas = []

    for arq in tqdm(arquivos, desc="Apagando lixo", unit="arq"):
        caminho = Path(arq["caminho_original"])

        if not confirmar:
            log_linhas.append(f"[SIMULADO] {caminho}")
            stats["simulados"] += 1
            continue

        try:
            if caminho.exists():
                os.remove(caminho)
                # Atualiza status no banco
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE files SET status='copiado', motivo='apagado_purger' WHERE caminho_original=?",
                        (str(caminho),)
                    )
                stats["apagados"] += 1
                log_linhas.append(f"[APAGADO] {caminho}")
            else:
                stats["nao_encontrados"] += 1
                log_linhas.append(f"[NÃO ENCONTRADO] {caminho}")

        except Exception as e:
            stats["erros"] += 1
            log_linhas.append(f"[ERRO] {caminho} — {e}")

    # Salva log
    pasta_logs = Path("logs")
    pasta_logs.mkdir(exist_ok=True)
    prefixo = "purge" if confirmar else "purge_dry"
    nome_log = f"{prefixo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    with open(pasta_logs / nome_log, "w", encoding="utf-8") as f:
        f.write(f"Backup Organizer — Purger\n")
        f.write(f"Data: {datetime.now().isoformat()}\n")
        f.write(f"Modo: {'REAL' if confirmar else 'SIMULAÇÃO'}\n")
        f.write("=" * 60 + "\n\n")
        f.write("\n".join(log_linhas))

    print(f"\n✅ Purge concluído:")
    if confirmar:
        print(f"   Apagados         : {stats['apagados']:,}")
        print(f"   Não encontrados  : {stats['nao_encontrados']:,}")
        print(f"   Erros            : {stats['erros']:,}")
        print(f"   Espaço liberado  : {tamanho_total / 1024**3:.2f} GB")
    else:
        print(f"   Seriam apagados  : {stats['simulados']:,}")
        print(f"   Espaço a liberar : {tamanho_total / 1024**3:.2f} GB")

    print(f"\n📄 Log salvo em: logs/{nome_log}")
    return stats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Purger — Apaga lixo da origem")
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Apaga de verdade. Sem esta flag, apenas simula."
    )
    args = parser.parse_args()
    apagar_lixo(confirmar=args.confirmar)
