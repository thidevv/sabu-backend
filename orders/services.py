from decimal import Decimal

from django.db import transaction

from inventory.services import baixar_estoque_variacao_fefo, estornar_vendas_do_pedido
from orders.exceptions import PedidoSemItem, TransicaoInvalida
from orders.models import Pedido, PedidoItem, Cliente, StatusPedido, TRANSICOES_PERMITIDAS_PEDIDO


@transaction.atomic
def criar_pedido_completo(usuario, dados_pedido, itens_data):
    if not itens_data:
        raise PedidoSemItem('O pedido deve conter pelo menos um item.')

    itens_data = sorted(itens_data, key=lambda i: i['variacao'].pk)

    valor_total = sum(
        (i['quantidade_item'] * i['variacao'].preco_final for i in itens_data),
        Decimal('0'),
    )

    pedido = Pedido.objects.create(valor_total=valor_total, **dados_pedido)

    for item_data in itens_data:
        variacao = item_data['variacao']
        quantidade = item_data['quantidade_item']

        baixar_estoque_variacao_fefo(
            variacao_id=variacao.pk,
            quantidade=quantidade,
            usuario=usuario,
            pedido=pedido,
            observacao='MOVIMENTAÇÃO AUTOMÁTICA DO SISTEMA: Saída por venda',
        )

        PedidoItem.objects.create(
            pedido=pedido,
            variacao=variacao,
            quantidade_item=quantidade,
            valor_unitario=variacao.preco_final,
        )

    cliente = dados_pedido.get('cliente')
    if cliente is not None:
        Cliente.objects.filter(pk=cliente.pk).update(
            ultimo_pedido_em=pedido.criado_em
        )

    return pedido

def _travar_e_validar_transicao(pedido_id, novo_status):
    pedido = Pedido.objects.select_for_update().get(pk=pedido_id)

    if novo_status not in TRANSICOES_PERMITIDAS_PEDIDO[pedido.status]:
        raise TransicaoInvalida(atual=pedido.status, novo=novo_status)

    return pedido


def _aplicar_status(pedido, novo_status):
    pedido.status = novo_status
    pedido.save(update_fields=['status', 'atualizado_em'])
    return pedido


@transaction.atomic
def alterar_status_pedido(*, pedido_id, novo_status):
    pedido = _travar_e_validar_transicao(pedido_id, novo_status)
    return _aplicar_status(pedido, novo_status)


@transaction.atomic
def cancelar_pedido(*, pedido_id, usuario):
    pedido = _travar_e_validar_transicao(pedido_id, StatusPedido.CANCELADO)

    estornar_vendas_do_pedido(
        pedido=pedido,
        usuario=usuario,
        observacao='MOVIMENTAÇÃO AUTOMÁTICA DO SISTEMA: Estorno com devolução ao estoque por cancelamento',
    )

    return _aplicar_status(pedido, StatusPedido.CANCELADO)


def concluir_pedido(*, pedido_id):
    return alterar_status_pedido(pedido_id=pedido_id, novo_status=StatusPedido.CONCLUIDO)


@transaction.atomic
def estornar_pedido_com_devolucao(*, pedido_id, usuario):
    pedido = _travar_e_validar_transicao(pedido_id, StatusPedido.ESTORNADO_COM_DEVOLUCAO)

    estornar_vendas_do_pedido(
        pedido=pedido,
        usuario=usuario,
        observacao='MOVIMENTAÇÃO AUTOMÁTICA DO SISTEMA: Estorno com devolução ao estoque',
    )

    return _aplicar_status(pedido, StatusPedido.ESTORNADO_COM_DEVOLUCAO)


def estornar_pedido_sem_devolucao(*, pedido_id):
    return alterar_status_pedido(pedido_id=pedido_id, novo_status=StatusPedido.ESTORNADO_SEM_DEVOLUCAO)