from rest_framework import serializers

CAMPOS_ENDERECO_OBRIGATORIOS = [
    'cep', 'logradouro', 'numero_residencia', 'bairro', 'cidade', 'sigla_estado',
]

class ValidaEnderecoMixin:
    def validate(self, attrs):
        def valor(campo):
            if campo in attrs:
                return attrs[campo]
            return getattr(self.instance, campo, '') if self.instance else ''

        campos = [*CAMPOS_ENDERECO_OBRIGATORIOS, 'complemento']
        if any(valor(c) for c in campos):
            faltando = {
                c: 'Obrigatório quando o endereço é informado.'
                for c in CAMPOS_ENDERECO_OBRIGATORIOS
                if not valor(c)
            }
            if faltando:
                raise serializers.ValidationError(faltando)
        return attrs


class SkuRelatedField(serializers.SlugRelatedField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            data = data.strip().upper()
        return super().to_internal_value(data)


class FiltrosSomenteNaLeituraMixin:
    def filter_queryset(self, queryset):
        if self.action not in ('list', 'retrieve'):
            return queryset
        return super().filter_queryset(queryset)