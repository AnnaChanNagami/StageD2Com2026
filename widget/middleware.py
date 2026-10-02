"""Middleware CORS du widget embarquable.

Autorise les appels cross-origin provenant des sites tiers qui embarquent le
widget Qwen3-ASR (script + upload + interrogation du statut).

Contrairement à l'ancien middleware global (qwenweb.middleware), celui-ci
n'ajoute les en-têtes CORS QUE sur les réponses sous /widget/ — l'application
principale (upload/dashboard) reste sans CORS.
"""

from django.http import HttpResponse


WIDGET_PREFIXES = ("/widget/",)

# Middleware CORS pour le widget embarquable
class WidgetCorsMiddleware:
    """Ajoute les en-têtes CORS sur /widget/* uniquement."""

# Initialisation du middleware avec la fonction get_response
    def __init__(self, get_response):
        self.get_response = get_response

# Appel du middleware pour chaque requête
    def __call__(self, request):
        path = request.path
        if not any(path.startswith(p) for p in WIDGET_PREFIXES):
            return self.get_response(request)

        if request.method == "OPTIONS":
            response = HttpResponse(status=200)
        else:
            response = self.get_response(request)

        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        response["Access-Control-Max-Age"] = "86400"
        return response