from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.mixins import AdminOnlyViewSetMixin
from core.exceptions import ErroDeDominio
from core.mixins import FiltrosSomenteNaLeituraMixin
from .filters import FichaTecnicaFilter, MovimentacaoEstoqueFilter, MovimentacaoMaterialFilter, VinculoFornecedorFilter, \
    MateriaPrimaFilter, FornecedorFilter, CompraFornecedorFilter, LoteMateriaPrimaFilter, LoteProdutoVariacaoFilter
from .models import MateriaPrima, FichaTecnica, MovimentacaoEstoque, MovimentacaoMaterial, Fornecedor, \
    VinculoFornecedor, CompraFornecedor, LoteMateriaPrima, LoteProdutoVariacao
from .schema import ficha_tecnica_schema, movimentacao_estoque_schema, \
    movimentacao_material_schema, vinculo_fornecedor_schema, compra_fornecedor_schema, fornecedor_schema, \
    materia_prima_schema, lote_materia_prima_schema, lote_produto_variacao_schema
from .serializers import (
    MateriaPrimaSerializer,
    FichaTecnicaSerializer,
    FichaTecnicaDetalhadaSerializer,
    FichaTecnicaUpdateSerializer,
    MovimentacaoEstoqueSerializer, MovimentacaoMaterialSerializer, FornecedorSerializer,
    VinculoFornecedorUpdateSerializer, VinculoFornecedorDetalhadoSerializer, VinculoFornecedorSerializer,
    CompraFornecedorSerializer, CompraFornecedorDetalhadaSerializer, CompraFornecedorUpdateSerializer,
    LoteMateriaPrimaSerializer, LoteProdutoVariacaoSerializer,
)
from .services import devolver_compra_fornecedor

@materia_prima_schema
class MateriaPrimaViewSet(AdminOnlyViewSetMixin, viewsets.ModelViewSet):
    queryset = MateriaPrima.objects.order_by('nome')
    serializer_class = MateriaPrimaSerializer
    filterset_class = MateriaPrimaFilter

    def perform_destroy(self, instance):
        with transaction.atomic():
            timestamp = timezone.now()
            instance.apagada_em = timestamp
            instance.save(update_fields=['apagada_em'])

            VinculoFornecedor.objects.filter(
                materia_prima_id=instance.pk,
                apagado_em__isnull=True,
            ).update(apagado_em=timestamp)

    @action(detail=True, methods=['patch'], url_path='restaurar')
    def restaurar(self, request, pk=None):
        materia_prima = self.get_object()

        if not materia_prima.apagada_em:
            raise ErroDeDominio('Esta matéria-prima não está apagada.')

        with transaction.atomic():
            materia_prima.apagada_em = None
            materia_prima.save(update_fields=['apagada_em'])

        return Response(MateriaPrimaSerializer(materia_prima).data, status=status.HTTP_200_OK)

@fornecedor_schema
class FornecedorViewSet(AdminOnlyViewSetMixin, viewsets.ModelViewSet):
    queryset = Fornecedor.objects.prefetch_related('categorias').order_by('nome')
    serializer_class = FornecedorSerializer
    filterset_class = FornecedorFilter

    def perform_destroy(self, instance):
        with transaction.atomic():
            timestamp = timezone.now()
            instance.apagado_em = timestamp
            instance.save(update_fields=['apagado_em'])

            VinculoFornecedor.objects.filter(
                fornecedor_id=instance.pk,
                apagado_em__isnull=True,
            ).update(apagado_em=timestamp)

    @action(detail=True, methods=['patch'], url_path='restaurar')
    def restaurar(self, request, pk=None):
        fornecedor = self.get_object()

        if not fornecedor.apagado_em:
            raise ErroDeDominio('Esta fornecedor não está apagado.')

        with transaction.atomic():
            fornecedor.apagado_em = None
            fornecedor.save(update_fields=['apagado_em'])

        return Response(FornecedorSerializer(fornecedor).data, status=status.HTTP_200_OK)

@compra_fornecedor_schema
class CompraFornecedorViewSet(AdminOnlyViewSetMixin,
                            mixins.CreateModelMixin,
                            mixins.ListModelMixin,
                            mixins.RetrieveModelMixin,
                            mixins.UpdateModelMixin,
                            viewsets.GenericViewSet):
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    queryset = (
        CompraFornecedor.objects
        .select_related('fornecedor')
        .prefetch_related('fornecedor_itens__lote_materiais')
        .order_by('-compra_realizada_em', '-id')
    )
    filterset_class = CompraFornecedorFilter

    def get_serializer_class(self):
        if self.action == 'create':
            return CompraFornecedorSerializer
        if self.action in ('update', 'partial_update'):
            return CompraFornecedorUpdateSerializer
        return CompraFornecedorDetalhadaSerializer

    @action(detail=True, methods=['post'])
    def devolver(self, request, pk=None):
        compra_fornecedor = devolver_compra_fornecedor(compra_fornecedor_id=self.get_object().pk, usuario=request.user)
        return Response(self.get_serializer(compra_fornecedor).data)

