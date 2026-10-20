from collections import Counter
from decimal import Decimal

from rest_framework import serializers

from core.mixins import VariacaoPorIdOuSkuMixin, MateriaPrimaPorIdOuSkuMixin
from .models import MateriaPrima, FichaTecnica, MovimentacaoEstoque, TIPOS_COM_PEDIDO, MovimentacaoMaterial, Fornecedor, \
    VinculoFornecedor, CompraFornecedor, CompraFornecedorItem, \
    TIPOS_MATERIAL_AUTOMATICOS_COM_FORNECEDOR
from .services import registrar_movimentacao_estoque, registrar_movimentacao_material, criar_compra_fornecedor_completa


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


class FornecedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fornecedor
        fields = [
            'id',
            'nome',
            'categoria',
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


class CompraFornecedorItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompraFornecedorItem
        fields = [
            'id',
            'materia_prima',
            'quantidade_item',
            'custo_unitario_momento_compra',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'quantidade_item': {'min_value': Decimal('0.001'), 'max_value': Decimal('999')},
        }


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


class MovimentacaoEstoqueSerializer(VariacaoPorIdOuSkuMixin, serializers.ModelSerializer):
    class Meta:
        model = MovimentacaoEstoque
        fields = [
            'id',
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
            variacao_id=validated_data['variacao'].pk,
            tipo=validated_data['tipo'],
            quantidade=validated_data['quantidade_movimentada'],
            usuario=self.context['request'].user,
            observacao=validated_data.get('observacao'),
        )


class MovimentacaoMaterialSerializer(MateriaPrimaPorIdOuSkuMixin, serializers.ModelSerializer):
    fornecedor_nome = serializers.CharField(source='fornecedor.nome', read_only=True)

    class Meta:
        model = MovimentacaoMaterial
        fields = [
            'id',
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
        if value in TIPOS_MATERIAL_AUTOMATICOS_COM_FORNECEDOR:
            raise serializers.ValidationError('Este tipo é gerado automaticamente pela compra de um fornecedor.')
        return value

    def create(self, validated_data):
        return registrar_movimentacao_material(
            materia_prima_id=validated_data['materia_prima'].pk,
            tipo=validated_data['tipo'],
            quantidade=validated_data['quantidade_movimentada'],
            usuario=self.context['request'].user,
            fornecedor=validated_data.get('fornecedor'),
            observacao=validated_data.get('observacao'),
        )