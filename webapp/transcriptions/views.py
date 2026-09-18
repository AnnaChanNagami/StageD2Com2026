from __future__ import annotations

import csv
import json
import os
from difflib import SequenceMatcher
from pathlib import Path

from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import qwen_service
from .models import TranscriptionJob

ALLOWED_EXT = {
    ".wav", ".mp3", ".mp4", ".flac", ".m4a", ".ogg", ".opus",
    ".aac", ".wma", ".mov", ".mkv", ".webm", ".amr",
}

TXT_HEADER = (
    "# Transcription Qwen3-ASR\n"
    "# Généré par l'application web — fichier : {name}\n"
    "# Date : {date}\n"
    "# Langue : {lang}\n\n"
)


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------

def _classify_error(error_msg: str) -> tuple[str, str]:
    """Classifie un message d'erreur en (catégorie, icône_bootstrap)."""
    msg = error_msg.lower()
    if "cuda" in msg or "out of memory" in msg or "oom" in msg:
        return ("Mémoire GPU / CUDA", "bi-memory")
    elif ("model" in msg or "modèle" in msg) and ("charg" in msg or "load" in msg or "download" in msg):
        return ("Modèle indisponible", "bi-box-seam")
    elif "timeout" in msg:
        return ("Délai dépassé", "bi-clock-history")
    elif "format" in msg or "codec" in msg or "decode" in msg:
        return ("Format audio invalide", "bi-file-earmark-x")
    elif "permission" in msg or "access" in msg:
        return ("Permissions", "bi-shield-lock")
    elif "disk" in msg or "space" in msg or "no space" in msg:
        return ("Espace disque", "bi-device-hdd")
    elif "key" in msg or "token" in msg or "auth" in msg:
        return ("Authentification", "bi-key")
    elif "network" in msg or "connection" in msg or "http" in msg or "timeout" in msg:
        return ("Réseau", "bi-wifi-off")
    elif "interrupted" in msg or "killed" in msg or "signal" in msg:
        return ("Interruption", "bi-x-octagon")
    elif "memoryerror" in msg or "memory" in msg:
        return ("Mémoire RAM", "bi-memory")
    elif "nocudamemoryerror" in msg:
        return ("Mémoire GPU / CUDA", "bi-memory")
    elif "transformers" in msg or "tokenizer" in msg:
        return ("Modèle indisponible", "bi-box-seam")
    elif error_msg.strip():
        return ("Autre erreur", "bi-question-circle")
    return ("Non catégorisé", "bi-help-circle")


