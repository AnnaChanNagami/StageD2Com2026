"""Sauvegarde des transcriptions.

À l'arrêt de l'enregistrement, le texte complet est écrit dans un fichier
texte horodaté. On gère aussi l'ajout d'un en-tête (date, durée, etc.).
"""

from __future__ import annotations

import datetime
from pathlib import Path

# On rend le dossier "config" importable en tant que package.
import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parent.parent / "config"))
import settings  # noqa: E402


def _timestamp() -> str:
    """Horodatage compact pour les noms de fichiers, ex: 20260831_105432."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def build_header() -> str:
    """Construit l'en-tête ajouté en haut de chaque transcription."""
    now = datetime.datetime.now()
    lines = [
        f"Date      : {now.strftime('%d/%m/%Y %H:%M:%S')}",
        f"Langue    : {settings.LANG}",
        f"Moteur    : {settings.STT_ENGINE}",
        "----------------------------------------",
    ]
    return "\n".join(lines)


def save_transcript(text: str, output_dir: Path | None = None) -> Path:
    """Écrit le transcript complet dans un fichier .txt et renvoie son chemin.

    Arguments
    ---------
    text       : le texte transcrit (peut contenir des retours à la ligne).
    output_dir : dossier de destination (par défaut : settings.OUTPUT_DIR).

    Retour
    ------
    Le chemin (pathlib.Path) du fichier créé.
    """
    folder = Path(output_dir) if output_dir else settings.OUTPUT_DIR
    folder.mkdir(parents=True, exist_ok=True)

    filename = f"transcript_{_timestamp()}.txt"
    filepath = folder / filename

    content = build_header() + "\n\n" + text.strip() + "\n"
    filepath.write_text(content, encoding="utf-8")
    return filepath
