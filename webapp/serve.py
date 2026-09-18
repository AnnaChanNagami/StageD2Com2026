#!/usr/bin/env python
"""serve.py — Lance Scribe via waitress (Windows-friendly, pas de TTY requis).

Sert les fichiers statiques de STATICFILES_DIRS sous /static/ (mode dev)
puis délègue le reste à l'application WSGI Django.

Usage:  ../.venv/Scripts/python.exe serve.py [port]
"""
import os
import sys
import mimetypes

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qwenweb.settings")

import django

django.setup()
from django.core.wsgi import get_wsgi_application
from django.conf import settings
from waitress import serve as wserve

DJANGO_APP = get_wsgi_application()

STATIC_DIRS = [str(p) for p in settings.STATICFILES_DIRS]


def static_path(url_path: str) -> str | None:
    """Résout un chemin /static/... vers un fichier existant, ou None."""
    rel = url_path[len("/static/"):].replace("/", os.sep)
    for d in STATIC_DIRS:
        candidate = os.path.join(d, rel)
        if os.path.isfile(candidate):
            return candidate
    return None


def app(environ, start_response):
    path = environ.get("PATH_INFO", "")
    if path.startswith("/static/"):
        fpath = static_path(path)
        if fpath:
            ctype = mimetypes.guess_type(fpath)[0] or "application/octet-stream"
            with open(fpath, "rb") as f:
                body = f.read()
            start_response("200 OK", [("Content-Type", ctype), ("Content-Length", str(len(body)))])
            return [body]
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"404 Not Found"]
    return DJANGO_APP(environ, start_response)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8002
    print(f"Scribe — waitress sur http://0.0.0.0:{port}", flush=True)
    wserve(app, host="0.0.0.0", port=port, threads=4)