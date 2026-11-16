
import os
from types import SimpleNamespace

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

import django
django.setup()

from django.urls import resolve
from rest_framework.test import (
    APIRequestFactory,
    force_authenticate,
)


dados = {
    "peso_g": 100,
    "unidade": 1,
    "formato": "Barra",
    "tipo_sabonete": "Corporal",
    "tipo_pele": "Todos os tipos",
    "embalagem": "Não informado",
    "base_sabonete": "Processo a frio",
    "tipo_vendedor": "Artesanal",
    "custo_unitario": "12.50",
    "margem_desejada": "30"
}

caminho = "/api/v1/intelligence/prever-preco/"

factory = APIRequestFactory()

requisicao = factory.post(
    caminho,
    dados,
    format="json"
)

# Autenticação simulada exclusivamente para o teste local.
# Não altera a segurança da API real.
usuario_teste = SimpleNamespace(
    is_authenticated=True,
    is_active=True,
)

force_authenticate(
    requisicao,
    user=usuario_teste
)

view = resolve(caminho).func
resposta = view(requisicao)

print("Status HTTP:", resposta.status_code)
print("Resposta:", resposta.data)
