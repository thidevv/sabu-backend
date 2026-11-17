import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase

from catalog.models import BaseProduto, Ingrediente, Produto, TipoPeleIndicado

CABECALHO = 'produto_id,nome,tipo_pele_indicado,base,essencia,sem_fragrancia,vegano,ingredientes\n'


class SeedCatalogoTests(TestCase):
    def _seed(self, *args):
        call_command('seed_catalogo', *args, stdout=StringIO())

    def _csv(self, linhas):
        arquivo = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, encoding='utf-8')
        arquivo.write(CABECALHO + linhas)
        arquivo.close()
        self.addCleanup(Path(arquivo.name).unlink)
        return arquivo.name

    def test_carrega_catalogo_padrao(self):
        self._seed()

        self.assertEqual(Produto.objects.count(), 12)
        aveia = Produto.objects.get(nome='Aveia e Mel')
        self.assertEqual(aveia.tipo_pele_indicado, TipoPeleIndicado.SECA)
        self.assertEqual(aveia.base, BaseProduto.PROCESSO_A_FRIO)
        self.assertFalse(aveia.vegano)
        self.assertFalse(aveia.sem_fragrancia)
        self.assertEqual(
            set(aveia.ingredientes.values_list('nome', flat=True)),
            {'aveia', 'mel', 'manteiga de karite', 'oleo vegetal'},
        )

    def test_rodar_duas_vezes_nao_duplica(self):
        self._seed()
        self._seed()

        self.assertEqual(Produto.objects.count(), 12)
        self.assertEqual(Ingrediente.objects.count(), 17)

    def test_nao_sobrescreve_produto_existente(self):
        Produto.objects.create(nome='Aveia e Mel', tipo_pele_indicado=TipoPeleIndicado.TODOS, vegano=True)

        self._seed()

        aveia = Produto.objects.get(nome='Aveia e Mel')
        self.assertEqual(aveia.tipo_pele_indicado, TipoPeleIndicado.TODOS)
        self.assertTrue(aveia.vegano)

    def test_linha_invalida_nao_salva_nada(self):
        arquivo = self._csv(
            '1,Produto Bom,seca,glicerina,neutro,0,1,glicerina\n'
            '2,Produto Ruim,muito_seca,glicerina,neutro,0,1,glicerina\n'
        )

        with self.assertRaisesMessage(CommandError, 'Linha 3'):
            self._seed('--arquivo', arquivo)
        self.assertEqual(Produto.objects.count(), 0)
        self.assertEqual(Ingrediente.objects.count(), 0)

    def test_arquivo_inexistente(self):
        with self.assertRaisesMessage(CommandError, 'Arquivo não encontrado'):
            self._seed('--arquivo', '/caminho/que/nao/existe.csv')
