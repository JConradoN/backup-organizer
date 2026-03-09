r"""
Indexacao de texto e busca full-text (FTS5).

Suporta:
- Texto plano (txt, md, csv, json, xml, codigo, logs)
- PDF (opcional, via pypdf)
- DOCX (opcional, via python-docx)
- OCR em imagens (opcional, via vision.py / EasyOCR)

Uso:
    python src/indexacao_texto.py --fonte F:/
    python src/indexacao_texto.py --fonte F:/ --ocr-imagens
    python src/indexacao_texto.py --buscar "conrado" --limite 30
    python src/indexacao_texto.py --buscar "nota fiscal" --ext .xml --pasta F:\projetos
    python src/indexacao_texto.py --buscar "silvana" --desde 2025-01-01 --ate 2026-12-31
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Iterable

from database import get_connection, DB_PATH

PROGRESS_INTERVAL_SEC = 30.0
_JOB_LOCK_HANDLE = None


TEXT_EXTS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm", ".log",
    ".py", ".js", ".ts", ".css", ".sql", ".yaml", ".yml", ".ini",
}

PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".heic"}
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".m4v", ".3gp", ".mpg", ".mpeg", ".ts"}

# Reusa a instancia de OCR no processo inteiro para evitar reinit por arquivo.
_VISION_PROCESSOR = None
_VISION_UNAVAILABLE = False


def _acquire_job_lock(job_id: str) -> bool:
    """Evita duas execucoes simultaneas do mesmo job_id no mesmo host."""
    global _JOB_LOCK_HANDLE

    lock_dir = Path("logs") / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"indexacao_{job_id}.lock"

    fh = lock_path.open("a+b")
    try:
        try:
            import msvcrt  # Windows
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        except ImportError:
            import fcntl  # type: ignore
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        fh.close()
        return False

    _JOB_LOCK_HANDLE = fh
    return True


def _try_import_pdf():
    try:
        from pypdf import PdfReader
        return PdfReader
    except Exception:
        return None


def _try_import_docx():
    try:
        from docx import Document
        return Document
    except Exception:
        return None


def init_text_index_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS text_index (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            caminho       TEXT NOT NULL UNIQUE,
            caminho_original_ref TEXT,
            extensao      TEXT,
            tamanho       INTEGER,
            mtime         REAL,
            origem_texto  TEXT,
            resumo_curto  TEXT,
            resumo_modelo TEXT,
            resumo_em     TEXT,
            conteudo      TEXT,
            atualizado_em TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS text_index_fts USING fts5(
            conteudo,
            caminho UNINDEXED,
            content='text_index',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS text_index_ai AFTER INSERT ON text_index BEGIN
            INSERT INTO text_index_fts(rowid, conteudo, caminho)
            VALUES (new.id, new.conteudo, new.caminho);
        END;

        CREATE TRIGGER IF NOT EXISTS text_index_ad AFTER DELETE ON text_index BEGIN
            INSERT INTO text_index_fts(text_index_fts, rowid, conteudo, caminho)
            VALUES('delete', old.id, old.conteudo, old.caminho);
        END;

        CREATE TRIGGER IF NOT EXISTS text_index_au AFTER UPDATE ON text_index BEGIN
            INSERT INTO text_index_fts(text_index_fts, rowid, conteudo, caminho)
            VALUES('delete', old.id, old.conteudo, old.caminho);
            INSERT INTO text_index_fts(rowid, conteudo, caminho)
            VALUES (new.id, new.conteudo, new.caminho);
        END;

        CREATE TABLE IF NOT EXISTS text_index_jobs (
            job_id             TEXT PRIMARY KEY,
            fonte              TEXT,
            incluir_duplicatas INTEGER,
            usar_ocr           INTEGER,
            max_video_mb       INTEGER,
            max_image_mb       INTEGER,
            last_path_norm     TEXT,
            processed_count    INTEGER DEFAULT 0,
            total_count        INTEGER DEFAULT 0,
            status             TEXT DEFAULT 'idle',
            updated_em         TEXT
        );
        """
    )
    conn.commit()

    # Migra schema antigo sem a coluna origem_texto.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(text_index)").fetchall()]
    if "caminho_original_ref" not in cols:
        conn.execute("ALTER TABLE text_index ADD COLUMN caminho_original_ref TEXT")
        conn.commit()
    if "origem_texto" not in cols:
        conn.execute("ALTER TABLE text_index ADD COLUMN origem_texto TEXT")
        conn.commit()
    if "resumo_curto" not in cols:
        conn.execute("ALTER TABLE text_index ADD COLUMN resumo_curto TEXT")
        conn.commit()
    if "resumo_modelo" not in cols:
        conn.execute("ALTER TABLE text_index ADD COLUMN resumo_modelo TEXT")
        conn.commit()
    if "resumo_em" not in cols:
        conn.execute("ALTER TABLE text_index ADD COLUMN resumo_em TEXT")
        conn.commit()

    job_cols = [r[1] for r in conn.execute("PRAGMA table_info(text_index_jobs)").fetchall()]
    if "max_image_mb" not in job_cols:
        conn.execute("ALTER TABLE text_index_jobs ADD COLUMN max_image_mb INTEGER")
        conn.commit()


