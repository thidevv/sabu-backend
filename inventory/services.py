from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from catalog.models import ProdutoVariacao
from orders.exceptions import TransicaoInvalida
from .exceptions import (
    CompraFornecedorSemItem,
    EstoqueInsuficiente,
    FichaTecnicaInexistente,
    ItemDesativado,
    LoteIndisponivel,
    MovimentacaoIncoerente,
    TipoMovimentacaoInvalido,
)
from .models import (
    CompraFornecedor,
    CompraFornecedorItem,
    FichaTecnica,
    FornecedorCategoria,
    LoteMateriaPrima,
    LoteProdutoVariacao,
    MateriaPrima,
    MovimentacaoEstoque,
    MovimentacaoMaterial,
    StatusCompraFornecedor,
    StatusLote,
    TIPOS_COM_PEDIDO,
    TIPOS_MATERIAL_QUE_AUMENTAM,
    TIPOS_MATERIAL_QUE_DIMINUEM,
    TIPOS_QUE_AUMENTAM,
    TIPOS_QUE_DIMINUEM,
    TRANSICOES_PERMITIDAS_COMPRA_FORNECEDOR,
    TipoMovimentacaoEstoque,
    TipoMovimentacaoMaterial,
)

PREFIXO_AUTOMATICO = 'MOVIMENTAÇÃO AUTOMÁTICA DO SISTEMA: '

TIPOS_BLOQUEADOS_EM_LOTE_VENCIDO = {'ENTRADA', 'SAIDA_VENDA', 'SAIDA_PRODUCAO'}


def _vencido(lote, hoje):
    return lote.data_validade is not None and lote.data_validade < hoje


def _status_calculado(lote, hoje):
    if lote.quantidade_atual == 0:
        return StatusLote.ESGOTADO
    if _vencido(lote, hoje):
        return StatusLote.VENCIDO
    return StatusLote.ATIVO


def _disponivel(lote):
    return lote.quantidade_atual if lote.status == StatusLote.ATIVO else 0


def _movimentar_lote(lote, agregado, *, tipo, quantidade, aumenta, hoje, rotulo_lote, identificacao):
    if tipo in TIPOS_BLOQUEADOS_EM_LOTE_VENCIDO and _vencido(lote, hoje):
        raise LoteIndisponivel(f'O lote "{rotulo_lote}" está vencido e não aceita esta movimentação.')

    disponivel_antes = _disponivel(lote)

    if aumenta:
        lote.quantidade_atual += quantidade
        if tipo == 'ENTRADA':
            lote.quantidade_inicial += quantidade
    else:
        if lote.quantidade_atual < quantidade:
            raise EstoqueInsuficiente(
                **identificacao,
                saldo=lote.quantidade_atual,
                solicitado=quantidade,
            )
        lote.quantidade_atual -= quantidade

    lote.status = _status_calculado(lote, hoje)
    lote.save(update_fields=['quantidade_inicial', 'quantidade_atual', 'status'])

    agregado.quantidade_estoque += _disponivel(lote) - disponivel_antes
    agregado.save(update_fields=['quantidade_estoque'])


def _expirar_lotes(agregado, modelo_lote, hoje, **filtro):
    lotes = list(
        modelo_lote.objects.select_for_update().filter(
            status=StatusLote.ATIVO,
            data_validade__lt=hoje,
            **filtro,
        )
    )

    baixa = 0
    for lote in lotes:
        disponivel = _disponivel(lote)
        lote.status = _status_calculado(lote, hoje)
        lote.save(update_fields=['status'])
        baixa += disponivel - _disponivel(lote)

    if baixa:
        agregado.quantidade_estoque -= baixa
        agregado.save(update_fields=['quantidade_estoque'])

    return len(lotes)


def _lotes_fefo(modelo_lote, hoje, **filtro):
    return list(
        modelo_lote.objects.select_for_update()
        .filter(status=StatusLote.ATIVO, quantidade_atual__gt=0, **filtro)
        .filter(Q(data_validade__isnull=True) | Q(data_validade__gte=hoje))
        .order_by(F('data_validade').asc(nulls_last=True), 'criado_em', 'pk')
    )


def atualizar_lotes_vencidos():
    hoje = timezone.localdate()
    resultado = {'variacoes': 0, 'materias_primas': 0}

    ids_variacoes = sorted(set(
        LoteProdutoVariacao.objects
        .filter(status=StatusLote.ATIVO, data_validade__lt=hoje)
        .values_list('variacao_id', flat=True),
    ))
    for variacao_id in ids_variacoes:
        with transaction.atomic():
            variacao = ProdutoVariacao.objects.select_for_update().get(pk=variacao_id)
            resultado['variacoes'] += _expirar_lotes(variacao, LoteProdutoVariacao, hoje, variacao=variacao)

    ids_materias = sorted(set(
        LoteMateriaPrima.objects
        .filter(status=StatusLote.ATIVO, data_validade__lt=hoje)
        .values_list('materia_prima_id', flat=True)
    ))
    for materia_prima_id in ids_materias:
        with transaction.atomic():
            materia_prima = MateriaPrima.objects.select_for_update().get(pk=materia_prima_id)
            resultado['materias_primas'] += _expirar_lotes(
                materia_prima, LoteMateriaPrima, hoje, materia_prima=materia_prima,
            )

    return resultado


