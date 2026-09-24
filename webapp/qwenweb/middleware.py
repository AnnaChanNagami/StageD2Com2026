"""Middlewares maison pour qwenweb."""

from django.http import HttpResponse


class CorsAllowAllMiddleware:
    """Autorise les appels cross-origin.

    L'API de transcription est volontairement ouverte (aucune authentification),
    ce qui permet d'embarquer le widget Qwen3-ASR sur n'importe quel site tiers.
    On ajoute les en-têtes CORS sur toutes les réponses et on répond aux
    requêtes OPTIONS de pré-vol (nécessaires pour les POST cross-origin).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "OPTIONS":
            response = HttpResponse(status=200)
        else:
            response = self.get_response(request)
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        response["Access-Control-Max-Age"] = "86400"
        return response