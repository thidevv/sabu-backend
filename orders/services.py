from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from inventory.services import baixar_estoque_variacao_fefo, estornar_vendas_do_pedido
from orders.exceptions import PedidoSemItem, TransicaoInvalida, DescontoInvalido
from orders.models import Pedido, PedidoItem, Cliente, StatusPedido, TRANSICOES_PERMITIDAS_PEDIDO, TipoDesconto

CENTAVO = Decimal('0.01')


def _quantizar(valor):
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _para_centavos(valor):
    return int((Decimal(valor) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _de_centavos(centavos):
    return (Decimal(centavos) / 100).quantize(CENTAVO)


def calcular_subtotal(itens_data):
    return sum(
        (_quantizar(i['quantidade_item'] * i['variacao'].preco_final) for i in itens_data),
        Decimal('0.00'),
    )


def calcular_valor_desconto(subtotal, tipo_desconto, desconto):
    desconto = Decimal(desconto or 0)

    if not tipo_desconto or desconto == 0:
        return Decimal('0.00')

    if desconto < 0:
        raise DescontoInvalido('O desconto não pode ser negativo.')

    if tipo_desconto == TipoDesconto.PERCENTUAL:
        if desconto > 100:
            raise DescontoInvalido('O desconto percentual não pode ser maior que 100%.')
        return _quantizar(subtotal * desconto / 100)

    if tipo_desconto == TipoDesconto.FIXO:
        if desconto > subtotal:
            raise DescontoInvalido(
                f'O desconto fixo (R$ {desconto}) não pode ser maior que o subtotal do pedido (R$ {subtotal}).'
            )
        return _quantizar(desconto)

    raise DescontoInvalido('Tipo de desconto inválido.')


def distribuir_desconto_igualmente(valor_desconto, totais_linhas):
    restante = _para_centavos(valor_desconto)
    limites = [_para_centavos(t) for t in totais_linhas]
    alocado = [0] * len(limites)
    abertos = [i for i, limite in enumerate(limites) if limite > 0]

    while restante > 0 and abertos:
        base, sobra = divmod(restante, len(abertos))
        for pos, i in enumerate(abertos):
            cota = base + (1 if pos < sobra else 0)
            dar = min(cota, limites[i] - alocado[i])
            alocado[i] += dar
            restante -= dar
        abertos = [i for i in abertos if alocado[i] < limites[i]]

    if restante > 0:
        raise DescontoInvalido('O desconto excede o valor total dos itens do pedido.')

    return [_de_centavos(c) for c in alocado]


@transaction.atomic
def criar_pedido_completo(usuario, dados_pedido, itens_data):
    if not itens_data:
        raise PedidoSemItem('O pedido deve conter pelo menos um item.')

    dados_pedido = dict(dados_pedido)
    tipo_desconto = dados_pedido.pop('tipo_desconto', '') or ''
    desconto = dados_pedido.pop('desconto', None) or Decimal('0.00')

    itens_data = sorted(itens_data, key=lambda i: i['variacao'].pk)

    precos = [i['variacao'].preco_final for i in itens_data]
    totais_linhas = [
        _quantizar(i['quantidade_item'] * preco)
        for i, preco in zip(itens_data, precos)
    ]

    valor_subtotal = sum(totais_linhas, Decimal('0.00'))
    valor_desconto = calcular_valor_desconto(valor_subtotal, tipo_desconto, desconto)
    descontos_linhas = distribuir_desconto_igualmente(valor_desconto, totais_linhas)

    if valor_desconto == 0:
        tipo_desconto, desconto = '', Decimal('0.00')

    pedido = Pedido.objects.create(
        valor_subtotal=valor_subtotal,
        tipo_desconto=tipo_desconto,
        desconto=desconto,
        valor_desconto=valor_desconto,
        valor_total=valor_subtotal - valor_desconto,
        **dados_pedido,
    )

    for item_data, preco, desconto_linha in zip(itens_data, precos, descontos_linhas):
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
            valor_unitario=preco,
            valor_desconto=desconto_linha,
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