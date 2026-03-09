"""
database.py
Camada de persistência SQLite — versão otimizada.
- Conexão única por thread (thread-local)
- Batch insert (commit a cada N registros)
- PRAGMAs de performance: WAL + synchronous OFF + cache 2GB
"""

import sqlite3
import threading
import os
from datetime import datetime
from pathlib import Path


DB_PATH    = os.getenv("DB_PATH", "backup_organizer.db")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "500"))

# Conexão thread-local — evita abrir/fechar N vezes
_local = threading.local()

# Buffer de inserção em lote por thread
_batch_lock   = threading.Lock()
_batch_buffer: list[dict] = []


def get_connection() -> sqlite3.Connection:
    """Retorna conexão thread-local, criando se necessário."""
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Performance máxima para operações em lote
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA cache_size=-2000")   # 2GB RAM de cache
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


def init_db() -> None:
    """Cria tabelas e índices se não existirem."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                caminho_original     TEXT NOT NULL UNIQUE,
                nome                 TEXT NOT NULL,
                extensao             TEXT,
                tamanho              INTEGER,
                hash_sha256          TEXT,
                data_criacao         TEXT,
                data_modificacao     TEXT,
                decisao              TEXT CHECK(decisao IN ('util','lixo','ambiguo','duplicata')),
                categoria            TEXT,
                caminho_destino      TEXT,
                metodo               TEXT CHECK(metodo IN ('heuristica','ia')),
                confianca            REAL,
                status               TEXT CHECK(status IN ('pendente','processado','erro','copiado'))
                                     DEFAULT 'pendente',
                dry_run              INTEGER DEFAULT 0,
                motivo               TEXT,
                timestamp_scan       TEXT,
                timestamp_processado TEXT
            );

            CREATE TABLE IF NOT EXISTS runs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                iniciado_em   TEXT NOT NULL,
                finalizado_em TEXT,
                fonte         TEXT,
                destino       TEXT,
                dry_run       INTEGER DEFAULT 0,
                total         INTEGER DEFAULT 0,
                processados   INTEGER DEFAULT 0,
                erros         INTEGER DEFAULT 0,
                status        TEXT DEFAULT 'em_andamento'
            );

            CREATE INDEX IF NOT EXISTS idx_hash     ON files(hash_sha256);
            CREATE INDEX IF NOT EXISTS idx_status   ON files(status);
            CREATE INDEX IF NOT EXISTS idx_decisao  ON files(decisao);
            CREATE INDEX IF NOT EXISTS idx_extensao ON files(extensao);
        """)
    print(f"[DB] Banco inicializado em: {DB_PATH}")


# ---------------------------------------------------------------------------
# Batch insert — acumula registros e faz commit em lote
# ---------------------------------------------------------------------------

def inserir_arquivo(dados: dict) -> int:
    """Adiciona ao buffer. Commit automático a cada BATCH_SIZE registros."""
    global _batch_buffer

    with _batch_lock:
        _batch_buffer.append(dados)
        if len(_batch_buffer) >= BATCH_SIZE:
            _flush_batch()

    return 0


def flush_final() -> None:
    """Força commit do que sobrou no buffer ao final do scan."""
    with _batch_lock:
        if _batch_buffer:
            _flush_batch()


def _flush_batch() -> None:
    """Executa INSERT em lote. Deve ser chamado com _batch_lock adquirido."""
    if not _batch_buffer:
        return

    sql = """
        INSERT OR IGNORE INTO files
            (caminho_original, nome, extensao, tamanho, hash_sha256,
             data_criacao, data_modificacao, status, dry_run, timestamp_scan)
        VALUES
            (:caminho_original, :nome, :extensao, :tamanho, :hash_sha256,
             :data_criacao, :data_modificacao, 'pendente', :dry_run, :timestamp_scan)
    """
    conn = get_connection()
    conn.executemany(sql, _batch_buffer)
    conn.commit()
    _batch_buffer.clear()


# ---------------------------------------------------------------------------
# Operações individuais (classifier, mover)
# ---------------------------------------------------------------------------

# Buffer de decisões — commit em lote para performance
_decisao_buffer: list[dict] = []
_decisao_lock = threading.Lock()
DECISAO_BATCH = 200

def atualizar_decisao(caminho_original: str, decisao: dict) -> None:
    global _decisao_buffer
    decisao["timestamp_processado"] = datetime.now().isoformat()
    decisao["caminho_original"] = caminho_original
    with _decisao_lock:
        _decisao_buffer.append(decisao)
        if len(_decisao_buffer) >= DECISAO_BATCH:
            _flush_decisoes()

def flush_decisoes_final() -> None:
    with _decisao_lock:
        if _decisao_buffer:
            _flush_decisoes()

def _flush_decisoes() -> None:
    if not _decisao_buffer:
        return
    sql = """
        UPDATE files SET
            decisao              = :decisao,
            categoria            = :categoria,
            metodo               = :metodo,
            confianca            = :confianca,
            motivo               = :motivo,
            caminho_destino      = :caminho_destino,
            status               = :status,
            timestamp_processado = :timestamp_processado
        WHERE caminho_original = :caminho_original
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executemany(sql, _decisao_buffer)
    conn.commit()
    conn.close()
    _decisao_buffer.clear()


def marcar_copiado(caminho_original: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE files SET status='copiado' WHERE caminho_original=?",
        (caminho_original,)
    )
    conn.commit()


def marcar_erro(caminho_original: str, motivo: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE files SET status='erro', motivo=? WHERE caminho_original=?",
        (motivo, caminho_original)
    )
    conn.commit()


def buscar_pendentes() -> list:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM files WHERE status='pendente'"
        ).fetchall()


def hash_ja_existe(hash_sha256: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM files WHERE hash_sha256=? AND status != 'pendente' LIMIT 1",
            (hash_sha256,)
        ).fetchone()
        return row is not None


def resumo() -> list:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT decisao, status, COUNT(*) as total
            FROM files
            GROUP BY decisao, status
        """).fetchall()
        return [dict(r) for r in rows]


def iniciar_run(fonte: str, destino: str, dry_run: bool, total: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO runs (iniciado_em, fonte, destino, dry_run, total, status)
               VALUES (?, ?, ?, ?, ?, 'em_andamento')""",
            (datetime.now().isoformat(), fonte, destino, int(dry_run), total)
        )
        return cur.lastrowid


def finalizar_run(run_id: int, processados: int, erros: int) -> None:
    conn = get_connection()
    conn.execute(
        """UPDATE runs SET finalizado_em=?, processados=?, erros=?, status='concluido'
           WHERE id=?""",
        (datetime.now().isoformat(), processados, erros, run_id)
    )
    conn.commit()
