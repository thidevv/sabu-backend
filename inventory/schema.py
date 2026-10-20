from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from core.schema import (
    ERRO_400, ERRO_400_FILTRO, ERRO_401, ERRO_403, ERRO_404, EX_VALIDACAO,
    crud_schema, exemplo_erro, resposta_erro, PARAM_APAGADAS,
)
from .serializers import (
    CompraFornecedorSerializer, CompraFornecedorDetalhadaSerializer,
    FichaTecnicaDetalhadaSerializer, FichaTecnicaSerializer, FichaTecnicaUpdateSerializer,
    FornecedorSerializer, MateriaPrimaSerializer, MovimentacaoEstoqueSerializer,
    MovimentacaoMaterialSerializer, VinculoFornecedorDetalhadoSerializer,
    VinculoFornecedorSerializer, VinculoFornecedorUpdateSerializer,
)

TAG = 'Estoque'

PARAM_APAGADOS = OpenApiParameter(
    name='apagados',
    type=bool,
    location=OpenApiParameter.QUERY,
    required=False,
    description='Omitido: ativos e apagados. `true`: só apagados. `false`: só ativos.',
)
ERRO_400_FILTRO_APAGADOS = resposta_erro(
    'Filtro inválido.',
    exemplo_erro('validation_error', 'Dados inválidos.', {'apagados': ['Informe true ou false.']}),
)

materia_prima_schema = extend_schema_view(**crud_schema(
    TAG, 'matéria-prima', 'matérias-primas',
    leitura=MateriaPrimaSerializer,
    destroy_extra={},
    params={'retrieve': [PARAM_APAGADAS]},
    list_extra={400: ERRO_400_FILTRO},
    retrieve_extra={400: ERRO_400_FILTRO},
    descricoes={
        'list': 'Ordenadas por nome. Sem `apagadas`, retorna ativas e apagadas. '
                '`apagadas=true`: só apagadas; `apagadas=false`: só ativas.',
        'destroy': 'Exclusão lógica. Os vínculos de fornecedor ativos desta matéria-prima '
                   'também são apagados logicamente.',
    },
))

fornecedor_schema = extend_schema_view(**crud_schema(
    TAG, 'fornecedor', 'fornecedores',
    leitura=FornecedorSerializer,
    destroy_extra={},
    params={'retrieve': [PARAM_APAGADOS]},
    list_extra={400: ERRO_400_FILTRO_APAGADOS},
    retrieve_extra={400: ERRO_400_FILTRO_APAGADOS},
    descricoes={
        'list': 'Ordenados por nome. Sem `apagados`, retorna ativos e apagados. '
                '`apagados=true`: só apagados; `apagados=false`: só ativos.',
        'destroy': 'Exclusão lógica. Os vínculos de fornecedor ativos deste fornecedor '
                   'também são apagados logicamente.',
    },
))

