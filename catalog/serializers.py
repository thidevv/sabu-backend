from decimal import Decimal

from rest_framework import serializers
from .models import Categoria, Produto, ProdutoVariacao, TipoPele
from core.constants import TAMANHO_MAXIMO_IMAGEM, FORMATOS_PERMITIDOS_IMAGEM


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nome']
        read_only_fields = ['id']


class TipoPeleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoPele
        fields = ['id', 'nome']
        read_only_fields = ['id']


class ProdutoVariacaoSerializer(serializers.ModelSerializer):
    produto_abstrato_esta_ativo = serializers.BooleanField(
        source='produto.esta_ativo',
        read_only=True,
    )

    class Meta:
        model = ProdutoVariacao
        fields = ['id', 'produto', 'sku', 'nome', 'imagem', 'preco', 'preco_promo',
                  'inicio_promo', 'fim_promo', 'peso_gramas',
                  'quantidade_estoque', 'apagado_em', 'produto_abstrato_esta_ativo']
        read_only_fields = ['id', 'imagem', 'apagado_em', 'quantidade_estoque']
        extra_kwargs = {
            'preco': {'min_value': Decimal('0')},
            'preco_promo': {'min_value': Decimal('0')},
            'peso_gramas': {'min_value': 1},
        }

    def validate_sku(self, value):
        sku_normalizado = value.strip().upper()
        return sku_normalizado

    def validate(self, attrs):
        def valor(campo):
            if campo in attrs:
                return attrs[campo]
            return getattr(self.instance, campo, None)

        preco = valor('preco')
        promo = valor('preco_promo')
        inicio = valor('inicio_promo')
        fim = valor('fim_promo')

        if promo is not None and preco is not None and promo >= preco:
            raise serializers.ValidationError(
                {'preco_promo': 'A promoção deve ser menor que o preço.'})

        if inicio is not None and fim is not None and inicio >= fim:
            raise serializers.ValidationError(
                {'fim_promo': 'O fim deve ser posterior ao início.'})

        if promo is not None and (inicio is None or fim is None):
            raise serializers.ValidationError(
                {'preco_promo': 'Informe o início e o fim da promoção.'})

        return attrs


class ProdutoVariacaoImagemSerializer(serializers.ModelSerializer):
    imagem = serializers.ImageField(required=True, allow_null=False)

    class Meta:
        model = ProdutoVariacao
        fields = ['imagem']

    def validate_imagem(self, value):
        if value.size > TAMANHO_MAXIMO_IMAGEM:
            raise serializers.ValidationError('A imagem deve ter no máximo 5 MB.')
        fmt = getattr(getattr(value, 'image', None), 'format', None)
        if fmt not in FORMATOS_PERMITIDOS_IMAGEM:
            raise serializers.ValidationError('Formato não permitido. Use JPEG, PNG ou WebP.')
        return value


class ProdutoVariacaoUpdateSerializer(ProdutoVariacaoSerializer):
    class Meta(ProdutoVariacaoSerializer.Meta):
        read_only_fields = ['id', 'imagem', 'apagado_em', 'quantidade_estoque']


class ProdutoSerializer(serializers.ModelSerializer):
    categorias = serializers.PrimaryKeyRelatedField(
        queryset=Categoria.objects.all(),
        many=True,
        required=False
    )

    tipo_pele = serializers.PrimaryKeyRelatedField(
        queryset=TipoPele.objects.all(),
        many=True,
        required=False
    )

    class Meta:
        model = Produto
        fields = [
            'id',
            'nome',
            'descricao',
            'imagem',
            'esta_ativo',
            'criado_em',
            'tipo_pele',
            'categorias',
        ]
        read_only_fields = ['id', 'imagem', 'criado_em']


class ProdutoImagemSerializer(serializers.ModelSerializer):
    imagem = serializers.ImageField(required=True, allow_null=False)

    class Meta:
        model = Produto
        fields = ['imagem']

    def validate_imagem(self, value):
        if value.size > TAMANHO_MAXIMO_IMAGEM:
            raise serializers.ValidationError('A imagem deve ter no máximo 5 MB.')
        fmt = getattr(getattr(value, 'image', None), 'format', None)
        if fmt not in FORMATOS_PERMITIDOS_IMAGEM:
            raise serializers.ValidationError('Formato não permitido. Use JPEG, PNG ou WebP.')
        return value


class ProdutoDetalhadoSerializer(serializers.ModelSerializer):
    categorias = CategoriaSerializer(many=True, read_only=True)
    variacoes = ProdutoVariacaoSerializer(many=True, read_only=True)
    tipo_pele = TipoPeleSerializer(many=True, read_only=True)

    class Meta:
        model = Produto
        fields = [
            'id',
            'nome',
            'descricao',
            'imagem',
            'esta_ativo',
            'criado_em',
            'tipo_pele',
            'categorias',
            'variacoes',
        ]
        read_only_fields = ['id', 'imagem', 'criado_em']