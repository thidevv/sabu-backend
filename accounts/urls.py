from django.urls import path
from .views import CustomTokenObtainPairView, CustomTokenRefreshView, CadastroUsuarioView

app_name = 'accounts'

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('registrar_admin/', CadastroUsuarioView.as_view(), name='registrar_admin'),
]