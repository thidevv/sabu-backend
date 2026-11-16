from drf_spectacular.utils import extend_schema, extend_schema_view

from core.schema import (
    ERRO_400, ERRO_400_FILTRO, ERRO_401, ERRO_403, ERRO_404, EX_VALIDACAO, crud_schema,
    exemplo_erro, resposta_erro, PARAM_APAGADAS,
)
from inventory.serializers import FabricarVariacaoSerializer, LoteProdutoVariacaoSerializer
from .serializers import (
    CategoriaSerializer, IngredienteSerializer, ProdutoDetalhadoSerializer, ProdutoSerializer,
    ProdutoVariacaoSerializer, ProdutoVariacaoUpdateSerializer, TipoPeleSerializer, ProdutoImagemSerializer,
    ProdutoVariacaoImagemSerializer,
)

TAG = 'Catálogo'

categoria_schema = extend_schema_view(**crud_schema(
    TAG, 'categoria', 'categorias', leitura=CategoriaSerializer, leitura_publica=True))

tipo_pele_schema = extend_schema_view(**crud_schema(
    TAG, 'tipo de pele', 'tipos de pele', leitura=TipoPeleSerializer, leitura_publica=True))

ingrediente_schema = extend_schema_view(**crud_schema(
    TAG, 'ingrediente', 'ingredientes', leitura=IngredienteSerializer, leitura_publica=True,
    descricoes={
        'create': 'O nome é salvo em minúsculas e sem espaços nas pontas.',
        'destroy': 'Ingrediente vinculado a algum produto não pode ser apagado (409).',
    },
))