def _gerar_numero_lote(variacao, data_fabricacao):
    base = f'{variacao.sku}-{data_fabricacao:%Y%m%d}'
    sequencia = LoteProdutoVariacao.objects.filter(numero_lote__startswith=base).count() + 1
    numero = f'{base}-{sequencia:02d}'
    while LoteProdutoVariacao.objects.filter(numero_lote=numero).exists():
        sequencia += 1
        numero = f'{base}-{sequencia:02d}'
    return numero


@transaction.atomic
def criar_lote_variacao(*, variacao, data_validade, data_fabricacao=None, numero_lote=None, observacao=None):
    variacao = ProdutoVariacao.objects.select_for_update().get(pk=variacao.pk)
    if variacao.apagado_em is not None:
        raise ItemDesativado(ids=variacao.pk, sku=variacao.sku, produto=variacao.nome)

    data_fabricacao = data_fabricacao or timezone.localdate()
    numero_lote = (numero_lote or '').strip() or _gerar_numero_lote(variacao, data_fabricacao)

    return LoteProdutoVariacao.objects.create(
        variacao=variacao,
        numero_lote=numero_lote,
        data_fabricacao=data_fabricacao,
        data_validade=data_validade,
        quantidade_inicial=0,
        quantidade_atual=0,
        observacao=observacao or '',
    )


@transaction.atomic
def criar_lote_materia_prima(*, materia_prima, numero_lote_fabricante=None, data_validade=None,
                             observacao=None, compra_fornecedor_item=None):
    materia_prima = MateriaPrima.objects.select_for_update().get(pk=materia_prima.pk)
    if materia_prima.apagada_em is not None:
        raise ItemDesativado(ids=materia_prima.pk, sku=materia_prima.sku, produto=materia_prima.nome)

    return LoteMateriaPrima.objects.create(
        materia_prima=materia_prima,
        compra_fornecedor_item=compra_fornecedor_item,
        numero_lote_fabricante=numero_lote_fabricante or '',
        data_validade=data_validade,
        quantidade_inicial=0,
        quantidade_atual=0,
        observacao=observacao or '',
    )


@transaction.atomic
def registrar_movimentacao_estoque(*, lote_id, tipo, quantidade, usuario,
                                   pedido=None, observacao=None):
    if tipo in TIPOS_QUE_AUMENTAM:
        aumenta = True
    elif tipo in TIPOS_QUE_DIMINUEM:
        aumenta = False
    else:
        raise TipoMovimentacaoInvalido(f'Tipo de movimentação inválido: {tipo}.')

    if (tipo in TIPOS_COM_PEDIDO) != (pedido is not None):
        raise MovimentacaoIncoerente(
            "Venda/estorno exigem pedido, os demais tipos não aceitam."
        )

    variacao_id = LoteProdutoVariacao.objects.values_list('variacao_id', flat=True).get(pk=lote_id)
    variacao = ProdutoVariacao.objects.select_for_update().filter(apagado_em__isnull=True).get(pk=variacao_id)
    lote = LoteProdutoVariacao.objects.select_for_update().get(pk=lote_id)

    _movimentar_lote(
        lote,
        variacao,
        tipo=tipo,
        quantidade=quantidade,
        aumenta=aumenta,
        hoje=timezone.localdate(),
        rotulo_lote=lote.numero_lote,
        identificacao={
            'ids': variacao.pk,
            'sku': variacao.sku,
            'produto': f'{variacao.nome} (lote {lote.numero_lote})',
        },
    )

    return MovimentacaoEstoque.objects.create(
        lote_produto_variacao=lote, tipo=tipo, quantidade_movimentada=quantidade,
        usuario=usuario, pedido=pedido, observacao=observacao or '',
    )


