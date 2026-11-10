from collections import Counter
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import (
    MateriaPrima, FichaTecnica, MovimentacaoEstoque, TIPOS_COM_PEDIDO, MovimentacaoMaterial, Fornecedor,
    VinculoFornecedor, CompraFornecedor, CompraFornecedorItem, LoteMateriaPrima, LoteProdutoVariacao,
    TIPOS_MATERIAL_AUTOMATICOS_COM_FORNECEDOR, CATEGORIA_MATERIA_PRIMA_CHOICES, TIPOS_MATERIAL_AUTOMATICOS,
)
from .services import (
    registrar_movimentacao_estoque, registrar_movimentacao_material, criar_compra_fornecedor_completa,
    definir_categorias_fornecedor, criar_lote_materia_prima, criar_lote_variacao,
)


def _validar_validade_nao_vencida(value):
    if value is not None and value < timezone.localdate():
        raise serializers.ValidationError('A data de validade não pode estar no passado.')
    return value


class CategoriasFornecedorField(serializers.ListField):
    child = serializers.ChoiceField(choices=CATEGORIA_MATERIA_PRIMA_CHOICES)

    def to_representation(self, data):
        return [c.categoria for c in data.all()]


class MateriaPrimaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MateriaPrima
        fields = [
            'id',
            'sku',
            'nome',
            'tipo',
            'unidade_medida',
            'quantidade_estoque',
            'custo_unitario_referencia',
            'apagada_em',
        ]
        read_only_fields = ['id', 'quantidade_estoque', 'apagada_em']
        extra_kwargs = {
            'custo_unitario_referencia': {'min_value': Decimal('0.0000')}
        }

    def validate_sku(self, value):
        sku_normalizado = value.strip().upper()
        return sku_normalizado

    def validate_unidade_medida(self, value):
        if self.instance is None:
            return value

        if value == self.instance.unidade_medida:
            return value

        possui_movimentacao = MovimentacaoMaterial.objects.filter(lote_materia_prima__materia_prima=self.instance).exists()

        if possui_movimentacao:
            raise serializers.ValidationError('A unidade de medida não pode ser alterada, pois existem movimentações vinculadas a lotes desta matéria-prima.')

        return value


class FornecedorSerializer(serializers.ModelSerializer):
    categorias = CategoriasFornecedorField(allow_empty=False)

    class Meta:
        model = Fornecedor
        fields = [
            'id',
            'nome',
            'categorias',
            'plataforma',
            'email',
            'telefone',
            'prazo_medio_entrega_em_dias',
            'forma_pagamento',
            'link',
            'favorito',
            'apagado_em',
        ]
        read_only_fields = ['id', 'apagado_em']
        extra_kwargs = {'prazo_medio_entrega_em_dias': {'min_value': 1}}

    def validate_categorias(self, value):
        return list(dict.fromkeys(value))

    def create(self, validated_data):
        categorias = validated_data.pop('categorias')
        fornecedor = super().create(validated_data)
        definir_categorias_fornecedor(fornecedor, categorias)
        return fornecedor

    def update(self, instance, validated_data):
        categorias = validated_data.pop('categorias', None)
        fornecedor = super().update(instance, validated_data)
        if categorias is not None:
            definir_categorias_fornecedor(fornecedor, categorias)
        return fornecedor


class CompraFornecedorItemSerializer(serializers.ModelSerializer):
    numero_lote_fabricante = serializers.CharField(max_length=50, required=False, allow_blank=True, write_only=True,)
    data_validade = serializers.DateField(required=False, allow_null=True, write_only=True)
    lote = serializers.SerializerMethodField()

    class Meta:
        model = CompraFornecedorItem
        fields = [
            'id',
            'materia_prima',
            'quantidade_item',
            'custo_unitario_momento_compra',
            'numero_lote_fabricante',
            'data_validade',
            'lote',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'quantidade_item': {'min_value': Decimal('0.001'), 'max_value': Decimal('999')},
        }

    def get_lote(self, obj):
        lote = next(iter(obj.lote_materiais.all()), None)
        return lote.pk if lote else None

    def validate_data_validade(self, value):
        return _validar_validade_nao_vencida(value)


class CompraFornecedorDetalhadaSerializer(serializers.ModelSerializer):
    itens = CompraFornecedorItemSerializer(many=True, read_only=True, source='fornecedor_itens')

    class Meta:
        model = CompraFornecedor
        fields = [
            'id',
            'fornecedor',
            'status',
            'valor_total',
            'observacao',
            'compra_realizada_em',
            'atualizada_em',
            'itens',
        ]
        read_only_fields = ['id', 'status', 'valor_total', 'compra_realizada_em', 'atualizada_em']


