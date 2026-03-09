"""Pre-sanitizacao de arquivos antes da indexacao textual.

Objetivo:
- Detectar arquivos com forte indicio de lixo de internet (meme/assets web/copias).
- Gerar relatorio em CSV.
- Opcionalmente mover para quarentena (nao deleta).

Padrao: DRY-RUN (somente relatorio)
Aplicar: --apply
"""

from __future__ import annotations

import argparse
import csv
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_ROOT = Path("F:/")
DEFAULT_QUARANTINE = Path("F:/quarentena_lixo_internet")
DEFAULT_REPORT = Path("logs/relatorio_sanitizacao_pre_indexacao.csv")


SKIP_DIRS = {
    "duplicatas_detectadas",
    "quarentena_lixo_internet",
}


WEB_ASSET_KEYWORDS = {
    "watermark", "favicon", "sprite", "thumbnail", "thumb", "icon", "logo",
    "banner", "ads", "adserver", "tracking", "pixel", "template", "theme",
    "bootstrap", "jquery", "site_", "wp-content", "wp-includes", "cdn", "cache",
    "button", "background", "header", "footer", "menu", "slider",
}

MEME_KEYWORDS = {
    "meme", "sticker", "reaction", "whatsapp image", "img_", "dank",
}


@dataclass
class Suspect:
    path: Path
    score: int
    reasons: list[str]


def _should_skip(path: Path) -> bool:
    lower = str(path).lower()
    return any(f"\\{d}\\" in lower for d in SKIP_DIRS)


def _build_score(path: Path) -> Suspect | None:
    name = path.name.lower()
    ext = path.suffix.lower()
    parent = str(path.parent).lower()

    score = 0
    reasons: list[str] = []

    # Strong signal: web asset naming.
    for kw in WEB_ASSET_KEYWORDS:
        if kw in name or kw in parent:
            score += 2
            reasons.append(f"kw_web:{kw}")
            break

    # Medium signal: meme-like naming.
    for kw in MEME_KEYWORDS:
        if kw in name:
            score += 1
            reasons.append(f"kw_meme:{kw}")
            break

    # Typical internet asset extensions.
    if ext in {".gif", ".webp", ".svg", ".ico"}:
        score += 1
        reasons.append(f"ext_asset:{ext}")

    # Very small images are often icons/buttons/tracking assets.
    try:
        size = path.stat().st_size
        if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".ico", ".svg"} and size <= 60 * 1024:
            score += 1
            reasons.append("img_muito_pequena<=60KB")
    except OSError:
        return None

    # Conservative threshold to avoid moving valid personal files.
    if score >= 3:
        return Suspect(path=path, score=score, reasons=reasons)
    return None


def _safe_target(src: Path, quarantine: Path) -> Path:
    target = quarantine / src.name
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    i = 1
    while True:
        cand = quarantine / f"{stem}_{i}{suffix}"
        if not cand.exists():
            return cand
        i += 1


def sanitizar(root: Path, quarantine: Path, report: Path, apply: bool) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    if apply:
        quarantine.mkdir(parents=True, exist_ok=True)

    suspects: list[Suspect] = []

    total = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if _should_skip(p):
            continue

        total += 1
        s = _build_score(p)
        if s:
            suspects.append(s)

        if total % 5000 == 0:
            print(f"Avaliados: {total}")

    moved = 0
    errors = 0
    ext_counter = Counter()
    rows: list[dict[str, str]] = []

    for s in suspects:
        ext_counter[s.path.suffix.lower() or "(sem_ext)"] += 1
        action = "detectado"
        target = ""

        if apply:
            try:
                dest = _safe_target(s.path, quarantine)
                shutil.move(str(s.path), str(dest))
                action = "movido_quarentena"
                target = str(dest)
                moved += 1
            except Exception:
                action = "erro_ao_mover"
                errors += 1

        rows.append(
            {
                "arquivo": str(s.path),
                "extensao": s.path.suffix.lower(),
                "score": str(s.score),
                "motivos": "|".join(s.reasons),
                "acao": action,
                "destino": target,
            }
        )

    with report.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["arquivo", "extensao", "score", "motivos", "acao", "destino"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print("=" * 60)
    print("Sanitizacao pre-indexacao")
    print("=" * 60)
    print(f"Modo                 : {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Arquivos avaliados   : {total}")
    print(f"Suspeitos detectados : {len(suspects)}")
    print(f"Movidos quarentena   : {moved}")
    print(f"Erros                : {errors}")
    print(f"Relatorio            : {report}")
    print("Top extensoes suspeitas:")
    for ext, qtd in ext_counter.most_common(10):
        print(f"  {ext}: {qtd}")
    if not apply:
        print("\nPara aplicar, rode com --apply")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sanitiza arquivos antes da indexacao textual")
    parser.add_argument("--fonte", default=str(DEFAULT_ROOT), help="Diretorio raiz a sanitizar")
    parser.add_argument("--quarentena", default=str(DEFAULT_QUARANTINE), help="Destino de quarentena")
    parser.add_argument("--relatorio", default=str(DEFAULT_REPORT), help="CSV de saida")
    parser.add_argument("--apply", action="store_true", help="Move suspeitos para quarentena")
    args = parser.parse_args()

    sanitizar(
        root=Path(args.fonte),
        quarantine=Path(args.quarentena),
        report=Path(args.relatorio),
        apply=args.apply,
    )


if __name__ == "__main__":
    main()
