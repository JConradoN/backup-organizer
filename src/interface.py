import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, unquote_plus

import pandas as pd
import streamlit as st


_ROOT_ENV = os.getenv("BACKUP_ORGANIZER_ROOT", "").strip()
ROOT_DIR = Path(_ROOT_ENV).resolve() if _ROOT_ENV else Path(__file__).resolve().parent.parent
DB_PATH = str(ROOT_DIR / "backup_organizer.db")
CONFIG_PATH = ROOT_DIR / "logs" / "ui_config.json"
SRC_DIR = ROOT_DIR / "src"
HELP_PATH = ROOT_DIR / "docs" / "HELPME_UI.md"

DEFAULT_CONFIG = {
    "fonte": "F:/",
    "destino": "F:/organizado",
    "job_id": "default",
    "ocr_profile": "stable",
    "max_video_mb": 50,
    "max_image_mb": 15,
    "resumo_modelo": "llama3.1:8b-instruct",
    "ollama_url": "http://127.0.0.1:11434",
}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_text_index_schema() -> None:
    with get_connection() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(text_index)").fetchall()]
        if not cols:
            return

        if "resumo_curto" not in cols:
            conn.execute("ALTER TABLE text_index ADD COLUMN resumo_curto TEXT")
        if "resumo_modelo" not in cols:
            conn.execute("ALTER TABLE text_index ADD COLUMN resumo_modelo TEXT")
        if "resumo_em" not in cols:
            conn.execute("ALTER TABLE text_index ADD COLUMN resumo_em TEXT")
        conn.commit()


def load_ui_config() -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update(data)
    except Exception:
        pass
    return cfg


def save_ui_config(cfg: dict[str, Any]) -> tuple[bool, str]:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=True), encoding="utf-8")
        return True, f"Configuracao salva em {CONFIG_PATH}"
    except Exception as exc:
        return False, f"Falha ao salvar configuracao: {exc}"


def script_path(name: str) -> str:
    return str((SRC_DIR / name).resolve())


def python_cmd() -> str:
    # Em dev usa o Python que executa o Streamlit; no empacotamento pode ser ajustado.
    return sys.executable


def run_command_capture(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd or ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="ignore",
        )
        out = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        return int(result.returncode), out.strip()
    except Exception as exc:
        return 1, f"Falha ao executar comando: {exc}"


