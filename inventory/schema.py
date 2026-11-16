from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from core.schema import (
    ERRO_400, ERRO_400_FILTRO, ERRO_401, ERRO_403, ERRO_404, EX_VALIDACAO,
    crud_schema, exemplo_erro, resposta_erro, PARAM_APAGADAS,
)
from .serializers import (
    CompraFornecedorSerializer, CompraFornecedorDetalhadaSerializer,
    FichaTecnicaDetalhadaSerializer, FichaTecnicaSerializer, FichaTecnicaUpdateSerializer,
    FornecedorSerializer, LoteMateriaPrimaSerializer, LoteProdutoVariacaoSerializer,
    MateriaPrimaSerializer, MovimentacaoEstoqueSerializer,
    MovimentacaoMaterialSerializer, VinculoFornecedorDetalhadoSerializer,
    VinculoFornecedorSerializer, VinculoFornecedorUpdateSerializer, MateriaPrimaImagemSerializer,
)

TAG = 'Estoque'

PARAM_APAGADOS = OpenApiParameter(
    name='apagados',
    type=bool,
    location=OpenApiParameter.QUERY,
    required=False,
    description='Omitido: ativos e apagados. `true`: só apagados. `false`: só ativos.',
)

PARAM_ORDERING_COMPRA_FORNECEDOR = OpenApiParameter(
    name="ordering",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    description=(
        "Campos de ordenação: compra_realizada_em, valor_total, id. "
        "Use '-' para ordem decrescente (ex.: ?ordering=-compra_realizada_em). "
        "Separe por vírgula para ordenar por mais de um campo "
        "(ex.: ?ordering=-valor_total,compra_realizada_em)."
    ),
)

ERRO_400_FILTRO_APAGADOS = resposta_erro(
    'Filtro inválido.',
    exemplo_erro('validation_error', 'Dados inválidos.', {'apagados': ['Informe true ou false.']}),
)

_EX_STATUS_LOTE_INVALIDO = exemplo_erro(
    'validation_error', 'Dados inválidos.',
    {'status': ['Faça uma escolha válida. INVALIDO não é uma das escolhas disponíveis.']},
    nome='status_invalido',
)
_EX_VALIDADE_PASSADO = exemplo_erro(
    'validation_error', 'Dados inválidos.',
    {'data_validade': ['A data de validade não pode estar no passado.']},
    nome='validade_no_passado',
)
_EX_LOTE_VENCIDO = exemplo_erro(
    'lote_indisponivel',
    'O lote "LT-2026-01" está vencido e não aceita esta movimentação.',
)

