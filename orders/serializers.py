import re
from collections import Counter
from decimal import Decimal

from rest_framework import serializers

from core.mixins import ValidaEnderecoMixin, ValidaNomeCompletoMixin, ValidaCpfCnpjMixin
from orders.models import Pedido, PedidoItem, Cliente, StatusPedido
from orders.services import criar_pedido_completo, calcular_subtotal, calcular_valor_desconto
from orders.exceptions import DescontoInvalido

STATUS_EDITAVEIS = {StatusPedido.PENDENTE}

class ClienteSerializer(serializers.ModelSerializer, ValidaNomeCompletoMixin, ValidaCpfCnpjMixin):
    class Meta:
        model = Cliente
        fields = ['id', 'nome', 'telefone', 'cpf_cnpj', 'ultimo_pedido_em', 'criado_em']
        read_only_fields = ['ultimo_pedido_em', 'criado_em']


class PedidoItemSerializer(serializers.ModelSerializer):
    promocao = serializers.SerializerMethodField()
    valor_final = serializers.SerializerMethodField()

    class Meta:
        model = PedidoItem
        fields = [
            'id',
            'variacao',
            'quantidade_item',
            'valor_unitario',
            'valor_desconto',
            'valor_final',
            'promocao',
        ]
        read_only_fields = ['valor_unitario', 'valor_desconto']
        extra_kwargs = {
            'quantidade_item': {'min_value': 1, 'max_value': 1000},
        }

    def get_promocao(self, obj):
        return obj.variacao.preco_promo is not None

    def get_valor_final(self, obj):
        return obj.valor_final


class PedidoDetalhadoSerializer(ValidaEnderecoMixin, serializers.ModelSerializer):
    itens = PedidoItemSerializer(many=True, read_only=True, source='pedido_itens')

    class Meta:
        model = Pedido
        fields = [
            'id',
            'cliente',
            'cep',
            'numero_residencia',
            'logradouro',
            'complemento',
            'bairro',
            'cidade',
            'sigla_estado',
            'status',
            'valor_subtotal',
            'tipo_desconto',
            'desconto',
            'valor_desconto',
            'valor_total',
            'observacao',
            'criado_em',
            'atualizado_em',
            'itens',
        ]
        read_only_fields = [
            'status',
            'valor_subtotal',
            'valor_desconto',
            'valor_total',
            'criado_em',
            'atualizado_em',
        ]


class PedidoSerializer(PedidoDetalhadoSerializer):
    itens = PedidoItemSerializer(many=True, write_only=True)

    def validate_itens(self, value):
        if not value:
            raise serializers.ValidationError('O pedido deve conter pelo menos um item.')

        contagem = Counter(item['variacao'] for item in value)
        repetidas = sorted(v.sku for v, qtd in contagem.items() if qtd > 1)

        if repetidas:
            raise serializers.ValidationError(
                f'Variações repetidas nos itens: {", ".join(repetidas)}. '
                'Some as quantidades em um único item.'
            )

        return value

    def validate_cep(self, value):
        if value:
            if not re.match(r'^\d{5}-\d{3}$', value):
                raise serializers.ValidationError('O CEP deve estar no formato correto. Exemplo: 13251-441')

        limpo = value.replace('-', '')

        return limpo

    def validate(self, attrs):
        attrs = super().validate(attrs)

        tipo = attrs.get('tipo_desconto') or ''
        desconto = attrs.get('desconto') or Decimal('0')

        if desconto > 0 and not tipo:
            raise serializers.ValidationError(
                {'tipo_desconto': 'Informe o tipo do desconto (FIXO ou PERCENTUAL).'}
            )

        if desconto == 0:
            attrs['tipo_desconto'] = ''
            attrs['desconto'] = Decimal('0.00')
            return attrs

        subtotal = calcular_subtotal(attrs['itens'])
        try:
            calcular_valor_desconto(subtotal, tipo, desconto)
        except DescontoInvalido as exc:
            raise serializers.ValidationError({'desconto': str(exc)})

        return attrs

    def create(self, validated_data):
        itens_data = validated_data.pop('itens')

        return criar_pedido_completo(
            usuario=self.context['request'].user,
            dados_pedido=validated_data,
            itens_data=itens_data,
        )

    def to_representation(self, instance):
        return PedidoDetalhadoSerializer(instance, context=self.context).data


class PedidoUpdateSerializer(ValidaEnderecoMixin, serializers.ModelSerializer):
    class Meta:
        model = Pedido
        fields = [
            'cep',
            'logradouro',
            'numero_residencia',
            'complemento',
            'bairro',
            'cidade',
            'sigla_estado',
            'observacao',
        ]

    def validate(self, attrs):
        if self.instance.status not in STATUS_EDITAVEIS:
            raise serializers.ValidationError(
                f'Pedido {self.instance.get_status_display().lower()} não pode mais ser alterado.'
            )
        return super().validate(attrs)

    def update(self, instance, validated_data):
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        instance.save(update_fields=[*validated_data.keys(), 'atualizado_em'])
        return instance

    def to_representation(self, instance):
        return PedidoDetalhadoSerializer(instance, context=self.context).data