def dashboard(request):
    completed = TranscriptionJob.objects.filter(status=TranscriptionJob.Status.COMPLETED)
    total_jobs = TranscriptionJob.objects.count()
    failed_jobs = TranscriptionJob.objects.filter(status=TranscriptionJob.Status.FAILED)
    failed_count = failed_jobs.count()
    running = TranscriptionJob.objects.filter(
        status__in=[TranscriptionJob.Status.PENDING, TranscriptionJob.Status.RUNNING]
    ).count()

    total_audio_dur = sum((j.duration_sec or 0) for j in completed)
    total_process = sum((j.elapsed_sec or 0) for j in completed)
    total_words = sum(j.total_words() for j in completed)
    total_chars = sum(j.total_chars() for j in completed)
    total_segments = sum(j.segment_count for j in completed)

    # Langues détectées (top)
    lang_counts = {}
    for j in completed:
        l = j.language_detected.strip()
        if l:
            lang_counts[l] = lang_counts.get(l, 0) + 1

    # Série horaire (7 derniers jours)
    cutoff = timezone.now() - timezone.timedelta(days=6)
    days_series = []
    for i in range(6, -1, -1):
        day = timezone.now() - timezone.timedelta(days=i)
        day_jobs = completed.filter(completed_at__date=day.date())
        days_series.append(
            {
                "label": day.date().strftime("%d/%m"),
                "count": day_jobs.count(),
                "audio_min": round(sum((j.duration_sec or 0) / 60 for j in day_jobs), 1),
                "process_min": round(sum((j.elapsed_sec or 0) / 60 for j in day_jobs), 1),
                "words": sum(j.total_words() for j in day_jobs),
                "chars": sum(j.total_chars() for j in day_jobs),
            }
        )

    # Données par job pour graphiques détaillés (5 derniers jobs)
    recent_jobs = completed[:5]
    jobs_chart = [
        {
            "name": j.original_name[:20] + ("..." if len(j.original_name) > 20 else ""),
            "audio_sec": round(j.duration_sec or 0, 1),
            "process_sec": round(j.elapsed_sec or 0, 1),
            "words": j.total_words(),
            "chars": j.total_chars(),
        }
        for j in reversed(recent_jobs)
    ]

    # Correction stats
    corrected_jobs = completed.filter(corrected_text__gt="")
    corrected_count = corrected_jobs.count()
    correction_rate = round(corrected_count / completed.count() * 100, 1) if completed.count() > 0 else 0

    # Calcul du taux d'erreur moyen (différence caractères entre original et corrigé)
    total_orig_chars = 0
    total_corr_chars = 0
    total_char_diff = 0
    total_word_diff = 0
    corrections_detail = []

    for j in corrected_jobs:
        orig = j.transcript_text or ""
        corr = j.corrected_text or ""
        orig_w = j.total_words()
        corr_w = len(corr.split()) if corr.strip() else 0
        char_diff = abs(len(orig) - len(corr))
        word_diff = abs(orig_w - corr_w)
        total_orig_chars += len(orig)
        total_corr_chars += len(corr)
        total_char_diff += char_diff
        total_word_diff += word_diff
        corrections_detail.append({
            "name": j.original_name[:25] + ("..." if len(j.original_name) > 25 else ""),
            "orig_chars": len(orig),
            "corr_chars": len(corr),
            "orig_words": orig_w,
            "corr_words": corr_w,
            "char_diff": char_diff,
            "word_diff": word_diff,
            "error_pct": round(char_diff / len(orig) * 100, 1) if len(orig) > 0 else 0,
        })

    avg_error_pct = round(total_char_diff / total_orig_chars * 100, 1) if total_orig_chars > 0 else 0
    avg_word_error = round(total_word_diff / corrected_count, 1) if corrected_count > 0 else 0

    # Ratio moyen analyse/durée audio
    avg_ratio = round(total_process / total_audio_dur, 2) if total_audio_dur > 0 else 0

    # --- Statistiques d'erreurs ---
    error_categories = {}
    error_days_series = []
    error_details = []

    for j in failed_jobs:
        cat, _ = _classify_error(j.error)
        error_categories[cat] = error_categories.get(cat, 0) + 1
        error_details.append({
            "name": j.original_name[:30] + ("..." if len(j.original_name) > 30 else ""),
            "category": cat,
            "error_msg": (j.error or "")[:120],
            "created_at": j.created_at.strftime("%d/%m %H:%M") if j.created_at else "",
            "duration_sec": round(j.duration_sec or 0, 1),
        })

    # Série temporelle des erreurs (7 derniers jours)
    for i in range(6, -1, -1):
        day = timezone.now() - timezone.timedelta(days=i)
        day_failed = failed_jobs.filter(created_at__date=day.date())
        day_cats = {}
        for j in day_failed:
            cat, _ = _classify_error(j.error)
            day_cats[cat] = day_cats.get(cat, 0) + 1
        error_days_series.append({
            "label": day.date().strftime("%d/%m"),
            "total": day_failed.count(),
            "categories": day_cats,
        })

    error_categories_json = json.dumps(
        [{"category": k, "count": v} for k, v in sorted(error_categories.items(), key=lambda x: -x[1])],
        ensure_ascii=False,
    )
    error_days_json = json.dumps(error_days_series, ensure_ascii=False)
    error_details_json = json.dumps(error_details, ensure_ascii=False)
    last_error_date = error_details[0]["created_at"] if error_details else ""

    # Taux de réussite
    success_rate = round(completed.count() / total_jobs * 100, 1) if total_jobs > 0 else 0
    error_category_count = len(error_categories)
    success_count = total_jobs - failed_count

    lang_json = json.dumps(
        [{"lang": k, "count": v} for k, v in sorted(lang_counts.items(), key=lambda x: -x[1])][:8],
        ensure_ascii=False,
    )

    recent = completed[:6]
    context = {
        "active": "dashboard",
        "total_jobs": total_jobs,
        "running": running,
        "failed": failed_count,
        "total_audio_dur": total_audio_dur,
        "total_audio_min": round(total_audio_dur / 60, 1) if total_audio_dur else 0,
        "total_process": total_process,
        "total_process_min": round(total_process / 60, 1) if total_process else 0,
        "total_words": total_words,
        "total_chars": total_chars,
        "total_segments": total_segments,
        "avg_ratio": avg_ratio,
        "recent": recent,
        "series": json.dumps(days_series, ensure_ascii=False),
        "lang_json": lang_json,
        "jobs_chart": json.dumps(jobs_chart, ensure_ascii=False),
        # Correction stats
        "corrected_count": corrected_count,
        "correction_rate": correction_rate,
        "avg_error_pct": avg_error_pct,
        "avg_word_error": avg_word_error,
        "total_orig_chars": total_orig_chars,
        "total_corr_chars": total_corr_chars,
        "corrections_detail": json.dumps(corrections_detail, ensure_ascii=False),
        # Erreur stats
        "success_rate": success_rate,
        "error_category_count": error_category_count,
        "success_count": success_count,
        "error_categories_json": error_categories_json,
        "error_days_json": error_days_json,
        "error_details_json": error_details_json,
        "last_error_date": last_error_date,
        "backend_available": qwen_service.backend_available(),
        "runtime": qwen_service.runtime_info(),
    }
    return render(request, "transcriptions/dashboard.html", context)


