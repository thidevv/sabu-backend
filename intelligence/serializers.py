from decimal import Decimal
from rest_framework import serializers


class PrevisaoPrecoSerializer(serializers.Serializer):

    # Características do sabonete para o ML
    peso_g = serializers.FloatField(min_value=0.01)
    unidade = serializers.IntegerField(min_value=1)

    formato = serializers.CharField(max_length=100)
    tipo_sabonete = serializers.CharField(max_length=100)
    tipo_pele = serializers.CharField(max_length=100)
    embalagem = serializers.CharField(max_length=100)
    base_sabonete = serializers.CharField(max_length=100)
    tipo_vendedor = serializers.CharField(max_length=100)

    # Dados financeiros opcionais
    custo_unitario = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False
    )

    margem_desejada = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("99.99"),
        required=False
    )

    def validate(self, attrs):
        # A margem desejada depende do custo de produção.
        if (
            "margem_desejada" in attrs
            and "custo_unitario" not in attrs
        ):
            raise serializers.ValidationError({
                "custo_unitario":
                    "Informe o custo para calcular a margem desejada."
            })

        return attrs

    def para_modelo(self):
        dados = self.validated_data

        return {
            "Peso (g)": dados["peso_g"],
            "Unidade": dados["unidade"],
            "Formato_norm": dados["formato"],
            "Tipo do Sabonete": dados["tipo_sabonete"],
            "Tipo de pele": dados["tipo_pele"],
            "Embalagem_norm": dados["embalagem"],
            "Base do sabonete": dados["base_sabonete"],
            "Tipo de vendedor": dados["tipo_vendedor"],
        }
