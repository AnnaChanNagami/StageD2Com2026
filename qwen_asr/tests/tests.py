# coding=utf-8
"""
Tests unitaires de qwen_asr/inference/utils.py

Pourquoi un chargement « standalone » de utils.py ?
-----------------------------------------------
`import qwen_asr.inference.utils` (en mode package) déclenche le
`__init__.py` de qwen_asr, qui charge torch / transformers et peut épuiser la
mémoire (MemoryError). Or les fonctions testées ici sont **pures** (aucune
inférence) : on charge donc directement le fichier via importlib, sans passer
par le package.

Ces tests ne couvrent volontairement pas :
  - le chargement réel du modèle (trop lourd / dépendant du GPU) ;
  - la dépendance réseau (URL, download de poids) ;
  - les entrées audio réelles (URL, base64) : cf. TestNormalizeAudioInput.

Exécution : la configuration pytest vit dans pyproject.toml
([tool.pytest.ini_options]), donc depuis la racine du dépôt :

    python -m pytest -q

Pour ne lancer que cette suite :

    python -m pytest qwen_asr/tests/tests.py -q
"""
from __future__ import annotations

import importlib.util as iu
from pathlib import Path

import numpy as np
import pytest

# --- Chargement standalone du module sous test ------------------------------
_MODULE_PATH = Path(__file__).resolve().parent.parent / "inference" / "utils.py"
_spec = iu.spec_from_file_location("_qwen_utils_under_test", _MODULE_PATH)
utils = iu.module_from_spec(_spec)
_spec.loader.exec_module(utils)