@require_GET
def job_list(request):
    filter_ = request.GET.get("filter", "all")
    qs = TranscriptionJob.objects.all()
    if filter_ == "completed":
        qs = qs.filter(status=TranscriptionJob.Status.COMPLETED)
    elif filter_ == "failed":
        qs = qs.filter(status=TranscriptionJob.Status.FAILED)
    elif filter_ in ("running", "pending"):
        qs = qs.filter(status__in=[TranscriptionJob.Status.PENDING, TranscriptionJob.Status.RUNNING])

    stats = {
        "all": TranscriptionJob.objects.count(),
        "completed": TranscriptionJob.objects.filter(status=TranscriptionJob.Status.COMPLETED).count(),
        "failed": TranscriptionJob.objects.filter(status=TranscriptionJob.Status.FAILED).count(),
        "running": TranscriptionJob.objects.filter(
            status__in=[TranscriptionJob.Status.PENDING, TranscriptionJob.Status.RUNNING]
        ).count(),
    }
    context = {
        "active": "jobs",
        "jobs": qs[:100],
        "filter": filter_,
        "stats": stats,
        "backend_available": qwen_service.backend_available(),
    }
    return render(request, "transcriptions/job_list.html", context)


def job_detail(request, job_id):
    job = get_object_or_404(TranscriptionJob, id=job_id)
    segments = job.parse_segments()
    duration = job.duration_sec or 0
    context = {
        "active": "jobs",
        "job": job,
        "segments": segments,
        "duration_min": round(duration / 60, 1),
        "segments_json": json.dumps(segments, ensure_ascii=False),
        "backend_available": qwen_service.backend_available(),
    }
    return render(request, "transcriptions/job_detail.html", context)


