"""Widget de transcription embarquable - app Django autonome.

Cette app est totalement indépendante du reste du projet : elle sert les pages
/widget/ et /widget/demo/, le script autonome qwen3asr-widget.js, et les
endpoints /widget/api/... (upload de fichier + statut du job).

CORS : le middleware WidgetCorsMiddleware s'applique uniquement aux chemins
/widget/* - l'API n'est ainsi accessible que depuis le widget, pas depuis
l'application principale.
"""

from django.apps import AppConfig

#Classe de configuration de l'app Django autonome "widget"
class WidgetConfig(AppConfig):
    name = "widget"
    verbose_name = "Widget de transcription embarquable"