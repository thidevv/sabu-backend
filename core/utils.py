import uuid
from pathlib import Path

from django.utils.deconstruct import deconstructible


@deconstructible
class CaminhoImagem:
    def __init__(self, pasta):
        self.pasta = pasta

    def __call__(self, instance, filename):
        return f"{self.pasta}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"