def correction(request, job_id):
    """Page de correction : affiche la transcription originale et permet d'écrire la version corrigée."""
    job = get_object_or_404(TranscriptionJob, id=job_id)

    if request.method == "POST":
        corrected = request.POST.get("corrected_text", "").strip()
        job.corrected_text = corrected
        job.corrected_at = timezone.now()
        job.save(update_fields=["corrected_text", "corrected_at"])
        return redirect("transcriptions:job_detail", job_id=job.id)

    segments = job.parse_segments()
    context = {
        "active": "jobs",
        "job": job,
        "segments": segments,
        "duration_min": round((job.duration_sec or 0) / 60, 1),
    }
    return render(request, "transcriptions/correction.html", context)


def upload(request):
    if request.method == "POST":
        return redirect("transcriptions:api_job_create")  # le POST passe par l'API
    return render(
        request,
        "transcriptions/upload.html",
        {
            "active": "upload",
            "backend_available": qwen_service.backend_available(),
            "languages": qwen_service.supported_languages(),
            "default_language": "",
        },
    )


# --------------------------------------------------------------------------
# API JSON
# --------------------------------------------------------------------------

@csrf_exempt
@require_POST
def api_job_create(request):
    audio = request.FILES.get("audio_file") or request.FILES.get("file")
    if not audio:
        return HttpResponseBadRequest(
            json.dumps({"error": "Aucun fichier audio fourni."}), content_type="application/json"
        )

    ext = Path(audio.name).suffix.lower()
    if ext not in ALLOWED_EXT:
        return HttpResponseBadRequest(
            json.dumps(
                {"error": f"Extension '{ext}' non prise en charge. Autorisé : {', '.join(sorted(ALLOWED_EXT))}"}
            ),
            content_type="application/json",
        )

    language = (request.POST.get("language", "") or "").strip()
    # La langue doit être dans la liste supportée, sinon on force l'auto-détection.
    if language and language not in qwen_service.supported_languages():
        language = ""

    job = TranscriptionJob(
        audio_file=audio,
        original_name=audio.name[:500],
        prompt=(request.POST.get("prompt", "") or "").strip(),
        language=language,
        max_new_tokens=int(
            request.POST.get("max_new_tokens", "")
            or request.POST.get("max_tokens", "")
            or 512
        ),
        want_timestamps=request.POST.get("timestamps", "") in ("1", "true", "on"),
        duration_sec=None,
    )
    job.save()
    url = reverse("transcriptions:job_detail", args=[job.id])
    return JsonResponse({"id": str(job.id), "status": job.status, "url": url}, status=201)


@require_GET
def api_job_status(request, job_id):
    job = get_object_or_404(TranscriptionJob, id=job_id)
    data = {
        "id": str(job.id),
        "status": job.status,
        "stage": job.stage,
        "progress": round(job.progress * 100, 1),
        "error": job.error,
        "original_name": job.original_name,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "elapsed_sec": job.elapsed_sec,
        "segment_count": job.segment_count,
        "transcript_text": job.transcript_text,
        "language_detected": job.language_detected,
        "url": reverse("transcriptions:job_detail", args=[job.id]),
    }
    return JsonResponse(data)


@require_GET
def api_stats(request):
    jobs = TranscriptionJob.objects.all()
    completed = jobs.filter(status=TranscriptionJob.Status.COMPLETED)
    data = {
        "total": jobs.count(),
        "completed": completed.count(),
        "failed": jobs.filter(status=TranscriptionJob.Status.FAILED).count(),
        "running": jobs.filter(
            status__in=[TranscriptionJob.Status.PENDING, TranscriptionJob.Status.RUNNING]
        ).count(),
        "total_audio_sec": sum((j.duration_sec or 0) for j in completed),
        "total_process_sec": sum((j.elapsed_sec or 0) for j in completed),
        "total_words": sum(j.total_words() for j in completed),
    }
    return JsonResponse(data)


# --------------------------------------------------------------------------
# Téléchargements
# --------------------------------------------------------------------------