# =============================================================================
# normalize_language_name
# =============================================================================
class TestNormalizeLanguageName:
    """Première lettre en majuscule, le reste en minuscules."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("cHINese", "Chinese"),
            ("  french  ", "French"),   # espaces autour tolérés
            ("ENGLISH", "English"),
            ("x", "X"),
            ("French", "French"),       # déjà normalisé = idempotent
        ],
    )
    def test_normalizes(self, raw, expected):
        assert utils.normalize_language_name(raw) == expected

    def test_idempotent(self):
        once = utils.normalize_language_name("pOrTuguESE")
        assert utils.normalize_language_name(once) == once == "Portuguese"

    @pytest.mark.parametrize("bad", [None, "", "   "])
    def test_raises_on_empty_or_none(self, bad):
        with pytest.raises(ValueError):
            utils.normalize_language_name(bad)


# =============================================================================
# validate_language
# =============================================================================
class TestValidateLanguage:
    @pytest.mark.parametrize("lang", ["French", "Chinese", "English", "Macedonian"])
    def test_accepts_supported(self, lang):
        assert utils.validate_language(lang) is None  # pas d'exception = succès

    @pytest.mark.parametrize("bad", ["Klingon", "french", "", "FRENCH"])
    def test_raises_on_unsupported(self, bad):
        # 'french' échoue aussi : la comparaison est sensible à la casse,
        # il faut normaliser d'abord avec normalize_language_name.
        with pytest.raises(ValueError):
            utils.validate_language(bad)

    def test_error_message_lists_supported(self):
        with pytest.raises(ValueError) as exc:
            utils.validate_language("Klingon")
        assert "Klingon" in str(exc.value)
        assert "French" in str(exc.value)  # la liste des langues est jointe


# =============================================================================
# ensure_list / is_url / is_probably_base64 / decode_base64_bytes
# =============================================================================
class TestMaybeListHelpers:
    def test_ensure_list_wraps_scalar(self):
        assert utils.ensure_list(1) == [1]
        assert utils.ensure_list("ab") == ["ab"]

    def test_ensure_list_passes_list_through(self):
        payload = [1, 2]
        assert utils.ensure_list(payload) is payload

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("http://a.com/x.wav", True),
            ("https://a.com", True),
            ("ftp://a.com", False),     # schéma non supporté
            ("a/b.wav", False),         # chemin local
            ("", False),
        ],
    )
    def test_is_url(self, raw, expected):
        assert utils.is_url(raw) is expected

    def test_is_probably_base64(self):
        assert utils.is_probably_base64("data:audio/wav;base64,AAA") is True
        assert utils.is_probably_base64("A" * 300) is True     # long, sans séparateur
        assert utils.is_probably_base64("a/b.wav") is False     # a un chemin
        assert utils.is_probably_base64("A" * 10) is False      # trop court

    def test_decode_base64_bytes(self):
        assert utils.decode_base64_bytes("aGVsbG8=") == b"hello"

    def test_decode_base64_strips_data_uri_prefix(self):
        assert utils.decode_base64_bytes("data:audio/wav;base64,aGVsbG8=") == b"hello"


# =============================================================================
# to_mono / float_range_normalize
# =============================================================================
class TestAudioShaping:
    def test_to_mono_passthrough_1d(self):
        x = np.zeros(10, dtype=np.float32)
        assert utils.to_mono(x) is x

    def test_to_mono_averages_channels_t_by_c(self):
        # soundfile renvoie (T, C) : on moyenne sur le dernier axe.
        stereo = np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]], dtype=np.float32)
        mono = utils.to_mono(stereo)
        assert mono.shape == (3,)
        assert np.allclose(mono, 0.5)  # moyenne de (1.0, 0.0)

    def test_to_mono_transposes_c_by_t(self):
        # (C, T) avec peu de canaux -> transposition avant moyennage.
        c_by_t = np.array([[1.0, 0.5, 0.0], [0.0, 0.5, 1.0]], dtype=np.float32)  # (2, 3)
        mono = utils.to_mono(c_by_t)
        assert mono.shape == (3,)

    def test_to_mono_raises_on_3d(self):
        with pytest.raises(ValueError):
            utils.to_mono(np.zeros((2, 2, 2), dtype=np.float32))

    def test_float_range_normalize_scales_down(self):
        # Crête > 1 : le signal est ramené dans [-1, 1].
        out = utils.float_range_normalize(np.array([2.0, -2.0, 0.0], dtype=np.float32))
        assert np.allclose(out, [1.0, -1.0, 0.0])

    def test_float_range_normalize_clips(self):
        out = utils.float_range_normalize(np.array([0.5, -0.5], dtype=np.float32))
        assert np.allclose(out, [0.5, -0.5])

    def test_float_range_normalize_handles_silence(self):
        out = utils.float_range_normalize(np.zeros(4, dtype=np.float32))
        assert out.shape == (4,)

    def test_float_range_normalize_empty(self):
        out = utils.float_range_normalize(np.array([], dtype=np.float32))
        assert out.size == 0


# =============================================================================
# normalize_audio_input / normalize_audios
# =============================================================================
class TestNormalizeAudioInput:
    def test_from_tuple_16k(self):
        wav = np.zeros(1600, dtype=np.float32)
        out = utils.normalize_audio_input((wav, 16000))
        assert out.dtype == np.float32
        assert out.shape == (1600,)

    def test_resamples_to_16k(self):
        wav = np.zeros(8000, dtype=np.float32)   # 8 kHz
        out = utils.normalize_audio_input((wav, 8000))
        # 8000 échantillons à 8 kHz = 1 s -> 16000 échantillons à 16 kHz.
        assert out.shape[0] == pytest.approx(16000, rel=0.01)

    def test_mono_conversion_applied(self):
        stereo = np.zeros((100, 2), dtype=np.float32)
        out = utils.normalize_audio_input((stereo, 16000))
        assert out.ndim == 1

    def test_raises_on_bad_type(self):
        with pytest.raises(TypeError):
            utils.normalize_audio_input(123)

    def test_normalize_audios_handles_list(self):
        items = [(np.zeros(16, dtype=np.float32), 16000), (np.zeros(8, dtype=np.float32), 8000)]
        out = utils.normalize_audios(items)
        assert len(out) == 2
        assert all(o.ndim == 1 for o in out)


# =============================================================================
# chunk_list
# =============================================================================
class TestChunkList:
    def test_splits_evenly(self):
        assert list(utils.chunk_list([1, 2, 3, 4, 5, 6], 3)) == [[1, 2, 3], [4, 5, 6]]

    def test_last_chunk_is_ragged(self):
        assert list(utils.chunk_list([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]

    @pytest.mark.parametrize("size", [0, -1])
    def test_non_positive_size_returns_whole_list(self, size):
        assert list(utils.chunk_list([1, 2, 3], size)) == [[1, 2, 3]]

    def test_size_larger_than_list(self):
        assert list(utils.chunk_list([1, 2, 3], 10)) == [[1, 2, 3]]

    def test_empty_list(self):
        assert list(utils.chunk_list([], 3)) == []


# =============================================================================
# detect_and_fix_repetitions
# =============================================================================
class TestDetectAndFixRepetitions:
    """Comportements relevés sur l'implémentation réelle (seuil par défaut = 20)."""

    def test_no_repetition_unchanged(self):
        assert utils.detect_and_fix_repetitions("hello world") == "hello world"

    def test_empty_unchanged(self):
        assert utils.detect_and_fix_repetitions("") == ""

    def test_long_char_run_collapsed(self):
        # 30 'a' consécutifs (30 > seuil 20) -> une seule lettre.
        assert utils.detect_and_fix_repetitions("a" * 30) == "a"

    def test_short_char_run_kept(self):
        # 20 'a' exactement : count > thresh est FAUX (20 > 20), donc conservé.
        assert utils.detect_and_fix_repetitions("a" * 20) == "a" * 20

    def test_threshold_is_strict(self):
        # 21 'a' -> réduit ; 20 'a' -> intact. Le seuil est strict (>) .
        assert utils.detect_and_fix_repetitions("a" * 21) == "a"
        assert utils.detect_and_fix_repetitions("a" * 20) == "a" * 20

    def test_char_run_then_other_text(self):
        assert utils.detect_and_fix_repetitions("a" * 25 + "b") == "ab"

    def test_pattern_repeats_collapsed(self):
        # "ab" répété 25 fois = motif de longueur 2 (>= 2*seuil) -> réduit à "ab".
        assert utils.detect_and_fix_repetitions("ab" * 25) == "ab"

    def test_pattern_repeats_just_below_threshold_kept(self):
        # "ab" x 15 = 30 caractères mais le motif n'atteint pas 2*seuil=40.
        assert utils.detect_and_fix_repetitions("ab" * 15) == "ab" * 15

    def test_speech_like_text_survives(self):
        text = "Bonjour, comment allez-vous aujourd'hui ?"
        assert utils.detect_and_fix_repetitions(text) == text

    def test_custom_threshold(self):
        assert utils.detect_and_fix_repetitions("a" * 10, threshold=5) == "a"
        assert utils.detect_and_fix_repetitions("a" * 10, threshold=50) == "a" * 10


