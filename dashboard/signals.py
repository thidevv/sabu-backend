from django.db import transaction
from django.db.models.signals import post_delete, post_init, post_save

from inventory.models import LoteMateriaPrima, LoteProdutoVariacao
from orders.models import Pedido

from .services import invalidar_resumo

MODELOS_MONITORADOS = (Pedido, LoteMateriaPrima, LoteProdutoVariacao)


def _guardar_status_original(sender, instance, **kwargs):
    instance._status_original = instance.__dict__.get('status')


def _invalidar_apos_commit():
    transaction.on_commit(invalidar_resumo)


def _ao_salvar(sender, instance, created, **kwargs):
    status_atual = instance.__dict__.get('status')
    mudou = created or status_atual != getattr(instance, '_status_original', None)
    instance._status_original = status_atual
    if mudou:
        _invalidar_apos_commit()


def _ao_apagar(sender, instance, **kwargs):
    _invalidar_apos_commit()


for _modelo in MODELOS_MONITORADOS:
    _nome = _modelo.__name__
    post_init.connect(_guardar_status_original, sender=_modelo, dispatch_uid=f'dashboard_init_{_nome}')
    post_save.connect(_ao_salvar, sender=_modelo, dispatch_uid=f'dashboard_save_{_nome}')
    post_delete.connect(_ao_apagar, sender=_modelo, dispatch_uid=f'dashboard_delete_{_nome}')