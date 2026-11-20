from django.urls import path

from .views import ResumoDashboardView

app_name = 'dashboard'

urlpatterns = [
    path('resumo/', ResumoDashboardView.as_view(), name='resumo'),
]