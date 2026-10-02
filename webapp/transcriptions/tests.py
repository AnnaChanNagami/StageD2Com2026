# coding=utf-8
"""
Tests unitaires de l'application Django `transcriptions`.

Périmètre couvert :
  - upload_validation : validation des fichiers téléversés (extension, type MIME,
    taille) et l'ordre dans lequel ces contrôles sont appliqués ;
  - qwen_service      : exports SRT / JSON, formatage de timestamps SRT, liste des
    langues supportées, machine à états du worker ;
  - views             : classement d'un message d'erreur, vues API (statut, stats),
    page d'accueil, téléchargement d'exports ;
  - models            : helpers de TranscriptionJob (segments, compteurs, cycle de vie).

Ce qui n'est PAS couvert, et pourquoi :
  - le chargement du modèle Qwen (poids plusieurs Go, GPU) ;
  - l'inférence réelle (nécessite le modèle) ;
  - l'écriture de fichiers sur disque via FileField (requiert un vrai MEDIA_ROOT ;
    les tests APIs utilisent des jobs dont le fichier n'est pas stocké).

Toutes les assertions ci-dessous ont été calées sur le comportement RÉEL observé
par sonde (exécutée sur ce dépôt, Django 5.2), pas sur des hypothèses.

Lancement :
    cd webapp && python manage.py test transcriptions -v 2
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader

from transcriptions import qwen_service as qs
from transcriptions import retention
from transcriptions import upload_validation as uv
from transcriptions.models import TranscriptionJob
from transcriptions.views import _classify_error


# =============================================================================
# upload_validation — validation de taille
# =============================================================================
class _FakeUploadedFile:
    """Objet minimal expposant `.size`, comme un UploadedFile Django."""

    def __init__(self, size: int):
        self.size = size


class TestValidateFileSize(SimpleTestCase):
    def test_small_file_accepted(self):
        # Pas d'exception = validation réussie.
        self.assertIsNone(uv.validate_file_size(_FakeUploadedFile(10)))

    def test_exactly_at_limit_accepted(self):
        # La borne est inclusive : `>` et non `>=`.
        self.assertIsNone(uv.validate_file_size(_FakeUploadedFile(uv.MAX_UPLOAD_SIZE)))

    def test_one_byte_over_limit_raises(self):
        with self.assertRaises(ValidationError):
            uv.validate_file_size(_FakeUploadedFile(uv.MAX_UPLOAD_SIZE + 1))

    def test_error_message_reports_size_in_mo(self):
        with self.assertRaises(ValidationError) as ctx:
            uv.validate_file_size(_FakeUploadedFile(uv.MAX_UPLOAD_SIZE + 1))
        msg = ctx.exception.messages[0]
        self.assertIn("trop volumineux", msg)
        self.assertIn("2000 Mo", msg)   # limite issue de settings (MAX_UPLOAD_SIZE_MB)

    def test_size_constant_matches_settings_mb(self):
        self.assertEqual(uv.MAX_UPLOAD_SIZE, uv.MAX_UPLOAD_SIZE_MB * 1024 * 1024)


# =============================================================================
# upload_validation — validation d'extension
# =============================================================================
class TestValidateExtension(SimpleTestCase):
    def test_every_allowed_extension_passes(self):
        # On itère sur la constante elle-même : le test suit ALLOWED_EXT.
        for ext in sorted(uv.ALLOWED_EXT):
            with self.subTest(ext=ext):
                self.assertIsNone(uv.validate_extension(f"essai{ext}"))

    def test_extension_is_case_insensitive(self):
        # Un utilisateur peut envoyer A.MP3 : la comparaison est en minuscules.
        self.assertIsNone(uv.validate_extension("A.MP3"))
        self.assertIsNone(uv.validate_extension("RECORDING.WAV"))

    def test_disallowed_extension_raises(self):
        for name in ("a.exe", "a.txt", "a.pdf", "script.sh"):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                uv.validate_extension(name)

    def test_missing_extension_raises(self):
        for name in ("noext", ""):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                uv.validate_extension(name)

    def test_error_message_says_none_found_when_no_extension(self):
        with self.assertRaises(ValidationError) as ctx:
            uv.validate_extension("noext")
        self.assertIn("'(aucune)'", ctx.exception.messages[0])

    def test_error_message_lists_allowed_extensions(self):
        with self.assertRaises(ValidationError) as ctx:
            uv.validate_extension("a.txt")
        for ext in sorted(uv.ALLOWED_EXT):
            self.assertIn(ext, ctx.exception.messages[0])

    def test_only_the_last_extension_is_considered(self):
        # 'archive.tar.gz' -> suffixe '.gz' -> refusé.
        with self.assertRaises(ValidationError) as ctx:
            uv.validate_extension("archive.tar.gz")
        self.assertIn("'.gz'", ctx.exception.messages[0])

    def test_none_filename_raises_instead_of_crashing(self):
        # filename=None arrive si un client envoie un nom vide ; pas de TypeError.
        with self.assertRaises(ValidationError):
            uv.validate_extension(None)


# =============================================================================
# upload_validation — validation du type MIME
# =============================================================================
class TestValidateMimeType(SimpleTestCase):
    def test_typical_audio_mimes_accepted(self):
        cases = [
            ("a.wav", "audio/wav"),
            ("a.wav", "audio/x-wav"),
            ("a.mp3", "audio/mpeg"),
            ("a.mp3", "audio/mpeg; codecs=mp3"),   # paramètres après ';' ignorés
            ("a.flac", "audio/flac"),
            ("a.opus", "audio/opus"),
            ("a.mkv", "application/ogg"),
            ("a.mp4", "video/mp4"),
            ("a.webm", "video/webm"),
        ]
        for name, content_type in cases:
            with self.subTest(name=name, ct=content_type):
                self.assertIsNone(uv.validate_mime_type(name, content_type))

    def test_mime_is_normalised_before_comparison(self):
        # Majuscules et espaces autour : 'AUDIO/WAV  ' doit passer.
        self.assertIsNone(uv.validate_mime_type("a.wav", "AUDIO/WAV"))
        self.assertIsNone(uv.validate_mime_type("a.wav", "  audio/wav  "))

    def test_any_audio_or_video_family_is_accepted(self):
        # La règle est un préfixe de famille ('audio/', 'video/'), pas une liste
        # d'exacts : un type exotique mais audio passe.
        self.assertIsNone(uv.validate_mime_type("a.wav", "audio/x-exotique"))

    def test_missing_mime_is_guessed_from_extension(self):
        # content_type absent -> mimetypes devine depuis le nom de fichier.
        for name in ("a.wav", "a.ogg", "a.mp3"):
            with self.subTest(name=name):
                self.assertIsNone(uv.validate_mime_type(name, None))

    def test_octet_stream_is_tolerated(self):
        # Valeur par défaut des navigateurs pour les conteneurs : on ne rejette pas.
        self.assertIsNone(uv.validate_mime_type("a.wav", "application/octet-stream"))
        self.assertIsNone(uv.validate_mime_type("a.mkv", "application/octet-stream"))
        self.assertIsNone(uv.validate_mime_type("a.mkv", "binary/octet-stream"))

    def test_obviously_wrong_mime_rejected(self):
        cases = [
            ("a.txt", "text/plain"),
            ("a.exe", "application/x-msdownload"),
            ("a.png", "image/png"),
            ("a.pdf", "application/pdf"),
        ]
        for name, content_type in cases:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                uv.validate_mime_type(name, content_type)

    def test_error_message_names_the_rejected_mime(self):
        with self.assertRaises(ValidationError) as ctx:
            uv.validate_mime_type("a.txt", "text/plain")
        self.assertIn("'text/plain'", ctx.exception.messages[0])

    def test_mime_rejection_uses_lowercased_value(self):
        # 'TEXT/PLAIN' est signalé en minuscules dans le message.
        with self.assertRaises(ValidationError) as ctx:
            uv.validate_mime_type("a.txt", "TEXT/PLAIN")
        self.assertIn("'text/plain'", ctx.exception.messages[0])


# =============================================================================
# upload_validation — validation combinée
# =============================================================================
class TestValidateAudioFile(SimpleTestCase):
    def test_valid_file_accepted(self):
        self.assertIsNone(uv.validate_audio_file("a.wav", "audio/wav", 100))

    def test_valid_uppercase_name_and_larger_size(self):
        self.assertIsNone(uv.validate_audio_file("record.MP3", "audio/mpeg", 5_000_000))

    def test_extension_is_checked_before_mime(self):
        # Les DEUX sont invalides : c'est le message d'extension qui remonte.
        with self.assertRaises(ValidationError) as ctx:
            uv.validate_audio_file("a.txt", "text/plain", 10)
        self.assertIn("non prise en charge", ctx.exception.messages[0])

    def test_mime_reported_when_extension_is_fine(self):
        with self.assertRaises(ValidationError) as ctx:
            uv.validate_audio_file("a.wav", "text/plain", 10)
        self.assertIn("Type de fichier non autorisé", ctx.exception.messages[0])

    def test_size_reported_last(self):
        with self.assertRaises(ValidationError) as ctx:
            uv.validate_audio_file("a.wav", "audio/wav", uv.MAX_UPLOAD_SIZE + 1)
        self.assertIn("trop volumineux", ctx.exception.messages[0])

    def test_all_three_invalid_reports_extension_only(self):
        # L'ordre des contrôles détermine quel message l'utilisateur voit.
        with self.assertRaises(ValidationError) as ctx:
            uv.validate_audio_file("a.txt", "text/plain", uv.MAX_UPLOAD_SIZE + 1)
        self.assertIn("non prise en charge", ctx.exception.messages[0])


# =============================================================================
# qwen_service — qwen_service._fmt_ts (formatage SRT)
# =============================================================================
class TestFmtTimestamp(SimpleTestCase):
    def test_zero(self):
        self.assertEqual(qs._fmt_ts(0), "00:00:00,000")
        self.assertEqual(qs._fmt_ts(0.0), "00:00:00,000")

    def test_simple_cases(self):
        self.assertEqual(qs._fmt_ts(1.5), "00:00:01,500")
        self.assertEqual(qs._fmt_ts(61.25), "00:01:01,250")
        self.assertEqual(qs._fmt_ts(3661.007), "01:01:01,007")

    def test_hour_boundary_is_not_rolled_over(self):
        # 3599.999 -> 00:59:59,999 (pas 01:00:00,000)
        self.assertEqual(qs._fmt_ts(3599.999), "00:59:59,999")
        self.assertEqual(qs._fmt_ts(7199.999), "01:59:59,999")

    def test_negative_and_none_clamped_to_zero(self):
        # Un timestamp aberrant ne doit pas produire un SRT illisible.
        self.assertEqual(qs._fmt_ts(-5), "00:00:00,000")
        self.assertEqual(qs._fmt_ts(None), "00:00:00,000")

    def test_millisecond_field_never_carries_to_four_digits(self):
        """
        Non-régression : la fraction de seconde est arrondie sur le TOTAL en
        millisecondes puis décomposée. Avant, on arrondissait la fraction seule,
        ce qui produisait 1000 ms (carry) donc '00:00:01,1000' — un champ à
        4 chiffres que la plupart des lecteurs SRT refusent.
        """
        self.assertEqual(qs._fmt_ts(1.9999), "00:00:02,000")
        self.assertEqual(qs._fmt_ts(0.9995), "00:00:01,000")
        self.assertEqual(qs._fmt_ts(59.9999), "00:01:00,000")

    def test_millisecond_field_always_has_exactly_three_digits(self):
        """Invariant global du format SRT, vérifié sur un balayage dense."""
        sec = 0.0
        while sec < 120.0:
            out = qs._fmt_ts(sec)
            with self.subTest(sec=sec):
                self.assertEqual(len(out), 12, out)
                self.assertTrue(out[8] == ",", out)
                self.assertTrue(out[9:].isdigit(), out)
                self.assertLessEqual(int(out[9:]), 999, out)
            sec += 0.0007

    def test_float_representation_error_does_not_lose_a_millisecond(self):
        """
        0.029 s est stocké en flottant comme 0.028999999999999998 : une
        troncature naïve de (sec - int(sec)) * 1000 donnerait 28 au lieu de 29.
        L'arrondi du total en ms absorbe cette erreur.
        """
        self.assertEqual(qs._fmt_ts(0.029), "00:00:00,029")
        self.assertEqual(qs._fmt_ts(1.029), "00:00:01,029")

    def test_sub_millisecond_values_round_to_zero(self):
        # round() de Python est « banker's » : round(0.5) = 0, round(1.5) = 2.
        self.assertEqual(qs._fmt_ts(0.0005), "00:00:00,000")
        self.assertEqual(qs._fmt_ts(0.0004), "00:00:00,000")


# =============================================================================
# qwen_service — build_srt
# =============================================================================
class TestBuildSrt(SimpleTestCase):
    SEGMENTS = [
        {"id": "seg_0001", "start": 0.0, "end": 1.5, "text": "Bonjour"},
        {"id": "seg_0002", "start": 2.0, "end": 3.0, "text": "le monde"},
    ]

    def test_two_segments_rendered_exactly(self):
        self.assertEqual(
            qs.build_srt(self.SEGMENTS),
            "1\n00:00:00,000 --> 00:00:01,500\nBonjour\n\n"
            "2\n00:00:02,000 --> 00:00:03,000\nle monde\n",
        )

    def test_index_is_one_based_and_follows_list_order(self):
        srt = qs.build_srt(self.SEGMENTS)
        self.assertTrue(srt.startswith("1\n"))
        self.assertIn("\n2\n", srt)

    def test_empty_list_yields_single_newline(self):
        # "\n".join([]) -> "" puis .strip() + "\n" -> "\n"
        self.assertEqual(qs.build_srt([]), "\n")

    def test_blank_text_segments_are_skipped(self):
        # Un segment vide ('   ') ne produit pas de sous-titre vide, et surtout
        # ne consomme pas de numéro : la numérotation reste 1, 2.
        segs = self.SEGMENTS + [{"id": "seg_0003", "start": 3.0, "end": 4.0, "text": "   "}]
        self.assertEqual(qs.build_srt(segs), qs.build_srt(self.SEGMENTS))

    def test_segment_without_text_key_is_skipped(self):
        # Segmentation incomplète : pas de KeyError, simplement ignoré.
        segs = self.SEGMENTS + [{"id": "seg_0004", "start": 4.0, "end": 5.0}]
        self.assertEqual(qs.build_srt(segs), qs.build_srt(self.SEGMENTS))

    def test_none_text_is_skipped(self):
        segs = self.SEGMENTS + [{"id": "seg_0005", "start": 5.0, "end": 6.0, "text": None}]
        self.assertEqual(qs.build_srt(segs), qs.build_srt(self.SEGMENTS))

    def test_index_continues_across_skipped_segments(self):
        """
        BUG CONNU, figé : le compteur i suit l'index de la liste source, pas le
        rang des sous-titres réellement émis. Avec un segment vide en position 2,
        le SRT contient '1' puis '3' — la numérotation SRT est discontinue.
        """
        segs = [
            {"id": "s1", "start": 0.0, "end": 1.0, "text": "un"},
            {"id": "s2", "start": 1.0, "end": 2.0, "text": "  "},
            {"id": "s3", "start": 2.0, "end": 3.0, "text": "trois"},
        ]
        self.assertEqual(
            qs.build_srt(segs),
            "1\n00:00:00,000 --> 00:00:01,000\nun\n\n"
            "3\n00:00:02,000 --> 00:00:03,000\ntrois\n",
        )

    def test_text_is_stripped(self):
        segs = [{"id": "s1", "start": 0.0, "end": 1.0, "text": "  espacé  "}]
        self.assertIn("\nespacé\n", qs.build_srt(segs))


# =============================================================================
# qwen_service — render_export
# =============================================================================
class TestRenderExport(SimpleTestCase):
    SEGMENTS = [
        {"id": "seg_0001", "start": 0.0, "end": 1.5, "text": "Bonjour"},
    ]

    def test_srt_delegates_to_build_srt(self):
        self.assertEqual(qs.render_export("srt", self.SEGMENTS), qs.build_srt(self.SEGMENTS))

    def test_json_is_indented_and_keeps_unicode(self):
        out = qs.render_export("json", self.SEGMENTS)
        self.assertIn('"text": "Bonjour"', out)
        self.assertIn("\n", out)          # indent=2 -> retour ligne
        self.assertNotIn("\\u", out)      # ensure_ascii=False
        self.assertTrue(out.endswith("\n"))

    def test_json_roundtrips_and_preserves_fields(self):
        payload = json.loads(qs.render_export("json", self.SEGMENTS))
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["text"], "Bonjour")
        self.assertEqual(payload[0]["start"], 0.0)
        self.assertEqual(payload[0]["end"], 1.5)
        self.assertEqual(payload[0]["id"], "seg_0001")

    def test_json_empty_list(self):
        self.assertEqual(json.loads(qs.render_export("json", [])), [])
        self.assertEqual(qs.render_export("json", []), "[]\n")

    def test_unknown_format_raises_value_error(self):
        for kind in ("txt", "", "SRT", "csv"):
            with self.subTest(kind=kind), self.assertRaises(ValueError) as ctx:
                qs.render_export(kind, self.SEGMENTS)
            self.assertIn(kind, str(ctx.exception))

    def test_unknown_format_raises_before_touching_segments(self):
        # Le format est validé avant l'itération : un segments invalide ne
        # provoque pas de KeyError mais bien une ValueError.
        with self.assertRaises(ValueError):
            qs.render_export("xml", [{"pas": "un segment"}])


# =============================================================================
# qwen_service — raw_transcript
# =============================================================================
class TestRawTranscript(SimpleTestCase):
    class _Job:
        transcript_text = ""

    def test_text_is_stripped_and_newline_terminated(self):
        job = self._Job()
        job.transcript_text = "  Bonjour le monde  "
        self.assertEqual(qs.raw_transcript(job), "Bonjour le monde\n")

    def test_empty_text_returns_newline(self):
        # Un job non transcrit rend un saut de ligne, pas None (affichage sûr).
        job = self._Job()
        job.transcript_text = ""
        self.assertEqual(qs.raw_transcript(job), "\n")

    def test_none_text_is_safe(self):
        job = self._Job()
        job.transcript_text = None
        self.assertEqual(qs.raw_transcript(job), "\n")

    def test_inner_whitespace_is_preserved(self):
        job = self._Job()
        job.transcript_text = "  a   b  "
        self.assertEqual(qs.raw_transcript(job), "a   b\n")


# =============================================================================
# qwen_service — métadonnées du service
# =============================================================================
class TestServiceMetadata(SimpleTestCase):
    def test_backend_available_matches_qwen_ok(self):
        self.assertEqual(qs.backend_available(), qs.QWEN_OK)

    def test_supported_languages_is_a_fresh_list_each_call(self):
        # list(...) : muter la liste retournée ne doit pas corrompre l'état.
        langs = qs.supported_languages()
        langs.append("Klingon")      # Pollution volontaire
        self.assertNotIn("Klingon", qs.supported_languages())

    def test_supported_languages_is_not_empty(self):
        self.assertGreater(len(qs.supported_languages()), 0)

    def test_known_languages_present(self):
        for lang in ("Chinese", "English", "French"):
            self.assertIn(lang, qs.supported_languages())

    def test_languages_have_no_duplicates(self):
        langs = qs.supported_languages()
        self.assertEqual(len(langs), len(set(langs)))

    def test_stages_cover_the_happy_path_and_errors(self):
        for stage in ("loading_model", "transcribing", "aligning", "parsing", "done", "error"):
            self.assertIn(stage, qs.STAGES)

    def test_every_stage_has_a_human_label(self):
        for stage, label in qs.STAGES.items():
            with self.subTest(stage=stage):
                self.assertIsInstance(label, str)
                self.assertTrue(label.strip())

    def test_runtime_info_degrades_without_backend(self):
        """
        runtime_info() ne doit jamais lever, même sans torch/modèle.
        On appelle get_model() pour de vrai (singleton) mais on tolère l'échec :
        la fonction retourne alors un dict 'unavailable'.
        """
        info = qs.runtime_info()
        self.assertIsInstance(info, dict)
        self.assertIn("backend", info)
        self.assertIn("model", info)
        self.assertIn("device", info)
        self.assertIn("dtype", info)


# =============================================================================
# views._classify_error — classement d'un message d'erreur
# =============================================================================
class TestClassifyError(SimpleTestCase):
    """
    La fonction prend un MESSAGE (str) et renvoie (catégorie, icône Bootstrap).

    L'ordre des `if` est significatif : la première branche qui matche gagne.
    Les tests encodent cet ordre, pas seulement les mots-clés isolés.
    """

    def _classify(self, msg: str):
        category, icon = _classify_error(msg)
        self.assertIsInstance(category, str)
        self.assertIsInstance(icon, str)
        self.assertNotEqual(category, icon)
        return category, icon

    # --- Mémoire GPU (branche la plus prioritaire) --------------------------
    def test_cuda_out_of_memory(self):
        self.assertEqual(
            self._classify("CUDA out of memory. Tried to allocate 2.00 GiB"),
            ("Mémoire GPU / CUDA", "bi-memory"),
        )

    def test_cuda_error_without_the_words_out_of_memory(self):
        self.assertEqual(
            self._classify("cuda runtime error"), ("Mémoire GPU / CUDA", "bi-memory")
        )

    def test_generic_oom_wording(self):
        self.assertEqual(
            self._classify("torch: oom detected"), ("Mémoire GPU / CUDA", "bi-memory")
        )

    # --- Modèle indisponible ------------------------------------------------
    def test_model_load_failure(self):
        self.assertEqual(
            self._classify("Failed to load model from local path"),
            ("Modèle indisponible", "bi-box-seam"),
        )

    def test_model_download_failure(self):
        self.assertEqual(
            self._classify("impossible de charger le modèle"),
            ("Modèle indisponible", "bi-box-seam"),
        )

    def test_model_mention_alone_is_not_a_model_error(self):
        # "model" sans "charg/load/download" ne matche pas cette branche.
        self.assertEqual(
            self._classify("bad model output"), ("Autre erreur", "bi-question-circle")
        )

    # --- Délai / réseau ----------------------------------------------------
    def test_timeout(self):
        self.assertEqual(
            self._classify("Request timeout after 30s"), ("Délai dépassé", "bi-clock-history")
        )

    def test_network_failure(self):
        self.assertEqual(
            self._classify("connection refused by peer"), ("Réseau", "bi-wifi-off")
        )

    def test_http_failure(self):
        self.assertEqual(
            self._classify("HTTP 500 from server"), ("Réseau", "bi-wifi-off")
        )

    def test_timeout_wins_over_network_branch(self):
        # 'timeout' est testé AVANT 'network' : il y a 'timeout' dans les deux
        # branches, c'est la première qui gagne.
        self.assertEqual(self._classify("connection timeout")[0], "Délai dépassé")

    # --- Format audio ------------------------------------------------------
    def test_bad_codec(self):
        self.assertEqual(
            self._classify("unsupported codec"), ("Format audio invalide", "bi-file-earmark-x")
        )

    def test_decode_error(self):
        self.assertEqual(
            self._classify("cannot decode stream"), ("Format audio invalide", "bi-file-earmark-x")
        )

    def test_format_mention_alone(self):
        self.assertEqual(
            self._classify("unknown format"), ("Format audio invalide", "bi-file-earmark-x")
        )

    # --- Permissions / disque ---------------------------------------------
    def test_permission_denied(self):
        self.assertEqual(
            self._classify("permission denied"), ("Permissions", "bi-shield-lock")
        )

    def test_no_space_left(self):
        self.assertEqual(
            self._classify("No space left on device"), ("Espace disque", "bi-device-hdd")
        )

    def test_space_mention_alone(self):
        self.assertEqual(
            self._classify("not enough disk space"), ("Espace disque", "bi-device-hdd")
        )

    def test_access_mention_alone(self):
        self.assertEqual(
            self._classify("access denied by policy"), ("Permissions", "bi-shield-lock")
        )

    # --- Authentification --------------------------------------------------
    def test_invalid_api_key(self):
        self.assertEqual(
            self._classify("401 Unauthorized: bad api key"), ("Authentification", "bi-key")
        )

    def test_token_expired(self):
        self.assertEqual(
            self._classify("token expiré"), ("Authentification", "bi-key")
        )

    def test_auth_mention_alone(self):
        self.assertEqual(
            self._classify("auth required"), ("Authentification", "bi-key")
        )

    # --- Interruption ------------------------------------------------------
    def test_process_killed(self):
        self.assertEqual(
            self._classify("worker killed by signal 9"), ("Interruption", "bi-x-octagon")
        )

    def test_interrupted_mention(self):
        self.assertEqual(
            self._classify("process interrupted"), ("Interruption", "bi-x-octagon")
        )

    # --- Mémoire RAM ------------------------------------------------------
    def test_ram_memory_error(self):
        self.assertEqual(
            self._classify("MemoryError"), ("Mémoire RAM", "bi-memory")
        )

    def test_plain_memory_mention(self):
        self.assertEqual(
            self._classify("out of system memory"), ("Mémoire RAM", "bi-memory")
        )

    def test_gpu_branch_wins_over_ram_branch(self):
        # 'cuda out of memory' matche 'memory' mais la branche GPU est prioritaire.
        self.assertEqual(self._classify("CUDA out of memory")[0], "Mémoire GPU / CUDA")

    # --- Repli ------------------------------------------------------------
    def test_unknown_message_is_other_error(self):
        self.assertEqual(
            self._classify("Quelque chose d'inattendu"), ("Autre erreur", "bi-question-circle")
        )

    def test_empty_message_is_uncategorised(self):
        self.assertEqual(self._classify(""), ("Non catégorisé", "bi-help-circle"))
        self.assertEqual(self._classify("    "), ("Non catégorisé", "bi-help-circle"))

    def test_result_is_case_insensitive(self):
        # Le message est mis en minuscules en interne.
        self.assertEqual(
            self._classify("cuda out of memory"), self._classify("CUDA OUT OF MEMORY")
        )

    def test_category_never_equals_icon(self):
        for msg in ("", "boom", "CUDA out of memory", "permission denied"):
            with self.subTest(msg=msg):
                self.assertNotEqual(*_classify_error(msg))

    # --- Non-régression : ordre des branches --------------------------------
    def test_keyboard_interrupt_is_classified_as_interruption(self):
        """
        "KeyboardInterrupt" contient la sous-chaîne "key" : si la branche
        Authentification était testée avant la branche Interruption, une
        interruption clavier serait affichée comme un problème de clé d'API.
        La branche Interruption est donc testée en premier.
        """
        self.assertEqual(
            self._classify("KeyboardInterrupt"), ("Interruption", "bi-x-octagon")
        )

    def test_keyboard_interrupt_full_sentence(self):
        self.assertEqual(
            self._classify("KeyboardInterrupt raised during transcription"),
            ("Interruption", "bi-x-octagon"),
        )

    def test_auth_errors_still_classified_as_auth(self):
        """La correction ne doit pas casser la vraie détection d'auth."""
        for msg in ("401 Unauthorized", "invalid api key", "missing token", "auth failed"):
            with self.subTest(msg=msg):
                self.assertEqual(
                    self._classify(msg), ("Authentification", "bi-key")
                )

    def test_timeout_wins_over_network(self):
        """"timeout" relève de « Délai dépassé », pas de « Réseau »."""
        self.assertEqual(
            self._classify("request timeout after 30s"), ("Délai dépassé", "bi-clock-history")
        )