def check_ollama(url: str) -> tuple[bool, str]:
    try:
        import urllib.request

        req = urllib.request.Request(url=url.rstrip("/") + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            body = resp.read(8000).decode("utf-8", errors="ignore")
        return True, body[:500]
    except Exception as exc:
        return False, f"Nao foi possivel acessar Ollama: {exc}"


def collect_env_status(cfg: dict[str, Any]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []

    deps = [
        ("streamlit", "streamlit"),
        ("pandas", "pandas"),
        ("easyocr", "easyocr"),
        ("cv2", "cv2"),
        ("pypdf", "pypdf"),
        ("docx", "python-docx"),
    ]

    checks.append(
        {
            "item": "Python",
            "status": "ok" if sys.version_info >= (3, 10) else "atencao",
            "detalhe": sys.version.replace("\n", " "),
        }
    )

    checks.append(
        {
            "item": "Banco SQLite",
            "status": "ok" if Path(DB_PATH).exists() else "atencao",
            "detalhe": DB_PATH,
        }
    )

    for module, label in deps:
        found = importlib.util.find_spec(module) is not None
        checks.append(
            {
                "item": f"Dependencia: {label}",
                "status": "ok" if found else "erro",
                "detalhe": "instalado" if found else "nao encontrado",
            }
        )

    ok_ollama, msg_ollama = check_ollama(str(cfg.get("ollama_url", DEFAULT_CONFIG["ollama_url"])))
    checks.append(
        {
            "item": "Ollama",
            "status": "ok" if ok_ollama else "atencao",
            "detalhe": "online" if ok_ollama else msg_ollama,
        }
    )

    return checks


def open_in_explorer(path_str: str) -> tuple[bool, str]:
    try:
        p = Path(path_str).expanduser()
        if p.exists() and p.is_file():
            subprocess.Popen(["explorer.exe", "/select,", str(p.resolve())])
            return True, "Arquivo selecionado no Explorer."
        if p.exists() and p.is_dir():
            subprocess.Popen(["explorer.exe", str(p.resolve())])
            return True, "Pasta aberta no Explorer."
        parent = p.parent
        if parent.exists():
            subprocess.Popen(["explorer.exe", str(parent.resolve())])
            return True, "Arquivo nao encontrado; pasta pai aberta no Explorer."
        return False, "Caminho nao encontrado no sistema."
    except Exception as exc:
        return False, f"Falha ao abrir no Explorer: {exc}"


def open_file_direct(path_str: str) -> tuple[bool, str]:
    try:
        p = Path(path_str).expanduser()
        if p.exists() and p.is_file():
            os.startfile(str(p.resolve()))
            return True, "Arquivo aberto no aplicativo padrao."
        if p.exists() and p.is_dir():
            subprocess.Popen(["explorer.exe", str(p.resolve())])
            return True, "Caminho e uma pasta; pasta aberta no Explorer."
        return False, "Arquivo nao encontrado no sistema."
    except Exception as exc:
        return False, f"Falha ao abrir arquivo: {exc}"


def _build_open_link(path_str: str, action: str) -> str:
    encoded = quote_plus(path_str)
    return f"?open_action={action}&open_path={encoded}"


def _inject_open_links(df: pd.DataFrame, path_column: str) -> pd.DataFrame:
    out = df.copy()
    out.insert(0, "abrir_arquivo", out[path_column].astype(str).map(lambda p: _build_open_link(p, "file")))
    out.insert(1, "abrir_explorer", out[path_column].astype(str).map(lambda p: _build_open_link(p, "explorer")))
    return out


def _handle_open_from_query_params() -> None:
    action = str(st.query_params.get("open_action") or "explorer").strip().lower()
    raw = st.query_params.get("open_path")
    if not raw:
        return

    caminho = unquote_plus(str(raw))
    if action == "file":
        ok, msg = open_file_direct(caminho)
    else:
        ok, msg = open_in_explorer(caminho)

    if ok:
        st.success(msg)
    else:
        st.error(msg)

    try:
        del st.query_params["open_action"]
    except Exception:
        pass
    try:
        del st.query_params["open_path"]
    except Exception:
        st.query_params.clear()


def _date_to_timestamp(date_str: str | None, end_of_day: bool) -> float | None:
    if not date_str:
        return None
    base = f"{date_str} 23:59:59" if end_of_day else f"{date_str} 00:00:00"
    return pd.Timestamp(base).timestamp()


def search_full_text(
    termo: str,
    limite: int,
    pasta: str,
    ext: str,
    resumo: str,
    desde: str,
    ate: str,
) -> pd.DataFrame:
    sql = (
        "SELECT t.caminho, t.caminho_original_ref, t.extensao, t.origem_texto, t.resumo_curto, "
        "snippet(text_index_fts, 0, '[', ']', ' ... ', 12) AS trecho, "
        "t.atualizado_em "
        "FROM text_index_fts f "
        "JOIN text_index t ON t.id = f.rowid "
        "WHERE text_index_fts MATCH ?"
    )
    params: list[Any] = [termo]

    if pasta:
        sql += " AND lower(t.caminho) LIKE ?"
        params.append(f"{pasta.lower()}%")

    if ext:
        ext_norm = ext.lower().strip()
        if ext_norm and not ext_norm.startswith("."):
            ext_norm = "." + ext_norm
        sql += " AND t.extensao = ?"
        params.append(ext_norm)

    if resumo:
        sql += " AND lower(COALESCE(t.resumo_curto, '')) LIKE ?"
        params.append(f"%{resumo.lower().strip()}%")

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

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def search_tags(
    decisoes: list[str],
    categorias: list[str],
    metodos: list[str],
    exts: list[str],
    status: list[str],
    limite: int,
) -> pd.DataFrame:
    sql = (
        "SELECT nome, extensao, categoria, decisao, metodo, status, confianca, "
        "motivo, caminho_original, caminho_destino, timestamp_processado "
        "FROM files WHERE 1=1"
    )
    params: list[Any] = []

    def add_in_clause(column: str, values: list[str]) -> None:
        nonlocal sql, params
        if not values:
            return
        placeholders = ",".join(["?"] * len(values))
        sql += f" AND {column} IN ({placeholders})"
        params.extend(values)

    add_in_clause("decisao", decisoes)
    add_in_clause("categoria", categorias)
    add_in_clause("metodo", metodos)
    add_in_clause("extensao", exts)
    add_in_clause("status", status)

    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limite)

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def get_distinct_values(column: str) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT DISTINCT {column} AS value FROM files WHERE {column} IS NOT NULL ORDER BY {column}"
        ).fetchall()
    return [str(r["value"]) for r in rows if r["value"] is not None]


