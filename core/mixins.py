import re
import regex

from rest_framework import serializers
from validate_docbr import CPF, CNPJ

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


class ValidaNomeCompletoMixin:
    def validate_nome(self, value):
        nome_limpo = value.strip()

        if " " not in nome_limpo:
            raise serializers.ValidationError('Insira o nome completo.')

        if not regex.match(r"^\p{L}+(?:[ '\-]\p{L}+)*$", nome_limpo):
            raise serializers.ValidationError('Caracteres inválidos.')

        nome_limpo_dividido = nome_limpo.split(' ')

        for nome in nome_limpo_dividido:
            if len(nome) < 2:
                raise serializers.ValidationError('Insira um nome válido.')

        return nome_limpo


class ValidaCpfCnpjMixin:
    def validate_cpf_cnpj(self, value):
        if not value:
            return None

        limpo = re.sub(r'[^0-9A-Za-z]', '', value).upper()

        if len(limpo) == 11:
            if not limpo.isdigit() or not CPF().validate(limpo):
                raise serializers.ValidationError('CPF inválido.')
        elif len(limpo) == 14:
            if not CNPJ().validate(limpo):
                raise serializers.ValidationError('CNPJ inválido.')
        else:
            raise serializers.ValidationError(
                'Informe um CPF (11 caracteres) ou um CNPJ (14 caracteres).'
            )

        return limpo


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