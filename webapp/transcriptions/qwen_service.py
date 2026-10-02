#Pont entre Django et la bibliothèque qwen_asr (Qwen3-ASR).
#Encapsule tout ce qui touche au modèle :
# - chargement paresseux et singleton du Qwen3ASRModel
# - transcription d'un fichier audio (bloquant — réservé au worker)
# - extraction de la durée audio
# - parsing des timestamps (forced aligner) en segments pour l'interface
# - calcul des métriques et génération des exports TXT / JSON / SRT

# Si torch / transformers / le modèle ne sont pas disponibles (machine sans GPU,
# premier téléchargement des poids pas encore fait), les fonctions liées au modèle
# dégradent proprement au lieu de crasher : la durée et les exports restent
#fonctionnels.


from __future__ import annotations

import io
import json
from pathlib import Path

from django.conf import settings
# Différents imports pour le support de l'audio
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
# Si la langue ne fait pas partie de la liste, elle ne sera pas supportée par le modèle.

# --- Singleton du modèle --------------------------------------------------

_model = None

#------------------Fonction get_model() pour charger Qwen3-----------------------------------------------------------
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
#------------------Fonction pour appeler le modèle et vérifier si le backend est disponible--------------------------------
def backend_available() -> bool:
    """Le backend complet (torch + modèle) est-il utilisable ?"""
    return QWEN_OK

#------------------Fonction pour lister les langues supportées par le modèle---------------------------------------------------
def supported_languages() -> list[str]:
    return list(_QWEN_LANGS)

#------------------Fonction pour obtenir les informations sur l'environnement d'exécution du modèle---------------------------
def runtime_info() -> dict:
    if not QWEN_OK:
        return {
            "backend": "unavailable",
            "model": settings.QWEN_ASR_MODEL,
            "device": settings.QWEN_DEVICE,
            "dtype": settings.QWEN_DTYPE,
        }
    # NE PAS appeler get_model() ici : cette fonction est appelée par les vues
    # (home, dashboard) à CHAQUE requête HTTP. Charger les poids (5,6 Go) dans le
    # processus du serveur web saturait la VRAM et faisait crasher le worker
    # (exit 139, CUDA OOM) sur une carte 6 Go. Les infos ci-dessous ne dépendent
    # que des settings, pas du modèle chargé.
    if _model is None:
        return {
            "backend": "qwen3-asr (transformers)",
            "model": settings.QWEN_ASR_MODEL,
            "device": str(settings.QWEN_DEVICE),
            "dtype": str(settings.QWEN_DTYPE),
            "languages": len(supported_languages()),
            "forced_aligner": bool(settings.QWEN_FORCED_ALIGNER),
            "model_loaded": False,
        }
    info = {
        "backend": "qwen3-asr (transformers)",
        "model": settings.QWEN_ASR_MODEL,
        "device": str(getattr(_model, "device", settings.QWEN_DEVICE)),
        "dtype": str(getattr(getattr(_model, "model", None), "dtype", "") or settings.QWEN_DTYPE),
        "languages": len(supported_languages()),
        "forced_aligner": bool(settings.QWEN_FORCED_ALIGNER),
        "model_loaded": True,
    }
    return info


# -------------------- Fonction pour la durée audio ----------------------------------------------------------

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


# -------------------Fonction pour lancer la transcription ----------------------------------------------------------
"""Définition des étapes de la transcription pour le suivi de progression."""
STAGES = {
    "loading_model": "Chargement du modèle…",
    "transcribing": "Transcription en cours…",
    "aligning": "Alignement des timestamps…",
    "parsing": "Analyse du résultat…",
    "done": "Terminé",
    "error": "Erreur",
}

""" Fonction principale pour exécuter la transcription d'un fichier audio avecc Qwen3-ASR
+ Suivi de la transcription avec un callback pour les MAJ de progression"""
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
#---------------Suivi de la transcription---------------------------------------------------------------------------------------
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
#--------------Mise à jour du travail effectué après le transcription et l'allignement des timestamps---------------------------
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

    # Si aucun segment n'a été généré, on crée un segment unique avec tout le texte
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
#---------------Fonction pour gérer les erreurs de transcription et mettre à jour le statut du travail en conséquence---------------------
def _fail(job, message: str) -> None:
    from .models import TranscriptionJob
    job.status = TranscriptionJob.Status.FAILED
    job.error = message
    job.stage = "error"
    job.progress = 1.0
    job.completed_at = None
    job.save()


# --- Exports ------------------------------------------------------------------
#--------------Fonctions pour générer des exports SRT / JSON à partir des segments dict.-----------------------------------------
def render_export(kind: str, segments: list[dict]) -> str:
    """Rend un export SRT / JSON à partir de segments dict."""
    if kind == "json":
        return json.dumps(segments, ensure_ascii=False, indent=2) + "\n"
    if kind == "srt":
        return build_srt(segments)
    raise ValueError(f"Export inconnu : {kind}")

#--------------Fonction pour formater les timestamps en format SRT (HH:MM:SS,mmm)-------------------------------------------------------
def _fmt_ts(sec: float) -> str:
    """Formate une durée en secondes au format SRT (HH:MM:SS,mmm)."""
    sec = max(0.0, float(sec or 0.0))
    # Arrondir la fraction de seconde pouvait produire 1000 (carry), donc un
    # champ ",1000" à 4 chiffres — invalide en SRT. On arrondit le TOTAL en
    # millisecondes puis on décompose : le carry est absorbé par la seconde,
    # et les erreurs de représentation flottante (0.029*1000 = 28.999…) sont
    # absorbées par le round.
    total_ms = int(round(sec * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

#--------------Fonction pour construire un fichier SRT à partir des segments dict.----------------------------------------------------
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

#--------------Fonction pour obtenir la transcription brute d'un travail de transcription----------------------------------------
def raw_transcript(job) -> str:
    return (job.transcript_text or "").strip() + "\n"