def start_background_job(name: str, cmd: list[str]) -> tuple[bool, str]:
    try:
        logs_dir = ROOT_DIR / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in name)[:40]
        log_path = logs_dir / f"run_{safe_name}_{stamp}.log"

        log_fh = open(log_path, "a", encoding="utf-8", errors="ignore")
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT_DIR),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )

        jobs = st.session_state.setdefault("bg_jobs", {})
        jobs[str(proc.pid)] = {
            "name": name,
            "pid": proc.pid,
            "cmd": " ".join(cmd),
            "started": datetime.now().isoformat(timespec="seconds"),
            "log_path": str(log_path),
            "proc": proc,
        }
        return True, f"Job iniciado em background. PID={proc.pid} | log={log_path}"
    except Exception as exc:
        return False, f"Falha ao iniciar job: {exc}"


def render_bg_jobs() -> None:
    jobs = st.session_state.get("bg_jobs", {})
    if not jobs:
        st.info("Nenhum job local iniciado por esta interface nesta sessao.")
        return

    rows = []
    for key, job in jobs.items():
        proc = job.get("proc")
        status = "running"
        code = ""
        if proc is not None:
            rc = proc.poll()
            if rc is not None:
                status = "finished"
                code = str(rc)
        rows.append(
            {
                "pid": job.get("pid"),
                "nome": job.get("name"),
                "status": status,
                "exit_code": code,
                "iniciado": job.get("started"),
                "log": job.get("log_path"),
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def tail_log(path_str: str, max_lines: int = 80) -> str:
    try:
        p = Path(path_str)
        if not p.exists():
            return "Log nao encontrado."
        text = p.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        return "\n".join(lines[-max_lines:])
    except Exception as exc:
        return f"Falha ao ler log: {exc}"


def list_directory(path_str: str) -> pd.DataFrame:
    p = Path(path_str).expanduser()
    if not p.exists() or not p.is_dir():
        return pd.DataFrame()

    rows = []
    for child in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        rows.append(
            {
                "nome": child.name,
                "tipo": "pasta" if child.is_dir() else "arquivo",
                "caminho": str(child),
            }
        )
    return pd.DataFrame(rows)


def render_overview() -> None:
    st.subheader("Visao Geral")
    st.info(
        "Este painel concentra instalacao, configuracao, execucao dos modulos, busca e monitoramento. "
        "Aviso: a execucao da analise de OCR pode demorar muito tempo, dependendo do volume de arquivos e do hardware."
    )

    try:
        with get_connection() as conn:
            files_total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            index_total = conn.execute("SELECT COUNT(*) FROM text_index").fetchone()[0]
            resumo_total = conn.execute(
                "SELECT COUNT(*) FROM text_index WHERE COALESCE(TRIM(resumo_curto),'')<>''"
            ).fetchone()[0]
            jobs_running = conn.execute(
                "SELECT COUNT(*) FROM text_index_jobs WHERE lower(status)='running'"
            ).fetchone()[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Arquivos (files)", int(files_total))
        c2.metric("Indexados (text_index)", int(index_total))
        c3.metric("Com resumo", int(resumo_total))
        c4.metric("Jobs running", int(jobs_running))
    except Exception as exc:
        st.warning(f"Nao foi possivel ler metricas do banco: {exc}")


def render_installation(cfg: dict[str, Any]) -> None:
    st.subheader("Instalacao e Ambiente")
    st.warning(
        "A analise de OCR e a geracao de resumo por IA podem ser demoradas. "
        "Em maquinas mais simples, execute primeiro com lotes pequenos para validacao."
    )

    if st.button("Verificar ambiente", use_container_width=True):
        status_rows = collect_env_status(cfg)
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    if col1.button("Instalar/atualizar dependencias (pip)", use_container_width=True):
        rc, out = run_command_capture([python_cmd(), "-m", "pip", "install", "-r", "requirements.txt"], cwd=ROOT_DIR, timeout=1800)
        if rc == 0:
            st.success("Dependencias instaladas/atualizadas com sucesso.")
        else:
            st.error(f"Falha ao instalar dependencias (exit={rc}).")
        st.code(out or "(sem saida)")

    if col2.button("Verificar Ollama", use_container_width=True):
        ok, msg = check_ollama(str(cfg.get("ollama_url", DEFAULT_CONFIG["ollama_url"])))
        if ok:
            st.success("Ollama respondeu corretamente.")
        else:
            st.warning("Ollama indisponivel no momento.")
        st.code(msg)


def render_configuration(cfg: dict[str, Any]) -> dict[str, Any]:
    st.subheader("Configuracao")
    st.caption("Defina caminhos e parametros padrao para execucao dos modulos")

    with st.form("cfg_form"):
        c1, c2 = st.columns(2)
        fonte = c1.text_input("Fonte", value=str(cfg.get("fonte", DEFAULT_CONFIG["fonte"])))
        destino = c2.text_input("Destino", value=str(cfg.get("destino", DEFAULT_CONFIG["destino"])))

        c3, c4, c5 = st.columns(3)
        job_id = c3.text_input("Job ID", value=str(cfg.get("job_id", DEFAULT_CONFIG["job_id"])))
        ocr_profile = c4.selectbox(
            "OCR profile",
            options=["stable", "balanced", "throughput"],
            index=["stable", "balanced", "throughput"].index(str(cfg.get("ocr_profile", "stable"))),
        )
        resumo_modelo = c5.text_input("Modelo de resumo (Ollama)", value=str(cfg.get("resumo_modelo", DEFAULT_CONFIG["resumo_modelo"])))

        c6, c7, c8 = st.columns(3)
        max_video_mb = c6.number_input("Max video (MB)", min_value=1, max_value=5000, value=int(cfg.get("max_video_mb", 50)), step=1)
        max_image_mb = c7.number_input("Max imagem OCR (MB)", min_value=0, max_value=2000, value=int(cfg.get("max_image_mb", 15)), step=1)
        ollama_url = c8.text_input("Ollama URL", value=str(cfg.get("ollama_url", DEFAULT_CONFIG["ollama_url"])))

        submitted = st.form_submit_button("Salvar configuracao", use_container_width=True)

    if submitted:
        cfg = {
            "fonte": fonte.strip(),
            "destino": destino.strip(),
            "job_id": job_id.strip() or "default",
            "ocr_profile": ocr_profile,
            "max_video_mb": int(max_video_mb),
            "max_image_mb": int(max_image_mb),
            "resumo_modelo": resumo_modelo.strip() or DEFAULT_CONFIG["resumo_modelo"],
            "ollama_url": ollama_url.strip() or DEFAULT_CONFIG["ollama_url"],
        }
        ok, msg = save_ui_config(cfg)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    st.divider()
    st.markdown("**Navegacao de pastas**")
    nav_path = st.text_input("Pasta atual", value=str(st.session_state.get("nav_path", cfg.get("fonte", "F:/"))))
    st.session_state["nav_path"] = nav_path

    cnav1, cnav2, cnav3, cnav4 = st.columns(4)
    if cnav1.button("Abrir no Explorer", use_container_width=True):
        ok, msg = open_in_explorer(nav_path)
        st.success(msg) if ok else st.error(msg)

    if cnav2.button("Subir nivel", use_container_width=True):
        p = Path(nav_path).expanduser()
        st.session_state["nav_path"] = str(p.parent if p.parent else p)
        st.rerun()

    if cnav3.button("Usar como Fonte", use_container_width=True):
        cfg["fonte"] = nav_path
        ok, msg = save_ui_config(cfg)
        st.success(msg) if ok else st.error(msg)

    if cnav4.button("Usar como Destino", use_container_width=True):
        cfg["destino"] = nav_path
        ok, msg = save_ui_config(cfg)
        st.success(msg) if ok else st.error(msg)

    df_dir = list_directory(st.session_state.get("nav_path", nav_path))
    if df_dir.empty:
        st.info("Sem itens para listar ou caminho invalido.")
    else:
        st.dataframe(df_dir, use_container_width=True, hide_index=True)
        dirs = df_dir[df_dir["tipo"] == "pasta"]
        if not dirs.empty:
            chosen = st.selectbox("Entrar em pasta", options=list(dirs["caminho"]))
            if st.button("Entrar", use_container_width=True):
                st.session_state["nav_path"] = chosen
                st.rerun()

    return cfg


def render_execution(cfg: dict[str, Any]) -> None:
    st.subheader("Execucao de Modulos")
    st.warning(
        "A execucao da analise de OCR pode demorar muito tempo, de acordo com seu hardware, "
        "quantidade de arquivos e tamanho das imagens."
    )

    st.markdown("**1) Indexacao textual / OCR**")
    with st.form("run_indexacao"):
        c1, c2, c3 = st.columns(3)
        fonte = c1.text_input("Fonte da indexacao", value=str(cfg.get("fonte", "F:/")))
        job_id = c2.text_input("Job ID", value=str(cfg.get("job_id", "default")))
        ocr_profile = c3.selectbox("OCR profile", ["stable", "balanced", "throughput"], index=["stable", "balanced", "throughput"].index(str(cfg.get("ocr_profile", "stable"))))

        c4, c5, c6 = st.columns(3)
        max_video_mb = c4.number_input("Max video MB", min_value=1, max_value=5000, value=int(cfg.get("max_video_mb", 50)), step=1)
        max_image_mb = c5.number_input("Max imagem MB", min_value=0, max_value=2000, value=int(cfg.get("max_image_mb", 15)), step=1)
        usar_ocr = c6.checkbox("Ativar OCR", value=True)

        c7, c8, c9 = st.columns(3)
        gerar_resumo = c7.checkbox("Gerar resumo IA", value=True)
        reset_job = c8.checkbox("Reset job", value=False)
        sem_resume = c9.checkbox("Sem resume checkpoint", value=False)

        run_idx = st.form_submit_button("Iniciar indexacao em background", use_container_width=True)

    if run_idx:
        cmd = [python_cmd(), script_path("indexacao_texto.py"), "--fonte", fonte, "--job-id", job_id, "--max-video-mb", str(int(max_video_mb)), "--max-image-mb", str(int(max_image_mb)), "--ocr-profile", ocr_profile]
        if usar_ocr:
            cmd.append("--ocr-imagens")
        if gerar_resumo:
            cmd.extend(["--gerar-resumo", "--resumo-modelo", str(cfg.get("resumo_modelo", DEFAULT_CONFIG["resumo_modelo"])), "--ollama-url", str(cfg.get("ollama_url", DEFAULT_CONFIG["ollama_url"]))])
        if reset_job:
            cmd.append("--reset-job")
        if sem_resume:
            cmd.append("--sem-resume")

        ok, msg = start_background_job("indexacao_texto", cmd)
        st.success(msg) if ok else st.error(msg)

    st.markdown("**2) Backfill de resumos**")
    with st.form("run_backfill"):
        c1, c2 = st.columns(2)
        limit = c1.number_input("Limite (0=todos)", min_value=0, max_value=2_000_000, value=0, step=100)
        fallback = c2.checkbox("Usar fallback local", value=True)
        run_backfill = st.form_submit_button("Iniciar backfill em background", use_container_width=True)

    if run_backfill:
        cmd = [python_cmd(), script_path("indexacao_texto.py"), "--backfill-resumos", "--backfill-limit", str(int(limit)), "--resumo-modelo", str(cfg.get("resumo_modelo", DEFAULT_CONFIG["resumo_modelo"])), "--ollama-url", str(cfg.get("ollama_url", DEFAULT_CONFIG["ollama_url"]))]
        if not fallback:
            cmd.append("--sem-resumo-fallback")
        ok, msg = start_background_job("backfill_resumos", cmd)
        st.success(msg) if ok else st.error(msg)

    st.markdown("**3) Pipeline principal (scan/classify/move)**")
    with st.form("run_main"):
        c1, c2 = st.columns(2)
        fonte_main = c1.text_input("Fonte pipeline", value=str(cfg.get("fonte", "F:/")))
        destino_main = c2.text_input("Destino pipeline", value=str(cfg.get("destino", "F:/organizado")))
        dry_run = st.checkbox("Dry run", value=True)
        run_main = st.form_submit_button("Iniciar pipeline em background", use_container_width=True)

    if run_main:
        cmd = [python_cmd(), script_path("main.py"), "--fonte", fonte_main, "--destino", destino_main]
        if dry_run:
            cmd.append("--dry-run")
        ok, msg = start_background_job("main_pipeline", cmd)
        st.success(msg) if ok else st.error(msg)


def render_search() -> None:
    if "df_texto" not in st.session_state:
        st.session_state["df_texto"] = pd.DataFrame()
    if "df_tags" not in st.session_state:
        st.session_state["df_tags"] = pd.DataFrame()

    sub_texto, sub_tags = st.tabs(["Busca Textual", "Busca por Tags"])

    with sub_texto:
        st.subheader("Busca full-text")
        col1, col2, col3 = st.columns([3, 1, 1])
        termo = col1.text_input("Termo", value="")
        limite_texto = col2.number_input("Limite", min_value=1, max_value=500, value=50, step=1)
        ext_texto = col3.text_input("Extensao", value="")

        col4, col5, col6 = st.columns([3, 1, 1])
        pasta_texto = col4.text_input("Pasta (prefixo de caminho)", value="")
        desde = col5.text_input("Desde (YYYY-MM-DD)", value="")
        ate = col6.text_input("Ate (YYYY-MM-DD)", value="")
        resumo_texto = st.text_input("Filtro no resumo (Ollama)", value="")

        if st.button("Pesquisar texto", use_container_width=True):
            if not termo.strip():
                st.warning("Informe um termo de busca.")
                st.session_state["df_texto"] = pd.DataFrame()
            else:
                try:
                    df_texto = search_full_text(
                        termo=termo.strip(),
                        limite=int(limite_texto),
                        pasta=pasta_texto.strip(),
                        ext=ext_texto.strip(),
                        resumo=resumo_texto.strip(),
                        desde=desde.strip(),
                        ate=ate.strip(),
                    )
                except Exception as exc:
                    st.error(f"Erro na busca textual: {exc}")
                    df_texto = pd.DataFrame()

                st.session_state["df_texto"] = df_texto

        df_texto = st.session_state.get("df_texto", pd.DataFrame())
        st.metric("Resultados", len(df_texto))
        if df_texto.empty:
            st.info("Nenhum resultado encontrado.")
        else:
            df_texto_link = _inject_open_links(df_texto, "caminho")
            st.data_editor(
                df_texto_link,
                use_container_width=True,
                hide_index=True,
                disabled=True,
                column_config={
                    "abrir_arquivo": st.column_config.LinkColumn("Abrir arquivo", display_text="Abrir"),
                    "abrir_explorer": st.column_config.LinkColumn("Abrir no Explorer", display_text="Explorer"),
                },
                key="texto_results",
            )

    with sub_tags:
        st.subheader("Busca por metadados/tags")

        decisoes_all = get_distinct_values("decisao")
        categorias_all = get_distinct_values("categoria")
        metodos_all = get_distinct_values("metodo")
        exts_all = get_distinct_values("extensao")
        status_all = get_distinct_values("status")

        c1, c2, c3 = st.columns(3)
        decisoes = c1.multiselect("Decisao", options=decisoes_all, default=[])
        categorias = c2.multiselect("Categoria", options=categorias_all, default=[])
        metodos = c3.multiselect("Metodo", options=metodos_all, default=[])

        c4, c5, c6 = st.columns(3)
        exts = c4.multiselect("Extensao", options=exts_all, default=[])
        status = c5.multiselect("Status", options=status_all, default=[])
        limite_tags = c6.number_input("Limite", min_value=1, max_value=5000, value=200, step=10)

        if st.button("Pesquisar tags", use_container_width=True):
            try:
                df_tags = search_tags(
                    decisoes=decisoes,
                    categorias=categorias,
                    metodos=metodos,
                    exts=exts,
                    status=status,
                    limite=int(limite_tags),
                )
            except Exception as exc:
                st.error(f"Erro na busca por tags: {exc}")
                df_tags = pd.DataFrame()

            st.session_state["df_tags"] = df_tags

        df_tags = st.session_state.get("df_tags", pd.DataFrame())
        st.metric("Resultados", len(df_tags))
        if df_tags.empty:
            st.info("Nenhum resultado encontrado.")
        else:
            df_tags = df_tags.copy()
            df_tags["caminho_abrir"] = df_tags["caminho_destino"].fillna("").astype(str)
            mask_vazio = df_tags["caminho_abrir"].str.strip() == ""
            df_tags.loc[mask_vazio, "caminho_abrir"] = df_tags.loc[mask_vazio, "caminho_original"].fillna("").astype(str)
            df_tags_link = _inject_open_links(df_tags, "caminho_abrir").drop(columns=["caminho_abrir"])

            st.data_editor(
                df_tags_link,
                use_container_width=True,
                hide_index=True,
                disabled=True,
                column_config={
                    "abrir_arquivo": st.column_config.LinkColumn("Abrir arquivo", display_text="Abrir"),
                    "abrir_explorer": st.column_config.LinkColumn("Abrir no Explorer", display_text="Explorer"),
                },
                key="tags_results",
            )


def render_jobs() -> None:
    st.subheader("Status de indexacao")
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT job_id, fonte, usar_ocr, status, processed_count, total_count, updated_em
                FROM text_index_jobs
                ORDER BY updated_em DESC
                """
            ).fetchall()
        df_jobs = pd.DataFrame([dict(r) for r in rows])
        if df_jobs.empty:
            st.info("Nenhum job encontrado.")
        else:
            st.dataframe(df_jobs, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(f"Falha ao ler jobs: {exc}")


def render_logs() -> None:
    st.subheader("Logs")
    render_bg_jobs()

    jobs = st.session_state.get("bg_jobs", {})
    if not jobs:
        return

    options = []
    for _, job in jobs.items():
        options.append(f"{job.get('pid')} | {job.get('name')} | {job.get('log_path')}")

    selected = st.selectbox("Escolha um log", options=options)
    log_path = selected.split(" | ", 2)[-1]

    max_lines = st.slider("Linhas finais", min_value=20, max_value=500, value=120, step=20)
    st.code(tail_log(log_path, max_lines=max_lines), language="text")


def render_helpme() -> None:
    st.subheader("HelpMe")
    st.caption("Guia rapido dos elementos da interface e fluxos recomendados")

    if HELP_PATH.exists():
        content = HELP_PATH.read_text(encoding="utf-8", errors="ignore")
        st.markdown(content)
    else:
        st.warning(f"Arquivo de ajuda nao encontrado: {HELP_PATH}")


st.set_page_config(page_title="Backup Organizer | Painel", layout="wide")
st.title("Backup Organizer - Painel Operacional")
st.caption("Instalacao, configuracao, execucao dos modulos, busca e monitoramento")

ensure_text_index_schema()
_handle_open_from_query_params()

cfg_state = st.session_state.get("ui_cfg")
if not cfg_state:
    st.session_state["ui_cfg"] = load_ui_config()

cfg = st.session_state["ui_cfg"]

st.sidebar.warning(
    "Aviso importante: a execucao da analise de OCR pode demorar muito tempo, "
    "de acordo com seu hardware e volume de arquivos."
)
st.sidebar.caption(f"Banco: {DB_PATH}")
st.sidebar.caption(f"Config: {CONFIG_PATH}")
if st.sidebar.button("Recarregar configuracao"):
    st.session_state["ui_cfg"] = load_ui_config()
    st.rerun()

(
    tab_inicio,
    tab_install,
    tab_config,
    tab_exec,
    tab_busca,
    tab_jobs,
    tab_logs,
    tab_help,
) = st.tabs([
    "Inicio",
    "Instalacao",
    "Configuracao",
    "Execucao",
    "Busca",
    "Jobs",
    "Logs",
    "HelpMe",
])

with tab_inicio:
    render_overview()

with tab_install:
    render_installation(cfg)

with tab_config:
    cfg = render_configuration(cfg)
    st.session_state["ui_cfg"] = cfg

with tab_exec:
    render_execution(cfg)

with tab_busca:
    render_search()

with tab_jobs:
    render_jobs()

with tab_logs:
    render_logs()

with tab_help:
    render_helpme()

if st.button("Atualizar painel", use_container_width=True):
    st.rerun()