compra_fornecedor_schema = extend_schema_view(
    **crud_schema(
        TAG, 'compra', 'compras',
        leitura=CompraFornecedorDetalhadaSerializer,
        list_extra={
            400: resposta_erro(
                'Filtro inválido.',
                exemplo_erro('validation_error', 'Dados inválidos.',
                             {'fornecedor_id': ['Informe um número.']}),
            ),
        },
        descricoes={
            'list': 'Ordenadas da mais recente para a mais antiga. '
                    'Use `fornecedor_id` para filtrar por fornecedor.',
            'partial_update': 'Apenas `observacao` é editável.',
        },
        ops=('list', 'retrieve', 'partial_update'),
    ),
    create=extend_schema(
        tags=[TAG],
        summary='Registrar compra de fornecedor',
        description='Cria a compra e seus itens em uma única operação, registrando a entrada '
                    'de cada matéria-prima no estoque. É obrigatório ao menos um item, '
                    'sem repetir matéria-prima.',
        responses={
            201: CompraFornecedorSerializer,
            400: resposta_erro(
                'Dados inválidos.',
                EX_VALIDACAO,
                exemplo_erro(
                    'validation_error', 'Dados inválidos.',
                    {'itens': ['Matérias-prima repetidas nos itens: GLI-01. '
                               'Some as quantidades em um único item.']},
                    nome='itens_repetidos',
                ),
                exemplo_erro('compra_fornecedor_sem_item',
                             'A compra deve conter pelo menos um item.'),
            ),
            401: ERRO_401,
            403: ERRO_403,
        },
    ),
    devolver=extend_schema(
        tags=[TAG],
        summary='Devolver compra',
        description='Devolve a compra ao fornecedor, dando saída no estoque de cada matéria-prima '
                    'dos itens, e retorna a compra atualizada. Só é permitido quando o status '
                    'da compra permite a transição para devolvida.',
        request=None,
        responses={
            200: CompraFornecedorDetalhadaSerializer,
            401: ERRO_401,
            403: ERRO_403,
            404: ERRO_404,
            409: resposta_erro(
                'Transição de status inválida ou estoque insuficiente.',
                exemplo_erro(
                    'transicao_status_invalida',
                    'Transição de status inválida: DEVOLVIDO → DEVOLVIDO.',
                    {'atual': 'DEVOLVIDO', 'novo': 'DEVOLVIDO'},
                ),
                exemplo_erro(
                    'estoque_insuficiente',
                    'Estoque insuficiente para "Glicerina" (SKU GLI-01). Saldo atual: 2, solicitado: 5.',
                    {'ids': 1, 'sku': 'GLI-01', 'produto': 'Glicerina', 'saldo': 2, 'solicitado': 5},
                ),
            ),
        },
    ),
)

vinculo_fornecedor_schema = extend_schema_view(
    **crud_schema(
        TAG, 'vínculo de fornecedor', 'vínculos de fornecedor',
        leitura=VinculoFornecedorDetalhadoSerializer,
        escrita=VinculoFornecedorSerializer,
        atualizacao=VinculoFornecedorUpdateSerializer,
        destroy_extra={},
        params={'retrieve': [PARAM_APAGADOS]},
        list_extra={
            400: resposta_erro(
                'Filtro inválido.',
                exemplo_erro('validation_error', 'Dados inválidos.',
                             {'materia_prima_id': ['Informe um número.']},
                             nome='materia_prima_id_invalido'),
                exemplo_erro('validation_error', 'Dados inválidos.',
                             {'apagados': ['Informe true ou false.']},
                             nome='apagados_invalido'),
            ),
        },
        retrieve_extra={400: ERRO_400_FILTRO_APAGADOS},
        descricoes={
            'list': 'Sem `apagados`, retorna ativos e apagados. '
                    '`apagados=true`: só apagados; `apagados=false`: só ativos. '
                    'Os filtros `materia_prima_id` e `apagados` podem ser combinados.',
            'update': 'Só vínculos ativos; vínculos apagados retornam 404 (restaure antes). '
                      'A matéria-prima não pode ser alterada.',
            'partial_update': 'Só vínculos ativos; vínculos apagados retornam 404 (restaure antes). '
                              'A matéria-prima não pode ser alterada.',
            'destroy': 'Exclusão lógica. Vínculo já apagado retorna 404.',
        },
    ),
    restaurar=extend_schema(
        tags=[TAG],
        summary='Restaurar vínculo de fornecedor',
        description='Desfaz a exclusão lógica. A matéria-prima e o fornecedor precisam estar '
                    'ativos (restaure-os antes).',
        request=None,
        responses={200: VinculoFornecedorDetalhadoSerializer, 400: ERRO_400,
                   401: ERRO_401, 403: ERRO_403, 404: ERRO_404},
    ),
)