class CompraFornecedorSerializer(CompraFornecedorDetalhadaSerializer):
    itens = CompraFornecedorItemSerializer(many=True, write_only=True)

    def validate_itens(self, value):
        if not value:
            raise serializers.ValidationError('A compra deve conter pelo menos um item.')

        contagem = Counter(item['materia_prima'] for item in value)
        repetidas = sorted(v.sku for v, qtd in contagem.items() if qtd > 1)

        if repetidas:
            raise serializers.ValidationError(
                f'Matérias-prima repetidas nos itens: {", ".join(repetidas)}. '
                'Some as quantidades em um único item.'
            )

        return value

    def create(self, validated_data):
        itens_data = validated_data.pop('itens')

        return criar_compra_fornecedor_completa(
            usuario=self.context['request'].user,
            dados_compra=validated_data,
            itens_data=itens_data,
        )

    def to_representation(self, instance):
        return CompraFornecedorDetalhadaSerializer(instance, context=self.context).data


class CompraFornecedorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompraFornecedor
        fields = [
            'observacao',
        ]

    def update(self, instance, validated_data):
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        instance.save(update_fields=[*validated_data.keys(), 'atualizada_em'])
        return instance

    def to_representation(self, instance):
        return CompraFornecedorDetalhadaSerializer(instance, context=self.context).data


class VinculoFornecedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = VinculoFornecedor
        fields = [
            'id',
            'fornecedor',
            'materia_prima',
            'custo_unitario_fornecedor',
            'sku_materia_prima_fornecedor',
            'apagado_em',
        ]
        read_only_fields = ['id', 'apagado_em']
        extra_kwargs = {
            'custo_unitario_fornecedor': {'min_value': Decimal('0.0000')}
        }


class VinculoFornecedorDetalhadoSerializer(VinculoFornecedorSerializer):
    materia_prima = MateriaPrimaSerializer(read_only=True)

    class Meta(VinculoFornecedorSerializer.Meta):
        pass


class VinculoFornecedorUpdateSerializer(VinculoFornecedorSerializer):
    class Meta(VinculoFornecedorSerializer.Meta):
        read_only_fields = ['id', 'materia_prima', 'apagado_em']


class FichaTecnicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = FichaTecnica
        fields = [
            'id',
            'variacao',
            'materia_prima',
            'quantidade_necessaria',
            'apagada_em'
        ]
        read_only_fields = ['id', 'apagada_em']
        extra_kwargs = {
            'quantidade_necessaria': {'min_value': Decimal('0.001')}
        }


class FichaTecnicaDetalhadaSerializer(FichaTecnicaSerializer):
    materia_prima = MateriaPrimaSerializer(read_only=True)

    class Meta(FichaTecnicaSerializer.Meta):
        pass


class FichaTecnicaUpdateSerializer(FichaTecnicaSerializer):
    class Meta(FichaTecnicaSerializer.Meta):
        read_only_fields = ['id', 'variacao', 'apagada_em']


class LoteMateriaPrimaSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source='materia_prima.sku', read_only=True)
    materia_prima_nome = serializers.CharField(source='materia_prima.nome', read_only=True)

    class Meta:
        model = LoteMateriaPrima
        fields = [
            'id',
            'materia_prima',
            'sku',
            'materia_prima_nome',
            'compra_fornecedor_item',
            'numero_lote_fabricante',
            'quantidade_inicial',
            'quantidade_atual',
            'status',
            'data_validade',
            'observacao',
            'criado_em',
        ]
        read_only_fields = [
            'id', 'compra_fornecedor_item', 'quantidade_inicial', 'quantidade_atual', 'status', 'criado_em',
        ]

    def validate_data_validade(self, value):
        return _validar_validade_nao_vencida(value)

    def create(self, validated_data):
        return criar_lote_materia_prima(**validated_data)


class LoteProdutoVariacaoSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source='variacao.sku', read_only=True)
    variacao_nome = serializers.CharField(source='variacao.nome', read_only=True)
    produto_nome = serializers.CharField(source='variacao.produto.nome', read_only=True)

    class Meta:
        model = LoteProdutoVariacao
        fields = [
            'id',
            'variacao',
            'sku',
            'variacao_nome',
            'produto_nome',
            'numero_lote',
            'data_fabricacao',
            'data_validade',
            'quantidade_inicial',
            'quantidade_atual',
            'status',
            'observacao',
            'criado_em',
        ]
        read_only_fields = ['id', 'quantidade_inicial', 'quantidade_atual', 'status', 'criado_em']
        extra_kwargs = {
            'numero_lote': {'required': False},
            'data_fabricacao': {'required': False},
        }

    def validate(self, attrs):
        data_fabricacao = attrs.get('data_fabricacao') or timezone.localdate()
        data_validade = attrs.get('data_validade')

        _validar_validade_nao_vencida(data_validade)

        if data_validade is not None and data_validade < data_fabricacao:
            raise serializers.ValidationError(
                {'data_validade': 'A validade deve ser igual ou posterior à data de fabricação.'})

        return attrs

    def create(self, validated_data):
        return criar_lote_variacao(**validated_data)


