from decimal import Decimal

from django.db import transaction

from catalog.models import ProdutoVariacao
from orders.exceptions import TransicaoInvalida
from .exceptions import (
    EstoqueInsuficiente,
    MovimentacaoIncoerente,
    TipoMovimentacaoInvalido, CompraFornecedorSemItem,
)
from .models import (
    MovimentacaoEstoque,
    TIPOS_COM_PEDIDO,
    TIPOS_QUE_AUMENTAM,
    TIPOS_QUE_DIMINUEM, TIPOS_MATERIAL_QUE_AUMENTAM, TIPOS_MATERIAL_QUE_DIMINUEM, MateriaPrima, MovimentacaoMaterial,
    CompraFornecedor, CompraFornecedorItem, TRANSICOES_PERMITIDAS_COMPRA_FORNECEDOR,
    StatusCompraFornecedor, FornecedorCategoria,
)


@transaction.atomic
def registrar_movimentacao_estoque(*, variacao_id, tipo, quantidade, usuario,
                           pedido=None, observacao=None):
    if tipo in TIPOS_QUE_AUMENTAM:
        delta = quantidade
    elif tipo in TIPOS_QUE_DIMINUEM:
        delta = -quantidade
    else:
        raise TipoMovimentacaoInvalido(f'Tipo de movimentação inválido: {tipo}.')

    if (tipo in TIPOS_COM_PEDIDO) != (pedido is not None):
        raise MovimentacaoIncoerente(
            "Venda/estorno exigem pedido, os demais tipos não aceitam."
        )

    variacao = ProdutoVariacao.objects.select_for_update().filter(apagado_em__isnull=True).get(pk=variacao_id)

    novo_saldo = variacao.quantidade_estoque + delta
    if novo_saldo < 0:
        raise EstoqueInsuficiente(
            ids=variacao.pk,
            sku=variacao.sku,
            produto=variacao.nome,
            saldo=variacao.quantidade_estoque,
            solicitado=quantidade,
        )

    variacao.quantidade_estoque = novo_saldo
    variacao.save(update_fields=['quantidade_estoque'])

    return MovimentacaoEstoque.objects.create(
        variacao=variacao, tipo=tipo, quantidade_movimentada=quantidade,
        usuario=usuario, pedido=pedido, observacao=observacao,
    )


@transaction.atomic
def registrar_movimentacao_material(*, materia_prima_id, tipo, quantidade, usuario,
                           fornecedor=None, observacao=None):
    if tipo in TIPOS_MATERIAL_QUE_AUMENTAM:
        delta = quantidade
    elif tipo in TIPOS_MATERIAL_QUE_DIMINUEM:
        delta = -quantidade
    else:
        raise TipoMovimentacaoInvalido(f'Tipo de movimentação inválido: {tipo}.')

    materia_prima = MateriaPrima.objects.select_for_update().filter(apagada_em__isnull=True).get(pk=materia_prima_id)

    novo_saldo = materia_prima.quantidade_estoque + delta
    if novo_saldo < 0:
        raise EstoqueInsuficiente(
            ids=materia_prima.pk,
            sku=materia_prima.sku,
            produto=materia_prima.nome,
            saldo=materia_prima.quantidade_estoque,
            solicitado=quantidade,
        )

    materia_prima.quantidade_estoque = novo_saldo
    materia_prima.save(update_fields=['quantidade_estoque'])

    return MovimentacaoMaterial.objects.create(
        materia_prima=materia_prima, tipo=tipo, quantidade_movimentada=quantidade,
        usuario=usuario, fornecedor=fornecedor, observacao=observacao,
    )


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

        registrar_movimentacao_material(
            materia_prima_id=materia_prima.pk,
            tipo='ENTRADA',
            quantidade=quantidade,
            usuario=usuario,
            fornecedor=dados_compra['fornecedor'],
            observacao='MOVIMENTAÇÃO AUTOMÁTICA DO SISTEMA: Entrada por compra de fornecedor',
        )

        CompraFornecedorItem.objects.create(
            compra_fornecedor=compra_fornecedor,
            materia_prima=materia_prima,
            quantidade_item=quantidade,
            custo_unitario_momento_compra=item_data['custo_unitario_momento_compra'],
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
        registrar_movimentacao_material(
            materia_prima_id=item.materia_prima_id,
            tipo='SAIDA_DEVOLUCAO',
            quantidade=item.quantidade_item,
            usuario=usuario,
            fornecedor=compra_fornecedor.fornecedor,
            observacao='MOVIMENTAÇÃO AUTOMÁTICA DO SISTEMA: Devolução das matérias-prima ao fornecedor',
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