def download_txt(request, job_id):
    job = get_object_or_404(TranscriptionJob, id=job_id)
    if job.status != TranscriptionJob.Status.COMPLETED:
        return HttpResponseBadRequest("Transcription non terminée.")
    body = TXT_HEADER.format(
        name=job.original_name or job.media_name(),
        date=timezone.now().strftime("%Y-%m-%d %H:%M"),
        lang=job.language_detected or "auto",
    ) + qwen_service.raw_transcript(job)
    resp = HttpResponse(body, content_type="text/plain; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="transcript_{job.id}.txt"'
    return resp


def download_json(request, job_id):
    job = get_object_or_404(TranscriptionJob, id=job_id)
    if job.status != TranscriptionJob.Status.COMPLETED:
        return HttpResponseBadRequest("Transcription non terminée.")
    body = qwen_service.render_export("json", job.parse_segments())
    resp = HttpResponse(body, content_type="application/json; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="segments_{job.id}.json"'
    return resp


def download_srt(request, job_id):
    job = get_object_or_404(TranscriptionJob, id=job_id)
    if job.status != TranscriptionJob.Status.COMPLETED:
        return HttpResponseBadRequest("Transcription non terminée.")
    body = qwen_service.render_export("srt", job.parse_segments())
    resp = HttpResponse(body, content_type="text/plain; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="subtitle_{job.id}.srt"'
    return resp


# --------------------------------------------------------------------------
# Suppression
# --------------------------------------------------------------------------

def _delete_job(job):
    if job.audio_file:
        try:
            if os.path.isfile(job.audio_file.path):
                os.remove(job.audio_file.path)
        except (ValueError, OSError):
            pass
    job.delete()


@require_POST
def delete_job(request, job_id):
    job = get_object_or_404(TranscriptionJob, id=job_id)
    _delete_job(job)
    return redirect("transcriptions:job_list")


@require_POST
def delete_jobs_bulk(request):
    ids = request.POST.getlist("job_ids")
    if ids:
        jobs = TranscriptionJob.objects.filter(id__in=ids)
        for job in jobs:
            _delete_job(job)
    return redirect("transcriptions:job_list")


# ============================================================
# Métriques d'erreur (corrections)
# ============================================================

def _levenshtein(s1: str, s2: str) -> int:
    """Distance de Levenshtein entre deux chaînes."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insert = prev_row[j + 1] + 1
            delete = curr_row[j] + 1
            replace = prev_row[j] + (c1 != c2)
            curr_row.append(min(insert, delete, replace))
        prev_row = curr_row
    return prev_row[-1]


def _compute_wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate : distance Levenshtein sur les mots."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if len(ref_words) == 0:
        return 0.0
    n, m = len(ref_words), len(hyp_words)
    if n < m:
        return _compute_wer(hypothesis, reference)
    prev = list(range(m + 1))
    for i, rw in enumerate(ref_words):
        curr = [i + 1]
        for j, hw in enumerate(hyp_words):
            ins = prev[j + 1] + 1
            del_ = curr[j] + 1
            sub = prev[j] + (rw != hw)
            curr.append(min(ins, del_, sub))
        prev = curr
    return prev[-1] / len(ref_words)


def _levenshtein_words(a: str, b: str) -> int:
    """Nombre d'éditions (distance de Levenshtein) au niveau des mots."""
    aw = a.split()
    bw = b.split()
    if not bw:
        return len(aw)
    prev = list(range(len(bw) + 1))
    for i, wa in enumerate(aw):
        curr = [i + 1]
        for j, wb in enumerate(bw):
            ins = prev[j + 1] + 1
            del_ = curr[j] + 1
            sub = prev[j] + (wa != wb)
            curr.append(min(ins, del_, sub))
        prev = curr
    return prev[-1]


def _word_diff(asr_text: str, corrected_text: str) -> list[dict]:
    """Renvoie une liste de dicts (word, status) : 'same', 'insert', 'delete'."""
    if not asr_text or not corrected_text:
        return []
    ref_words = corrected_text.split()
    hyp_words = asr_text.split()
    sm = SequenceMatcher(None, ref_words, hyp_words)
    result = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for w in ref_words[i1:i2]:
                result.append({"word": w, "status": "same"})
        elif tag == "replace":
            for w in ref_words[i1:i2]:
                result.append({"word": w, "status": "delete"})
            for w in hyp_words[j1:j2]:
                result.append({"word": w, "status": "insert"})
        elif tag == "delete":
            for w in ref_words[i1:i2]:
                result.append({"word": w, "status": "delete"})
        elif tag == "insert":
            for w in hyp_words[j1:j2]:
                result.append({"word": w, "status": "insert"})
    return result


def corrections(request):
    """Page statistiques d'erreurs : CER, WER, graphiques, comparatif côte à côte."""
    qs = TranscriptionJob.objects.filter(status="completed").order_by("-created_at")

    rows = []
    total_cer = 0
    total_wer = 0
    corrected_count = 0

    for t in qs:
        asr = (t.transcript_text or "").strip()
        corr = (t.corrected_text or "").strip()
        # Utiliser le texte corrigé pour les statistiques si disponible, sinon l'original
        stats_text = corr if corr else asr
        wc = len(stats_text.split()) if stats_text else 0
        cc = len(stats_text) if stats_text else 0

        cer = 0.0
        wer = 0.0
        char_edits = 0
        word_edits = 0

        if corr and asr:
            char_edits = _levenshtein(corr, asr)
            cer = char_edits / len(corr) * 100
            word_edits = _levenshtein_words(corr, asr)
            wer = _compute_wer(corr, asr) * 100
            corrected_count += 1
            total_cer += cer
            total_wer += wer

        rows.append({
            "pk": t.pk,
            "filename": t.original_name or str(t.id),
            "asr_text": asr,
            "corrected_text": corr,
            "chars": cc,
            "words": wc,
            "char_edits": char_edits,
            "word_edits": word_edits,
            "cer": round(cer, 1),
            "wer": round(wer, 1),
            "has_correction": bool(corr),
        })

    summary = {
        "total": len(rows),
        "corrected": corrected_count,
        "avg_cer": round(total_cer / corrected_count, 1) if corrected_count else 0,
        "avg_wer": round(total_wer / corrected_count, 1) if corrected_count else 0,
    }

    # Données pour les graphiques (seulement les transcriptions corrigées)
    corr_rows = [r for r in rows if r["has_correction"]]
    chart_labels = [r["filename"][:22] for r in corr_rows]
    chart_cer = [r["cer"] for r in corr_rows]
    chart_wer = [r["wer"] for r in corr_rows]

    # Diff mot-à-mot pour chaque ligne corrigée
    for r in rows:
        r["diff"] = _word_diff(r["asr_text"], r["corrected_text"]) if r["has_correction"] else []
        r["diff_errors"] = sum(1 for d in r["diff"] if d["status"] != "same")

    # Export CSV si demandé
    if request.GET.get("export") == "csv":
        return _corrections_csv(rows)

    return render(
        request,
        "transcriptions/corrections.html",
        {
            "rows": rows,
            "summary": summary,
            "chart_labels": json.dumps(chart_labels),
            "chart_cer": json.dumps(chart_cer),
            "chart_wer": json.dumps(chart_wer),
            "active": "corrections",
        },
    )


def _corrections_csv(rows: list[dict]) -> HttpResponse:
    """Génère un CSV téléchargeable avec les métriques de correction."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="corrections.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "fichier", "mots_asr", "caracteres_asr", "erreurs_caracteres",
        "erreurs_mots", "cer_pct", "wer_pct", "texte_asr", "texte_corrige",
    ])
    for r in rows:
        writer.writerow([
            r["filename"], r["words"], r["chars"], r["char_edits"],
            r["word_edits"], f"{r['cer']:.1f}".replace(".", ","),
            f"{r['wer']:.1f}".replace(".", ","), r["asr_text"], r["corrected_text"],
        ])
    return response
