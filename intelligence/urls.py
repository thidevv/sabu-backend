
from django.urls import path
from .views import PreverPrecoView

urlpatterns = [
    path(
        "prever-preco/",
        PreverPrecoView.as_view(),
        name="prever-preco"
    ),
]
