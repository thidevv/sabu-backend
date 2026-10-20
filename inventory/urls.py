from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MateriaPrimaViewSet,
    FichaTecnicaViewSet,
    MovimentacaoEstoqueViewSet, MovimentacaoMaterialViewSet, FornecedorViewSet, VinculoFornecedorViewSet,
    CompraFornecedorViewSet,
)

app_name = 'inventory'

router = DefaultRouter()
router.register(r'materias-primas', MateriaPrimaViewSet, basename='materia-prima')
router.register(r'fichas-tecnicas', FichaTecnicaViewSet, basename='ficha-tecnica')
router.register(r'movimentacoes-estoque', MovimentacaoEstoqueViewSet, basename='movimentacao-estoque')
router.register(r'movimentacoes-material', MovimentacaoMaterialViewSet, basename='movimentacao-material')
router.register(r'fornecedores', FornecedorViewSet, basename='fornecedor')
router.register(r'vinculo-fornecedores', VinculoFornecedorViewSet, basename='vinculo-fornecedor')
router.register(r'compra-fornecedores', CompraFornecedorViewSet, basename='compra-fornecedor')


urlpatterns = [
    path('', include(router.urls)),
]