# =============================================================================
# parse_asr_output
# =============================================================================
class TestParseAsrOutput:
    def test_standard_tagged_output(self):
        assert utils.parse_asr_output("language French<asr_text>bonjour") == ("French", "bonjour")

    def test_newline_variant(self):
        raw = "language French\nbonjour\n<asr_text>bonjour le monde"
        assert utils.parse_asr_output(raw) == ("French", "bonjour le monde")

    def test_language_name_is_normalized(self):
        assert utils.parse_asr_output("language cHINese<asr_text>ni hao") == ("Chinese", "ni hao")

    def test_untagged_output_is_pure_text(self):
        # Sans tag : langue inconnue, tout le texte est conservé.
        assert utils.parse_asr_output("bonjour sans tag") == ("", "bonjour sans tag")

    def test_language_none_empty_audio(self):
        assert utils.parse_asr_output("language None<asr_text>") == ("", "")

    def test_language_none_with_text_keeps_text(self):
        assert utils.parse_asr_output("language None<asr_text>du texte") == ("", "du texte")

    def test_none_input(self):
        assert utils.parse_asr_output(None) == ("", "")

    def test_blank_input(self):
        assert utils.parse_asr_output("   ") == ("", "")

    def test_forced_language_overrides_and_keeps_raw_as_text(self):
        # Quand la langue est forcée, la sortie du modèle est du texte brut :
        # la balise n'est pas interprétée.
        assert utils.parse_asr_output(
            "language French<asr_text>bonjour", user_language="English"
        ) == ("English", "language French<asr_text>bonjour")

    def test_whitespace_is_stripped(self):
        assert utils.parse_asr_output("  language French<asr_text>  bonjour  ") == (
            "French",
            "bonjour",
        )


