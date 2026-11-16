from drf_spectacular.utils import (
    OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view,
)

from core.schema import (
    ERRO_401, ERRO_403, ERRO_404, EX_VALIDACAO,
    crud_schema, exemplo_erro, resposta_erro,
)
from .serializers import ClienteSerializer, PedidoDetalhadoSerializer, PedidoSerializer

TAG_CLIENTES = 'Clientes'
TAG_PEDIDOS = 'Pedidos'

cliente_schema = extend_schema_view(**crud_schema(
    TAG_CLIENTES, 'cliente', 'clientes',
    leitura=ClienteSerializer,
))

PARAM_ORDERING_PEDIDO = OpenApiParameter(
    name="ordering",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    description=(
        "Campos de ordenação: criado_em, atualizado_em, valor_total, id. "
        "Use '-' para ordem decrescente (ex.: ?ordering=-criado_em). "
        "Separe por vírgula para ordenar por mais de um campo "
        "(ex.: ?ordering=-valor_total,criado_em)."
    ),
)

_EX_TRANSICAO = exemplo_erro(
    'transicao_status_invalida', 'Não é possível mudar o pedido de CANCELADO para CONCLUIDO.',
    {'atual': 'CANCELADO', 'novo': 'CONCLUIDO'})
_EX_ESTOQUE = exemplo_erro(
    'estoque_insuficiente',
    'Estoque insuficiente para "Sabonete" (SKU SAB-01). Saldo atual: 2, solicitado: 5.',
    {'ids': 1, 'sku': 'SAB-01', 'produto': 'Sabonete', 'saldo': 2, 'solicitado': 5})
_EX_PEDIDO_NAO_EDITAVEL = exemplo_erro(
    'validation_error', 'Dados inválidos.',
    {'non_field_errors': ['Pedido concluído não pode mais ser alterado.']},
    nome='pedido_nao_editavel')
_EX_ITENS_VAZIO = exemplo_erro(
    'validation_error', 'Dados inválidos.',
    {'itens': ['O pedido deve conter pelo menos um item.']},
    nome='itens_vazio')
_EX_ITENS_REPETIDOS = exemplo_erro(
    'validation_error', 'Dados inválidos.',
    {'itens': ['Variações repetidas nos itens: [3]. Some as quantidades em um único item.']},
    nome='variacoes_repetidas')
_EX_DESCONTO_SEM_TIPO = exemplo_erro(
    'validation_error', 'Dados inválidos.',
    {'tipo_desconto': ['Informe o tipo do desconto (FIXO ou PERCENTUAL).']},
    nome='desconto_sem_tipo')
_EX_DESCONTO_FIXO_MAIOR = exemplo_erro(
    'validation_error', 'Dados inválidos.',
    {'desconto': ['O desconto fixo (R$ 80.00) não pode ser maior que o subtotal do pedido (R$ 50.00).']},
    nome='desconto_fixo_maior_que_subtotal')
_EX_DESCONTO_PERCENTUAL_MAIOR = exemplo_erro(
    'validation_error', 'Dados inválidos.',
    {'desconto': ['O desconto percentual não pode ser maior que 100%.']},
    nome='desconto_percentual_acima_de_100')
_EX_CLIENTE_ID_INVALIDO = exemplo_erro(
    'validation_error', 'Dados inválidos.',
    {'cliente_id': ['Informe um número.']},
    nome='cliente_id_invalido')
_EX_LOTE_VENCIDO = exemplo_erro(
    'lote_indisponivel',
    'O lote "SAB-01-20261028-01" está vencido e não aceita esta movimentação.')

