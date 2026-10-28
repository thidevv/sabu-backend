from django_filters import rest_framework as df

from core.filters import ApagadasFilter
from .models import FichaTecnica, MovimentacaoEstoque, MovimentacaoMaterial, VinculoFornecedor, MateriaPrima, \
    Fornecedor, CompraFornecedor, LoteMateriaPrima, LoteProdutoVariacao, StatusLote


class MateriaPrimaFilter(df.FilterSet):
    apagadas = ApagadasFilter(
        campo="apagada_em",
        somente_admin=True,
        help_text="Somente admin. Omitido: ativas e apagadas. `true`: só apagadas. `false`: só ativas.",
    )

    class Meta:
        model = MateriaPrima
        fields = ["apagadas"]


class FornecedorFilter(df.FilterSet):
    apagados = ApagadasFilter(
        campo="apagado_em",
        somente_admin=True,
        help_text="Somente admin. Omitido: ativas e apagadas. `true`: só apagadas. `false`: só ativas.",
    )

    class Meta:
        model = Fornecedor
        fields = ["apagados"]


class CompraFornecedorFilter(df.FilterSet):
    fornecedor_id = df.NumberFilter(
        field_name="fornecedor_id",
        help_text="Filtra por fornecedor (valor não numérico retorna 400).",
    )

    class Meta:
        model = CompraFornecedor
        fields = ["fornecedor_id"]


class VinculoFornecedorFilter(df.FilterSet):
    materia_prima_id = df.NumberFilter(
        field_name="materia_prima_id",
        help_text="Filtra por matéria-prima.",
    )
    apagados = ApagadasFilter(campo="apagado_em")

    class Meta:
        model = VinculoFornecedor
        fields = ["materia_prima_id", "apagados"]


class FichaTecnicaFilter(df.FilterSet):
    variacao_id = df.NumberFilter(
        field_name="variacao_id",
        help_text="Filtra por variação.",
    )
    apagadas = ApagadasFilter(campo="apagada_em")

    class Meta:
        model = FichaTecnica
        fields = ["variacao_id", "apagadas"]


class LoteMateriaPrimaFilter(df.FilterSet):
    materia_prima_id = df.NumberFilter(
        field_name="materia_prima_id",
        error_messages={"invalid": "Informe um ID numérico."},
        help_text="Filtra por matéria-prima.",
    )
    compra_fornecedor_item_id = df.NumberFilter(
        field_name="compra_fornecedor_item_id",
        error_messages={"invalid": "Informe um ID numérico."},
        help_text="Filtra pelo item de compra de fornecedor que originou o lote.",
    )
    status = df.ChoiceFilter(
        choices=StatusLote.choices,
        help_text="Filtra pelo status do lote.",
    )
    sku = df.CharFilter(
        method="filter_sku",
        help_text="Filtra pelo SKU da matéria-prima (ignora espaços e maiúsculas/minúsculas).",
    )

    class Meta:
        model = LoteMateriaPrima
        fields = ["materia_prima_id", "compra_fornecedor_item_id", "status", "sku"]

    def filter_sku(self, queryset, name, value):
        return queryset.filter(materia_prima__sku=value.strip().upper())


class LoteProdutoVariacaoFilter(df.FilterSet):
    variacao_id = df.NumberFilter(
        field_name="variacao_id",
        error_messages={"invalid": "Informe um ID numérico."},
        help_text="Filtra por variação.",
    )
    status = df.ChoiceFilter(
        choices=StatusLote.choices,
        help_text="Filtra pelo status do lote.",
    )
    sku = df.CharFilter(
        method="filter_sku",
        help_text="Filtra pelo SKU da variação (ignora espaços e maiúsculas/minúsculas).",
    )

    class Meta:
        model = LoteProdutoVariacao
        fields = ["variacao_id", "status", "sku"]

    def filter_sku(self, queryset, name, value):
        return queryset.filter(variacao__sku=value.strip().upper())


class MovimentacaoEstoqueFilter(df.FilterSet):
    variacao_id = df.NumberFilter(
        field_name="lote_produto_variacao__variacao_id",
        error_messages={"invalid": "Informe um ID numérico."},
        help_text="Filtra por variação.",
    )
    lote_produto_variacao_id = df.NumberFilter(
        field_name="lote_produto_variacao_id",
        error_messages={"invalid": "Informe um ID numérico."},
        help_text="Filtra por lote de variação.",
    )
    sku = df.CharFilter(
        method="filter_sku",
        help_text="Filtra pelo SKU da variação (ignora espaços e maiúsculas/minúsculas).",
    )

    class Meta:
        model = MovimentacaoEstoque
        fields = ["variacao_id", "lote_produto_variacao_id", "sku"]

    def filter_sku(self, queryset, name, value):
        return queryset.filter(lote_produto_variacao__variacao__sku=value.strip().upper())


class MovimentacaoMaterialFilter(df.FilterSet):
    materia_prima_id = df.NumberFilter(
        field_name="lote_materia_prima__materia_prima_id",
        error_messages={"invalid": "Informe um ID numérico."},
        help_text="Filtra por matéria-prima.",
    )
    lote_materia_prima_id = df.NumberFilter(
        field_name="lote_materia_prima_id",
        error_messages={"invalid": "Informe um ID numérico."},
        help_text="Filtra por lote de matéria-prima.",
    )
    sku = df.CharFilter(
        method="filter_sku",
        help_text="Filtra pelo SKU da matéria-prima (ignora espaços e maiúsculas/minúsculas).",
    )

    class Meta:
        model = MovimentacaoMaterial
        fields = ["materia_prima_id", "lote_materia_prima_id", "sku"]

    def filter_sku(self, queryset, name, value):
        return queryset.filter(lote_materia_prima__materia_prima__sku=value.strip().upper())