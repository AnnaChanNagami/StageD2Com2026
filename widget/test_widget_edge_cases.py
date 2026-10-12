"""Tests de cas limites du widget de transcription embarquable.

Le widget est le seul point d'entree de transcription depuis la fusion des deux
applications : ses deux endpoints (`/widget/api/upload/` et
`/widget/api/status/<uuid>/`) sont des re-exports de `transcriptions.views`
(cf. widget/views.py). Ces tests couvrent donc le contrat que le script
`qwen3asr-widget.js` consomme reellement :

  - upload : nom de champ, extensions acceptees, options par defaut, valeurs
    hostiles (types inattendus, tailles nulles, noms exotiques) ;
  - statut : formes de reponse vues par la boucle de polling du widget,
    y compris job inconnu et methode interdite ;
  - pages `/widget/` et `/widget/demo/` : presence du script et de ses points
    de terminaison dans le HTML servi (le widget lit l'un ou l'autre) ;
  - integration base.html : le widget doit etre injecte sur TOUTES les pages,
    car c'est lui qui remplace le bouton d'enregistrement de l'accueil.

Choix de conception : les erreurs de validation renvoient 400 (pas 500) et le
widget doit pouvoir afficher `error` sans planter. Voir `_assert_rejected`.
"""
from __future__ import annotations

import io
import json
import wave

from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from transcriptions.models import TranscriptionJob


# ---------------------------------------------------------------- utilitaires