def _norm_path(s: str) -> str:
    # Normaliza para lookup no Windows sem depender de path existir no momento.
    return s.replace("/", "\\").lower()


def map_destino_para_origem(conn: sqlite3.Connection) -> dict[str, str]:
    """Cria mapa caminho_destino (F:) -> caminho_original (G:) a partir da tabela files."""
    rows = conn.execute(
        """
        SELECT caminho_destino, caminho_original, status, id
        FROM files
        WHERE caminho_destino IS NOT NULL
          AND caminho_original IS NOT NULL
        ORDER BY CASE WHEN status='copiado' THEN 0 WHEN status='processado' THEN 1 ELSE 2 END,
                 id DESC
        """
    ).fetchall()

    result: dict[str, str] = {}
    for r in rows:
        key = _norm_path(r["caminho_destino"])
        # Mantem o primeiro registro encontrado (ja ordenado por prioridade).
        if key not in result:
            result[key] = r["caminho_original"]
    return result


def ler_texto(path: Path, max_chars: int = 200_000) -> str | None:
    try:
        data = path.read_text(encoding="utf-8", errors="ignore")
        if len(data) > max_chars:
            return data[:max_chars]
        return data
    except OSError:
        return None


def ler_pdf(path: Path, max_chars: int = 200_000) -> str | None:
    PdfReader = _try_import_pdf()
    if PdfReader is None:
        return None
    try:
        reader = PdfReader(str(path))
        chunks: list[str] = []
        total = 0
        for page in reader.pages:
            txt = page.extract_text() or ""
            if not txt:
                continue
            chunks.append(txt)
            total += len(txt)
            if total >= max_chars:
                break
        data = "\n".join(chunks)
        return data[:max_chars] if data else None
    except Exception:
        return None


def ler_docx(path: Path, max_chars: int = 200_000) -> str | None:
    Document = _try_import_docx()
    if Document is None:
        return None
    try:
        doc = Document(str(path))
        parts: list[str] = []
        total = 0
        for p in doc.paragraphs:
            txt = (p.text or "").strip()
            if not txt:
                continue
            parts.append(txt)
            total += len(txt)
            if total >= max_chars:
                break
        data = "\n".join(parts)
        return data[:max_chars] if data else None
    except Exception:
        return None


def ler_ocr_imagem(path: Path, max_chars: int = 200_000) -> str | None:
    global _VISION_PROCESSOR, _VISION_UNAVAILABLE

    if _VISION_UNAVAILABLE:
        return None

    try:
        if _VISION_PROCESSOR is None:
            try:
                from vision import VisionProcessor
                _VISION_PROCESSOR = VisionProcessor(profile=os.getenv("OCR_PROFILE", "stable"))
            except Exception:
                _VISION_UNAVAILABLE = True
                return None

        txt = _VISION_PROCESSOR.ler_imagem(str(path))
        if not txt:
            return None
        return txt[:max_chars]
    except Exception:
        # Falha pontual de arquivo nao deve desligar OCR do job inteiro.
        return None


def extrair_texto(path: Path, usar_ocr: bool, max_image_mb: int) -> tuple[str | None, str]:
    ext = path.suffix.lower()
    if ext in TEXT_EXTS:
        return ler_texto(path), "texto"
    if ext in PDF_EXTS:
        return ler_pdf(path), "pdf"
    if ext in DOCX_EXTS:
        return ler_docx(path), "docx"
    if usar_ocr and ext in IMG_EXTS:
        if max_image_mb > 0:
            try:
                if path.stat().st_size > (max_image_mb * 1024 * 1024):
                    return None, "ignorado"
            except OSError:
                return None, "ignorado"
        return ler_ocr_imagem(path), "ocr"
    return None, "ignorado"


