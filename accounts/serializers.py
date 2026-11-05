from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from core.mixins import ValidaNomeCompletoMixin, ValidaCpfCnpjMixin
from .models import Usuario
import re


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        data = super().validate(attrs)

        if not self.user.cargo:
            raise serializers.ValidationError("O conta do usuário não está ativa.")

        if self.user.cargo != 'ADMIN':
            raise serializers.ValidationError("Somente admins podem fazer login.")

        data['id'] = self.user.id
        data['nome'] = self.user.nome
        data['cargo'] = self.user.cargo

        return data


class UsuarioCadastroSerializer(serializers.ModelSerializer, ValidaNomeCompletoMixin, ValidaCpfCnpjMixin):
    senha = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = Usuario
        fields = [
            'nome',
            'email',
            'senha',
            'telefone',
            'cpf_cnpj',
        ]

    def validate_senha(self, value):
        errors = []

        if len(value) < 8:
            errors.append("A senha não pode conter menos que 8 caracteres.")

        if not re.search(r'[A-Z]', value):
            errors.append("A senha deve conter pelo menos um caractere maiúsculo.")

        if not re.search(r'[0-9]', value):
            errors.append("A senha deve conter pelo menos um número.")

        if not re.search(r'[\W_]', value):
            errors.append("A senha deve conter pelo menos um caractere especial.")

        if errors:
            raise serializers.ValidationError(errors)

        return value

    def create(self, validated_data):
        senha = validated_data.pop('senha')

        usuario = Usuario.objects.create_user(
            password=senha,
            cargo='ADMIN',
            **validated_data
        )
        return usuario