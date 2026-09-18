from django.urls import path

from . import views

app_name = "transcriptions"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/create/", views.api_job_create, name="api_job_create"),
    path("jobs/<uuid:job_id>/", views.job_detail, name="job_detail"),
    path("jobs/<uuid:job_id>/correction/", views.correction, name="correction"),
    path("jobs/<uuid:job_id>/delete/", views.delete_job, name="delete_job"),
    path("jobs/delete-bulk/", views.delete_jobs_bulk, name="delete_jobs_bulk"),
    path("upload/", views.upload, name="upload"),
    path("corrections/", views.corrections, name="corrections"),
    # API JSON
    path("api/status/<uuid:job_id>/", views.api_job_status, name="api_job_status"),
    path("api/stats/", views.api_stats, name="api_stats"),
    # Téléchargements
    path("download/<uuid:job_id>/txt/", views.download_txt, name="download_txt"),
    path("download/<uuid:job_id>/json/", views.download_json, name="download_json"),
    path("download/<uuid:job_id>/srt/", views.download_srt, name="download_srt"),
]