# =============================================================================
# merge_languages
# =============================================================================
class TestMergeLanguages:
    def test_removes_consecutive_duplicates(self):
        assert utils.merge_languages(["Chinese", "English", "English"]) == "Chinese,English"

    def test_skips_empty_and_none(self):
        assert utils.merge_languages(["", "French", None, "French"]) == "French"

    def test_strips_whitespace(self):
        assert utils.merge_languages(["  French  "]) == "French"

    def test_keeps_non_consecutive_duplicates(self):
        # A, B, A -> les doublons non consécutifs sont conservés.
        assert utils.merge_languages(["French", "English", "French"]) == "French,English,French"

    def test_empty_list(self):
        assert utils.merge_languages([]) == ""


# =============================================================================
# AudioChunk (dataclass)
# =============================================================================
class TestAudioChunk:
    def test_is_frozen(self):
        chunk = utils.AudioChunk(
            orig_index=0, chunk_index=1, wav=np.zeros(4, dtype=np.float32), sr=16000, offset_sec=0.0
        )
        with pytest.raises(Exception):
            chunk.sr = 8000  # type: ignore[misc]

    def test_fields_kept(self):
        wav = np.zeros(4, dtype=np.float32)
        chunk = utils.AudioChunk(0, 2, wav, 16000, 1.5)
        assert chunk.orig_index == 0
        assert chunk.chunk_index == 2
        assert chunk.wav is wav
        assert chunk.sr == 16000
        assert chunk.offset_sec == 1.5


