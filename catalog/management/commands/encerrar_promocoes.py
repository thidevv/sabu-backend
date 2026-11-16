from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import ProdutoVariacao


class Command(BaseCommand):
    help = "Encerra promoções cujo fim_promo já passou, limpando os campos de promoção."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas mostra quantas variações seriam afetadas, sem alterar nada.",
        )

    def handle(self, *args, **options):
        agora = timezone.now()

        expiradas = ProdutoVariacao.objects.filter(
            fim_promo__lt=agora,
            apagado_em__isnull=True,
        )

        total = expiradas.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(f"[dry-run] {total} promoção(ões) seriam encerradas.")
            )
            return

        atualizadas = expiradas.update(
            preco_promo=None,
            inicio_promo=None,
            fim_promo=None,
        )

        self.stdout.write(
            self.style.SUCCESS(f"{atualizadas} promoção(ões) encerrada(s).")
        )