@transaction.atomic
def registrar_movimentacao_material(*, lote_id, tipo, quantidade, usuario,
                                    fornecedor=None, observacao=None):
    if tipo in TIPOS_MATERIAL_QUE_AUMENTAM:
        aumenta = True
    elif tipo in TIPOS_MATERIAL_QUE_DIMINUEM:
        aumenta = False
    else:
        raise TipoMovimentacaoInvalido(f'Tipo de movimentação inválido: {tipo}.')

    materia_prima_id = LoteMateriaPrima.objects.values_list('materia_prima_id', flat=True).get(pk=lote_id)
    materia_prima = MateriaPrima.objects.select_for_update().filter(apagada_em__isnull=True).get(pk=materia_prima_id)
    lote = LoteMateriaPrima.objects.select_for_update().get(pk=lote_id)

    _movimentar_lote(
        lote,
        materia_prima,
        tipo=tipo,
        quantidade=quantidade,
        aumenta=aumenta,
        hoje=timezone.localdate(),
        rotulo_lote=lote.numero_lote_fabricante,
        identificacao={
            'ids': materia_prima.pk,
            'sku': materia_prima.sku,
            'produto': f'{materia_prima.nome} (lote {lote.numero_lote_fabricante})',
        },
    )

    return MovimentacaoMaterial.objects.create(
        lote_materia_prima=lote, tipo=tipo, quantidade_movimentada=quantidade,
        usuario=usuario, fornecedor=fornecedor, observacao=observacao or '',
    )


@transaction.atomic
def baixar_estoque_variacao_fefo(*, variacao_id, quantidade, usuario, pedido, observacao):
    variacao = ProdutoVariacao.objects.select_for_update().filter(apagado_em__isnull=True).get(pk=variacao_id)
    hoje = timezone.localdate()

    _expirar_lotes(variacao, LoteProdutoVariacao, hoje, variacao=variacao)
    lotes = _lotes_fefo(LoteProdutoVariacao, hoje, variacao=variacao)

    saldo = sum((lote.quantidade_atual for lote in lotes), 0)
    if saldo < quantidade:
        raise EstoqueInsuficiente(
            ids=variacao.pk,
            sku=variacao.sku,
            produto=variacao.nome,
            saldo=saldo,
            solicitado=quantidade,
        )

    movimentacoes = []
    restante = quantidade
    for lote in lotes:
        if restante <= 0:
            break
        retirada = min(lote.quantidade_atual, restante)
        movimentacoes.append(
            registrar_movimentacao_estoque(
                lote_id=lote.pk,
                tipo=TipoMovimentacaoEstoque.SAIDA_VENDA,
                quantidade=retirada,
                usuario=usuario,
                pedido=pedido,
                observacao=observacao,
            )
        )
        restante -= retirada

    return movimentacoes


@transaction.atomic
def estornar_vendas_do_pedido(*, pedido, usuario, observacao):
    saidas = list(
        MovimentacaoEstoque.objects
        .filter(pedido=pedido, tipo=TipoMovimentacaoEstoque.SAIDA_VENDA)
        .select_related('lote_produto_variacao')
        .order_by('lote_produto_variacao__variacao_id', 'lote_produto_variacao_id', 'pk')
    )

    for saida in saidas:
        registrar_movimentacao_estoque(
            lote_id=saida.lote_produto_variacao_id,
            tipo=TipoMovimentacaoEstoque.ESTORNO_VENDA,
            quantidade=saida.quantidade_movimentada,
            usuario=usuario,
            pedido=pedido,
            observacao=observacao,
        )


@transaction.atomic
def _consumir_materia_prima_fefo(*, materia_prima_id, quantidade, usuario, observacao):
    materia_prima = MateriaPrima.objects.select_for_update().filter(apagada_em__isnull=True).get(pk=materia_prima_id)
    hoje = timezone.localdate()

    _expirar_lotes(materia_prima, LoteMateriaPrima, hoje, materia_prima=materia_prima)
    lotes = _lotes_fefo(LoteMateriaPrima, hoje, materia_prima=materia_prima)

    saldo = sum((lote.quantidade_atual for lote in lotes), Decimal('0'))
    if saldo < quantidade:
        raise EstoqueInsuficiente(
            ids=materia_prima.pk,
            sku=materia_prima.sku,
            produto=materia_prima.nome,
            saldo=saldo,
            solicitado=quantidade,
        )

    restante = quantidade
    for lote in lotes:
        if restante <= 0:
            break
        retirada = min(lote.quantidade_atual, restante)
        registrar_movimentacao_material(
            lote_id=lote.pk,
            tipo=TipoMovimentacaoMaterial.SAIDA_PRODUCAO,
            quantidade=retirada,
            usuario=usuario,
            observacao=observacao,
        )
        restante -= retirada


