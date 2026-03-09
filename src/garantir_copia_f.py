r"""Garante consistencia no drive F por hash real (SHA-256).

Regra de negocio:
- Todo arquivo em F:\duplicatas_detectadas deve ter ao menos 1 copia valida fora
    dessa pasta em F: com o MESMO hash SHA-256.
- Se nao houver copia valida, o script cria uma copia de recuperacao em pasta
    equivalente (fotos/videos/musica/documentos/outros) no F:.

Este fluxo NAO depende de prefixo no nome, nem de tamanho aproximado.
Funciona para qualquer nome/tamanho de arquivo.

Modo padrao: simulacao
Modo real:    --apply
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import sqlite3
from collections import defaultdict
from pathlib import Path


F_BASE = Path("F:/")
F_DUP = F_BASE / "duplicatas_detectadas"
DB_PATH = Path("C:/Users/morph/dev-tools/backup-organizer/backup_organizer.db")
REPORT_PATH = Path("C:/Users/morph/dev-tools/backup-organizer/logs/garantia_f_hash_relatorio.csv")

HASH_PREFIX_RE = re.compile(r"^[0-9a-f]{10}$", re.IGNORECASE)


FOTOS_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
    ".heic", ".heif", ".webp", ".raw", ".cr2", ".nef", ".arw",
    ".ico", ".thm", ".icns", ".mpo", ".psd", ".ai", ".cdr", ".dwg",
}
VIDEOS_EXT = {
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".m4v", ".3gp",
    ".mpg", ".mpeg", ".ts", ".vob", ".lrv", ".mts", ".dav",
}
MUSICA_EXT = {
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus", ".amr",
}
DOC_EXT = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp", ".txt", ".rtf", ".csv", ".md", ".xml", ".json",
    ".sql", ".yaml", ".yml",
}


def _hash_sha256(path: Path) -> str | None:
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


def _is_in_dup(path: Path) -> bool:
    return "\\duplicatas_detectadas\\" in str(path).lower()


def _categoria_por_ext(ext: str) -> str:
    ext = ext.lower()
    if ext in FOTOS_EXT:
        return "fotos"
    if ext in VIDEOS_EXT:
        return "videos"
    if ext in MUSICA_EXT:
        return "musica"
    if ext in DOC_EXT:
        return "documentos"
    return "outros"


def _extrair_prefixo_e_nome(path: Path) -> tuple[str | None, str]:
    nome = path.name
    if "_" not in nome:
        return None, nome
    prefixo, resto = nome.split("_", 1)
    if HASH_PREFIX_RE.match(prefixo):
        return prefixo.lower(), resto
    return None, nome


def _escolher_destino_fallback(src_dup: Path, nome_sem_prefixo: str) -> Path:
    ext = src_dup.suffix.lower()
    categoria = _categoria_por_ext(ext)
    # Usa ano real por mtime para manter estrutura temporal.
    from datetime import datetime
    ano = str(datetime.fromtimestamp(src_dup.stat().st_mtime).year)
    return F_BASE / categoria / ano / nome_sem_prefixo


def _resolver_conflito_destino(destino: Path, source_hash: str | None) -> Path:
    if not destino.exists():
        return destino

    if source_hash:
        dest_hash = _hash_sha256(destino)
        if dest_hash == source_hash:
            return destino

    stem, suffix = destino.stem, destino.suffix
    i = 1
    while True:
        cand = destino.with_name(f"{stem}_recuperado_{i}{suffix}")
        if not cand.exists():
            return cand
        if source_hash:
            cand_hash = _hash_sha256(cand)
            if cand_hash == source_hash:
                return cand
        i += 1


def _indexar_arquivos_fora_duplicatas() -> dict[int, list[Path]]:
    """Indexa todos os arquivos em F: fora de duplicatas por tamanho."""
    by_size: dict[int, list[Path]] = defaultdict(list)
    total = 0
    for p in F_BASE.rglob("*"):
        if not p.is_file():
            continue
        if _is_in_dup(p):
            continue
        try:
            by_size[p.stat().st_size].append(p)
            total += 1
        except OSError:
            continue
    print(f"Indexacao externa concluida: {total} arquivos fora de duplicatas.")
    return by_size


def _encontrar_copias_exatas(
    hash_val: str,
    tamanho: int,
    outside_by_size: dict[int, list[Path]],
    outside_hash_cache: dict[Path, str | None],
) -> list[Path]:
    """Retorna caminhos em F: fora de duplicatas com hash exato igual."""
    candidatos = outside_by_size.get(tamanho, [])
    encontrados: list[Path] = []
    for c in candidatos:
        if c not in outside_hash_cache:
            outside_hash_cache[c] = _hash_sha256(c)
        if outside_hash_cache[c] == hash_val:
            encontrados.append(c)
    return encontrados


def _atualizar_banco_para_hash(cur: sqlite3.Cursor, hash_val: str, caminho_destino: str) -> None:
    """Atualiza um registro do hash para apontar para uma copia valida em F:."""
    cur.execute(
        """
        UPDATE files
        SET caminho_destino=?, status='copiado', motivo='recuperado_de_duplicatas_hash'
        WHERE id = (
            SELECT id FROM files
            WHERE hash_sha256 = ?
            ORDER BY id ASC
            LIMIT 1
        )
        """,
        (caminho_destino, hash_val),
    )


def garantir_copia_em_f(apply_changes: bool = False) -> None:
    if not F_DUP.exists():
        raise FileNotFoundError(f"Diretorio nao encontrado: {F_DUP}")
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Banco nao encontrado: {DB_PATH}")

    dup_files = [p for p in F_DUP.rglob("*") if p.is_file()]
    outside_by_size = _indexar_arquivos_fora_duplicatas()
    outside_hash_cache: dict[Path, str | None] = {}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Agrupa por hash REAL dos arquivos em duplicatas.
    groups_by_hash: dict[str, list[Path]] = defaultdict(list)
    sem_hash = 0
    for idx, p in enumerate(dup_files, start=1):
        h = _hash_sha256(p)
        if not h:
            sem_hash += 1
            continue
        groups_by_hash[h].append(p)
        if idx % 2000 == 0:
            print(f"Hash duplicatas calculado: {idx}/{len(dup_files)}")

    stats = {
        "arquivos_em_duplicatas": len(dup_files),
        "grupos_hash": len(groups_by_hash),
        "grupos_ja_ok": 0,
        "grupos_sem_copia": 0,
        "copias_criadas": 0,
        "sem_hash": sem_hash,
        "erros": 0,
    }

    relatorio_rows: list[dict[str, str]] = []

    for idx, (hash_val, arquivos_grupo) in enumerate(groups_by_hash.items(), start=1):
        src = arquivos_grupo[0]
        tamanho = src.stat().st_size

        candidatos_exatos = _encontrar_copias_exatas(
            hash_val=hash_val,
            tamanho=tamanho,
            outside_by_size=outside_by_size,
            outside_hash_cache=outside_hash_cache,
        )

        if candidatos_exatos:
            stats["grupos_ja_ok"] += 1
            relatorio_rows.append({
                "hash_sha256": hash_val,
                "arquivo_referencia_dup": str(src),
                "status": "ja_tinha_copia_exata",
                "copia_em_f": str(candidatos_exatos[0]),
            })
            continue

        stats["grupos_sem_copia"] += 1
        _, nome_sem_prefixo = _extrair_prefixo_e_nome(src)
        destino_base = _escolher_destino_fallback(src, nome_sem_prefixo)
        destino_final = _resolver_conflito_destino(destino_base, hash_val)

        try:
            if apply_changes:
                destino_final.parent.mkdir(parents=True, exist_ok=True)
                # Se ja existe e hash igual, nao precisa copiar novamente.
                if not destino_final.exists():
                    shutil.copy2(src, destino_final)
                _atualizar_banco_para_hash(cur, hash_val, str(destino_final))
                conn.commit()

                # Atualiza index/cache externos para grupos seguintes.
                try:
                    outside_by_size[destino_final.stat().st_size].append(destino_final)
                except OSError:
                    pass
                outside_hash_cache[destino_final] = hash_val

            stats["copias_criadas"] += 1
            relatorio_rows.append({
                "hash_sha256": hash_val,
                "arquivo_referencia_dup": str(src),
                "status": "copiado_para_fora" if apply_changes else "seria_copiado_para_fora",
                "copia_em_f": str(destino_final),
            })
        except Exception:
            stats["erros"] += 1
            relatorio_rows.append({
                "hash_sha256": hash_val,
                "arquivo_referencia_dup": str(src),
                "status": "erro",
                "copia_em_f": str(destino_final),
            })

        if idx % 500 == 0:
            print(f"Processados grupos: {idx}/{stats['grupos_hash']}")

    conn.close()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["hash_sha256", "arquivo_referencia_dup", "status", "copia_em_f"],
        )
        writer.writeheader()
        writer.writerows(relatorio_rows)

    print("=" * 60)
    print("Garantia de copia valida no F (fora de duplicatas_detectadas)")
    print("=" * 60)
    print(f"Arquivos em duplicatas_detectadas : {stats['arquivos_em_duplicatas']}")
    print(f"Grupos por hash SHA-256           : {stats['grupos_hash']}")
    print(f"Grupos ja OK                      : {stats['grupos_ja_ok']}")
    print(f"Grupos sem copia externa          : {stats['grupos_sem_copia']}")
    print(f"Copias criadas/planejadas         : {stats['copias_criadas']}")
    print(f"Arquivos sem hash legivel         : {stats['sem_hash']}")
    print(f"Erros                             : {stats['erros']}")
    print(f"Relatorio                         : {REPORT_PATH}")
    if not apply_changes:
        print("\nMODO SIMULACAO: nenhuma copia foi criada.")
        print("Use --apply para executar de verdade.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Garante copia valida no F para itens de duplicatas_detectadas")
    parser.add_argument("--apply", action="store_true", help="Aplica alteracoes reais (copia arquivos)")
    args = parser.parse_args()
    garantir_copia_em_f(apply_changes=args.apply)


if __name__ == "__main__":
    main()