ficha_tecnica_schema = extend_schema_view(
    **crud_schema(
        TAG, 'ficha técnica', 'fichas técnicas',
        leitura=FichaTecnicaDetalhadaSerializer,
        escrita=FichaTecnicaSerializer,
        atualizacao=FichaTecnicaUpdateSerializer,
        destroy_extra={},
        params={'retrieve': [PARAM_APAGADAS]},
        list_extra={400: ERRO_400_FILTRO},
        retrieve_extra={400: ERRO_400_FILTRO},
        descricoes={
            'list': 'Sem `apagadas`, retorna ativas e apagadas. '
                    '`apagadas=true`: só apagadas; `apagadas=false`: só ativas.',
            'update': 'Só fichas ativas; fichas apagadas retornam 404 (restaure antes).',
            'partial_update': 'Só fichas ativas; fichas apagadas retornam 404 (restaure antes).',
            'destroy': 'Exclusão lógica. Ficha já apagada retorna 404.',
        },
    ),
    restaurar=extend_schema(
        tags=[TAG],
        summary='Restaurar ficha técnica',
        description='Desfaz a exclusão lógica. A variação precisa estar ativa (restaure-a antes).',
        request=None,
        responses={200: FichaTecnicaDetalhadaSerializer, 400: ERRO_400,
                   401: ERRO_401, 403: ERRO_403, 404: ERRO_404},
    ),
)

movimentacao_estoque_schema = extend_schema_view(
    **crud_schema(
        TAG, 'movimentação', 'movimentações',
        leitura=MovimentacaoEstoqueSerializer,
        list_extra={
            400: resposta_erro(
                'Filtro inválido.',
                exemplo_erro('validation_error', 'Dados inválidos.',
                             {'variacao_id': ['Informe um ID numérico.']}),
            ),
        },
        descricoes={'list': 'Ordenadas da mais recente para a mais antiga. '
                            'Os filtros `variacao_id` e `sku` podem ser combinados.'},
        ops=('list', 'retrieve'),
    ),
    create=extend_schema(
        tags=[TAG],
        summary='Registrar movimentação de estoque',
        description='Venda/estorno exigem pedido, os demais tipos não aceitam.',
        responses={
            201: MovimentacaoEstoqueSerializer,
            400: resposta_erro(
                'Dados inválidos ou movimentação incoerente.',
                EX_VALIDACAO,
                exemplo_erro('tipo_movimentacao_invalido', 'Tipo de movimentação inválido.'),
                exemplo_erro('movimentacao_incoerente',
                             'Venda/estorno exigem pedido, os demais tipos não aceitam.'),
            ),
            401: ERRO_401,
            403: ERRO_403,
            409: resposta_erro('Estoque insuficiente.', exemplo_erro(
                'estoque_insuficiente',
                'Estoque insuficiente para "Sabonete" (SKU SAB-01). Saldo atual: 2, solicitado: 5.',
                {'ids': 1, 'sku': 'SAB-01', 'produto': 'Sabonete', 'saldo': 2, 'solicitado': 5},
            )),
        },
    ),
)

movimentacao_material_schema = extend_schema_view(
    **crud_schema(
        TAG, 'movimentação', 'movimentações',
        leitura=MovimentacaoMaterialSerializer,
        list_extra={
            400: resposta_erro(
                'Filtro inválido.',
                exemplo_erro('validation_error', 'Dados inválidos.',
                             {'materia_prima_id': ['Informe um ID numérico.']}),
            ),
        },
        descricoes={'list': 'Ordenadas da mais recente para a mais antiga. '
                            'Os filtros `materia_prima_id` e `sku` podem ser combinados.'},
        ops=('list', 'retrieve'),
    ),
    create=extend_schema(
        tags=[TAG],
        summary='Registrar movimentação de matéria-prima',
        description='Todos os tipos aceitam fornecedor, com exceção das saídas por produção.',
        responses={
            201: MovimentacaoMaterialSerializer,
            400: resposta_erro(
                'Dados inválidos ou movimentação incoerente.',
                EX_VALIDACAO,
                exemplo_erro('tipo_movimentacao_invalido', 'Tipo de movimentação inválido.'),
                exemplo_erro('movimentacao_incoerente',
                             'Este tipo não permite um fornecedor.'),
            ),
            401: ERRO_401,
            403: ERRO_403,
            409: resposta_erro('Estoque insuficiente.', exemplo_erro(
                'estoque_insuficiente',
                'Estoque insuficiente para "Glicerina" (SKU SAB-01). Saldo atual: 2, solicitado: 5.',
                {'ids': 1, 'sku': 'SAB-01', 'produto': 'Glicerina', 'saldo': 2, 'solicitado': 5},
            )),
        },
    ),
)