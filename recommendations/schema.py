from drf_spectacular.utils import extend_schema, extend_schema_view

from core.schema import EX_VALIDACAO, exemplo_erro, resposta_erro
from .serializers import QuizSerializer, RecomendacaoSerializer

TAG = 'Recomendações'

_EX_OPCAO_INVALIDA = exemplo_erro(
    'validation_error', 'Dados inválidos.',
    {'tipo_pele': ['"muito_seca" não é uma escolha válida.']},
    nome='opcao_invalida')
_EX_INGREDIENTE_INEXISTENTE = exemplo_erro(
    'validation_error', 'Dados inválidos.',
    {'alergia_ingrediente': ['Objeto com nome=abacate não existe.']},
    nome='ingrediente_inexistente')
_EX_THROTTLED = exemplo_erro(
    'throttled', 'Pedido foi suprimido. Espera-se que esteja diponível em 42 segundos.')
_EX_MODELO = exemplo_erro(
    'modelo_indisponivel', 'O modelo de recomendação está indisponível no momento.')

recomendacao_schema = extend_schema_view(
    post=extend_schema(
        tags=[TAG],
        summary='Recomendar sabonetes pelo quiz',
        description='Rota pública (sem login). Recebe as respostas do quiz e devolve até 3 produtos ativos '
                    'do catálogo, ordenados pela estimativa da árvore de decisão (`prob`). '
                    'Antes do modelo, regras fixas removem os produtos com ingrediente declarado em '
                    '`alergia_ingrediente` e, se `quer_vegano = 1`, os não veganos. '
                    'Produtos com `prob` abaixo de 0,5 não são mostrados: a lista pode vir vazia. '
                    '`aviso` é sempre: "Não realiza diagnóstico dermatológico nem recomenda tratamento." '
                    'Limitado por IP (padrão: 20 requisições por minuto).',
        request=QuizSerializer,
        responses={
            200: RecomendacaoSerializer,
            400: resposta_erro('Resposta fora das opções ou ingrediente não cadastrado.',
                               EX_VALIDACAO, _EX_OPCAO_INVALIDA, _EX_INGREDIENTE_INEXISTENTE),
            429: resposta_erro('Limite de requisições por IP atingido.', _EX_THROTTLED),
            503: resposta_erro('Modelo de recomendação indisponível.', _EX_MODELO),
        },
    ),
)
