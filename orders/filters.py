import re

from django_filters import rest_framework as df
from rest_framework.exceptions import ValidationError

from orders.models import Cliente, Pedido, StatusPedido


class ClienteFilter(df.FilterSet):
    nome = df.CharFilter(
        lookup_expr="icontains",
        help_text="Busca parcial (contém), sem diferenciar maiúsculas.",
    )
    cpf_cnpj = df.CharFilter(
        method="filter_cpf_cnpj",
        help_text="Busca exata; pontuação é ignorada.",
    )

    class Meta:
        model = Cliente
        fields = ["nome", "cpf_cnpj"]

    def filter_cpf_cnpj(self, queryset, name, value):
        documento = re.sub(r"[^0-9A-Za-z]", "", value).upper()
        return queryset.filter(cpf_cnpj=documento)


class PedidoFilter(df.FilterSet):
    cliente_id = df.NumberFilter(
        field_name="cliente_id",
        help_text="Filtra por cliente (valor não numérico retorna 400).",
    )
    status = df.MultipleChoiceFilter(
        choices=StatusPedido.choices,
        help_text=(
            "Filtra por um ou mais status. Repita o parâmetro para múltiplos "
            "valores (ex.: ?status=PENDENTE&status=ENVIADO). "
            "Valor fora das opções retorna 400."
        ),
    )
    criado_de = df.DateFilter(
        field_name="criado_em",
        lookup_expr="date__gte",
        help_text="Pedidos criados a partir desta data, inclusive (AAAA-MM-DD).",
    )
    criado_ate = df.DateFilter(
        field_name="criado_em",
        lookup_expr="date__lte",
        help_text="Pedidos criados até esta data, inclusive (AAAA-MM-DD).",
    )
    valor_min = df.NumberFilter(
        field_name="valor_total",
        lookup_expr="gte",
        help_text="Valor total mínimo, inclusive (ex.: 50.00).",
    )
    valor_max = df.NumberFilter(
        field_name="valor_total",
        lookup_expr="lte",
        help_text="Valor total máximo, inclusive (ex.: 200.00).",
    )

    ordering = df.OrderingFilter(
        fields=(
            ("criado_em", "criado_em"),
            ("atualizado_em", "atualizado_em"),
            ("valor_total", "valor_total"),
            ("id", "id"),
        ),
        help_text=(
            "Campos de ordenação: criado_em, atualizado_em, valor_total, id. "
            "Use '-' para ordem decrescente (ex.: ?ordering=-criado_em). "
            "Separe por vírgula para ordenar por mais de um campo "
            "(ex.: ?ordering=-valor_total,criado_em)."
        ),
    )

    class Meta:
        model = Pedido
        fields = [
            "cliente_id",
            "status",
            "criado_de",
            "criado_ate",
            "valor_min",
            "valor_max",
        ]

    def filter_queryset(self, queryset):
        dados = self.form.cleaned_data
        criado_de, criado_ate = dados.get("criado_de"), dados.get("criado_ate")
        valor_min, valor_max = dados.get("valor_min"), dados.get("valor_max")

        erros = {}
        if criado_de and criado_ate and criado_de > criado_ate:
            erros["criado_de"] = "Deve ser anterior ou igual a 'criado_ate'."
        if valor_min is not None and valor_max is not None and valor_min > valor_max:
            erros["valor_min"] = "Deve ser menor ou igual a 'valor_max'."
        if erros:
            raise ValidationError(erros)

        return super().filter_queryset(queryset)