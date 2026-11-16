from rest_framework import serializers

from catalog.models import BaseProduto, Ingrediente, TipoPeleIndicado
from recommendations.constants import (
    OPCOES_PREFERENCIA, OPCOES_RESSECAMENTO, OPCOES_SENSIBILIDADE, OPCOES_SIM_NAO, OPCOES_TIPO_PELE,
)


class IngredientePorNomeField(serializers.SlugRelatedField):
    # Os nomes de ingrediente são salvos normalizados; "Mel " deve achar "mel"
    def to_internal_value(self, data):
        if isinstance(data, str):
            data = data.strip().lower()
        return super().to_internal_value(data)


class QuizSerializer(serializers.Serializer):
    tipo_pele = serializers.ChoiceField(choices=OPCOES_TIPO_PELE)
    sensibilidade = serializers.ChoiceField(choices=OPCOES_SENSIBILIDADE)
    ressecamento = serializers.ChoiceField(choices=OPCOES_RESSECAMENTO)
    preferencia = serializers.ChoiceField(choices=OPCOES_PREFERENCIA)
    evita_fragrancia = serializers.ChoiceField(choices=OPCOES_SIM_NAO)
    quer_vegano = serializers.ChoiceField(choices=OPCOES_SIM_NAO)
    alergia_ingrediente = IngredientePorNomeField(
        slug_field='nome',
        queryset=Ingrediente.objects.all(),
        many=True,
        required=False,
        help_text='Nomes de ingredientes cadastrados (GET /api/v1/catalog/ingredientes/). '
                  'Omitido ou vazio: sem alergia.',
    )

    def validate_alergia_ingrediente(self, value):
        return [ingrediente.nome for ingrediente in value]


class ProdutoRecomendadoSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='produto.id', read_only=True)
    nome = serializers.CharField(source='produto.nome', read_only=True)
    imagem = serializers.ImageField(source='produto.imagem', read_only=True)
    tipo_pele_indicado = serializers.ChoiceField(
        source='produto.tipo_pele_indicado', choices=TipoPeleIndicado.choices, read_only=True)
    base = serializers.ChoiceField(source='produto.base', choices=BaseProduto.choices, read_only=True)
    essencia = serializers.CharField(source='produto.essencia', read_only=True)
    prob = serializers.FloatField(
        read_only=True,
        help_text='Estimativa do modelo (0 a 1) usada para ordenar. Não é garantia de compatibilidade.',
    )


class RecomendacaoSerializer(serializers.Serializer):
    produtos = ProdutoRecomendadoSerializer(many=True, read_only=True)
    aviso = serializers.CharField(read_only=True)
