"""
Script d'automatisation : téléverse tous les fichiers audio du dossier Audacity
et les soumet à la transcription via l'API Qwen3-ASR.

Usage : ../.venv/Scripts/python.exe upload_all.py
"""
import glob
import json
import os
import sys
import time
import urllib.request

BASE_URL = "http://127.0.0.1:8002"
AUDACITY_DIR = os.path.join(os.path.expanduser("~"), "Documents", "audacity")
SERVER_FILE = os.path.join(os.path.dirname(__file__), "run_server.py")


def upload_file(filepath):
    """Téléverse un fichier audio via l'API et retourne l'id du job."""
    filename = os.path.basename(filepath)
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"

    with open(filepath, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="audio_file"; filename="{filename}"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/jobs/create/",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        return data
    except Exception as e:
        return {"error": str(e)}


def poll_job(job_id, max_wait=180):
    """Attend qu'un job soit terminé (polling toutes les 3s)."""
    start = time.time()
    while time.time() - start < max_wait:
        try:
            resp = urllib.request.urlopen(f"{BASE_URL}/api/status/{job_id}/", timeout=5)
            data = json.loads(resp.read().decode())
            if data["status"] in ("completed", "failed"):
                return data
        except Exception:
            pass
        time.sleep(3)
    return {"status": "timeout", "error": "Délai dépassé"}


def main():
    # Vérifier que le serveur tourne
    try:
        urllib.request.urlopen(BASE_URL, timeout=5)
    except Exception:
        print(f"Le serveur Django ne répond pas sur {BASE_URL}.")
        print("Lancez d'abord : python manage.py runserver 0.0.0.0:8002")
        sys.exit(1)

    # Trouver tous les fichiers audio
    patterns = ["*.wav", "*.mp3", "*.flac", "*.ogg"]
    files = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(AUDACITY_DIR, pat)))
    files.sort()

    if not files:
        print(f"Aucun fichier audio trouvé dans {AUDACITY_DIR}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  QWEN3-ASR — Upload automatisé")
    print(f"  Dossier : {AUDACITY_DIR}")
    print(f"  Fichiers trouvés : {len(files)}")
    print(f"{'='*60}\n")

    results = []
    for i, filepath in enumerate(files, 1):
        filename = os.path.basename(filepath)
        print(f"[{i}/{len(files)}] {filename}")

        # Upload
        result = upload_file(filepath)
        if "error" in result:
            print(f"  ERREUR upload : {result['error']}")
            results.append({"file": filename, "status": "upload_error", "error": result["error"]})
            continue

        job_id = result["id"]
        print(f"  Job créé : {job_id[:12]}... — en attente du worker")

    print(f"\n{'='*60}")
    print(f"  {len(results)} erreurs sur {len(files)} fichiers")
    print(f"  Les jobs seront traités automatiquement par le worker.")
    print(f"  Consulte l'historique sur http://127.0.0.1:8002/jobs/")
    print(f"{'='*60}\n")

    return results


if __name__ == "__main__":
    main()
