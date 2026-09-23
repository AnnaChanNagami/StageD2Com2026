"""
Pont entre Django et la bibliothèque qwen_asr (Qwen3-ASR).

Encapsule tout ce qui touche au modèle :
  - chargement paresseux et singleton du Qwen3ASRModel
  - transcription d'un fichier audio (bloquant — réservé au worker)
  - extraction de la durée audio
  - parsing des timestamps (forced aligner) en segments pour l'interface
  - calcul des métriques et génération des exports TXT / JSON / SRT

Si torch / transformers / le modèle ne sont pas disponibles (machine sans GPU,
premier téléchargement des poids pas encore fait), les fonctions liées au modèle
dégradent proprement au lieu de crasher : la durée et les exports restent
fonctionnels.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from django.conf import settings

try:
    import torch
    from qwen_asr import Qwen3ASRModel
    from qwen_asr.inference.utils import SUPPORTED_LANGUAGES as _QWEN_LANGS
    QWEN_OK = True
except Exception:  # noqa: BLE001 - la bibliothèque peut manquer
    QWEN_OK = False
    _QWEN_LANGS = [
        "Chinese", "English", "Cantonese", "Arabic", "German", "French",
        "Spanish", "Portuguese", "Indonesian", "Italian", "Korean", "Russian",
        "Thai", "Vietnamese", "Japanese", "Turkish", "Hindi", "Malay",
        "Dutch", "Swedish", "Danish", "Finnish", "Polish", "Czech",
        "Filipino", "Persian", "Greek", "Romanian", "Hungarian", "Macedonian",
    ]


# --- Singleton du modèle --------------------------------------------------

_model = None


def get_model():
    """Crée (une seule fois) le Qwen3ASRModel selon la configuration Django."""
    global _model
    if _model is None:
        dtype = getattr(torch, str(settings.QWEN_DTYPE).lower(), None) or torch.bfloat16
        kwargs = {
            "dtype": dtype,
            "device_map": settings.QWEN_DEVICE,
            "max_inference_batch_size": 16,
            "max_new_tokens": settings.QWEN_MAX_NEW_TOKENS,
        }
        forced_aligner = str(settings.QWEN_FORCED_ALIGNER or "").strip()
        _model = Qwen3ASRModel.from_pretrained(
            settings.QWEN_ASR_MODEL,
            forced_aligner=forced_aligner or None,
            forced_aligner_kwargs=dict(dtype=dtype, device_map=settings.QWEN_DEVICE)
            if forced_aligner else None,
            **kwargs,
        )
    return _model


def backend_available() -> bool:
    """Le backend complet (torch + modèle) est-il utilisable ?"""
    return QWEN_OK


def supported_languages() -> list[str]:
    return list(_QWEN_LANGS)


def runtime_info() -> dict:
    if not QWEN_OK:
        return {
            "backend": "unavailable",
            "model": settings.QWEN_ASR_MODEL,
            "device": settings.QWEN_DEVICE,
            "dtype": settings.QWEN_DTYPE,
        }
    try:
        m = get_model()
        info = {
            "backend": "qwen3-asr (transformers)",
            "model": settings.QWEN_ASR_MODEL,
            "device": str(getattr(m, "device", settings.QWEN_DEVICE)),
            "dtype": str(getattr(getattr(m, "model", None), "dtype", "") or settings.QWEN_DTYPE),
            "languages": len(supported_languages()),
            "forced_aligner": bool(settings.QWEN_FORCED_ALIGNER),
        }
        return info
    except Exception:  # noqa: BLE001
        return {
            "backend": "unavailable",
            "model": settings.QWEN_ASR_MODEL,
            "device": settings.QWEN_DEVICE,
            "dtype": settings.QWEN_DTYPE,
        }


# --- Durée audio ----------------------------------------------------------

def audio_duration(path) -> float | None:
    """Durée (secondes) d'un fichier audio, sans charger le modèle."""
    try:
        import soundfile as sf
        with sf.SoundFile(path) as f:
            return float(f.frames) / float(f.samplerate)
    except Exception:  # noqa: BLE001 - format non lu par soundfile (ex. mp4)
        try:
            import librosa
            y, sr = librosa.load(str(path), sr=None, mono=True)
            return float(len(y)) / float(sr)
        except Exception:  # noqa: BNE001
            return None