def iter_text_files(
    root: Path,
    incluir_duplicatas: bool,
    usar_ocr: bool,
    max_video_mb: int,
) -> Iterable[Path]:
    valid_exts = set(TEXT_EXTS) | set(PDF_EXTS) | set(DOCX_EXTS)
    if usar_ocr:
        valid_exts |= set(IMG_EXTS)

    max_video_bytes = max_video_mb * 1024 * 1024

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        p_lower = str(p).lower()
        if "\\quarentena_lixo_internet\\" in p_lower:
            continue
        if (not incluir_duplicatas) and "\\duplicatas_detectadas\\" in p_lower:
            continue

        # Videos grandes entram como METADADOS apenas (sem OCR/conteudo pesado).
        ext = p.suffix.lower()
        if ext in VIDEO_EXTS:
            try:
                if p.stat().st_size > max_video_bytes:
                    yield p
                    continue
            except OSError:
                continue

        if ext in valid_exts:
            yield p


def _metadata_doc(path: Path, st) -> str:
    return (
        f"nome:{path.name}\n"
        f"stem:{path.stem}\n"
        f"ext:{path.suffix.lower()}\n"
        f"pasta:{path.parent}\n"
        f"caminho:{path}\n"
        f"tamanho_bytes:{st.st_size}\n"
        f"mtime:{datetime.fromtimestamp(st.st_mtime).isoformat()}"
    )