@vinculo_fornecedor_schema
class VinculoFornecedorViewSet(AdminOnlyViewSetMixin, FiltrosSomenteNaLeituraMixin, viewsets.ModelViewSet):
    queryset = VinculoFornecedor.objects.select_related('fornecedor', 'materia_prima')
    filterset_class = VinculoFornecedorFilter

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return VinculoFornecedorUpdateSerializer
        if self.action in ['list', 'retrieve']:
            return VinculoFornecedorDetalhadoSerializer
        return VinculoFornecedorSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action not in ('list', 'retrieve', 'restaurar'):
            qs = qs.filter(apagado_em__isnull=True)
        return qs

    def perform_destroy(self, instance):
        instance.apagado_em = timezone.now()
        instance.save(update_fields=['apagado_em'])

    @action(detail=True, methods=['patch'], url_path='restaurar')
    def restaurar(self, request, pk=None):
        vinculo = self.get_object()

        if not vinculo.apagado_em:
            raise ErroDeDominio('Este vínculo de fornecedor não está apagado.')

        if vinculo.materia_prima.apagada_em or vinculo.fornecedor.apagado_em:
            raise ErroDeDominio('Restaure a matéria-prima e o fornecedor antes de restaurar o vínculo de fornecedor.')

        vinculo.apagado_em = None
        vinculo.save(update_fields=['apagado_em'])

        return Response(
            VinculoFornecedorDetalhadoSerializer(vinculo).data,
            status=status.HTTP_200_OK,
        )


@ficha_tecnica_schema
class FichaTecnicaViewSet(AdminOnlyViewSetMixin, FiltrosSomenteNaLeituraMixin, viewsets.ModelViewSet):
    queryset = FichaTecnica.objects.select_related('materia_prima', 'variacao')
    filterset_class = FichaTecnicaFilter

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return FichaTecnicaUpdateSerializer
        if self.action in ['list', 'retrieve']:
            return FichaTecnicaDetalhadaSerializer
        return FichaTecnicaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action not in ('list', 'retrieve', 'restaurar'):
            qs = qs.filter(apagada_em__isnull=True)
        return qs

    def perform_destroy(self, instance):
        instance.apagada_em = timezone.now()
        instance.save(update_fields=['apagada_em'])

    @action(detail=True, methods=['patch'], url_path='restaurar')
    def restaurar(self, request, pk=None):
        ficha = self.get_object()

        if not ficha.apagada_em:
            raise ErroDeDominio('Esta ficha técnica não está apagada.')

        if ficha.variacao.apagado_em or ficha.materia_prima.apagada_em:
            raise ErroDeDominio('Restaure a variação e a matéria-prima antes de restaurar a ficha técnica.')

        ficha.apagada_em = None
        ficha.save(update_fields=['apagada_em'])

        return Response(
            FichaTecnicaDetalhadaSerializer(ficha).data,
            status=status.HTTP_200_OK,
        )

@lote_materia_prima_schema
class LoteMateriaPrimaViewSet(AdminOnlyViewSetMixin,
                              mixins.CreateModelMixin,
                              mixins.RetrieveModelMixin,
                              mixins.ListModelMixin,
                              viewsets.GenericViewSet):
    queryset = LoteMateriaPrima.objects.select_related('materia_prima').order_by('-criado_em', '-pk')
    serializer_class = LoteMateriaPrimaSerializer
    filterset_class = LoteMateriaPrimaFilter

@lote_produto_variacao_schema
class LoteProdutoVariacaoViewSet(AdminOnlyViewSetMixin,
                                 mixins.CreateModelMixin,
                                 mixins.RetrieveModelMixin,
                                 mixins.ListModelMixin,
                                 viewsets.GenericViewSet):
    queryset = LoteProdutoVariacao.objects.select_related('variacao__produto').order_by('-criado_em', '-pk')
    serializer_class = LoteProdutoVariacaoSerializer
    filterset_class = LoteProdutoVariacaoFilter


@movimentacao_estoque_schema
class MovimentacaoEstoqueViewSet(AdminOnlyViewSetMixin,
                                 mixins.CreateModelMixin,
                                 mixins.RetrieveModelMixin,
                                 mixins.ListModelMixin,
                                 viewsets.GenericViewSet):
    queryset = (
        MovimentacaoEstoque.objects
        .select_related('lote_produto_variacao__variacao__produto')
        .order_by('-movimentado_em', '-pk')
    )
    serializer_class = MovimentacaoEstoqueSerializer
    filterset_class = MovimentacaoEstoqueFilter


@movimentacao_material_schema
class MovimentacaoMaterialViewSet(AdminOnlyViewSetMixin,
                                 mixins.CreateModelMixin,
                                 mixins.RetrieveModelMixin,
                                 mixins.ListModelMixin,
                                 viewsets.GenericViewSet):
    queryset = (
        MovimentacaoMaterial.objects
        .select_related('lote_materia_prima__materia_prima', 'fornecedor')
        .order_by('-movimentado_em', '-pk')
    )
    serializer_class = MovimentacaoMaterialSerializer
    filterset_class = MovimentacaoMaterialFilter