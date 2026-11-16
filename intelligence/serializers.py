
from rest_framework import serializers


class PrevisaoPrecoSerializer(serializers.Serializer):
    peso_g = serializers.FloatField(min_value=0.01)
    unidade = serializers.IntegerField(min_value=1)

    formato = serializers.CharField(max_length=100)
    tipo_sabonete = serializers.CharField(max_length=100)
    tipo_pele = serializers.CharField(max_length=100)
    embalagem = serializers.CharField(max_length=100)
    base_sabonete = serializers.CharField(max_length=100)
    tipo_vendedor = serializers.CharField(max_length=100)

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