# --- Transcription ----------------------------------------------------------

STAGES = {
    "loading_model": "Chargement du modèle…",
    "transcribing": "Transcription en cours…",
    "aligning": "Alignement des timestamps…",
    "parsing": "Analyse du résultat…",
    "done": "Terminé",
    "error": "Erreur",
}


def run_transcription(job, on_status=None) -> None:
    """Exécute la transcription pour un TranscriptionJob (réservé au worker)."""
    from .models import TranscriptionJob

    def status_callback(stage: str, progress: float | None) -> None:
        if on_status:
            on_status(stage, progress)

    job.set_status(TranscriptionJob.Status.RUNNING)
    if on_status:
        on_status("loading_model", 0.05)

    try:
        model = get_model()
    except Exception as exc:  # noqa: BLE001
        _fail(job, f"Impossible de charger le modèle : {type(exc).__name__}: {exc}")
        return

    # Durée audio (pas bloquant, fait dans le worker avant l'inférence)
    if job.duration_sec is None:
        job.duration_sec = audio_duration(job.audio_file.path)
        TranscriptionJob.objects.filter(id=job.id).update(duration_sec=job.duration_sec)

    if on_status:
        on_status("transcribing", 0.3)

    try:
        result = model.transcribe(
            audio=job.audio_file.path,
            context=job.prompt or "",
            language=(job.language or None),
            return_time_stamps=bool(job.want_timestamps),
        )[0]
    except Exception as exc:  # noqa: BLE001
        _fail(job, f"{type(exc).__name__}: {exc}")
        return

    job.transcript_text = (result.text or "").strip()
    job.language_detected = (result.language or "").strip()

    segments = []
    ts = getattr(result, "time_stamps", None)
    if ts is not None and len(ts) > 0:
        if on_status:
            on_status("aligning", 0.8)
        for it in ts:
            txt = str(getattr(it, "text", "") or "").strip()
            if not txt:
                continue
            segments.append(
                {
                    "id": f"seg_{len(segments) + 1:04d}",
                    "start": float(getattr(it, "start_time", 0.0) or 0.0),
                    "end": float(getattr(it, "end_time", 0.0) or 0.0),
                    "text": txt,
                }
            )

    # If no timestamps from forced aligner, create a single segment with full text
    if not segments and job.transcript_text.strip():
        segments.append(
            {
                "id": "seg_0001",
                "start": 0.0,
                "end": 0.0,
                "text": job.transcript_text.strip(),
            }
        )

    job.segments_json = json.dumps(segments, ensure_ascii=False)
    job.segment_count = len(segments)
    job.device = str(getattr(model, "device", "") or settings.QWEN_DEVICE)
    job.generated_tokens = len((result.text or "").split()) if result.text else 0

    if on_status:
        on_status("parsing", 0.95)
    job.progress = 1.0
    job.stage = "done"
    job.set_status(TranscriptionJob.Status.COMPLETED)
    job.save()


def _fail(job, message: str) -> None:
    from .models import TranscriptionJob
    job.status = TranscriptionJob.Status.FAILED
    job.error = message
    job.stage = "error"
    job.progress = 1.0
    job.completed_at = None
    job.save()


# --- Exports ------------------------------------------------------------------

def render_export(kind: str, segments: list[dict]) -> str:
    """Rend un export SRT / JSON à partir de segments dict."""
    if kind == "json":
        return json.dumps(segments, ensure_ascii=False, indent=2) + "\n"
    if kind == "srt":
        return build_srt(segments)
    raise ValueError(f"Export inconnu : {kind}")


def _fmt_ts(sec: float) -> str:
    """Formate une durée en secondes au format SRT (HH:MM:SS,mmm)."""
    sec = max(0.0, float(sec or 0.0))
    ms = int(round((sec - int(sec)) * 1000))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments: list[dict]) -> str:
    lines = []
    for i, seg in enumerate(segments, start=1):
        txt = str(seg.get("text", "") or "").strip()
        if not txt:
            continue
        start = _fmt_ts(float(seg.get("start", 0.0) or 0.0))
        end = _fmt_ts(float(seg.get("end", 0.0) or 0.0))
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(txt)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def raw_transcript(job) -> str:
    return (job.transcript_text or "").strip() + "\n"