# =============================================================================
# models.TranscriptionJob — helpers
# =============================================================================
class TestTranscriptionJobHelpers(TestCase):
    """
    Aucun accès base : on instancie le modèle en mémoire. `audio_file` n'est pas
    renseigné, seul son `.name` est posé manuellement quand nécessaire.
    """

    def test_str_uses_name_then_id(self):
        job = TranscriptionJob(original_name="essai.wav")
        self.assertEqual(str(job), "essai.wav (pending)")

    def test_str_falls_back_to_id_when_no_name(self):
        job = TranscriptionJob(original_name="")
        self.assertIn(str(job.pk), str(job))

    def test_status_default_is_pending(self):
        self.assertEqual(TranscriptionJob().status, TranscriptionJob.Status.PENDING)

    def test_total_words_ignores_empty_text(self):
        self.assertEqual(TranscriptionJob(transcript_text="").total_words(), 0)
        self.assertEqual(TranscriptionJob(transcript_text="   ").total_words(), 0)
        self.assertEqual(TranscriptionJob(transcript_text="un deux trois").total_words(), 3)

    def test_total_chars_counts_everything(self):
        self.assertEqual(TranscriptionJob(transcript_text="un deux trois").total_chars(), 13)
        self.assertEqual(TranscriptionJob(transcript_text="").total_chars(), 0)

    def test_parse_segments_empty_when_no_json(self):
        self.assertEqual(TranscriptionJob().parse_segments(), [])

    def test_parse_segments_sorted_by_start(self):
        job = TranscriptionJob(
            segments_json=json.dumps([{"id": "b", "start": 2.0}, {"id": "a", "start": 1.0}])
        )
        self.assertEqual(
            job.parse_segments(), [{"id": "a", "start": 1.0}, {"id": "b", "start": 2.0}]
        )

    def test_parse_segments_returns_empty_on_invalid_json(self):
        # Un segments_json corrompu ne doit pas faire planter une vue.
        job = TranscriptionJob(segments_json="{pas du json")
        self.assertEqual(job.parse_segments(), [])

    def test_parse_segments_handles_missing_start_key(self):
        job = TranscriptionJob(segments_json=json.dumps([{"id": "a"}]))
        self.assertEqual(job.parse_segments(), [{"id": "a"}])

    def test_media_name_is_the_basename(self):
        job = TranscriptionJob()
        job.audio_file.name = "uploads/abc/essai.wav"
        self.assertEqual(job.media_name(), "essai.wav")

    def test_elapsed_sec_is_none_without_timestamps(self):
        self.assertIsNone(TranscriptionJob().elapsed_sec)

    def test_ratio_audio_is_zero_without_data(self):
        self.assertEqual(TranscriptionJob().ratio_audio, 0.0)

    def test_ratio_audio_guards_against_zero_duration(self):
        # duration_sec=0 : pas de ZeroDivisionError.
        job = TranscriptionJob(duration_sec=0.0)
        job.started_at = timezone.now()
        job.completed_at = job.started_at + timedelta(seconds=10)
        self.assertEqual(job.ratio_audio, 0.0)