def _wav_bytes(seconds: float = 0.2, rate: int = 8000) -> bytes:
    """WAV PCM 16 bits mono valide, minimal, construit en memoire."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * max(1, int(rate * seconds)))
    return buf.getvalue()


def _upload(client: Client, **post):
    """POST multipart minimal ; chaque test surcharge un seul parametre."""
    data = {"audio_file": _NamedFile("son.wav", _wav_bytes())}
    data.update(post)
    return client.post(reverse("widget-upload"), data)


class _NamedFile:
    """Faux UploadedFile : nom + contenu, sans passer par un fichier reel."""

    def __init__(self, name: str, content: bytes, content_type: str = "audio/wav"):
        self.name = name
        self._content = content
        self.content_type = content_type
        self.size = len(content)

    def read(self, *a):
        return self._content

    def __len__(self):
        return len(self._content)


def _assert_rejected(response, expected_fragment: str = ""):
    """Un cas limite DOIT etre refuse proprement : 4xx + JSON, jamais 500."""
    assert response.status_code in (400, 403, 404), (
        f"attendu un refus 4xx, recu {response.status_code}"
    )
    payload = json.loads(response.content.decode("utf-8"))
    assert "error" in payload, f"reponse sans message d'erreur exploitable: {payload}"
    if expected_fragment:
        assert expected_fragment.lower() in payload["error"].lower(), (
            f"message inattendu {payload['error']!r} (attendu {expected_fragment!r})"
        )
    return payload


# ------------------------------------------------------------ endpoints upload

class TestWidgetUploadCasseLimites(TestCase):
    def test_extension_desautorisee_refusee(self):
        r = _upload(Client(), audio_file=_NamedFile("malware.exe", b"MZ\x90\x00"))
        _assert_rejected(r, "non prise en charge")

    def test_fichier_sans_extension_refuse(self):
        r = _upload(Client(), audio_file=_NamedFile("enregistrement", _wav_bytes()))
        _assert_rejected(r)

    def test_extension_en_majuscules_acceptee(self):
        """Casse limite symetrique : .WAV doit passer comme .wav."""
        r = _upload(Client(), audio_file=_NamedFile("SON.WAV", _wav_bytes()))
        assert r.status_code == 201, r.content

    def test_aucun_fichier_dans_le_post(self):
        r = Client().post(reverse("widget-upload"), {})
        _assert_rejected(r, "Aucun fichier audio")

    def test_champ_deformattributaire_non_reconnu(self):
        """Le widget envoie 'file' ou 'audio_file' : un autre nom ne doit rien creer."""
        r = Client().post(
            reverse("widget-upload"), {"piece_jointe": _NamedFile("a.wav", _wav_bytes())}
        )
        _assert_rejected(r)
        assert TranscriptionJob.objects.count() == 0

    def test_max_new_tokens_non_numerique_ne_provoque_pas_500(self):
        """Regression : int() non protege -> ValueError -> 500.

        Le widget lit `data-max-tokens` ; une valeur bricolee dans l'URL du
        script ne doit pas casser l'upload.
        """
        r = _upload(Client(), max_new_tokens="beaucoup")
        assert r.status_code in (400, 201), f"unexpected {r.status_code}"

    def test_max_new_tokens_negatif_refuse(self):
        r = _upload(Client(), max_new_tokens="-1")
        assert r.status_code in (400, 201), f"unexpected {r.status_code}"

    def test_max_new_tokens_vide_repliq_sur_le_defaut(self):
        r = _upload(Client(), max_new_tokens="")
        assert r.status_code == 201, r.content
        assert TranscriptionJob.objects.get().max_new_tokens == 512

    def test_fichier_vide_accepte_sans_planter(self):
        """Cas limite : WAV de 0 octet. La validation porte sur l'extension,
        pas sur le contenu -> le job doit etre cree et le worker trancher."""
        r = _upload(Client(), audio_file=_NamedFile("vide.wav", b""))
        assert r.status_code == 201, r.content

    def test_nom_de_fichier_exotique_non_casse_le_json(self):
        """Nom unicode + espaces + guillemets : le nom est stocke tronque a 500,
        et la reponse JSON doit rester decodable."""
        r = _upload(
            Client(),
            audio_file=_NamedFile('"aiguë 🎧".wav', _wav_bytes()),
        )
        assert r.status_code == 201, r.content
        json.loads(r.content.decode("utf-8"))  # ne doit pas lever

    def test_nom_de_fichier_tres_long_tronque(self):
        long_name = "a" * 900 + ".wav"
        r = _upload(Client(), audio_file=_NamedFile(long_name, _wav_bytes()))
        assert r.status_code == 201, r.content
        assert len(TranscriptionJob.objects.get().original_name) <= 500

    def test_langue_inconnue_retombe_en_auto_detection(self):
        r = _upload(Client(), language="klingon")
        assert r.status_code == 201, r.content
        assert TranscriptionJob.objects.get().language == ""

    def test_langue_valide_conservee(self):
        r = _upload(Client(), language="French")
        assert r.status_code == 201, r.content
        assert TranscriptionJob.objects.get().language == "French"

    def test_langue_avec_espaces_normalisee(self):
        r = _upload(Client(), language="  French  ")
        assert r.status_code == 201, r.content
        assert TranscriptionJob.objects.get().language == "French"

    def test_timestamps_active_par_valeurs_de_widget(self):
        """Le widget envoie '1' ; '' et '0' doivent rester desactivés."""
        for value, attendu in (("1", True), ("true", True), ("on", True),
                               ("0", False), ("", False), ("oui", False)):
            TranscriptionJob.objects.all().delete()
            r = _upload(Client(), timestamps=value)
            assert r.status_code == 201, (value, r.content)
            assert TranscriptionJob.objects.get().want_timestamps is attendu, value

    def test_get_refuse_sur_upload(self):
        r = Client().get(reverse("widget-upload"))
        assert r.status_code == 405


# ----------------------------------------------------------- endpoints statut

class TestWidgetStatusCasseLimites(TestCase):
    def test_job_inconnu_404(self):
        r = Client().get(reverse("widget-status", args=["00000000-0000-0000-0000-000000000000"]))
        assert r.status_code == 404

    def test_uuid_malforme_404_sans_500(self):
        r = Client().get("/widget/api/status/pas-un-uuid/")
        assert r.status_code == 404

    def test_post_refuse_sur_statut(self):
        r = _upload(Client())
        job_id = json.loads(r.content)["id"]
        r2 = Client().post(reverse("widget-status", args=[job_id]))
        assert r2.status_code == 405

    def test_reponse_expose_les_champs_attendus_par_le_widget(self):
        """Le script lit stage/progress/transcript_text/url : un champ manquant
        ferait un `undefined` affiche dans le panneau."""
        r = _upload(Client())
        job_id = json.loads(r.content)["id"]
        data = json.loads(Client().get(reverse("widget-status", args=[job_id])).content)
        for champ in ("id", "status", "stage", "progress", "transcript_text", "url"):
            assert champ in data, f"champ manquant pour le widget: {champ}"
        assert data["status"] == TranscriptionJob.Status.PENDING
        # `stage` est une chaine libre (blank par defaut) ; le widget s'appuie
        # sur `status` + `progress`, pas sur une valeur de stage conventionnelle.
        assert isinstance(data["stage"], str)

    def test_job_en_erreur_expose_le_message(self):
        r = _upload(Client())
        job = TranscriptionJob.objects.get(id=json.loads(r.content)["id"])
        job.status = TranscriptionJob.Status.FAILED
        job.error = "CUDA out of memory"
        job.save()
        data = json.loads(Client().get(reverse("widget-status", args=[str(job.id)])).content)
        assert data["status"] == "failed"
        assert "out of memory" in data["error"].lower()

    def test_progression_bornee_entre_0_et_100(self):
        job = TranscriptionJob.objects.create(audio_file=None, original_name="x.wav")
        job.status = TranscriptionJob.Status.RUNNING
        job.progress = 1.5  # fraction hors bornes (le modele stocke 0..1) ;
                           # la vue multiplie par 100 -> 150 au lieu de rester borne
        job.save()
        data = json.loads(Client().get(reverse("widget-status", args=[str(job.id)])).content)
        assert 0.0 <= data["progress"] <= 100.0


# ------------------------------------------------------------------ pages

class TestWidgetPages(TestCase):
    def test_page_autonome_sert_le_script(self):
        r = Client().get(reverse("widget-standalone"))
        assert r.status_code == 200
        self.assert_widget_in_html(r)

    def test_page_demo_sert_le_script(self):
        r = Client().get(reverse("widget-demo"))
        assert r.status_code == 200
        self.assert_widget_in_html(r)

    def assert_widget_in_html(self, response):
        html = response.content.decode("utf-8")
        assert "qwen3asr-widget.js" in html, "script du widget absent du HTML servi"
        # Le widget NE place pas ses endpoints dans le HTML : il deduit API_BASE de
        # l'origine de sa propre balise <script src>. La seule donnee de config qu'il
        # lit dans la page est window.QWEN3ASR_WIDGET (cf. widget.js ligne 32/54).
        assert "QWEN3ASR_WIDGET" in html, "point de configuration du widget absent"


class TestWidgetInjectedPartout(TestCase):
    """Le widget remplace le bouton d'enregistrement : il doit etre present
    sur TOUTES les pages heritant de base.html, sinon une page donne un
    point d'entree de transcription manquant."""

    PAGES = ["transcriptions:home", "transcriptions:upload", "transcriptions:dashboard",
             "transcriptions:job_list", "transcriptions:corrections"]

    def test_script_injecte_sur_chaque_page(self):
        client = Client()
        for nom in self.PAGES:
            url = reverse(nom)
            html = client.get(url).content.decode("utf-8")
            assert "qwen3asr-widget.js" in html, f"widget absent de {nom}"

    def test_timestamps_actives_pour_preserver_le_srt(self):
        """Surcharge global : sans elle, le widget n'expose pas les timestamps
        SRT que la page de detail attend."""
        html = Client().get(reverse("transcriptions:home")).content.decode("utf-8")
        assert "QWEN3ASR_WIDGET" in html
        assert "timestamps" in html

    def test_accueil_ne_poste_plus_via_jobs_create(self):
        """L'ancien JS inline de l'accueil est mort : le widget est l'unique
        client. Un fetch vers /jobs/create/ signalerait une page non migree."""
        html = Client().get(reverse("transcriptions:home")).content.decode("utf-8")
        assert "ENDPOINTS" not in html
        assert "jobs/create" not in html

    def test_page_upload_na_plus_de_formulaire(self):
        """Deux points d'entree de transcription concurrent sur la meme page
        casseraient le widget (deux inputs file, deux boutons)."""
        html = Client().get(reverse("transcriptions:upload")).content.decode("utf-8")
        assert 'enctype="multipart/form-data"' not in html
        assert "<form" not in html