produto_schema = extend_schema_view(
    **crud_schema(
        TAG, 'produto', 'produtos',
        leitura=ProdutoDetalhadoSerializer, escrita=ProdutoSerializer,
        leitura_publica=True,
        list_extra={
            400: resposta_erro(
                'Filtro inválido.',
                exemplo_erro('validation_error', 'Dados inválidos.',
                             {'categoria_id': ['Informe um número.']}),
            ),
        },
        descricoes={
            'list': 'Não-admin vê apenas produtos ativos. '
                    '`image` é a URL da imagem do produto, ou `null` se não houver.',
            'create': 'A imagem não é enviada aqui: use `PUT /api/v1/catalog/produtos/{id}/imagem/` depois de criar o produto.',
            'update': 'A imagem não é alterada aqui: use `PUT /api/v1/catalog/produtos/{id}/imagem/`.',
        },
    ),
    imagem=extend_schema(
        tags=[TAG],
        summary='Enviar ou trocar imagem do produto',
        description='Envia a imagem do produto (`multipart/form-data`, campo `imagem`). '
                    'Se já houver uma imagem, ela é substituída e o arquivo antigo é apagado. '
                    'Formatos aceitos: JPEG, PNG e WebP, com no máximo 5 MB. '
                    'Retorna o produto atualizado, com a URL nova em `imagem`.',
        request={'multipart/form-data': ProdutoImagemSerializer},
        responses={
            200: ProdutoDetalhadoSerializer,
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
        summary='Remover imagem do produto',
        description='Remove a imagem do produto e apaga o arquivo. '
                    'Se o produto não tiver imagem, a operação é idempotente e também retorna 204.',
        request=None,
        responses={204: None, 401: ERRO_401, 403: ERRO_403, 404: ERRO_404},
    ),
)

variacao_schema = extend_schema_view(
    **crud_schema(
        TAG, 'variação', 'variações',
        leitura=ProdutoVariacaoSerializer, escrita=ProdutoVariacaoUpdateSerializer,
        leitura_publica=True,
        destroy_extra={},
        params={'retrieve': [PARAM_APAGADAS]},
        list_extra={
            400: resposta_erro(
                'Filtro inválido.',
                exemplo_erro('validation_error', 'Dados inválidos.',
                             {'apagadas': ['Informe true ou false.']}, nome='apagadas_invalido'),
                exemplo_erro('validation_error', 'Dados inválidos.',
                             {'produto_id': ['Informe um número.']}, nome='produto_id_invalido'),
            ),
        },
        retrieve_extra={400: ERRO_400_FILTRO},
        descricoes={
            'list': 'Não-admin vê apenas variações ativas de produtos ativos e `apagadas` é ignorado. '
                    'Admin: sem `apagadas`, retorna ativas e apagadas. '
                    '`quantidade_estoque` é a soma das quantidades dos lotes ativos (não vencidos e não esgotados).',
            'destroy': 'Exclusão lógica. Apaga também as fichas técnicas ativas da variação. '
                       'Variação já apagada retorna 404. Os lotes existentes são mantidos.',
        },
    ),
    restaurar=extend_schema(
        tags=[TAG],
        summary='Restaurar variação',
        description='Desfaz a exclusão lógica apenas para a variação; não restaura as fichas técnicas junto.',
        request=None,
        responses={200: ProdutoVariacaoSerializer, 400: ERRO_400,
                   401: ERRO_401, 403: ERRO_403, 404: ERRO_404},
    ),
    fabricar=extend_schema(
        tags=[TAG],
        summary='Fabricar variação',
        description='Fabrica a quantidade informada com base na ficha técnica ativa da variação. '
                    'Consome as matérias-primas de cada ingrediente seguindo o FEFO (primeiro lote a vencer, '
                    'primeiro a sair), com uma saída por produção em cada lote consumido, e cria um lote '
                    'de variação com uma movimentação de entrada. Lotes de matéria-prima vencidos não são '
                    'usados. Tudo roda em uma única transação: se faltar saldo de qualquer ingrediente, '
                    'nada é gravado. `data_validade` é obrigatória e não pode estar no passado. '
                    'Sem `data_fabricacao`, usa a data atual. Sem `numero_lote`, o número é gerado '
                    'automaticamente (SKU-AAAAMMDD-NN).',
        request=FabricarVariacaoSerializer,
        responses={
            201: LoteProdutoVariacaoSerializer,
            400: resposta_erro(
                'Dados inválidos ou variação sem ficha técnica ativa.',
                EX_VALIDACAO,
                exemplo_erro(
                    'validation_error', 'Dados inválidos.',
                    {'data_validade': ['A data de validade não pode estar no passado.']},
                    nome='validade_no_passado',
                ),
                exemplo_erro(
                    'validation_error', 'Dados inválidos.',
                    {'numero_lote': ['Já existe um lote com este número.']},
                    nome='numero_lote_duplicado',
                ),
                exemplo_erro(
                    'ficha_tecnica_inexistente',
                    'A variação "Lavanda 90g" (SKU SAB-LAV-90) não possui ficha técnica ativa.',
                ),
            ),
            401: ERRO_401,
            403: ERRO_403,
            404: ERRO_404,
            409: resposta_erro(
                'Estoque de matéria-prima insuficiente.',
                exemplo_erro(
                    'estoque_insuficiente',
                    'Estoque insuficiente para "Glicerina" (SKU GLI-01). Saldo atual: 2.000, solicitado: 5.000.',
                    {'ids': 1, 'sku': 'GLI-01', 'produto': 'Glicerina', 'saldo': '2.000', 'solicitado': '5.000'},
                ),
            ),
        },
    ),
    imagem=extend_schema(
        tags=[TAG],
        summary='Enviar ou trocar imagem da variação',
        description='Envia a imagem da variação (`multipart/form-data`, campo `imagem`). '
                    'Se já houver uma imagem, ela é substituída e o arquivo antigo é apagado. '
                    'Formatos aceitos: JPEG, PNG e WebP, com no máximo 5 MB. '
                    'Retorna a variação atualizada, com a URL nova em `imagem`.',
        request={'multipart/form-data': ProdutoVariacaoImagemSerializer},
        responses={
            200: ProdutoVariacaoSerializer,
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
        summary='Remover imagem da variação',
        description='Remove a imagem da variação e apaga o arquivo. '
                    'Se a variação não tiver imagem, a operação é idempotente e também retorna 204.',
        request=None,
        responses={204: None, 401: ERRO_401, 403: ERRO_403, 404: ERRO_404},
    ),
)