# =============================================================================
# models.TranscriptionJob — cycle de vie (avec base)
# =============================================================================
class TestTranscriptionJobLifecycle(TestCase):
    """Ces tests utilisent TestCase -> base de données de test isolée."""

    def test_create_and_read_back(self):
        job = TranscriptionJob.objects.create(
            original_name="essai.wav",
            content_type="audio/wav",
            file_size=1024,
        )
        fetched = TranscriptionJob.objects.get(pk=job.pk)
        self.assertEqual(fetched.original_name, "essai.wav")
        self.assertEqual(fetched.status, "pending")
        self.assertIsNotNone(fetched.created_at)

    def test_set_status_running_stamps_started_at_once(self):
        job = TranscriptionJob.objects.create(original_name="essai.wav")
        self.assertIsNone(job.started_at)

        job.set_status(TranscriptionJob.Status.RUNNING)
        first_start = job.started_at
        self.assertIsNotNone(first_start)

        # Un second passage en RUNNING ne réécrit pas started_at.
        job.set_status(TranscriptionJob.Status.RUNNING)
        self.assertEqual(job.started_at, first_start)

    def test_set_status_completed_stamps_completed_at_and_computes_elapsed(self):
        job = TranscriptionJob.objects.create(original_name="essai.wav")
        job.set_status(TranscriptionJob.Status.RUNNING)
        job.set_status(TranscriptionJob.Status.COMPLETED)
        self.assertIsNotNone(job.completed_at)
        self.assertIsNotNone(job.elapsed_sec)
        self.assertGreaterEqual(job.elapsed_sec, 0.0)

    def test_set_status_failed_also_stamps_completed_at(self):
        job = TranscriptionJob.objects.create(original_name="essai.wav")
        job.set_status(TranscriptionJob.Status.FAILED)
        self.assertEqual(job.status, "failed")
        self.assertIsNotNone(job.completed_at)

    def test_set_status_without_save_does_not_persist(self):
        job = TranscriptionJob.objects.create(original_name="essai.wav")
        job.set_status(TranscriptionJob.Status.RUNNING, save=False)
        job.refresh_from_db()
        self.assertEqual(job.status, "pending")

    def test_elapsed_sec_computed_from_persisted_timestamps(self):
        job = TranscriptionJob.objects.create(
            original_name="essai.wav",
            started_at=timezone.now() - timedelta(seconds=12),
            completed_at=timezone.now(),
        )
        self.assertAlmostEqual(job.elapsed_sec, 12.0, delta=1.0)

    def test_default_ordering_is_most_recent_first(self):
        old = TranscriptionJob.objects.create(original_name="vieux.wav")
        new = TranscriptionJob.objects.create(original_name="recent.wav")
        # On force des created_at distincts (timezone.now() a une résolution
        # suffisante, mais on l'explicite pour éviter toute ambiguïté).
        TranscriptionJob.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        self.assertEqual(TranscriptionJob.objects.first().pk, new.pk)


