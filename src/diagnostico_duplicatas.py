"""
Sincroniza caminhos de destino após higienização de nomes FileHistory.

Regras:
1. Percorre registros com status processado/copiado.
2. Remove sufixo de timestamp FileHistory de caminho_destino.
3. Se o caminho limpo existir no disco, atualiza caminho_destino e status='copiado'.
4. Para duplicatas com mesmo hash + mesmo caminho limpo, mantém 1 registro e marca os demais
   como 'duplicata_removida' (ou, se o schema não permitir esse status, registra em motivo).
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
import sys

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from database import get_connection, DB_PATH  # noqa: E402

PATTERN_FILEHISTORY = re.compile(r"\s\(\d{4}_\d{2}_\d{2}\s\d{2}_\d{2}_\d{2}\sUTC\)")


def limpar_nome_filehistory(nome_arquivo: str) -> str:
    return PATTERN_FILEHISTORY.sub("", nome_arquivo)


def limpar_caminho_destino(caminho_destino: str) -> str:
    p = Path(caminho_destino)
    return str(p.with_name(limpar_nome_filehistory(p.name)))


def status_permite_duplicata_removida(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='files'"
    ).fetchone()
    if not row or not row[0]:
        return False
    ddl = row[0]
    return "duplicata_removida" in ddl


def sincronizar(apply_changes: bool = False) -> None:
    print(f"[DB] Usando: {DB_PATH}")

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        permite_status_dup = status_permite_duplicata_removida(conn)

        rows = conn.execute(
            """
            SELECT id, status, hash_sha256, caminho_destino
            FROM files
            WHERE status IN ('processado', 'copiado')
              AND caminho_destino IS NOT NULL
            """
        ).fetchall()

        stats = {
            "avaliados": 0,
            "com_nome_alterado": 0,
            "caminho_limpo_existe": 0,
            "atualizados_para_copiado": 0,
            "duplicatas_marcadas": 0,
        }

        # 1) Sincroniza caminho_destino com nome limpo, quando o arquivo existe fisicamente.
        for row in rows:
            stats["avaliados"] += 1
            original = row["caminho_destino"]
            caminho_limpo = limpar_caminho_destino(original)

            if caminho_limpo == original:
                continue

            stats["com_nome_alterado"] += 1
            if Path(caminho_limpo).is_file():
                stats["caminho_limpo_existe"] += 1
                if apply_changes:
                    conn.execute(
                        "UPDATE files SET caminho_destino=?, status='copiado' WHERE id=?",
                        (caminho_limpo, row["id"]),
                    )
                stats["atualizados_para_copiado"] += 1

        # 2) Detecta duplicatas por (hash_sha256 + caminho_destino limpo já salvo no banco).
        dup_groups = conn.execute(
            """
            SELECT hash_sha256, caminho_destino, COUNT(*) AS qtd
            FROM files
            WHERE status IN ('processado', 'copiado')
              AND caminho_destino IS NOT NULL
              AND hash_sha256 IS NOT NULL
              AND hash_sha256 != 'sem_hash'
            GROUP BY hash_sha256, caminho_destino
            HAVING COUNT(*) > 1
            """
        ).fetchall()

        for group in dup_groups:
            regs = conn.execute(
                """
                SELECT id, status
                FROM files
                WHERE hash_sha256=?
                  AND caminho_destino=?
                  AND status IN ('processado', 'copiado')
                ORDER BY CASE WHEN status='copiado' THEN 0 ELSE 1 END, id ASC
                """,
                (group["hash_sha256"], group["caminho_destino"]),
            ).fetchall()

            # Mantém o primeiro, marca os demais como duplicata removida.
            for dup in regs[1:]:
                if apply_changes:
                    if permite_status_dup:
                        conn.execute(
                            "UPDATE files SET status='duplicata_removida', motivo='duplicata_removida' WHERE id=?",
                            (dup["id"],),
                        )
                    else:
                        conn.execute(
                            "UPDATE files SET motivo='duplicata_removida' WHERE id=?",
                            (dup["id"],),
                        )
                stats["duplicatas_marcadas"] += 1

        if apply_changes:
            conn.commit()

    print("=" * 60)
    print("Sincronizacao FileHistory -> Banco")
    print("=" * 60)
    print(f"Registros avaliados                : {stats['avaliados']}")
    print(f"Com sufixo FileHistory             : {stats['com_nome_alterado']}")
    print(f"Caminho limpo existente no disco   : {stats['caminho_limpo_existe']}")
    print(f"Atualizados para status 'copiado'  : {stats['atualizados_para_copiado']}")
    print(f"Duplicatas marcadas                : {stats['duplicatas_marcadas']}")

    if not apply_changes:
        print("\nMODO SIMULACAO: nenhuma alteracao foi gravada.")
        print("Use --apply para persistir no banco.")

    if apply_changes and not permite_status_dup:
        print("\nAviso: schema atual nao aceita status 'duplicata_removida'.")
        print("As duplicatas foram marcadas em motivo='duplicata_removida'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza caminho_destino apos higienizacao FileHistory")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica alteracoes no banco. Sem esta flag, roda em simulacao.",
    )
    args = parser.parse_args()
    sincronizar(apply_changes=args.apply)


if __name__ == "__main__":
    main()