from django.urls import path

from . import views
# Points d'extrémités utilisés par le script du widget (upload + statut partagent le même backend que l'application principale)
urlpatterns = [
    path("", views.widget_standalone, name="widget-standalone"),
    path("demo/", views.widget_demo, name="widget-demo"),
    # Points d'extrémité utilisés par le script du widget (upload + statut)
    path("api/upload/", views.upload_audio, name="widget-upload"),
    path("api/status/<uuid:job_id>/", views.job_status, name="widget-status"),
]