materia_prima_schema = extend_schema_view(
    **crud_schema(
        TAG, 'matéria-prima', 'matérias-primas',
        leitura=MateriaPrimaSerializer,
        destroy_extra={},
        params={'retrieve': [PARAM_APAGADAS]},
        list_extra={400: ERRO_400_FILTRO},
        retrieve_extra={400: ERRO_400_FILTRO},
        descricoes={
            'list': 'Ordenadas por nome. Sem `apagadas`, retorna ativas e apagadas. '
                    '`apagadas=true`: só apagadas; `apagadas=false`: só ativas. '
                    '`quantidade_estoque` é a soma das quantidades dos lotes ativos (não vencidos e não esgotados) '
                    'e usa até 3 casas decimais. '
                    '`custo_unitario_referencia` usa até 4 casas decimais.',
            'create': '`custo_unitario_referencia` aceita até 4 casas decimais e não pode ser negativo. '
                      'Categorias permitidas: OLEOS_E_GORDURAS (Óleos e gorduras), AGENTES_SAPONIFICANTES (Agentes saponificantes), '
                      'LIQUIDOS_DILUICAO (Líquidos de diluição), AROMAS_E_FRAGANCIAS (Aromas e fragâncias), '
                      'CORANTES_E_PIGMENTOS (Corantes e pigmentos), ADITIVOS_E_ATIVOS (Aditivos e ativos), '
                      'EMBALAGENS_E_ROTULOS (Embalagens e rótulos), MATERIAL_DE_APOIO (Material de apoio). '
                      'Unidades de medida permitidas: KG (Quilograma), G (Grama), MG (Miligrama), L (Litro), ML (Mililitro), UN (Unidade).',
            'update': 'Não é possível alterar a `unidade_medida` quando existem movimentações '
                      'vinculadas à matéria-prima; nesse caso a requisição retorna erro 400. '
                      '`custo_unitario_referencia` aceita até 4 casas decimais e não pode ser negativo.',
            'partial_update': 'Não é possível alterar a `unidade_medida` quando existem movimentações '
                              'vinculadas à matéria-prima; nesse caso a requisição retorna erro 400. '
                              '`custo_unitario_referencia` aceita até 4 casas decimais e não pode ser negativo.',
            'destroy': 'Exclusão lógica. Os vínculos de fornecedor ativos desta matéria-prima '
                       'também são apagados logicamente.',
        },
    ),
    restaurar=extend_schema(
        tags=[TAG],
        summary='Restaurar matéria-prima',
        description='Desfaz a exclusão lógica apenas para a matéria-prima; não restaura os vínculos de fornecedor junto.',
        request=None,
        responses={200: MateriaPrimaSerializer, 400: ERRO_400,
                   401: ERRO_401, 403: ERRO_403, 404: ERRO_404},
    ),
    imagem=extend_schema(
        tags=[TAG],
        summary='Enviar ou trocar imagem da matéria-prima',
        description='Envia a imagem da matéria-prima (`multipart/form-data`, campo `imagem`). '
                    'Se já houver uma imagem, ela é substituída e o arquivo antigo é apagado. '
                    'Formatos aceitos: JPEG, PNG e WebP, com no máximo 5 MB. '
                    'Retorna a matéria-prima atualizada, com a URL nova em `imagem`.',
        request={'multipart/form-data': MateriaPrimaImagemSerializer},
        responses={
            200: MateriaPrimaSerializer,
            400: resposta_erro(
                'Arquivo inválido.',
                EX_VALIDACAO,
                exemplo_erro(
                    'validation_error', 'Dados inválidos.',
                    {'image': ['A imagem deve ter no máximo 5 MB.']},
                    nome='imagem_muito_grande',
                ),
                exemplo_erro(
                    'validation_error', 'Dados inválidos.',
                    {'image': ['Formato não permitido. Use JPEG, PNG ou WebP.']},
                    nome='formato_invalido',
                ),
            ),
            401: ERRO_401,
            403: ERRO_403,
            404: ERRO_404,
        },
    ),
    remover_imagem=extend_schema(
        tags=[TAG],
        summary='Remover imagem da matéria-prima',
        description='Remove a imagem da matéria-prima e apaga o arquivo. '
                    'Se a matéria-prima não tiver imagem, a operação é idempotente e também retorna 204.',
        request=None,
        responses={204: None, 401: ERRO_401, 403: ERRO_403, 404: ERRO_404},
    ),
)

fornecedor_schema = extend_schema_view(
    **crud_schema(
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
    ),
    restaurar=extend_schema(
        tags=[TAG],
        summary='Restaurar fornecedor',
        description='Desfaz a exclusão lógica apenas para o fornecedor; não restaura os vínculos de fornecedor junto.',
        request=None,
        responses={200: FornecedorSerializer, 400: ERRO_400,
                   401: ERRO_401, 403: ERRO_403, 404: ERRO_404},
    ),
)

