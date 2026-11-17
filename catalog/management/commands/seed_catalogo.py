import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import BaseProduto, Ingrediente, Produto, ProdutoIngrediente, TipoPeleIndicado

ARQUIVO_PADRAO = Path(__file__).resolve().parents[2] / 'seeds' / 'catalogo_sabu.csv'
COLUNAS = {'nome', 'tipo_pele_indicado', 'base', 'essencia', 'sem_fragrancia', 'vegano', 'ingredientes'}


def _choice(valor, choices, campo):
    # CSV usa o formato do treino ('processo a frio'); o model guarda 'PROCESSO_A_FRIO'
    convertido = valor.strip().upper().replace(' ', '_')
    if convertido not in choices.values:
        raise ValueError(f'{campo} inválido: "{valor}"')
    return convertido


def _booleano(valor, campo):
    if valor.strip() not in ('0', '1'):
        raise ValueError(f'{campo} deve ser 0 ou 1: "{valor}"')
    return valor.strip() == '1'


def _linha_para_produto(linha):
    nome = linha['nome'].strip()
    if not nome:
        raise ValueError('nome vazio')
    dados = {
        'tipo_pele_indicado': _choice(linha['tipo_pele_indicado'], TipoPeleIndicado, 'tipo_pele_indicado'),
        'base': _choice(linha['base'], BaseProduto, 'base'),
        'essencia': linha['essencia'].strip(),
        'sem_fragrancia': _booleano(linha['sem_fragrancia'], 'sem_fragrancia'),
        'vegano': _booleano(linha['vegano'], 'vegano'),
    }
    ingredientes = [i.strip().lower() for i in linha['ingredientes'].split(';') if i.strip()]
    return nome, dados, ingredientes


class Command(BaseCommand):
    help = 'Carrega o catálogo de exemplo do quiz (produtos com perfil de pele e ingredientes). Não duplica registros.'

    def add_arguments(self, parser):
        parser.add_argument('--arquivo', type=Path, default=ARQUIVO_PADRAO, help='CSV a carregar.')

    @transaction.atomic
    def handle(self, *args, **options):
        arquivo = options['arquivo']
        if not arquivo.exists():
            raise CommandError(f'Arquivo não encontrado: {arquivo}')

        criados = existentes = 0
        with arquivo.open(encoding='utf-8-sig', newline='') as f:
            leitor = csv.DictReader(f)
            faltando = COLUNAS - set(leitor.fieldnames or [])
            if faltando:
                raise CommandError(f'Colunas ausentes no CSV: {", ".join(sorted(faltando))}')

            for numero, linha in enumerate(leitor, start=2):
                try:
                    nome, dados, ingredientes = _linha_para_produto(linha)
                except ValueError as erro:
                    raise CommandError(f'Linha {numero}: {erro}. Nada foi salvo.')

                produto, criado = Produto.objects.get_or_create(nome=nome, defaults=dados)
                for nome_ingrediente in ingredientes:
                    ingrediente, _ = Ingrediente.objects.get_or_create(nome=nome_ingrediente)
                    ProdutoIngrediente.objects.get_or_create(produto=produto, ingrediente=ingrediente)

                if criado:
                    criados += 1
                    self.stdout.write(f'  criado: {produto.nome}')
                else:
                    existentes += 1
                    self.stdout.write(f'  já existia: {produto.nome}')

        self.stdout.write(self.style.SUCCESS(f'{criados} produto(s) criado(s), {existentes} já existia(m).'))