_REQUEST_SEM_DESCONTO = OpenApiExample(
    'Pedido sem desconto',
    request_only=True,
    value={
        'cliente': 1,
        'cep': '13251-441',
        'logradouro': 'Rua das Flores',
        'numero_residencia': '120',
        'bairro': 'Centro',
        'cidade': 'Itatiba',
        'sigla_estado': 'SP',
        'observacao': '',
        'itens': [
            {'variacao': 1, 'quantidade_item': 2},
            {'variacao': 2, 'quantidade_item': 1},
        ],
    },
)
_REQUEST_DESCONTO_FIXO = OpenApiExample(
    'Pedido com desconto fixo (R$)',
    request_only=True,
    value={
        'cliente': 1,
        'cep': '13251-441',
        'logradouro': 'Rua das Flores',
        'numero_residencia': '120',
        'bairro': 'Centro',
        'cidade': 'Itatiba',
        'sigla_estado': 'SP',
        'observacao': '',
        'itens': [
            {'variacao': 1, 'quantidade_item': 2},
            {'variacao': 2, 'quantidade_item': 1},
        ],
        'tipo_desconto': 'FIXO',
        'desconto': '10.00',
    },
)
_REQUEST_DESCONTO_PERCENTUAL = OpenApiExample(
    'Pedido com desconto percentual (%)',
    request_only=True,
    value={
        'cliente': 1,
        'cep': '13251-441',
        'logradouro': 'Rua das Flores',
        'numero_residencia': '120',
        'bairro': 'Centro',
        'cidade': 'Itatiba',
        'sigla_estado': 'SP',
        'observacao': '',
        'itens': [
            {'variacao': 1, 'quantidade_item': 2},
            {'variacao': 2, 'quantidade_item': 1},
        ],
        'tipo_desconto': 'PERCENTUAL',
        'desconto': '20.00',
    },
)
_RESPONSE_COM_DESCONTO = OpenApiExample(
    'Pedido criado com desconto fixo de R$ 10,00',
    response_only=True,
    status_codes=['201'],
    value={
        'id': 42,
        'cliente': 1,
        'cep': '13251441',
        'numero_residencia': '120',
        'logradouro': 'Rua das Flores',
        'complemento': '',
        'bairro': 'Centro',
        'cidade': 'Itatiba',
        'sigla_estado': 'SP',
        'status': 'PENDENTE',
        'valor_subtotal': '50.00',
        'tipo_desconto': 'FIXO',
        'desconto': '10.00',
        'valor_desconto': '10.00',
        'valor_total': '40.00',
        'observacao': '',
        'criado_em': '2026-11-16T14:30:00Z',
        'atualizado_em': '2026-11-16T14:30:00Z',
        'itens': [
            {'id': 101, 'variacao': 1, 'quantidade_item': 2, 'valor_unitario': '20.00',
             'valor_desconto': '5.00', 'valor_final': '35.00', 'promocao': False},
            {'id': 102, 'variacao': 2, 'quantidade_item': 1, 'valor_unitario': '10.00',
             'valor_desconto': '5.00', 'valor_final': '5.00', 'promocao': False},
        ],
    },
)


def _acao(resumo, descricao):
    return extend_schema(
        tags=[TAG_PEDIDOS],
        summary=resumo,
        description=descricao,
        request=None,
        responses={
            200: PedidoDetalhadoSerializer,
            401: ERRO_401, 403: ERRO_403, 404: ERRO_404,
            409: resposta_erro('Transição de status inválida.', _EX_TRANSICAO),
        },
    )


