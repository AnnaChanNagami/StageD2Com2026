"""Génération du compte rendu PDF d'une transcription.

fpdf2 est utilisé en Unicode (TTF) parce que les transcriptions contiennent des
accents (français) et souvent du CJK (chinois) : les polices coeur de fpdf2
(Helvetica/Courier) ne couvrent que Latin-1 et plantent au-delà de U+00FF.

Deux polices sont donc enregistrées :
  - "body" : Segoe UI / Arial / Calibri -> latin + accents
  - "cjk"  : msyh.ttc / simsun.ttc      -> chinois, japonais, coréen
fpdf2 ne sait pas changer de police au milieu d'une ligne, donc chaque ligne est
découpée en fragments (runs) et chaque run est écrit avec sa police, au même
niveau de ligne (pas de multi_cell, qui sauterait une ligne par run).

Si aucune police TTF n'est trouvée, on retombe sur la police coeur et le texte
est translittéré en Latin-1 (les caractères hors Latin-1 deviennent "?") : on
préfère un "?" à un HTTP 500.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fpdf import FPDF

logger = logging.getLogger(__name__)

# Couleurs de la charte marine/azur
MARINE = (13, 42, 74)
AZUR = (14, 116, 189)
SLATE = (71, 85, 105)
INK = (15, 23, 42)
RULE = (210, 218, 230)
MUTED = (120, 130, 145)

# Géométrie (mm)
PAGE_W, PAGE_H = 210.0, 297.0
MARGIN = 18.0
CONTENT_W = PAGE_W - 2 * MARGIN

RUNNING_TITLE = "Compte rendu de transcription - Qwen3-ASR"


# ------------------- Polices ------------------------------------------------------------------
def _win_font(*names: str) -> str | None:
    """Premier fichier de police existant parmi `names`, sinon None."""
    root = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts"
    for name in names:
        path = root / name
        if path.is_file():
            return str(path)
    return None


def _is_cjk(ch: str) -> bool:
    """Vrai pour les caractères servis par la police CJK (kanji, kana, hangul, pleine largeur).

    Les PONCTUATIONS CJK sont incluses (。、「」) : Segoe UI ne les a pas, et les
    perdre produirait des "?" au milieu du texte chinois.
    """
    cp = ord(ch)
    return (
        0x3000 <= cp <= 0x30FF      # ponctuation CJK + hiragana / katakana
        or 0x3400 <= cp <= 0x9FFF   # idéographes CJK
        or 0xF900 <= cp <= 0xFAFF   # idéogrammes de compatibilité
        or 0xFF00 <= cp <= 0xFFEF   # pleine largeur
        or 0xAC00 <= cp <= 0xD7AF   # hangul syllabaire
    )


def _to_latin1(text: str) -> str:
    """Remplace les caractères hors Latin-1 (repli quand aucune police TTF)."""
    return text.encode("latin-1", "replace").decode("latin-1")


# ------------------- Document ------------------------------------------------------------------
class TranscriptPDF(FPDF):
    """Compte rendu PDF : titre, métadonnées, puis le texte de la transcription."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._body_font = "helvetica"
        self._body_bold = "body"
        self._body_italic = "helvetica"
        self._cjk_font: str | None = None
        self._unicode_ok = False

    def setup_fonts(self) -> None:
        """Enregistre la police latine et, si possible, la police CJK."""
        latin = _win_font("segoeui.ttf", "arial.ttf", "calibri.ttf")
        if latin is None:
            logger.warning("Aucune police TTF trouvee : PDF limite a Latin-1")
            return
        # Les noms coeur (Helvetica, Courier...) sont réservés : add_font est
        # silencieusement ignoré si on les réutilise. D'où les noms "body" / "cjk".
        self.add_font("body", "", latin)
        bold = _win_font("segoeuib.ttf", "arialbd.ttf", "calibrib.ttf") or latin
        self.add_font("body", "B", bold)
        italic = _win_font("segoeuii.ttf", "ariali.ttf", "calibrii.ttf") or latin
        self.add_font("body", "I", italic)
        self._body_font = "body"
        self._body_bold = "body"
        self._body_italic = "body"
        self._unicode_ok = True
        # La police CJK n'est PAS chargée ici : voir ensure_cjk_font().

    def ensure_cjk_font(self) -> None:
        """Charge la police CJK à la demande.

        msyh.ttc/simsun.ttc pèsent ~20 Mo et couvrent ~44 000 glyphes : les charger
        prend plusieurs secondes et plus de 100 Mo de RAM. On ne le fait donc que si le
        document contient réellement des caractères CJK.
        """
        if self._cjk_font is not None:
            return
        cjk = _win_font("msyh.ttc", "simsun.ttc", "msgothic.ttc")
        if not cjk:
            return
        try:
            self.add_font("cjk", "", cjk)
            self._cjk_font = "cjk"
        except Exception:  # noqa: BLE001 - police illisible : on reste en latin
            logger.warning("Police CJK inutilisable (%s)", cjk, exc_info=True)
            self._cjk_font = None

    # --- habillage des pages ---------------------------------------------------
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font(self._body_font, "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, RUNNING_TITLE, new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 6, f"Page {self.page_no()}/{self.pages_count}", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        """Pied vide : le numéro de page est dans l'en-tête courant."""

    # --- mesure / découpe ------------------------------------------------------
    def _measure(self, token: str, needs_cjk: bool, size: float) -> float:
        font = self._cjk_font if (needs_cjk and self._cjk_font) else self._body_font
        if not self._unicode_ok:
            token = _to_latin1(token)
        self.set_font(font, "", size)
        return self.get_string_width(token)

    def _tokens(self, line: str) -> list[tuple[str, bool]]:
        """Découpe une ligne en atomes : mots latins (espace collé) ou chars CJK.

        Fonction pure : construit une nouvelle liste (ne mute pas l'input).
        """
        tokens: list[tuple[str, bool]] = []
        latin_buf = ""

        def flush_latin() -> None:
            """Émet le tampon latin en tokens (mot, espace), sans espace final."""
            nonlocal latin_buf
            if not latin_buf:
                return
            for word in latin_buf.split(" "):
                if word:
                    tokens.append((word, False))
                tokens.append((" ", False))
            tokens.pop()  # pas d'espace final
            latin_buf = ""

        for ch in line:
            if _is_cjk(ch) and self._cjk_font:
                flush_latin()
                tokens.append((ch, True))
            else:
                latin_buf += ch
        flush_latin()
        return tokens

    def _wrap(self, line: str, size: float) -> list[list[tuple[str, bool]]]:
        """Coupe `line` en lignes de largeur CONTENT_W (liste de tokens)."""
        out: list[list[tuple[str, bool]]] = []
        current: list[tuple[str, bool]] = []
        width = 0.0
        for token, need in self._tokens(line):
            w = self._measure(token, need, size)
            if current and width + w > CONTENT_W:
                out.append(current)
                current, width = [], 0.0
                if token == " ":
                    continue  # pas d'espace en début de ligne
            if not current and w > CONTENT_W and len(token) > 1:
                # Mot plus large que la page : coupe caractère par caractère.
                for ch in token:
                    cw = self._measure(ch, need, size)
                    if current and width + cw > CONTENT_W:
                        out.append(current)
                        current, width = [], 0.0
                    current.append((ch, need))
                    width += cw
                continue
            current.append((token, need))
            width += w
        if current:
            out.append(current)
        return out or [[("", False)]]

    def _draw_line(self, tokens: list[tuple[str, bool]], size: float, lh: float) -> None:
        """Écrit les tokens d'une ligne à partir de la position X courante."""
        top = self.get_y()
        x = self.get_x() if self.get_x() > MARGIN else MARGIN
        for token, need in tokens:
            if not token:
                continue
            font = self._cjk_font if (need and self._cjk_font) else self._body_font
            if not self._unicode_ok:
                token = _to_latin1(token)
            self.set_font(font, "", size)
            w = self.get_string_width(token)
            if x + w > PAGE_W - MARGIN and x > MARGIN:
                # Filet de sécurité si la mesure a été faussée.
                self.set_xy(PAGE_W - MARGIN - w, top)
            self.set_xy(x, top)
            self.cell(w + 0.2, lh, token, new_x="RIGHT", new_y="TOP")
            x += w
        self.set_xy(self.l_margin, top + lh)

    # --- blocs de texte --------------------------------------------------------
    def paragraph(self, text: str, size: float = 10.5, lh: float = 6.0) -> None:
        """Écrit un paragraphe en respectant les sauts de ligne d'origine."""
        for raw in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = "".join(" " if (ord(c) < 32 or ord(c) == 127) else c for c in raw)
            if not line.strip():
                self.ln(lh * 0.5)
                continue
            for tokens in self._wrap(line, size):
                self._draw_line(tokens, size, lh)
            self.ln(lh * 0.3)

    def meta_line(self, label: str, value: str) -> None:
        """Ligne « Libellé : valeur », libellé en gras."""
        if not value:
            return
        size, lh = 9.5, 5.4
        top = self.get_y()
        label_w = self.get_string_width(f"{label} :") + 2

        def draw_label() -> None:
            """Pose le libellé en gras à la position courante."""
            self.set_font(self._body_bold, "B", size)
            self.set_text_color(*SLATE)
            self.cell(label_w, lh, f"{label} :", new_x="RIGHT", new_y="TOP")
            self.set_text_color(*INK)
            self.set_font(self._body_font, "", size)

        value_w = self.get_string_width(value)
        if label_w + value_w <= CONTENT_W:
            draw_label()
            self.cell(value_w + 0.2, lh, value, new_x="RIGHT", new_y="TOP")
            self.set_xy(MARGIN, top + lh)
            return

        # Valeur trop large : la valeur passe sous le libellé, sur plusieurs lignes.
        self.set_xy(MARGIN, top)
        draw_label()
        self.set_xy(MARGIN + label_w, top)
        for tokens in self._wrap(value, size):
            self._draw_line(tokens, size, lh)

    def rule(self, color: tuple[int, int, int], width: float = 0.3, pad: float = 3.0) -> None:
        self.set_draw_color(*color)
        self.set_line_width(width)
        self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
        self.ln(pad)


# ------------------- Rendu ------------------------------------------------------------------
def _fmt_duration(sec: float) -> str:
    """93.8 -> '1 min 33.8 s'."""
    minutes, seconds = divmod(float(sec), 60.0)
    if minutes >= 1:
        return f"{int(minutes)} min {seconds:.1f} s"
    return f"{seconds:.1f} s"


def _pick_text(job, corrected: bool) -> str:
    """Texte à exporter : corrigé si demandé et disponible, sinon transcription brute."""
    if corrected:
        text = (getattr(job, "corrected_text", "") or "").strip()
        if text:
            return text
        logger.info("Export PDF : pas de texte corrigé, export de la transcription brute.")
    return (job.transcript_text or "").strip()


def build_transcript_pdf(job, *, corrected: bool = False) -> bytes:
    """Retourne les octets du PDF pour un `TranscriptionJob`."""
    title = job.original_name or job.media_name() or f"transcription {job.pk}"
    text = _pick_text(job, corrected)

    pdf = TranscriptPDF(format="A4")
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_auto_page_break(auto=True, margin=24)
    pdf.set_title(title)
    pdf.set_author("Qwen3-ASR")
    pdf.set_creator("Qwen3-ASR webapp")
    pdf.setup_fonts()
    pdf.add_page()

    # Titre
    pdf.set_font(pdf._body_bold, "B", 18)
    pdf.set_text_color(*MARINE)
    pdf.paragraph("Compte rendu de transcription", size=18, lh=8.5)
    pdf.set_font(pdf._body_font, "", 10.5)
    pdf.set_text_color(*AZUR)
    pdf.paragraph(title, size=10.5, lh=6.0)
    pdf.ln(1)
    pdf.rule(AZUR, width=0.7, pad=5)

    # Métadonnées
    pdf.meta_line("Fichier", title)
    pdf.meta_line("Langue", job.language_detected or "auto")
    if job.duration_sec:
        pdf.meta_line("Durée", _fmt_duration(job.duration_sec))
    if job.segment_count:
        pdf.meta_line("Segments", str(job.segment_count))
    words = job.total_words()
    if words:
        pdf.meta_line("Mots", str(words))
    if job.elapsed_sec and job.elapsed_sec > 0:
        pdf.meta_line("Traitement", f"{job.elapsed_sec:.1f} s")
    if getattr(job, "created_at", None):
        pdf.meta_line("Date", job.created_at.strftime("%d/%m/%Y à %H:%M"))
    pdf.meta_line("Identifiant", str(job.pk))
    pdf.ln(2)
    pdf.rule(RULE, width=0.3, pad=5)

    # Corps. La police CJK (~20 Mo, ~44 000 glyphes) n'est chargée que si le texte
    # en contient réellement : sinon on gaspille plusieurs secondes et >100 Mo de RAM.
    pdf.set_text_color(*INK)
    if text:
        if any(_is_cjk(ch) for ch in text):
            pdf.ensure_cjk_font()
        pdf.paragraph(text, size=10.5, lh=6.2)
    else:
        pdf.set_font(pdf._body_italic, "I", 10.5)
        pdf.set_text_color(*SLATE)
        pdf.paragraph("Aucune transcription disponible pour ce fichier.", size=10.5, lh=6.2)

    out = pdf.output()
    return bytes(out)