@transaction.atomic
def fabricar_variacao(*, variacao_id, quantidade, usuario, data_validade,
                      data_fabricacao=None, numero_lote=None, observacao=None):
    variacao = ProdutoVariacao.objects.filter(apagado_em__isnull=True).get(pk=variacao_id)

    fichas = list(
        FichaTecnica.objects
        .filter(variacao_id=variacao.pk, apagada_em__isnull=True, materia_prima__apagada_em__isnull=True)
        .order_by('materia_prima_id')
    )
    if not fichas:
        raise FichaTecnicaInexistente(
            f'A variação "{variacao.nome}" (SKU {variacao.sku}) não possui ficha técnica ativa.'
        )

    for ficha in fichas:
        _consumir_materia_prima_fefo(
            materia_prima_id=ficha.materia_prima_id,
            quantidade=ficha.quantidade_necessaria * quantidade,
            usuario=usuario,
            observacao=f'{PREFIXO_AUTOMATICO}Saída por produção',
        )

    lote = criar_lote_variacao(
        variacao=variacao,
        data_validade=data_validade,
        data_fabricacao=data_fabricacao,
        numero_lote=numero_lote,
        observacao=observacao,
    )

    registrar_movimentacao_estoque(
        lote_id=lote.pk,
        tipo=TipoMovimentacaoEstoque.ENTRADA,
        quantidade=quantidade,
        usuario=usuario,
        observacao=f'{PREFIXO_AUTOMATICO}Entrada por fabricação',
    )

    lote.refresh_from_db()
    return lote


@transaction.atomic
def criar_compra_fornecedor_completa(usuario, dados_compra, itens_data):
    if not itens_data:
        raise CompraFornecedorSemItem('A compra deve conter pelo menos um item.')

    itens_data = sorted(itens_data, key=lambda i: i['materia_prima'].pk)

    valor_total = sum(
        (i['quantidade_item'] * i['custo_unitario_momento_compra'] for i in itens_data),
        Decimal('0'),
    )

    compra_fornecedor = CompraFornecedor.objects.create(valor_total=valor_total, **dados_compra)

    for item_data in itens_data:
        materia_prima = item_data['materia_prima']
        quantidade = item_data['quantidade_item']

        item = CompraFornecedorItem.objects.create(
            compra_fornecedor=compra_fornecedor,
            materia_prima=materia_prima,
            quantidade_item=quantidade,
            custo_unitario_momento_compra=item_data['custo_unitario_momento_compra'],
        )

        lote = criar_lote_materia_prima(
            materia_prima=materia_prima,
            numero_lote_fabricante=item_data.get('numero_lote_fabricante'),
            data_validade=item_data.get('data_validade'),
            observacao='Lote criado automaticamente pela compra de fornecedor',
            compra_fornecedor_item=item,
        )

        registrar_movimentacao_material(
            lote_id=lote.pk,
            tipo=TipoMovimentacaoMaterial.ENTRADA,
            quantidade=quantidade,
            usuario=usuario,
            fornecedor=dados_compra['fornecedor'],
            observacao=f'{PREFIXO_AUTOMATICO}Entrada por compra de fornecedor',
        )

    return compra_fornecedor


def _travar_e_validar_transicao(compra_fornecedor_id, novo_status):
    compra_fornecedor = CompraFornecedor.objects.select_for_update().get(pk=compra_fornecedor_id)

    if novo_status not in TRANSICOES_PERMITIDAS_COMPRA_FORNECEDOR[compra_fornecedor.status]:
        raise TransicaoInvalida(atual=compra_fornecedor.status, novo=novo_status)

    return compra_fornecedor


def _aplicar_status(compra_fornecedor, novo_status):
    compra_fornecedor.status = novo_status
    compra_fornecedor.save(update_fields=['status', 'atualizada_em'])
    return compra_fornecedor


@transaction.atomic
def devolver_compra_fornecedor(*, compra_fornecedor_id, usuario):
    compra_fornecedor = _travar_e_validar_transicao(compra_fornecedor_id, StatusCompraFornecedor.DEVOLVIDO)

    for item in compra_fornecedor.fornecedor_itens.order_by('materia_prima_id'):
        lote = item.lote_materiais.get()
        registrar_movimentacao_material(
            lote_id=lote.pk,
            tipo=TipoMovimentacaoMaterial.SAIDA_DEVOLUCAO,
            quantidade=item.quantidade_item,
            usuario=usuario,
            fornecedor=compra_fornecedor.fornecedor,
            observacao=f'{PREFIXO_AUTOMATICO}Devolução das matérias-prima ao fornecedor',
        )

    return _aplicar_status(compra_fornecedor, StatusCompraFornecedor.DEVOLVIDO)


@transaction.atomic
def definir_categorias_fornecedor(fornecedor, categorias):
    novas = set(categorias)
    atuais = set(fornecedor.categorias.values_list('categoria', flat=True))

    fornecedor.categorias.filter(categoria__in=atuais - novas).delete()
    FornecedorCategoria.objects.bulk_create([
        FornecedorCategoria(fornecedor=fornecedor, categoria=c)
        for c in novas - atuais
    ])