class FabricarVariacaoSerializer(serializers.Serializer):
    quantidade = serializers.IntegerField(min_value=1, max_value=100000)
    data_validade = serializers.DateField()
    data_fabricacao = serializers.DateField(required=False)
    numero_lote = serializers.CharField(max_length=50, required=False, allow_blank=True)
    observacao = serializers.CharField(required=False, allow_blank=True)

    def validate_numero_lote(self, value):
        value = value.strip()
        if value and LoteProdutoVariacao.objects.filter(numero_lote=value).exists():
            raise serializers.ValidationError('Já existe um lote com este número.')
        return value

    def validate(self, attrs):
        data_fabricacao = attrs.get('data_fabricacao') or timezone.localdate()
        data_validade = attrs['data_validade']

        _validar_validade_nao_vencida(data_validade)

        if data_validade < data_fabricacao:
            raise serializers.ValidationError(
                {'data_validade': 'A validade deve ser igual ou posterior à data de fabricação.'})

        return attrs


class MovimentacaoEstoqueSerializer(serializers.ModelSerializer):
    numero_lote = serializers.CharField(source='lote_produto_variacao.numero_lote', read_only=True)
    variacao = serializers.IntegerField(source='lote_produto_variacao.variacao_id', read_only=True)
    sku = serializers.CharField(source='lote_produto_variacao.variacao.sku', read_only=True)
    variacao_nome = serializers.CharField(source='lote_produto_variacao.variacao.nome', read_only=True)
    produto_nome = serializers.CharField(source='lote_produto_variacao.variacao.produto.nome', read_only=True)

    class Meta:
        model = MovimentacaoEstoque
        fields = [
            'id',
            'lote_produto_variacao',
            'numero_lote',
            'sku',
            'variacao',
            'variacao_nome',
            'produto_nome',
            'usuario',
            'pedido',
            'tipo',
            'quantidade_movimentada',
            'observacao',
            'movimentado_em',
        ]
        read_only_fields = ['id', 'usuario', 'pedido', 'movimentado_em']
        extra_kwargs = {
            'quantidade_movimentada': {'min_value': 1, 'max_value': 100000}
        }

    def validate_tipo(self, value):
        if value in TIPOS_COM_PEDIDO:
            raise serializers.ValidationError('Este tipo é gerado automaticamente pelo pedido.')
        return value

    def create(self, validated_data):
        return registrar_movimentacao_estoque(
            lote_id=validated_data['lote_produto_variacao'].pk,
            tipo=validated_data['tipo'],
            quantidade=validated_data['quantidade_movimentada'],
            usuario=self.context['request'].user,
            observacao=validated_data.get('observacao'),
        )


class MovimentacaoMaterialSerializer(serializers.ModelSerializer):
    numero_lote_fabricante = serializers.CharField(source='lote_materia_prima.numero_lote_fabricante', read_only=True)
    materia_prima = serializers.IntegerField(source='lote_materia_prima.materia_prima_id', read_only=True)
    sku = serializers.CharField(source='lote_materia_prima.materia_prima.sku', read_only=True)
    materia_prima_nome = serializers.CharField(source='lote_materia_prima.materia_prima.nome', read_only=True)
    fornecedor_nome = serializers.CharField(source='fornecedor.nome', read_only=True)

    class Meta:
        model = MovimentacaoMaterial
        fields = [
            'id',
            'lote_materia_prima',
            'numero_lote_fabricante',
            'sku',
            'materia_prima',
            'materia_prima_nome',
            'fornecedor',
            'fornecedor_nome',
            'tipo',
            'quantidade_movimentada',
            'observacao',
            'movimentado_em',
        ]
        read_only_fields = ['id', 'usuario', 'movimentado_em']
        extra_kwargs = {
            'quantidade_movimentada': {'min_value': Decimal('0.001'), 'max_value': Decimal('100000')}
        }

    def validate_tipo(self, value):
        if value in TIPOS_MATERIAL_AUTOMATICOS:
            raise serializers.ValidationError('Este tipo é gerado automaticamente na operação de fabricação de um produto.')

        if value in TIPOS_MATERIAL_AUTOMATICOS_COM_FORNECEDOR:
            raise serializers.ValidationError('Este tipo é gerado automaticamente pela compra de um fornecedor.')

        return value

    def create(self, validated_data):
        return registrar_movimentacao_material(
            lote_id=validated_data['lote_materia_prima'].pk,
            tipo=validated_data['tipo'],
            quantidade=validated_data['quantidade_movimentada'],
            usuario=self.context['request'].user,
            fornecedor=validated_data.get('fornecedor'),
            observacao=validated_data.get('observacao'),
        )