from django.urls import path

from recommendations.views import RecomendacaoView

app_name = 'recommendations'

urlpatterns = [
    path('quiz/', RecomendacaoView.as_view(), name='quiz'),
]