pedido_schema = extend_schema_view(
    list=extend_schema(
        tags=[TAG_PEDIDOS], summary='Listar pedidos',
        description='Ordenados do mais recente para o mais antigo.',
        parameters=[PARAM_ORDERING_PEDIDO],
        responses={
            200: PedidoDetalhadoSerializer,
            400: resposta_erro('Parâmetro de filtro inválido.', _EX_CLIENTE_ID_INVALIDO),
            401: ERRO_401, 403: ERRO_403,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG_PEDIDOS], summary='Detalhar pedido',
        responses={200: PedidoDetalhadoSerializer, 401: ERRO_401, 403: ERRO_403, 404: ERRO_404},
    ),
    create=extend_schema(
        tags=[TAG_PEDIDOS], summary='Criar pedido',
        description='Baixa o estoque de cada item na criação, seguindo o FEFO (primeiro lote a vencer, '
                    'primeiro a sair): um item pode consumir mais de um lote, com uma saída por venda '
                    'em cada lote. Lotes vencidos ou esgotados não são usados, então o saldo considerado '
                    'é o dos lotes ativos. Tudo roda em uma transação: '
                    'se algum item não tiver saldo, nada é gravado. '
                    'Não pode haver variações repetidas entre os itens. '
                    'Status inicial: PENDENTE.\n\n'
                    '**Desconto (opcional):** informe `tipo_desconto` (`FIXO` em reais ou `PERCENTUAL` '
                    'de 0 a 100) e `desconto` (o valor ou o percentual). `tipo_desconto` é obrigatório '
                    'quando `desconto` for maior que zero. O desconto fixo não pode ser maior que o '
                    'subtotal do pedido. Se for percentual, ele é calculado sobre o subtotal '
                    '(soma de quantidade × valor unitário dos itens) e arredondado em centavos. '
                    'O valor em reais resultante (`valor_desconto`) é dividido igualmente entre os '
                    'itens do pedido e gravado em `valor_desconto` de cada item. Os centavos que sobrarem '
                    'da divisão vão para os primeiros itens (ordenados por id da variação). '
                    'Nenhum item recebe mais desconto do que o total da própria linha; o excedente é '
                    'redistribuído entre os demais. '
                    '`valor_total = valor_subtotal - valor_desconto`. '
                    '`valor_subtotal`, `valor_desconto` e `valor_total` são calculados pelo servidor '
                    'e ignorados se enviados.',
        request=PedidoSerializer,
        examples=[
            _REQUEST_SEM_DESCONTO, _REQUEST_DESCONTO_FIXO,
            _REQUEST_DESCONTO_PERCENTUAL, _RESPONSE_COM_DESCONTO,
        ],
        responses={
            201: PedidoDetalhadoSerializer,
            400: resposta_erro('Dados inválidos.', EX_VALIDACAO,
                               _EX_ITENS_VAZIO, _EX_ITENS_REPETIDOS,
                               _EX_DESCONTO_SEM_TIPO, _EX_DESCONTO_FIXO_MAIOR,
                               _EX_DESCONTO_PERCENTUAL_MAIOR),
            401: ERRO_401, 403: ERRO_403,
            409: resposta_erro('Estoque insuficiente nos lotes ativos.', _EX_ESTOQUE),
        },
    ),
    partial_update=extend_schema(
        tags=[TAG_PEDIDOS], summary='Atualizar pedido parcialmente',
        description='Altera apenas endereço e observação. O status e o desconto não são alterados aqui '
                    '(para o status, use `concluir`, `cancelar` e `estornar`). '
                    'Pedidos fora dos status editáveis retornam 400.',
        responses={
            200: PedidoDetalhadoSerializer,
            400: resposta_erro('Dados inválidos ou pedido não editável.',
                               EX_VALIDACAO, _EX_PEDIDO_NAO_EDITAVEL),
            401: ERRO_401, 403: ERRO_403, 404: ERRO_404,
        },
    ),
    concluir=_acao(
        'Concluir pedido',
        'Muda o status para concluído. O estoque já foi baixado na criação. '
        'Transições permitidas a partir de PENDENTE: CONCLUIDO e CANCELADO.'
    ),
    cancelar=_acao(
        'Cancelar pedido (COM devolução ao estoque automaticamente)',
        'Cancela o pedido e devolve cada item aos mesmos lotes de onde saiu, com um estorno '
        'de venda por lote. Movimenta o estoque. Se um lote já venceu, a quantidade volta '
        'para ele, mas não é somada ao estoque da variação. '
        'Transições permitidas a partir de PENDENTE: CONCLUIDO e CANCELADO.'
    ),
    estornar_com_devolucao=_acao(
        'Estornar pedido COM devolução ao estoque',
        'Muda o status para estornado e devolve cada item aos mesmos lotes de onde saiu, '
        'com um estorno de venda por lote. Movimenta o estoque. Se um lote já venceu, '
        'a quantidade volta para ele, mas não é somada ao estoque da variação. '
        'Transições permitidas a partir de CONCLUIDO: ESTORNADO_COM_DEVOLUCAO e ESTORNADO_SEM_DEVOLUCAO.'
    ),
    estornar_sem_devolucao=_acao(
        'Estornar pedido SEM devolução ao estoque',
        'Muda o status para estornado. Não movimenta o estoque. '
        'Transições permitidas a partir de CONCLUIDO: ESTORNADO_COM_DEVOLUCAO e ESTORNADO_SEM_DEVOLUCAO.'
    ),
)