# =============================================================================
# Vues — API
# =============================================================================
class TestApiJobStatus(TestCase):
    def test_returns_404_for_unknown_id(self):
        from django.test import Client

        url = reverse("transcriptions:api_job_status", args=[uuid.uuid4()])
        response = Client().get(url)
        self.assertEqual(response.status_code, 404)


class TestApiJobStatusWithDb(TestCase):
    def _get(self, job):
        return self.client.get(reverse("transcriptions:api_job_status", args=[job.pk]))

    def test_pending_job_payload(self):
        job = TranscriptionJob.objects.create(original_name="essai.wav")
        data = self._get(job).json()
        self.assertEqual(data["id"], str(job.pk))
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["stage"], "")
        self.assertEqual(data["progress"], 0.0)
        self.assertEqual(data["segment_count"], 0)
        self.assertEqual(data["transcript_text"], "")
        self.assertEqual(data["original_name"], "essai.wav")
        self.assertIn("url", data)

    def test_progress_is_a_percentage(self):
        job = TranscriptionJob.objects.create(original_name="essai.wav", progress=0.42)
        self.assertEqual(self._get(job).json()["progress"], 42.0)

    def test_completed_job_exposes_text_and_elapsed(self):
        job = TranscriptionJob.objects.create(
            original_name="essai.wav",
            status=TranscriptionJob.Status.COMPLETED,
            progress=1.0,
            stage="done",
            transcript_text="Bonjour le monde",
            segment_count=2,
            language_detected="French",
            duration_sec=3.0,
        )
        data = self._get(job).json()
        self.assertEqual(data["transcript_text"], "Bonjour le monde")
        self.assertEqual(data["language_detected"], "French")
        self.assertEqual(data["segment_count"], 2)
        self.assertEqual(data["progress"], 100.0)
        self.assertEqual(data["stage"], "done")

    def test_failed_job_exposes_error(self):
        job = TranscriptionJob.objects.create(
            original_name="essai.wav",
            status=TranscriptionJob.Status.FAILED,
            error="CUDA out of memory",
        )
        data = self._get(job).json()
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["error"], "CUDA out of memory")

    def test_created_at_is_isoformat(self):
        job = TranscriptionJob.objects.create(original_name="essai.wav")
        self.assertEqual(self._get(job).json()["created_at"], job.created_at.isoformat())

    def test_response_is_json(self):
        job = TranscriptionJob.objects.create(original_name="essai.wav")
        response = self._get(job)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_post_is_not_allowed(self):
        job = TranscriptionJob.objects.create(original_name="essai.wav")
        self.assertEqual(self.client.post(reverse("transcriptions:api_job_status", args=[job.pk])).status_code, 405)

    def test_404_on_unknown_id_with_db(self):
        response = self.client.get(reverse("transcriptions:api_job_status", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)


# =============================================================================
# Vues — page d'accueil
# =============================================================================
class TestHomeView(TestCase):
    def test_renders_200(self):
        response = self.client.get(reverse("transcriptions:home"))
        self.assertEqual(response.status_code, 200)

    def test_context_exposes_upload_limits(self):
        from transcriptions.views import MAX_UPLOAD_BYTES

        context = self.client.get(reverse("transcriptions:home")).context
        self.assertEqual(context["max_upload_bytes"], MAX_UPLOAD_BYTES)

    def test_context_exposes_allowed_extensions(self):
        context = self.client.get(reverse("transcriptions:home")).context
        self.assertEqual(json.loads(context["allowed_ext_json"]), sorted(uv.ALLOWED_EXT))
        self.assertIn(".wav", context["allowed_accept"])

    def test_context_exposes_sorted_languages(self):
        context = self.client.get(reverse("transcriptions:home")).context
        self.assertEqual(context["languages"], sorted(qs.supported_languages()))

    # La vue appelle runtime_info() -> get_model() -> chargement du modèle réel.
    # On patche runtime_info pour ne pas charger les poids.
    def test_context_exposes_backend_availability(self):
        from unittest.mock import patch

        with patch("transcriptions.views.qwen_service.runtime_info", return_value={"backend": "stub"}):
            context = self.client.get(reverse("transcriptions:home")).context
        self.assertEqual(context["runtime"], {"backend": "stub"})

    def test_context_exposes_backend_available_flag(self):
        from unittest.mock import patch

        with patch("transcriptions.views.qwen_service.runtime_info", return_value={}):
            context = self.client.get(reverse("transcriptions:home")).context
        self.assertEqual(context["backend_available"], qs.backend_available())


# =============================================================================
# Vues — liste / dashboard
# =============================================================================
class TestJobListView(TestCase):
    def test_renders_with_empty_database(self):
        response = self.client.get(reverse("transcriptions:job_list"))
        self.assertEqual(response.status_code, 200)

    def test_renders_with_pinned_runtime_info(self):
        from unittest.mock import patch

        with patch("transcriptions.views.qwen_service.runtime_info", return_value={"backend": "stub"}):
            response = self.client.get(reverse("transcriptions:job_list"))
        self.assertEqual(response.status_code, 200)


# =============================================================================
# Vues — téléchargements
# =============================================================================
class TestDownloads(TestCase):
    def test_download_txt_for_unknown_job(self):
        response = self.client.get(reverse("transcriptions:download_txt", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_download_json_for_unknown_job(self):
        response = self.client.get(reverse("transcriptions:download_json", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_download_srt_for_unknown_job(self):
        response = self.client.get(reverse("transcriptions:download_srt", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_download_srt_returns_attachment(self):
        job = TranscriptionJob.objects.create(
            original_name="essai.wav", status=TranscriptionJob.Status.COMPLETED
        )
        response = self.client.get(reverse("transcriptions:download_srt", args=[job.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response.content.decode(), qs.build_srt([]))

    def test_download_srt_rejects_unfinished_job(self):
        """Contrainte réelle : SRT/JSON exigent le statut COMPLETED."""
        job = TranscriptionJob.objects.create(
            original_name="encours.wav", status=TranscriptionJob.Status.RUNNING
        )
        for name in ("download_srt", "download_json"):
            with self.subTest(name=name):
                response = self.client.get(reverse(f"transcriptions:{name}", args=[job.pk]))
                self.assertEqual(response.status_code, 400)

    def test_download_srt_uses_job_segments(self):
        job = TranscriptionJob.objects.create(
            original_name="essai.wav",
            status=TranscriptionJob.Status.COMPLETED,
            segments_json=json.dumps(
                [{"id": "seg_0001", "start": 0.0, "end": 1.5, "text": "Bonjour"}]
            ),
        )
        response = self.client.get(reverse("transcriptions:download_srt", args=[job.pk]))
        self.assertEqual(response.content.decode(), qs.build_srt(job.parse_segments()))

    # ---------------------------------------------------------------- export PDF
    def test_download_pdf_for_unknown_job(self):
        response = self.client.get(reverse("transcriptions:download_pdf", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_download_pdf_returns_real_pdf_attachment(self):
        """Le corps de la réponse doit être un PDF lisible, pas une page d'erreur."""
        job = TranscriptionJob.objects.create(
            original_name="essai.wav",
            status=TranscriptionJob.Status.COMPLETED,
            transcript_text="Bonjour le monde",
        )
        response = self.client.get(reverse("transcriptions:download_pdf", args=[job.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".pdf", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIsInstance(response.content, bytes)

    def test_download_pdf_rejects_unfinished_job(self):
        job = TranscriptionJob.objects.create(
            original_name="encours.wav", status=TranscriptionJob.Status.RUNNING
        )
        response = self.client.get(reverse("transcriptions:download_pdf", args=[job.pk]))
        self.assertEqual(response.status_code, 400)

    def test_download_pdf_contains_transcript_text(self):
        """Le texte de la transcription doit être extractible du PDF généré."""
        job = TranscriptionJob.objects.create(
            original_name="essai.wav",
            status=TranscriptionJob.Status.COMPLETED,
            transcript_text="Reunion de lancement du projet a Paris.",
        )
        response = self.client.get(reverse("transcriptions:download_pdf", args=[job.pk]))
        text = PdfReader(io.BytesIO(response.content)).pages[0].extract_text()
        self.assertIn("Reunion de lancement", text)

    def test_download_pdf_uses_corrected_text_when_requested(self):
        job = TranscriptionJob.objects.create(
            original_name="essai.wav",
            status=TranscriptionJob.Status.COMPLETED,
            transcript_text="version brute",
            corrected_text="version corrigee",
        )
        url = reverse("transcriptions:download_pdf", args=[job.pk])
        corrige = self.client.get(url + "?corrige=1")
        self.assertIn(
            "version corrigee", PdfReader(io.BytesIO(corrige.content)).pages[0].extract_text()
        )

    def test_download_pdf_handles_empty_transcript(self):
        """Un job terminé sans texte ne doit pas faire planter la génération."""
        job = TranscriptionJob.objects.create(
            original_name="vide.wav", status=TranscriptionJob.Status.COMPLETED, transcript_text=""
        )
        response = self.client.get(reverse("transcriptions:download_pdf", args=[job.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF-"))


# =============================================================================
# Module pdf_export — génération du PDF
# =============================================================================
class TestPdfExport(TestCase):
    """Tests du module pur, sans HTTP ni base de données."""

    def _pdf(self):
        from transcriptions.pdf_export import TranscriptPDF

        pdf = TranscriptPDF()
        pdf.setup_fonts()
        return pdf

    def test_tokens_keeps_latin_words_glued_with_their_space(self):
        """Les mots latins sortent en tokens distincts, séparés par un token d'espace."""
        pdf = self._pdf()
        self.assertEqual(
            pdf._tokens("bonjour le monde"),
            [
                ("bonjour", False),
                (" ", False),
                ("le", False),
                (" ", False),
                ("monde", False),
            ],
        )

    def test_tokens_does_not_mutate_its_input(self):
        """Régression : la liste retournée ne doit plus être aliasée sur l'entrée.

        Une mutation pendant l'itération provoquait une boucle infinie.
        """
        pdf = self._pdf()
        pdf._tokens("bonjour le monde")  # ne doit pas exploser
        self.assertEqual(pdf._tokens("a b"), [("a", False), (" ", False), ("b", False)])

    def test_tokens_splits_cjk_per_character(self):
        """Sans police CJK chargée, pas de découpage par caractère."""
        pdf = self._pdf()
        self.assertEqual(pdf._tokens("会議")[0][1], False)

    def test_tokens_splits_cjk_per_character_with_cjk_font(self):
        pdf = self._pdf()
        pdf.ensure_cjk_font()
        if pdf._cjk_font is None:
            self.skipTest("Aucune police CJK disponible sur ce systeme")
        self.assertEqual(
            pdf._tokens("会議anglaise"),
            [("会", True), ("議", True), ("anglaise", False)],
        )

    def test_is_cjk_covers_cjk_punctuation(self):
        """Segoe UI n'a pas les ponctuations CJK : elles doivent aller dans la police CJK."""
        from transcriptions.pdf_export import _is_cjk

        for ch in "。、「」（）":
            self.assertTrue(_is_cjk(ch), f"{ch} (U+{ord(ch):04X}) doit utiliser la police CJK")

    def test_build_returns_bytes_and_starts_with_pdf_magic(self):
        from transcriptions.pdf_export import build_transcript_pdf

        job = TranscriptionJob(
            status=TranscriptionJob.Status.COMPLETED, original_name="x.wav", transcript_text="Bonjour"
        )
        data = build_transcript_pdf(job)
        self.assertIsInstance(data, bytes)
        self.assertTrue(data.startswith(b"%PDF-"))


# =============================================================================
# Vues — création de job
# =============================================================================
class TestApiJobCreate(TestCase):
    """api_job_create : 201 + job persisté, 400 sur fichier absent ou extension refusée."""

    URL = "transcriptions:api_job_create"

    def _post(self, **fields):
        return self.client.post(reverse(self.URL), fields)

    def test_400_when_no_file_is_posted(self):
        response = self._post()
        self.assertEqual(response.status_code, 400)
        self.assertIn("Aucun fichier audio fourni", response.json()["error"])

    def test_400_when_extension_is_not_allowed(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self._post(
            audio_file=SimpleUploadedFile("notes.txt", b"x", content_type="text/plain")
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(".txt", response.json()["error"])

    def test_201_and_persists_job(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self._post(
            audio_file=SimpleUploadedFile("essai.wav", b"RIFF0000", content_type="audio/wav")
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], TranscriptionJob.Status.PENDING)
        job = TranscriptionJob.objects.get(id=data["id"])
        self.assertEqual(job.original_name, "essai.wav")
        self.assertEqual(job.file_size, 8)
        self.assertEqual(job.content_type, "audio/wav")
        self.assertEqual(data["url"], reverse("transcriptions:job_detail", args=[job.pk]))

    def test_unknown_language_falls_back_to_autodetect(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self._post(
            audio_file=SimpleUploadedFile("essai.wav", b"RIFF", content_type="audio/wav"),
            language="Klingon",
        )
        self.assertEqual(response.status_code, 201)
        job = TranscriptionJob.objects.get(id=response.json()["id"])
        self.assertEqual(job.language, "")

    def test_supported_language_is_kept(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self._post(
            audio_file=SimpleUploadedFile("essai.wav", b"RIFF", content_type="audio/wav"),
            language="French",
        )
        job = TranscriptionJob.objects.get(id=response.json()["id"])
        self.assertEqual(job.language, "French")

    def test_max_new_tokens_default_and_override(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self._post(
            audio_file=SimpleUploadedFile("essai.wav", b"RIFF", content_type="audio/wav")
        )
        job = TranscriptionJob.objects.get(id=response.json()["id"])
        self.assertEqual(job.max_new_tokens, 512)

        response = self._post(
            audio_file=SimpleUploadedFile("essai2.wav", b"RIFF", content_type="audio/wav"),
            max_new_tokens="256",
        )
        job = TranscriptionJob.objects.get(id=response.json()["id"])
        self.assertEqual(job.max_new_tokens, 256)

    def test_original_name_is_truncated_to_500_chars(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        long_name = "a" * 600 + ".wav"
        response = self._post(
            audio_file=SimpleUploadedFile(long_name, b"RIFF", content_type="audio/wav")
        )
        job = TranscriptionJob.objects.get(id=response.json()["id"])
        # La vue tronque à 500 ; le champ est en plus limité à 512 et Django
        # tronque les noms de fichiers uploadés à 255 caractères.
        self.assertLessEqual(len(job.original_name), 500)

    def test_timestamps_flag_is_read_from_several_truthy_values(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        for value, expected in (("1", True), ("true", True), ("on", True), ("0", False)):
            with self.subTest(value=value):
                response = self._post(
                    audio_file=SimpleUploadedFile("essai.wav", b"RIFF", content_type="audio/wav"),
                    timestamps=value,
                )
                job = TranscriptionJob.objects.get(id=response.json()["id"])
                self.assertEqual(job.want_timestamps, expected)

    def test_get_is_rejected(self):
        # @require_POST : un GET doit être refusé.
        self.assertEqual(self.client.get(reverse(self.URL)).status_code, 405)


# =============================================================================
# Vues — statistiques et suppression
# =============================================================================
class TestStatsAndDelete(TestCase):
    """api_stats : compteurs par statut + cumul sur les jobs terminés."""

    def test_api_stats_renders_as_json(self):
        response = self.client.get(reverse("transcriptions:api_stats"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_api_stats_on_empty_database(self):
        data = self.client.get(reverse("transcriptions:api_stats")).json()
        self.assertEqual(data["total"], 0)
        for key in ("completed", "failed", "running", "total_audio_sec", "total_process_sec", "total_words"):
            self.assertEqual(data[key], 0, msg=key)

    def test_pending_and_running_are_grouped_as_running(self):
        TranscriptionJob.objects.create(
            original_name="a.wav", status=TranscriptionJob.Status.PENDING
        )
        TranscriptionJob.objects.create(
            original_name="b.wav", status=TranscriptionJob.Status.RUNNING
        )
        data = self.client.get(reverse("transcriptions:api_stats")).json()
        self.assertEqual(data["running"], 2)
        self.assertEqual(data["completed"], 0)

    def test_counts_are_split_by_status(self):
        for status in (
            TranscriptionJob.Status.PENDING,
            TranscriptionJob.Status.COMPLETED,
            TranscriptionJob.Status.FAILED,
        ):
            TranscriptionJob.objects.create(original_name=f"{status}.wav", status=status)
        data = self.client.get(reverse("transcriptions:api_stats")).json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["completed"], 1)
        self.assertEqual(data["failed"], 1)
        self.assertEqual(data["running"], 1)

    def test_cumulates_audio_seconds_only_over_completed_jobs(self):
        now = timezone.now()
        TranscriptionJob.objects.create(
            original_name="fait.wav",
            status=TranscriptionJob.Status.COMPLETED,
            duration_sec=10.0,
            created_at=now,
            started_at=now,
            completed_at=now + timedelta(seconds=4),
            transcript_text="un deux trois",
        )
        # Job non terminé : sa durée ne doit pas entrer dans le cumul.
        TranscriptionJob.objects.create(
            original_name="encours.wav",
            status=TranscriptionJob.Status.RUNNING,
            duration_sec=999.0,
        )
        data = self.client.get(reverse("transcriptions:api_stats")).json()
        self.assertEqual(data["total_audio_sec"], 10.0)
        # elapsed_sec se mesure entre started_at et completed_at.
        self.assertEqual(data["total_process_sec"], 4.0)
        self.assertEqual(data["total_words"], 3)

    def test_get_only_endpoint_rejects_post(self):
        response = self.client.post(reverse("transcriptions:api_stats"))
        self.assertEqual(response.status_code, 405)


# =============================================================================
# retention — politique de conservation RGPD (6 mois)
# =============================================================================
class TestRetentionConfig(SimpleTestCase):
    """Durée de conservation : 6 mois par défaut, surchargeable par settings."""

    def test_default_is_six_months(self):
        # RGPD_RETENTION_MONTHS est défini à 6 dans settings.py.
        self.assertEqual(retention.retention_months(), 6)

    def test_six_months_converts_to_about_183_days(self):
        # 6 * 30.44 = 182.64 -> 183 jours.
        self.assertEqual(retention.retention_days(), 183)

    def test_retention_is_never_below_one_month(self):
        with self.settings(RGPD_RETENTION_MONTHS=0):
            self.assertEqual(retention.retention_months(), 1)
        with self.settings(RGPD_RETENTION_MONTHS=-5):
            self.assertEqual(retention.retention_months(), 1)

    def test_cutoff_is_six_months_in_the_past(self):
        from datetime import timedelta

        now = timezone.now()
        gap = now - retention.retention_cutoff(now)
        self.assertAlmostEqual(gap.total_seconds() / 86400, 183, delta=1)

    def test_automatic_purge_is_enabled_by_default(self):
        self.assertTrue(retention.is_enabled())

    def test_automatic_purge_can_be_disabled(self):
        with self.settings(RGPD_AUTO_PURGE=False):
            self.assertFalse(retention.is_enabled())


class TestPurgeReport(SimpleTestCase):
    def test_summary_reports_counts(self):
        report = retention.PurgeReport(rows_deleted=3, files_deleted=3, dirs_removed=2)
        text = report.summary()
        self.assertIn("3 transcription(s)", text)
        self.assertIn("3 fichier(s) audio", text)
        self.assertIn("2 dossier(s) vide(s)", text)

    def test_summary_marks_dry_run(self):
        self.assertIn("SIMULATION", retention.PurgeReport(dry_run=True).summary())

    def test_ok_is_false_when_errors_occurred(self):
        self.assertTrue(retention.PurgeReport().ok)
        self.assertFalse(retention.PurgeReport(errors=["boom"]).ok)


class TestPurgeExpiredJobs(TestCase):
    """Purge : la date de référence est `created_at`, pas `completed_at`."""

    def _job(self, *, age_days, status=TranscriptionJob.Status.COMPLETED):
        job = TranscriptionJob.objects.create(original_name="essai.wav", status=status)
        TranscriptionJob.objects.filter(pk=job.pk).update(
            created_at=timezone.now() - timedelta(days=age_days)
        )
        job.refresh_from_db()
        return job

    def test_recent_job_is_kept(self):
        job = self._job(age_days=10)
        report = retention.purge_expired_jobs()
        self.assertEqual(report.rows_deleted, 0)
        self.assertTrue(TranscriptionJob.objects.filter(pk=job.pk).exists())

    def test_job_older_than_retention_is_deleted(self):
        job = self._job(age_days=retention.retention_days() + 1)
        report = retention.purge_expired_jobs()
        self.assertEqual(report.rows_deleted, 1)
        self.assertFalse(TranscriptionJob.objects.filter(pk=job.pk).exists())

    def test_job_just_inside_retention_is_kept(self):
        # Borne : la purge ne doit pas manger la fringe de rétention.
        job = self._job(age_days=retention.retention_days() - 1)
        retention.purge_expired_jobs()
        self.assertTrue(TranscriptionJob.objects.filter(pk=job.pk).exists())

    def test_failed_jobs_are_purged_too(self):
        # Une transcription en échec contient la même donnée personnelle.
        job = self._job(age_days=400, status=TranscriptionJob.Status.FAILED)
        retention.purge_expired_jobs()
        self.assertFalse(TranscriptionJob.objects.filter(pk=job.pk).exists())

    def test_active_jobs_are_never_purged(self):
        """
        Un job PENDING/RUNNING peut être dans la file du worker : l'effacer
        ferait disparaître le fichier sous ses pieds.
        """
        for index, status in enumerate(
            (TranscriptionJob.Status.PENDING, TranscriptionJob.Status.RUNNING), start=1
        ):
            with self.subTest(status=status):
                job = self._job(age_days=400, status=status)
                report = retention.purge_expired_jobs()
                self.assertEqual(report.rows_deleted, 0)
                # Le compteur cumule les jobs actifs des sous-tests précédents.
                self.assertEqual(report.skipped_active, index)
                self.assertTrue(TranscriptionJob.objects.filter(pk=job.pk).exists())

    def test_dry_run_changes_nothing(self):
        job = self._job(age_days=400)
        report = retention.purge_expired_jobs(dry_run=True)
        self.assertEqual(report.rows_deleted, 1)          # compté...
        self.assertTrue(TranscriptionJob.objects.filter(pk=job.pk).exists())  # ...mais pas supprimé

    def test_keep_rows_preserves_the_database_line(self):
        job = self._job(age_days=400)
        retention.purge_expired_jobs(keep_rows=True)
        self.assertTrue(TranscriptionJob.objects.filter(pk=job.pk).exists())

    def test_explicit_reference_date_is_honoured(self):
        job = self._job(age_days=10)
        # En simulant « il était dans 1 an », le job de 10 jours devient hors délai.
        report = retention.purge_expired_jobs(reference=timezone.now() + timedelta(days=365))
        self.assertEqual(report.rows_deleted, 1)
        self.assertFalse(TranscriptionJob.objects.filter(pk=job.pk).exists())

    def test_error_in_one_job_does_not_stop_the_others(self):
        old_a = self._job(age_days=400)
        old_b = self._job(age_days=401)
        keep = self._job(age_days=1)

        # On fait échouer la suppression du premier job.
        original_delete = TranscriptionJob.delete

        def flaky(self, *args, **kwargs):
            if self.pk == old_a.pk:
                raise RuntimeError("verrou de base de donnees")
            return original_delete(self, *args, **kwargs)

        with patch.object(TranscriptionJob, "delete", flaky):
            report = retention.purge_expired_jobs()

        self.assertEqual(report.rows_deleted, 1)
        self.assertEqual(len(report.errors), 1)
        self.assertIn("verrou de base de donnees", report.errors[0])
        self.assertFalse(TranscriptionJob.objects.filter(pk=old_b.pk).exists())
        self.assertTrue(TranscriptionJob.objects.filter(pk=keep.pk).exists())


class TempMediaRootMixin:
    """
    Isole le test sur un MEDIA_ROOT temporaire jetable.

    IMPÉRATIF : sans cela, un test qui appelle `purge_orphan_files()` parcours
    le VRAI `webapp/media/uploads/`. Comme `TestCase` utilise une base de test
    séparée de la base de production, aucune ligne réelle n'y est visible : tous
    les dossiers de production paraissent alors orphelins et sont supprimés.
    Ce mixin crée ses propres dossiers, qu'on peut effacer sans casse.

    L'isolation est par TEST (`setUp`), pas par classe : les tests qui laissent
    volontairement un dossier derrière (ex. `--dry-run`) ne doivent pas polluer
    les comptages des suivants.
    """

    def setUp(self):
        super().setUp()
        self._temp_media = tempfile.mkdtemp(prefix="qwen-test-media-")
        self.addCleanup(shutil.rmtree, self._temp_media, ignore_errors=True)
        media_override = override_settings(MEDIA_ROOT=self._temp_media)
        media_override.enable()
        self.addCleanup(media_override.disable)


class TestPurgeOrphanFiles(TempMediaRootMixin, TestCase):
    """Le filet de sécurité : dossiers audio sans job correspondant."""

    def _orphan_dir(self, name="essai.wav"):
        """Crée un dossier uploads/<uuid>/ avec un fichier, SANS ligne en base."""
        from django.core.files.base import ContentFile

        orphan_id = uuid.uuid4()
        d = Path(self._temp_media) / "uploads" / str(orphan_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(b"RIFF0000WAVEfmt ")
        return d

    def test_orphan_directory_is_removed(self):
        # Ancien de plus de la durée de conservation, sinon le garde-fou l'ignore.
        d = self._orphan_dir()
        old = timezone.now().timestamp() - (retention.retention_days() + 1) * 86400
        os.utime(d, (old, old))

        removed = retention.purge_orphan_files()
        self.assertEqual(removed, 1)
        self.assertFalse(d.exists())

    def test_recent_orphan_is_left_alone(self):
        """
        Garde-fou anti-upload-cassé : un dossier créé il y a peu peut être un
        upload en cours dont la ligne n'est pas encore en base.
        """
        d = self._orphan_dir()
        self.assertEqual(retention.purge_orphan_files(), 0)
        self.assertTrue(d.exists())

    def test_force_deletes_a_recent_orphan(self):
        d = self._orphan_dir()
        # `force=True` ignore l'âge mais pas les dossiers d'un job vivant :
        # notre dossier orphelin n'est le SEUL candidat car aucun autre n'existe
        # dans le MEDIA_ROOT temporaire.
        self.assertEqual(retention.purge_orphan_files(force=True), 1)
        self.assertFalse(d.exists())

    def test_directory_of_a_live_job_is_preserved(self):
        from django.core.files.base import ContentFile

        job = TranscriptionJob.objects.create(original_name="vivant.wav")
        job.audio_file.save("essai.wav", ContentFile(b"RIFF0000"), save=True)
        path = job.audio_file.path

        self.assertEqual(retention.purge_orphan_files(force=True), 0)
        self.assertTrue(os.path.exists(path))

    def test_dry_run_counts_without_deleting(self):
        d = self._orphan_dir()
        old = timezone.now().timestamp() - (retention.retention_days() + 1) * 86400
        os.utime(d, (old, old))

        removed = retention.purge_orphan_files(dry_run=True)
        self.assertEqual(removed, 1)
        self.assertTrue(d.exists())

    def test_missing_uploads_root_is_not_an_error(self):
        with self.settings(MEDIA_ROOT=os.path.join(self._temp_media, "absent")):
            self.assertEqual(retention.purge_orphan_files(), 0)

    def test_expiry_and_orphan_purge_do_not_touch_each_other(self):
        """Un job expiré purge son dossier par la purge DB, pas par les orphelins."""
        from django.core.files.base import ContentFile

        job = TranscriptionJob.objects.create(
            original_name="expire.wav", status=TranscriptionJob.Status.COMPLETED
        )
        job.audio_file.save("expire.wav", ContentFile(b"RIFF0000"), save=True)
        job_dir = Path(job.audio_file.path).parent
        TranscriptionJob.objects.filter(pk=job.pk).update(
            created_at=timezone.now() - timedelta(days=retention.retention_days() + 1)
        )

        report = retention.purge_expired_jobs()
        self.assertEqual(report.rows_deleted, 1)
        self.assertEqual(report.files_deleted, 1)
        self.assertFalse(job_dir.exists())


class TestPurgeExpiredCommand(TestCase):
    """La commande `manage.py purge_expired` doit exposer la politique et purger."""

    def _call(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("purge_expired", *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def _old_job(self, age_days=400):
        job = TranscriptionJob.objects.create(
            original_name="essai.wav", status=TranscriptionJob.Status.COMPLETED
        )
        TranscriptionJob.objects.filter(pk=job.pk).update(
            created_at=timezone.now() - timedelta(days=age_days)
        )
        return job

    def test_status_reports_six_months_without_purging(self):
        job = self._old_job()
        output = self._call("--status")
        self.assertIn("6 mois", output)
        self.assertIn("1 hors délai", output)
        self.assertTrue(TranscriptionJob.objects.filter(pk=job.pk).exists())

    def test_dry_run_output_is_labelled_as_simulation(self):
        job = self._old_job()
        output = self._call("--dry-run")
        self.assertIn("SIMULATION", output)
        self.assertTrue(TranscriptionJob.objects.filter(pk=job.pk).exists())

    def test_command_purges_expired_jobs(self):
        job = self._old_job()
        self._call()
        self.assertFalse(TranscriptionJob.objects.filter(pk=job.pk).exists())

    def test_keep_rows_flag_preserves_the_line(self):
        job = self._old_job()
        self._call("--keep-rows")
        self.assertTrue(TranscriptionJob.objects.filter(pk=job.pk).exists())