# =============================================================================
# split_audio_into_chunks
# =============================================================================
class TestSplitAudioIntoChunks:
    """
    ATTENTION — performances.

    L'estimation d'énergie utilise `np.convolve(seg, ones(win), 'valid')` qui est
    en O(n x win). Sur cette machine, une fenêtre de 100 ms à 16 kHz (win=1600)
    combinée à un signal long rend la fonction inutilisable en test (minutes).
    On utilise donc de **petits signaux** et une fenêtre réduite (min_window_ms
    petit) pour rester sous quelques centaines de millisecondes.

    Invariant réel, vérifié : les chunks pavent le signal sans recouvrement ni
    trou, et le dernier chunk est complété par des zéros jusqu'à
    MIN_ASR_INPUT_SECONDS. La docstring de `split_audio_into_chunks` a été
    alignée sur ce comportement (elle promettait un reassemblage à l'échantillon
    près, ce qui est faux dès qu'un chunk est plus court que 0,5 s).
    """

    SR = 16000
    MIN_LEN = int(utils.MIN_ASR_INPUT_SECONDS * SR)  # 8000 échantillons

    @staticmethod
    def _tone(sec: float, freq: float = 220.0) -> np.ndarray:
        t = np.arange(int(sec * TestSplitAudioIntoChunks.SR), dtype=np.float32) / TestSplitAudioIntoChunks.SR
        return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)

    @pytest.mark.parametrize("sec", [0.1, 1.0])
    def test_short_audio_returned_whole(self, sec):
        # <= max_chunk_sec : un seul chunk.
        wav = self._tone(sec)
        chunks = utils.split_audio_into_chunks(wav, self.SR, max_chunk_sec=2.0, min_window_ms=10.0)
        assert len(chunks) == 1
        assert chunks[0][0].shape[0] == wav.shape[0]

    def test_long_audio_is_split(self):
        wav = self._tone(2.0)
        chunks = utils.split_audio_into_chunks(wav, self.SR, max_chunk_sec=0.5, min_window_ms=10.0)
        assert len(chunks) > 1
        for c, off in chunks:
            assert c.shape[0] > 0
            assert off >= 0.0
            assert c.dtype == np.float32

    def test_split_is_lossless(self):
        # Invariant principal : le signal d'origine est intégralement couvert,
        # dans l'ordre, par la concaténation des chunks. Le dernier chunk peut
        # être complété par des zéros pour atteindre max_chunk_sec (comportement
        # observé) : l'excédent est un padding, pas une perte.
        wav = self._tone(2.0)
        chunks = utils.split_audio_into_chunks(wav, self.SR, max_chunk_sec=0.5, min_window_ms=10.0)
        joined = np.concatenate([c for c, _ in chunks])
        assert joined.shape[0] >= wav.shape[0]  # padding éventuel en fin
        assert np.array_equal(joined[: wav.shape[0]], wav)  # origine intacte
        # Ce qui dépasse l'entrée est du silence numérique.
        assert np.all(joined[wav.shape[0]:] == 0)

    def test_chunk_len_bounded_by_max_plus_search_window(self):
        # Le code ne découpe pas à max_chunk_sec pile : il cherche une frontière
        # dans une fenêtre de +/- search_expand_sec autour de la coupure idéale
        # (recherche d'un silence). La borne réelle est donc
        # max_chunk_sec + search_expand_sec, relevée au-delà par le padding
        # jusqu'à MIN_ASR_INPUT_SECONDS.
        wav = self._tone(2.0)
        chunks = utils.split_audio_into_chunks(
            wav, self.SR, max_chunk_sec=0.5, search_expand_sec=5.0, min_window_ms=10.0
        )
        bound = int((0.5 + 5.0) * self.SR)
        bound = max(bound, self.MIN_LEN)
        for c, _ in chunks:
            assert c.shape[0] <= bound

    def test_narrow_search_window_keeps_chunks_close_to_target(self):
        # Avec une fenêtre de recherche réduite, les chunks se rapprochent
        # de max_chunk_sec (frontière trouvée vite, peu d'écart possible).
        wav = self._tone(2.0)
        chunks = utils.split_audio_into_chunks(
            wav, self.SR, max_chunk_sec=0.5, search_expand_sec=0.05, min_window_ms=10.0
        )
        assert len(chunks) > 1
        bound = int((0.5 + 0.05) * self.SR)
        for c, _ in chunks:
            assert c.shape[0] <= max(bound, self.MIN_LEN)

    def test_short_chunks_are_padded_to_min_duration(self):
        # Un chunk plus court que MIN_ASR_INPUT_SECONDS est complété par des
        # zéros : le modèle ASR refuse les entrées trop brèves.
        wav = self._tone(2.0)
        chunks = utils.split_audio_into_chunks(
            wav, self.SR, max_chunk_sec=0.5, search_expand_sec=5.0, min_window_ms=10.0
        )
        for c, _ in chunks:
            assert c.shape[0] >= self.MIN_LEN

    def test_offsets_are_monotonic(self):
        wav = self._tone(2.0)
        chunks = utils.split_audio_into_chunks(wav, self.SR, max_chunk_sec=0.5, min_window_ms=10.0)
        offsets = [off for _, off in chunks]
        for a, b in zip(offsets, offsets[1:]):
            assert b > a

    def test_multichannel_is_mixed_down(self):
        stereo = np.stack([self._tone(2.0), self._tone(2.0, 330.0)], axis=-1)
        chunks = utils.split_audio_into_chunks(stereo, self.SR, max_chunk_sec=0.5, min_window_ms=10.0)
        assert len(chunks) > 1
        for c, _ in chunks:
            assert c.ndim == 1  # mono attendu

    def test_offsets_accumulate_from_chunk_durations(self):
        wav = self._tone(2.0)
        chunks = utils.split_audio_into_chunks(wav, self.SR, max_chunk_sec=0.5, min_window_ms=10.0)
        running = 0.0
        for c, off in chunks:
            assert off == pytest.approx(running, abs=1e-6)
            running += c.shape[0] / self.SR


# =============================================================================
# Constantes du module
# =============================================================================
class TestModuleConstants:
    def test_sample_rate_is_16k(self):
        assert utils.SAMPLE_RATE == 16000

    def test_min_input_duration(self):
        assert utils.MIN_ASR_INPUT_SECONDS == 0.5

    def test_max_durations_are_ordered(self):
        # Le maximum ASR doit couvrir le maximum d'alignement forcé.
        assert utils.MAX_FORCE_ALIGN_INPUT_SECONDS < utils.MAX_ASR_INPUT_SECONDS

    def test_supported_languages_non_empty(self):
        assert len(utils.SUPPORTED_LANGUAGES) > 0

    def test_supported_languages_are_canonical(self):
        # Chaque entrée doit être déjà normalisée (initiale majuscule).
        for lang in utils.SUPPORTED_LANGUAGES:
            assert lang == utils.normalize_language_name(lang), lang

    def test_no_duplicate_languages(self):
        assert len(utils.SUPPORTED_LANGUAGES) == len(set(utils.SUPPORTED_LANGUAGES))

    def test_expected_languages_present(self):
        for lang in ("Chinese", "English", "French", "Spanish", "German"):
            assert lang in utils.SUPPORTED_LANGUAGES
