import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase

from accounts.models import Usuario
from catalog.models import BaseProduto, Ingrediente, Produto, ProdutoVariacao, TipoPeleIndicado
from inventory.models import MovimentacaoEstoque

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


CABECALHO_VARIACAO = (
    'produto_id,nome,tipo_pele_indicado,base,essencia,sem_fragrancia,vegano,ingredientes,'
    'variacao,peso_gramas,preco,estoque\n'
)


class SeedCatalogoVariacoesTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            email='admin@exemplo.com', password='x', nome='Admin', cargo='ADMIN')

    def _seed(self, *args):
        saida = StringIO()
        call_command('seed_catalogo', *args, stdout=saida)
        return saida.getvalue()

    def _csv(self, linhas):
        arquivo = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, encoding='utf-8')
        arquivo.write(CABECALHO_VARIACAO + linhas)
        arquivo.close()
        self.addCleanup(Path(arquivo.name).unlink)
        return arquivo.name

    def test_cria_uma_variacao_com_estoque_por_produto(self):
        self._seed()

        self.assertEqual(ProdutoVariacao.objects.count(), 12)
        variacao = ProdutoVariacao.objects.get(produto__nome='Aveia e Mel')
        self.assertEqual(variacao.sku, 'SEED-001-100G')
        self.assertEqual(variacao.nome, 'Barra')
        self.assertEqual(variacao.peso_gramas, 100)
        self.assertEqual(str(variacao.preco), '18.90')
        self.assertEqual(variacao.quantidade_estoque, 20)
        movimentacao = MovimentacaoEstoque.objects.get(lote_produto_variacao__variacao=variacao)
        self.assertEqual(movimentacao.usuario, self.admin)

    def test_rodar_duas_vezes_nao_duplica_variacao_nem_soma_estoque(self):
        self._seed()
        self._seed()

        self.assertEqual(ProdutoVariacao.objects.count(), 12)
        self.assertEqual(ProdutoVariacao.objects.get(sku='SEED-001-100G').quantidade_estoque, 20)
        self.assertEqual(MovimentacaoEstoque.objects.count(), 12)

    def test_produto_existente_ganha_variacao(self):
        # Caso do servidor: produtos de um seed antigo, sem variação
        Produto.objects.create(nome='Aveia e Mel')

        self._seed()

        self.assertTrue(ProdutoVariacao.objects.filter(produto__nome='Aveia e Mel').exists())

    def test_nao_cria_variacao_se_produto_ja_tem_uma_com_o_mesmo_nome(self):
        produto = Produto.objects.create(nome='Aveia e Mel')
        ProdutoVariacao.objects.create(produto=produto, sku='MANUAL-1', nome='Barra', preco='10.00')

        self._seed()

        self.assertEqual(produto.variacoes.count(), 1)
        self.assertEqual(produto.variacoes.get().sku, 'MANUAL-1')

    def test_sem_admin_cria_variacoes_sem_estoque(self):
        self.admin.delete()

        saida = self._seed()

        self.assertIn('Nenhum ADMIN ativo', saida)
        self.assertEqual(ProdutoVariacao.objects.count(), 12)
        self.assertFalse(ProdutoVariacao.objects.filter(quantidade_estoque__gt=0).exists())

    def test_sem_estoque(self):
        self._seed('--sem-estoque')

        self.assertEqual(ProdutoVariacao.objects.count(), 12)
        self.assertFalse(MovimentacaoEstoque.objects.exists())

    def test_usuario_inexistente(self):
        with self.assertRaisesMessage(CommandError, 'Usuário não encontrado'):
            self._seed('--usuario', 'ninguem@exemplo.com')

    def test_preco_invalido_nao_salva_nada(self):
        arquivo = self._csv(
            '1,Produto Bom,seca,glicerina,neutro,0,1,glicerina,Barra,100,10.00,5\n'
            '2,Produto Ruim,seca,glicerina,neutro,0,1,glicerina,Barra,100,dez reais,5\n'
        )

        with self.assertRaisesMessage(CommandError, 'Linha 3: preco inválido'):
            self._seed('--arquivo', arquivo)
        self.assertEqual(Produto.objects.count(), 0)
        self.assertEqual(ProdutoVariacao.objects.count(), 0)
