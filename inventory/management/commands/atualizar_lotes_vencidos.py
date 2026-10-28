from django.core.management.base import BaseCommand

from inventory.services import atualizar_lotes_vencidos


class Command(BaseCommand):
    help = 'Marca como VENCIDO os lotes ativos com validade ultrapassada e atualiza o estoque agregado.'

    def handle(self, *args, **options):
        resultado = atualizar_lotes_vencidos()
        self.stdout.write(self.style.SUCCESS(
            f'Lotes de variações vencidos: {resultado["variacoes"]}. '
            f'Lotes de matérias-primas vencidos: {resultado["materias_primas"]}.'
        ))