compra_fornecedor_schema = extend_schema_view(
    **crud_schema(
        TAG, 'compra', 'compras',
        leitura=CompraFornecedorDetalhadaSerializer,
        params={
            'list': [
                PARAM_ORDERING_COMPRA_FORNECEDOR
            ]
        },
        list_extra={
            400: resposta_erro(
                'Filtro inválido.',
                exemplo_erro('validation_error', 'Dados inválidos.',
                             {'fornecedor_id': ['Informe um número.']}),
            ),
        },
        descricoes={
            'list': 'Ordenadas da mais recente para a mais antiga. '
                    'Use `fornecedor_id` para filtrar por fornecedor. '
                    'Cada item informa o `lote` gerado por ele. '
                    '`quantidade_item` usa até 3 casas decimais. '
                    '`valor_total` e `custo_unitario_momento_compra` usam até 4 casas decimais.',
            'partial_update': 'Apenas `observacao` é editável.',
        },
        ops=('list', 'retrieve', 'partial_update'),
    ),
    create=extend_schema(
        tags=[TAG],
        summary='Registrar compra de fornecedor',
        description='Cria a compra e seus itens em uma única operação. Cada item gera um lote único '
                    'de matéria-prima, criado vazio e em seguida abastecido por uma movimentação '
                    'de entrada. `numero_lote_fabricante` é opcional (vazio é gravado como '
                    '"Não informado") e `data_validade` é opcional e não pode estar no passado. '
                    'É obrigatório ao menos um item, sem repetir matéria-prima. '
                    '`quantidade_item` aceita até 3 casas decimais, deve ser maior que 0 e no máximo 999. '
                    '`valor_total` e `custo_unitario_momento_compra` aceitam até 4 casas decimais.',
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
                exemplo_erro(
                    'validation_error', 'Dados inválidos.',
                    {'itens': [{'data_validade': ['A data de validade não pode estar no passado.']}]},
                    nome='item_validade_no_passado',
                ),
                exemplo_erro('compra_fornecedor_sem_item',
                             'A compra deve conter pelo menos um item.'),
                exemplo_erro('item_desativado',
                             'O item "Glicerina" (SKU GLI-01) está desativado.',
                             {'ids': 1, 'sku': 'GLI-01', 'produto': 'Glicerina'}),
            ),
            401: ERRO_401,
            403: ERRO_403,
        },
    ),
    devolver=extend_schema(
        tags=[TAG],
        summary='Devolver compra',
        description='Devolve a compra ao fornecedor com uma saída por devolução no lote de cada item, '
                    'e retorna a compra atualizada. Os lotes não são apagados: ao zerar, ficam com '
                    'status `ESGOTADO`. Só é permitido quando o status da compra permite a transição '
                    'para devolvida e quando cada lote ainda tem a quantidade comprada disponível. '
                    'As quantidades usam até 3 casas decimais e os valores e custos usam até 4 casas decimais.',
        request=None,
        responses={
            200: CompraFornecedorDetalhadaSerializer,
            401: ERRO_401,
            403: ERRO_403,
            404: ERRO_404,
            409: resposta_erro(
                'Transição de status inválida ou estoque insuficiente no lote.',
                exemplo_erro(
                    'transicao_status_invalida',
                    'Transição de status inválida: DEVOLVIDO → DEVOLVIDO.',
                    {'atual': 'DEVOLVIDO', 'novo': 'DEVOLVIDO'},
                ),
                exemplo_erro(
                    'estoque_insuficiente',
                    'Estoque insuficiente para "Glicerina (lote LT-2026-01)" (SKU GLI-01). '
                    'Saldo atual: 2.000, solicitado: 5.000.',
                    {'ids': 1, 'sku': 'GLI-01', 'produto': 'Glicerina (lote LT-2026-01)',
                     'saldo': '2.000', 'solicitado': '5.000'},
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
                    'Os filtros `materia_prima_id` e `apagados` podem ser combinados. '
                    '`custo_unitario_fornecedor` usa até 4 casas decimais.',
            'create': '`custo_unitario_fornecedor` aceita até 4 casas decimais e não pode ser negativo.',
            'update': 'Só vínculos ativos; vínculos apagados retornam 404 (restaure antes). '
                      'A matéria-prima não pode ser alterada. '
                      '`custo_unitario_fornecedor` aceita até 4 casas decimais e não pode ser negativo.',
            'partial_update': 'Só vínculos ativos; vínculos apagados retornam 404 (restaure antes). '
                              'A matéria-prima não pode ser alterada. '
                              '`custo_unitario_fornecedor` aceita até 4 casas decimais e não pode ser negativo.',
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
                    '`apagadas=true`: só apagadas; `apagadas=false`: só ativas. '
                    '`quantidade_necessaria` usa até 3 casas decimais (mínimo 0.001).',
            'create': '`quantidade_necessaria` aceita até 3 casas decimais, com valor mínimo de 0.001.',
            'update': 'Só fichas ativas; fichas apagadas retornam 404 (restaure antes). '
                      '`quantidade_necessaria` aceita até 3 casas decimais (mínimo 0.001).',
            'partial_update': 'Só fichas ativas; fichas apagadas retornam 404 (restaure antes). '
                              '`quantidade_necessaria` aceita até 3 casas decimais (mínimo 0.001).',
            'destroy': 'Exclusão lógica. Ficha já apagada retorna 404.',
        },
    ),
    restaurar=extend_schema(
        tags=[TAG],
        summary='Restaurar ficha técnica',
        description='Desfaz a exclusão lógica. A variação e a matéria-prima precisam estar ativas (restaure-as antes).',
        request=None,
        responses={200: FichaTecnicaDetalhadaSerializer, 400: ERRO_400,
                   401: ERRO_401, 403: ERRO_403, 404: ERRO_404},
    ),
)

lote_materia_prima_schema = extend_schema_view(
    **crud_schema(
        TAG, 'lote de matéria-prima', 'lotes de matéria-prima',
        leitura=LoteMateriaPrimaSerializer,
        list_extra={
            400: resposta_erro(
                'Filtro inválido.',
                exemplo_erro('validation_error', 'Dados inválidos.',
                             {'materia_prima_id': ['Informe um ID numérico.']},
                             nome='materia_prima_id_invalido'),
                _EX_STATUS_LOTE_INVALIDO,
            ),
        },
        descricoes={'list': 'Ordenados do mais recente para o mais antigo. '
                            'Os filtros `materia_prima_id`, `compra_fornecedor_item_id`, `status` e `sku` '
                            'podem ser combinados. Os lotes gerados por compra de fornecedor são criados '
                            'automaticamente; esta listagem também mostra os lotes manuais. '
                            '`quantidade_inicial` e `quantidade_atual` usam até 3 casas decimais.'},
        ops=('list', 'retrieve'),
    ),
    create=extend_schema(
        tags=[TAG],
        summary='Criar lote de matéria-prima vazio',
        description='Cria um lote vazio (quantidade 0). Para abastecê-lo, registre em seguida uma '
                    'movimentação de matéria-prima do tipo `ENTRADA` informando o lote. '
                    '`numero_lote_fabricante` vazio é gravado como "Não informado". '
                    '`data_validade` é opcional e não pode estar no passado. '
                    'Lotes sem validade nunca vencem. '
                    'As quantidades do lote usam até 3 casas decimais.',
        responses={
            201: LoteMateriaPrimaSerializer,
            400: resposta_erro(
                'Dados inválidos ou matéria-prima desativada.',
                EX_VALIDACAO,
                _EX_VALIDADE_PASSADO,
                exemplo_erro('item_desativado',
                             'O item "Glicerina" (SKU GLI-01) está desativado.',
                             {'ids': 1, 'sku': 'GLI-01', 'produto': 'Glicerina'}),
            ),
            401: ERRO_401,
            403: ERRO_403,
        },
    ),
)

lote_produto_variacao_schema = extend_schema_view(
    **crud_schema(
        TAG, 'lote de variação', 'lotes de variação',
        leitura=LoteProdutoVariacaoSerializer,
        list_extra={
            400: resposta_erro(
                'Filtro inválido.',
                exemplo_erro('validation_error', 'Dados inválidos.',
                             {'variacao_id': ['Informe um ID numérico.']},
                             nome='variacao_id_invalido'),
                _EX_STATUS_LOTE_INVALIDO,
            ),
        },
        descricoes={'list': 'Ordenados do mais recente para o mais antigo. '
                            'Os filtros `variacao_id`, `status` e `sku` podem ser combinados. '
                            'Os lotes gerados pela fabricação são criados automaticamente; '
                            'esta listagem também mostra os lotes manuais.'},
        ops=('list', 'retrieve'),
    ),
    create=extend_schema(
        tags=[TAG],
        summary='Criar lote de variação vazio',
        description='Cria um lote vazio (quantidade 0). Para abastecê-lo, registre em seguida uma '
                    'movimentação de estoque do tipo `ENTRADA` informando o lote. '
                    '`data_validade` é obrigatória e não pode estar no passado nem anteceder '
                    '`data_fabricacao`. Sem `data_fabricacao`, usa a data atual. Sem `numero_lote`, '
                    'o número é gerado automaticamente (SKU-AAAAMMDD-NN). Para produzir a partir da '
                    'ficha técnica, use a fabricação da variação.',
        responses={
            201: LoteProdutoVariacaoSerializer,
            400: resposta_erro(
                'Dados inválidos ou variação desativada.',
                EX_VALIDACAO,
                _EX_VALIDADE_PASSADO,
                exemplo_erro(
                    'validation_error', 'Dados inválidos.',
                    {'numero_lote': ['Já existe um lote com este número.']},
                    nome='numero_lote_duplicado',
                ),
                exemplo_erro('item_desativado',
                             'O item "Lavanda 90g" (SKU SAB-LAV-90) está desativado.',
                             {'ids': 1, 'sku': 'SAB-LAV-90', 'produto': 'Lavanda 90g'}),
            ),
            401: ERRO_401,
            403: ERRO_403,
        },
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
                            'Os filtros `variacao_id`, `lote_produto_variacao_id` e `sku` podem ser combinados.'},
        ops=('list', 'retrieve'),
    ),
    create=extend_schema(
        tags=[TAG],
        summary='Registrar movimentação de estoque',
        description='A movimentação é feita sobre um lote de variação existente '
                    '(`lote_produto_variacao`). Para um lote novo, crie-o vazio antes e registre uma '
                    '`ENTRADA`. Venda/estorno exigem pedido e são gerados automaticamente pelos pedidos; '
                    'os demais tipos não aceitam. Entrada, saída por venda e saída por produção não são '
                    'aceitas em lote vencido. O estoque da variação soma apenas os lotes ativos.'
                    'Tipos manuais permitidos: ENTRADA, AJUSTE_OU_PERDA',
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
            409: resposta_erro(
                'Estoque insuficiente no lote ou lote vencido.',
                exemplo_erro(
                    'estoque_insuficiente',
                    'Estoque insuficiente para "Sabonete (lote SAB-01-20261028-01)" (SKU SAB-01). '
                    'Saldo atual: 2, solicitado: 5.',
                    {'ids': 1, 'sku': 'SAB-01', 'produto': 'Sabonete (lote SAB-01-20261028-01)',
                     'saldo': 2, 'solicitado': 5},
                ),
                _EX_LOTE_VENCIDO,
            ),
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
                            'Os filtros `materia_prima_id`, `lote_materia_prima_id` e `sku` podem ser combinados. '
                            '`quantidade_movimentada` usa até 3 casas decimais.'},
        ops=('list', 'retrieve'),
    ),
    create=extend_schema(
        tags=[TAG],
        summary='Registrar movimentação de matéria-prima',
        description='A movimentação é feita sobre um lote de matéria-prima existente '
                    '(`lote_materia_prima`). Para um lote novo, crie-o vazio antes e registre uma '
                    '`ENTRADA`. Todos os tipos aceitam fornecedor, com exceção das saídas por produção. '
                    'A saída por devolução é gerada automaticamente pela devolução da compra. '
                    'Entrada e saída por produção não são aceitas em lote vencido. '
                    'O estoque da matéria-prima soma apenas os lotes ativos. '
                    '`quantidade_movimentada` aceita até 3 casas decimais e deve ser maior que 0. '
                    'Tipos manuais permitidos: ENTRADA, AJUSTE_OU_PERDA',
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
            409: resposta_erro(
                'Estoque insuficiente no lote ou lote vencido.',
                exemplo_erro(
                    'estoque_insuficiente',
                    'Estoque insuficiente para "Glicerina (lote LT-2026-01)" (SKU GLI-01). '
                    'Saldo atual: 2.000, solicitado: 5.000.',
                    {'ids': 1, 'sku': 'GLI-01', 'produto': 'Glicerina (lote LT-2026-01)',
                     'saldo': '2.000', 'solicitado': '5.000'},
                ),
                _EX_LOTE_VENCIDO,
            ),
        },
    ),
)