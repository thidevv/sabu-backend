from django.core.cache import cache
from django.utils import timezone

from inventory.models import LoteMateriaPrima, LoteProdutoVariacao, StatusLote
from orders.models import Pedido, StatusPedido

CACHE_KEY_RESUMO = 'dashboard:resumo:v1'

CACHE_TTL_SEGUNDOS = 60 * 15


def _calcular_resumo():
    return {
        'pedidos_pendentes': Pedido.objects.filter(status=StatusPedido.PENDENTE).count(),
        'lotes_materia_prima_vencidos': LoteMateriaPrima.objects.filter(status=StatusLote.VENCIDO).count(),
        'lotes_produto_vencidos': LoteProdutoVariacao.objects.filter(status=StatusLote.VENCIDO).count(),
        'atualizado_em': timezone.now(),
    }


def obter_resumo():
    return cache.get_or_set(CACHE_KEY_RESUMO, _calcular_resumo, CACHE_TTL_SEGUNDOS)


def invalidar_resumo():
    cache.delete(CACHE_KEY_RESUMO)