def _fmt_seconds(total_seconds: float) -> str:
    if total_seconds < 0:
        total_seconds = 0
    s = int(total_seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _compact_summary(text: str, max_len: int = 220) -> str:
    one_line = " ".join((text or "").split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 3].rstrip() + "..."


def _build_summary_prompt(path: Path, origem: str, texto: str) -> str:
    trecho = (texto or "")[:1800]
    return (
        "Voce gera uma descricao curta de arquivo em portugues-BR. "
        "Regras: responda em uma unica frase, objetiva, sem inventar fatos, "
        "sem nomes de pessoas se nao estiver explicitamente no conteudo, "
        "maximo 220 caracteres.\n"
        f"Arquivo: {path.name}\n"
        f"Extensao: {path.suffix.lower()}\n"
        f"Origem do texto: {origem}\n"
        f"Conteudo extraido:\n{trecho}\n\n"
        "Resposta:"
    )


def gerar_resumo_ollama(
    path: Path,
    origem: str,
    texto: str,
    model: str,
    base_url: str,
    timeout_sec: float,
) -> str | None:
    prompt = _build_summary_prompt(path, origem, texto)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    req = urllib.request.Request(
        url=base_url.rstrip("/") + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        body = json.loads(raw)
        resposta = str(body.get("response") or "").strip()
        if not resposta:
            return None
        return _compact_summary(resposta)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def gerar_resumo_fallback(path: Path, origem: str, texto: str) -> str:
    snippet = _compact_summary(texto or "", max_len=160)
    ext = (path.suffix or "").lower()
    if not snippet:
        return f"Arquivo {path.name} ({ext or 'sem extensao'}) indexado via {origem}."
    return _compact_summary(
        f"Arquivo {path.name} ({ext or 'sem extensao'}) com conteudo identificado via {origem}: {snippet}",
        max_len=220,
    )


def gerar_resumo_curto(
    path: Path,
    origem: str,
    texto: str,
    model: str,
    base_url: str,
    timeout_sec: float,
    usar_fallback: bool,
) -> tuple[str | None, str]:
    resumo_ollama = gerar_resumo_ollama(
        path=path,
        origem=origem,
        texto=texto,
        model=model,
        base_url=base_url,
        timeout_sec=timeout_sec,
    )
    if resumo_ollama:
        return resumo_ollama, "ollama"

    if usar_fallback:
        return gerar_resumo_fallback(path, origem, texto), "fallback"

    return None, "none"


def _print_progress(
    prefix: str,
    done: int,
    total: int,
    elapsed: float,
    done_for_rate: int | None = None,
) -> None:
    if total <= 0:
        print(f"{prefix} | itens: 0 | decorrido: {_fmt_seconds(elapsed)}")
        return

    # Em retomada, "done" inclui itens ja processados em execucoes anteriores.
    # Para taxa/ETA corretos, use apenas o que foi processado nesta execucao.
    done_rate = done if done_for_rate is None else done_for_rate
    rate = (done_rate / elapsed) if elapsed > 0 else 0.0
    restante = max(total - done, 0)
    eta = (restante / rate) if rate > 0 else 0.0
    pct = (done / total) * 100
    print(
        f"{prefix} | {done}/{total} ({pct:.1f}%) | "
        f"taxa: {rate:.1f} arq/s | decorrido: {_fmt_seconds(elapsed)} | "
        f"ETA: {_fmt_seconds(eta)}"
    )


def _get_job_state(conn: sqlite3.Connection, job_id: str):
    return conn.execute(
        "SELECT * FROM text_index_jobs WHERE job_id=?",
        (job_id,),
    ).fetchone()


def _reset_job_state(conn: sqlite3.Connection, job_id: str) -> None:
    conn.execute("DELETE FROM text_index_jobs WHERE job_id=?", (job_id,))
    conn.commit()


def _save_job_state(
    conn: sqlite3.Connection,
    job_id: str,
    fonte: str,
    incluir_duplicatas: bool,
    usar_ocr: bool,
    max_video_mb: int,
    max_image_mb: int,
    last_path_norm: str | None,
    processed_count: int,
    total_count: int,
    status: str,
) -> None:
    conn.execute(
        """
        INSERT INTO text_index_jobs (
            job_id, fonte, incluir_duplicatas, usar_ocr, max_video_mb,
            max_image_mb, last_path_norm, processed_count, total_count, status, updated_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            fonte=excluded.fonte,
            incluir_duplicatas=excluded.incluir_duplicatas,
            usar_ocr=excluded.usar_ocr,
            max_video_mb=excluded.max_video_mb,
            max_image_mb=excluded.max_image_mb,
            last_path_norm=excluded.last_path_norm,
            processed_count=excluded.processed_count,
            total_count=excluded.total_count,
            status=excluded.status,
            updated_em=excluded.updated_em
        """,
        (
            job_id,
            fonte,
            int(incluir_duplicatas),
            int(usar_ocr),
            int(max_video_mb),
            int(max_image_mb),
            last_path_norm,
            int(processed_count),
            int(total_count),
            status,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()


def indexar_texto(
    fonte: Path,
    incluir_duplicatas: bool = False,
    usar_ocr: bool = False,
    max_video_mb: int = 50,
    max_image_mb: int = 15,
    job_id: str = "default",
    resume: bool = True,
    reset_job: bool = False,
    batch_size: int = 0,
    batch_number: int = 1,
    gerar_resumo: bool = False,
    resumo_modelo: str = "llama3.1:8b-instruct",
    ollama_url: str = "http://127.0.0.1:11434",
    resumo_timeout_sec: float = 12.0,
    resumo_fallback: bool = True,
) -> None:
    if not _acquire_job_lock(job_id):
        print(f"Job '{job_id}' ja esta em execucao em outro processo. Encerrando instancia duplicada.")
        return

    scan_start_ts = time.perf_counter()
    candidates = list(iter_text_files(fonte, incluir_duplicatas, usar_ocr, max_video_mb))
    candidates.sort(key=lambda p: _norm_path(str(p)))
    scan_elapsed = time.perf_counter() - scan_start_ts
    print(f"Candidatos descobertos: {len(candidates)}")
    print(f"Fase descoberta concluida em: {_fmt_seconds(scan_elapsed)}")

    with get_connection() as conn:
        init_text_index_db(conn)
        conn.row_factory = sqlite3.Row

        if reset_job:
            _reset_job_state(conn, job_id)

        enable_checkpoint = batch_size <= 0
        processed_offset = 0
        total_planejado = len(candidates)

        if enable_checkpoint and resume:
            state = _get_job_state(conn, job_id)
            if state:
                cfg_match = (
                    (state["fonte"] == str(fonte))
                    and (int(state["incluir_duplicatas"] or 0) == int(incluir_duplicatas))
                    and (int(state["usar_ocr"] or 0) == int(usar_ocr))
                    and (int(state["max_video_mb"] or 0) == int(max_video_mb))
                    and (int(state["max_image_mb"] or 0) == int(max_image_mb))
                )
                if cfg_match and state["last_path_norm"]:
                    processed_offset = int(state["processed_count"] or 0)
                    last_path = str(state["last_path_norm"])
                    candidates = [p for p in candidates if _norm_path(str(p)) > last_path]
                    total_planejado = int(state["total_count"] or len(candidates) + processed_offset)
                    print(f"Retomada ativa (job={job_id}) | ja processados: {processed_offset}")
                elif cfg_match and str(state["status"] or "") == "done":
                    print(f"Job '{job_id}' ja concluido anteriormente. Nada a fazer.")
                    return
                elif not cfg_match:
                    print("Checkpoint encontrado com configuracao diferente; iniciando do zero para este job.")

        if batch_size > 0:
            total_batches = max(1, math.ceil(len(candidates) / batch_size))
            if batch_number < 1 or batch_number > total_batches:
                raise ValueError(f"--batch-number invalido. Use 1..{total_batches}")
            start = (batch_number - 1) * batch_size
            end = min(len(candidates), start + batch_size)
            print(f"Modo lote: lote {batch_number}/{total_batches} | faixa {start}:{end}")
            candidates = candidates[start:end]
            total_planejado = len(candidates)

        origem_map = map_destino_para_origem(conn)

        existentes = {
            r["caminho"]: (
                r["tamanho"],
                r["mtime"],
                r["origem_texto"],
                r["caminho_original_ref"],
                r["resumo_curto"],
            )
            for r in conn.execute(
                "SELECT caminho, tamanho, mtime, origem_texto, caminho_original_ref, resumo_curto FROM text_index"
            )
        }

        total = total_planejado
        novos = 0
        atualizados = 0
        ignorados = 0
        erros = 0
        sem_suporte = 0
        por_origem = {"texto": 0, "pdf": 0, "docx": 0, "ocr": 0, "metadata": 0, "ignorado": 0}
        resumo_stats = {"ollama": 0, "fallback": 0, "none": 0}

        max_video_bytes = max_video_mb * 1024 * 1024
        start_ts = time.perf_counter()
        last_progress_ts = start_ts

        for i, p in enumerate(candidates, start=1):
            try:
                st = p.stat()
                key = str(p)
                origem_ref = origem_map.get(_norm_path(key))
                old = existentes.get(key)

                # Skip rapido: mesmo tamanho e mesmo mtime
                if old and old[0] == st.st_size and abs((old[1] or 0) - st.st_mtime) < 0.001:
                    # Backfill origem_texto when old rows predate schema migration.
                    if not old[2]:
                        origem_guess = "texto"
                        if p.suffix.lower() in PDF_EXTS:
                            origem_guess = "pdf"
                        elif p.suffix.lower() in DOCX_EXTS:
                            origem_guess = "docx"
                        elif usar_ocr and p.suffix.lower() in IMG_EXTS:
                            origem_guess = "ocr"

                        conn.execute(
                            "UPDATE text_index SET origem_texto=?, caminho_original_ref=?, atualizado_em=? WHERE caminho=?",
                            (origem_guess, origem_ref, datetime.now().isoformat(), key),
                        )
                        atualizados += 1
                    elif origem_ref and (not old[3]):
                        conn.execute(
                            "UPDATE text_index SET caminho_original_ref=?, atualizado_em=? WHERE caminho=?",
                            (origem_ref, datetime.now().isoformat(), key),
                        )
                        atualizados += 1
                    elif gerar_resumo and (not old[4]):
                        txt_exist = conn.execute(
                            "SELECT conteudo, origem_texto FROM text_index WHERE caminho=?",
                            (key,),
                        ).fetchone()
                        if txt_exist:
                            conteudo_exist = str(txt_exist["conteudo"] or "")
                            origem_exist = str(txt_exist["origem_texto"] or "texto")
                            resumo, resumo_src = gerar_resumo_curto(
                                path=p,
                                origem=origem_exist,
                                texto=conteudo_exist,
                                model=resumo_modelo,
                                base_url=ollama_url,
                                timeout_sec=resumo_timeout_sec,
                                usar_fallback=resumo_fallback,
                            )
                            resumo_stats[resumo_src] = resumo_stats.get(resumo_src, 0) + 1
                            if resumo:
                                conn.execute(
                                    "UPDATE text_index SET resumo_curto=?, resumo_modelo=?, resumo_em=?, atualizado_em=? WHERE caminho=?",
                                    (
                                        resumo,
                                        resumo_modelo if resumo_src == "ollama" else "fallback",
                                        datetime.now().isoformat(),
                                        datetime.now().isoformat(),
                                        key,
                                    ),
                                )
                                atualizados += 1
                    else:
                        ignorados += 1
                    continue

                ext = p.suffix.lower()

                # Arquivo acima do limite (video) -> indexa metadados somente.
                if ext in VIDEO_EXTS and st.st_size > max_video_bytes:
                    txt = _metadata_doc(p, st)
                    origem = "metadata"
                else:
                    txt, origem = extrair_texto(p, usar_ocr, max_image_mb)

                por_origem[origem] = por_origem.get(origem, 0) + 1
                if txt is None:
                    sem_suporte += 1
                    continue

                resumo = None
                if gerar_resumo:
                    resumo, resumo_src = gerar_resumo_curto(
                        path=p,
                        origem=origem,
                        texto=txt,
                        model=resumo_modelo,
                        base_url=ollama_url,
                        timeout_sec=resumo_timeout_sec,
                        usar_fallback=resumo_fallback,
                    )
                    resumo_stats[resumo_src] = resumo_stats.get(resumo_src, 0) + 1

                now = datetime.now().isoformat()
                if old:
                    conn.execute(
                        """
                        UPDATE text_index
                        SET caminho_original_ref=?, extensao=?, tamanho=?, mtime=?, origem_texto=?,
                            resumo_curto=?, resumo_modelo=?, resumo_em=?, conteudo=?, atualizado_em=?
                        WHERE caminho=?
                        """,
                        (
                            origem_ref,
                            p.suffix.lower(),
                            st.st_size,
                            st.st_mtime,
                            origem,
                            resumo,
                            resumo_modelo if resumo_src == "ollama" else ("fallback" if resumo else None),
                            now if resumo else None,
                            txt,
                            now,
                            key,
                        ),
                    )
                    atualizados += 1
                else:
                    conn.execute(
                        """
                        INSERT INTO text_index (
                            caminho, caminho_original_ref, extensao, tamanho, mtime, origem_texto,
                            resumo_curto, resumo_modelo, resumo_em, conteudo, atualizado_em
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            key,
                            origem_ref,
                            p.suffix.lower(),
                            st.st_size,
                            st.st_mtime,
                            origem,
                            resumo,
                            resumo_modelo if resumo_src == "ollama" else ("fallback" if resumo else None),
                            now if resumo else None,
                            txt,
                            now,
                        ),
                    )
                    novos += 1

            except Exception:
                erros += 1

            now = time.perf_counter()
            if (now - last_progress_ts) >= PROGRESS_INTERVAL_SEC or i == len(candidates):
                conn.commit()
                elapsed = now - start_ts
                done_global = processed_offset + i
                _print_progress(
                    "Fase indexacao",
                    done_global,
                    total,
                    elapsed,
                    done_for_rate=i,
                )

                if enable_checkpoint:
                    _save_job_state(
                        conn=conn,
                        job_id=job_id,
                        fonte=str(fonte),
                        incluir_duplicatas=incluir_duplicatas,
                        usar_ocr=usar_ocr,
                        max_video_mb=max_video_mb,
                        max_image_mb=max_image_mb,
                        last_path_norm=_norm_path(str(p)),
                        processed_count=done_global,
                        total_count=total,
                        status="running",
                    )
                last_progress_ts = now

        conn.commit()

        if enable_checkpoint:
            _save_job_state(
                conn=conn,
                job_id=job_id,
                fonte=str(fonte),
                incluir_duplicatas=incluir_duplicatas,
                usar_ocr=usar_ocr,
                max_video_mb=max_video_mb,
                max_image_mb=max_image_mb,
                last_path_norm=None,
                processed_count=total,
                total_count=total,
                status="done",
            )

    print("=" * 60)
    print("Indexacao de texto concluida")
    print(f"Fonte                 : {fonte}")
    print(f"OCR imagens           : {'ON' if usar_ocr else 'OFF'}")
    print(f"Video max (MB)        : {max_video_mb}")
    print(f"Imagem max OCR (MB)   : {max_image_mb}")
    print(f"Job ID                : {job_id}")
    print(f"Resume                : {'ON' if resume else 'OFF'}")
    print(f"Resumo via Ollama     : {'ON' if gerar_resumo else 'OFF'}")
    if gerar_resumo:
        print(f"Modelo resumo         : {resumo_modelo} @ {ollama_url}")
        print(
            "Resumos gerados       : "
            f"ollama={resumo_stats['ollama']} fallback={resumo_stats['fallback']} sem_resumo={resumo_stats['none']}"
        )
    if batch_size > 0:
        print(f"Batch                 : {batch_number} (size={batch_size})")
    print(f"Total varrido         : {total}")
    print(f"Novos                 : {novos}")
    print(f"Atualizados           : {atualizados}")
    print(f"Ignorados             : {ignorados}")
    print(f"Sem suporte/sem texto : {sem_suporte}")
    print(f"Erros                 : {erros}")
    print(
        "Origem texto          : "
        f"texto={por_origem['texto']} pdf={por_origem['pdf']} "
        f"docx={por_origem['docx']} ocr={por_origem['ocr']} metadata={por_origem['metadata']}"
    )
    print(f"Banco                 : {DB_PATH}")
    print("Dependencias opcionais: pypdf (PDF), python-docx (DOCX)")
    print("=" * 60)


def _date_to_timestamp(date_str: str | None, end_of_day: bool) -> float | None:
    if not date_str:
        return None
    try:
        if end_of_day:
            dt = datetime.strptime(date_str + " 23:59:59", "%Y-%m-%d %H:%M:%S")
        else:
            dt = datetime.strptime(date_str + " 00:00:00", "%Y-%m-%d %H:%M:%S")
        return dt.timestamp()
    except ValueError:
        raise ValueError("Use formato de data YYYY-MM-DD para --desde/--ate")


def buscar_texto(
    termo: str,
    limite: int = 30,
    pasta: str | None = None,
    ext: str | None = None,
    desde: str | None = None,
    ate: str | None = None,
) -> None:
    with get_connection() as conn:
        init_text_index_db(conn)
        conn.row_factory = sqlite3.Row

        sql = (
            "SELECT t.caminho, t.caminho_original_ref, t.extensao, t.origem_texto, t.resumo_curto, "
            "snippet(text_index_fts, 0, '[', ']', ' ... ', 12) AS trecho, "
            "t.atualizado_em "
            "FROM text_index_fts f "
            "JOIN text_index t ON t.id = f.rowid "
            "WHERE text_index_fts MATCH ?"
        )
        params: list[object] = [termo]

        if pasta:
            sql += " AND lower(t.caminho) LIKE ?"
            params.append(f"{pasta.lower()}%")

        if ext:
            ext_norm = ext.lower()
            if not ext_norm.startswith("."):
                ext_norm = "." + ext_norm
            sql += " AND t.extensao = ?"
            params.append(ext_norm)

        ts_from = _date_to_timestamp(desde, end_of_day=False)
        if ts_from is not None:
            sql += " AND t.mtime >= ?"
            params.append(ts_from)

        ts_to = _date_to_timestamp(ate, end_of_day=True)
        if ts_to is not None:
            sql += " AND t.mtime <= ?"
            params.append(ts_to)

        sql += " LIMIT ?"
        params.append(limite)

        rows = conn.execute(sql, params).fetchall()

    print(f"\nBusca por: {termo}")
    print("=" * 60)
    if not rows:
        print("Nenhum resultado.")
        return
    for r in rows:
        print(f"Arquivo : {r['caminho']}")
        print(f"Origem  : {r['caminho_original_ref'] or '(nao mapeado)'}")
        print(f"Ext     : {r['extensao']} | Origem: {r['origem_texto']}")
        if r["resumo_curto"]:
            print(f"Resumo  : {r['resumo_curto']}")
        print(f"Trecho  : {r['trecho']}")
        print(f"Indexado: {r['atualizado_em']}")
        print("-" * 60)


def backfill_resumos(
    limite: int,
    resumo_modelo: str,
    ollama_url: str,
    resumo_timeout_sec: float,
    resumo_fallback: bool,
) -> None:
    with get_connection() as conn:
        init_text_index_db(conn)
        conn.row_factory = sqlite3.Row

        sql = (
            "SELECT id, caminho, origem_texto, conteudo "
            "FROM text_index "
            "WHERE COALESCE(TRIM(resumo_curto), '') = '' "
            "AND COALESCE(TRIM(conteudo), '') <> '' "
            "ORDER BY id"
        )
        params: list[object] = []
        if limite > 0:
            sql += " LIMIT ?"
            params.append(limite)

        rows = conn.execute(sql, params).fetchall()
        total = len(rows)
        if total == 0:
            print("Nenhum registro pendente de resumo.")
            return

        stats = {"ollama": 0, "fallback": 0, "none": 0}
        start_ts = time.perf_counter()
        print(f"Backfill de resumos iniciado | pendentes: {total}")
        for i, r in enumerate(rows, start=1):
            p = Path(str(r["caminho"]))
            origem = str(r["origem_texto"] or "texto")
            conteudo = str(r["conteudo"] or "")
            resumo, src = gerar_resumo_curto(
                path=p,
                origem=origem,
                texto=conteudo,
                model=resumo_modelo,
                base_url=ollama_url,
                timeout_sec=resumo_timeout_sec,
                usar_fallback=resumo_fallback,
            )
            stats[src] = stats.get(src, 0) + 1

            if resumo:
                now = datetime.now().isoformat()
                conn.execute(
                    "UPDATE text_index SET resumo_curto=?, resumo_modelo=?, resumo_em=?, atualizado_em=? WHERE id=?",
                    (
                        resumo,
                        resumo_modelo if src == "ollama" else "fallback",
                        now,
                        now,
                        int(r["id"]),
                    ),
                )

            if i % 200 == 0 or i == total:
                conn.commit()
                elapsed = time.perf_counter() - start_ts
                _print_progress("Backfill resumo", i, total, elapsed)

    print("=" * 60)
    print("Backfill de resumos concluido")
    print(f"Total avaliado         : {total}")
    print(f"Resumos via Ollama     : {stats['ollama']}")
    print(f"Resumos via fallback   : {stats['fallback']}")
    print(f"Sem resumo             : {stats['none']}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexacao e busca textual (FTS5)")
    parser.add_argument("--fonte", default="F:/", help="Diretorio raiz para indexar")
    parser.add_argument("--incluir-duplicatas", action="store_true", help="Inclui F:/duplicatas_detectadas na indexacao")
    parser.add_argument("--ocr-imagens", action="store_true", help="Executa OCR para imagens suportadas durante a indexacao")
    parser.add_argument(
        "--ocr-profile",
        choices=["stable", "balanced", "throughput"],
        default="stable",
        help="Perfil de OCR: stable (mais estavel), balanced (melhor ocupacao), throughput (mais agressivo)",
    )
    parser.add_argument("--max-video-mb", type=int, default=50, help="Videos maiores que este tamanho entram como metadados")
    parser.add_argument("--max-image-mb", type=int, default=15, help="Imagens maiores que este tamanho sao ignoradas no OCR (0=sem limite)")
    parser.add_argument("--job-id", default="default", help="Identificador do job para checkpoint de retomada")
    parser.add_argument("--sem-resume", action="store_true", help="Desativa retomada por checkpoint")
    parser.add_argument("--reset-job", action="store_true", help="Limpa checkpoint do job antes de iniciar")
    parser.add_argument("--batch-size", type=int, default=0, help="Processa somente um lote com este tamanho (0=desligado)")
    parser.add_argument("--batch-number", type=int, default=1, help="Numero do lote (1-based) quando --batch-size > 0")
    parser.add_argument("--gerar-resumo", action="store_true", help="Gera resumo curto por arquivo usando Ollama")
    parser.add_argument("--resumo-modelo", default="llama3.1:8b-instruct", help="Modelo Ollama para resumo")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434", help="URL base da API do Ollama")
    parser.add_argument("--resumo-timeout", type=float, default=12.0, help="Timeout (s) por resumo no Ollama")
    parser.add_argument("--sem-resumo-fallback", action="store_true", help="Nao usa fallback local quando Ollama falhar")
    parser.add_argument("--backfill-resumos", action="store_true", help="Preenche resumo_curto dos registros ja indexados")
    parser.add_argument("--backfill-limit", type=int, default=0, help="Limite de registros no backfill (0=todos)")
    parser.add_argument("--buscar", help="Termo para busca full-text")
    parser.add_argument("--limite", type=int, default=30, help="Limite de resultados da busca")
    parser.add_argument("--pasta", help="Filtro de busca por pasta/prefixo de caminho")
    parser.add_argument("--ext", help="Filtro de busca por extensao (ex: .pdf, pdf)")
    parser.add_argument("--desde", help="Filtro data inicial (mtime) no formato YYYY-MM-DD")
    parser.add_argument("--ate", help="Filtro data final (mtime) no formato YYYY-MM-DD")
    args = parser.parse_args()

    if args.buscar:
        buscar_texto(
            args.buscar,
            limite=args.limite,
            pasta=args.pasta,
            ext=args.ext,
            desde=args.desde,
            ate=args.ate,
        )
        return

    if args.backfill_resumos:
        backfill_resumos(
            limite=args.backfill_limit,
            resumo_modelo=args.resumo_modelo,
            ollama_url=args.ollama_url,
            resumo_timeout_sec=args.resumo_timeout,
            resumo_fallback=not args.sem_resumo_fallback,
        )
        return

    # Controla comportamento do OCR sem quebrar compatibilidade de assinatura.
    os.environ["OCR_PROFILE"] = args.ocr_profile

    indexar_texto(
        Path(args.fonte),
        incluir_duplicatas=args.incluir_duplicatas,
        usar_ocr=args.ocr_imagens,
        max_video_mb=args.max_video_mb,
        max_image_mb=args.max_image_mb,
        job_id=args.job_id,
        resume=not args.sem_resume,
        reset_job=args.reset_job,
        batch_size=args.batch_size,
        batch_number=args.batch_number,
        gerar_resumo=args.gerar_resumo,
        resumo_modelo=args.resumo_modelo,
        ollama_url=args.ollama_url,
        resumo_timeout_sec=args.resumo_timeout,
        resumo_fallback=not args.sem_resumo_fallback,
    )


if __name__ == "__main__":
    main()
