import sys
import os
import shutil
from pathlib import Path

from streamlit.web import cli as stcli


def main() -> int:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)).resolve()
    app_path = bundle_root / "src" / "interface.py"

    # Mantem dados editaveis (db/logs/config) ao lado do executavel no destino final.
    runtime_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    os.environ["BACKUP_ORGANIZER_ROOT"] = str(runtime_root)

    if getattr(sys, "frozen", False):
        for rel in ["src", "docs", "requirements.txt"]:
            src_path = bundle_root / rel
            dst_path = runtime_root / rel
            if not src_path.exists():
                continue
            if src_path.is_dir():
                if not dst_path.exists():
                    shutil.copytree(src_path, dst_path)
            else:
                if not dst_path.exists():
                    shutil.copy2(src_path, dst_path)

    # Faz o Streamlit abrir diretamente a UI operacional.
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]
    return stcli.main()


if __name__ == "__main__":
    raise SystemExit(main())
