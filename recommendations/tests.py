from unittest import mock

import pandas as pd
from django.test import SimpleTestCase, TestCase

from catalog.models import BaseProduto, Ingrediente, Produto, TipoPeleIndicado
from recommendations import constants
from recommendations.constants import PROB_MINIMA
from recommendations.exceptions import ModeloIndisponivel
from recommendations.services import carregar_modelo, combinacao_pele, passa_regras_seguranca, recomendar


def _perfil(**extra):
    return {'alergia_ingrediente': [], 'quer_vegano': 0, **extra}


def _produto(ingredientes=(), vegano=1):
    return {'ingredientes_lista': list(ingredientes), 'vegano': vegano}


def _respostas(**extra):
    return {
        'tipo_pele': 'seca', 'sensibilidade': 'as_vezes', 'ressecamento': 'sim', 'preferencia': 'hidratacao',
        'evita_fragrancia': 1, 'quer_vegano': 0, 'alergia_ingrediente': [], **extra,
    }


class PassaRegrasSegurancaTests(SimpleTestCase):
    def test_alergia_a_ingrediente_do_produto_exclui(self):
        produto = _produto(['aveia', 'mel'])
        self.assertFalse(passa_regras_seguranca(_perfil(alergia_ingrediente=['mel']), produto))

    def test_alergia_exclui_mesmo_entre_varias_alergias(self):
        produto = _produto(['glicerina', 'menta'])
        self.assertFalse(passa_regras_seguranca(_perfil(alergia_ingrediente=['lavanda', 'menta']), produto))

    def test_alergia_ignora_maiusculas_e_espacos(self):
        produto = _produto(['menta'])
        self.assertFalse(passa_regras_seguranca(_perfil(alergia_ingrediente=['  Menta ']), produto))

    def test_menta_nao_casa_com_outra_palavra(self):
        produto = _produto(['mentol', 'hortela-menta', 'menta piperita'])
        self.assertTrue(passa_regras_seguranca(_perfil(alergia_ingrediente=['menta']), produto))

    def test_mel_nao_casa_com_caramelo(self):
        produto = _produto(['caramelo'])
        self.assertTrue(passa_regras_seguranca(_perfil(alergia_ingrediente=['mel']), produto))

    def test_sem_alergia_nao_exclui(self):
        produto = _produto(['mel'])
        self.assertTrue(passa_regras_seguranca(_perfil(alergia_ingrediente=[]), produto))
        self.assertTrue(passa_regras_seguranca(_perfil(alergia_ingrediente=['nenhuma']), produto))

    def test_quer_vegano_exclui_nao_vegano(self):
        self.assertFalse(passa_regras_seguranca(_perfil(quer_vegano=1), _produto(vegano=0)))

    def test_quer_vegano_aceita_vegano(self):
        self.assertTrue(passa_regras_seguranca(_perfil(quer_vegano=1), _produto(vegano=1)))

    def test_nao_exige_vegano_aceita_nao_vegano(self):
        self.assertTrue(passa_regras_seguranca(_perfil(quer_vegano=0), _produto(vegano=0)))


class CombinacaoPeleTests(SimpleTestCase):
    def test_quatro_casos(self):
        df = pd.DataFrame({
            'tipo_pele': ['nao_sei', 'seca', 'seca', 'seca'],
            'tipo_pele_indicado': ['seca', 'todos', 'seca', 'oleosa'],
        })
        self.assertEqual(list(combinacao_pele(df)), ['perfil_nao_sabe', 'produto_todos', 'sim', 'nao'])


class RecomendarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def criar(nome, tipo_pele, base, sem_fragrancia, vegano, ingredientes, esta_ativo=True):
            produto = Produto.objects.create(
                nome=nome, tipo_pele_indicado=tipo_pele, base=base,
                sem_fragrancia=sem_fragrancia, vegano=vegano, esta_ativo=esta_ativo,
            )
            produto.ingredientes.set([Ingrediente.objects.get_or_create(nome=i)[0] for i in ingredientes])
            return produto

        cls.aveia_mel = criar('Aveia e Mel', TipoPeleIndicado.SECA, BaseProduto.PROCESSO_A_FRIO, False, False,
                              ['aveia', 'mel', 'manteiga de karite', 'oleo vegetal'])
        cls.karite = criar('Karité Hidratante', TipoPeleIndicado.SECA, BaseProduto.PROCESSO_A_FRIO, True, True,
                           ['manteiga de karite', 'oleo vegetal'])
        cls.leite_cabra = criar('Leite de Cabra', TipoPeleIndicado.SECA, BaseProduto.PROCESSO_A_FRIO, True, False,
                                ['leite de cabra', 'manteiga de karite', 'oleo vegetal'])
        cls.argila_verde = criar('Argila Verde', TipoPeleIndicado.OLEOSA, BaseProduto.PROCESSO_A_FRIO, False, True,
                                 ['argila verde', 'oleo vegetal', 'menta'])
        cls.alecrim = criar('Alecrim e Capim-limão', TipoPeleIndicado.OLEOSA, BaseProduto.GLICERINA, False, True,
                            ['glicerina', 'alecrim', 'capim-limao'])
        cls.carvao = criar('Carvão Ativado', TipoPeleIndicado.OLEOSA, BaseProduto.GLICERINA, True, True,
                           ['glicerina', 'carvao ativado'])
        cls.inativo = criar('Seca Inativo', TipoPeleIndicado.SECA, BaseProduto.PROCESSO_A_FRIO, True, True,
                            ['oleo vegetal'], esta_ativo=False)

    def _nomes(self, **respostas):
        return [r['produto'].nome for r in recomendar(respostas=_respostas(**respostas), queryset=Produto.objects.all())]

    def test_pele_seca_recomenda_produtos_para_pele_seca(self):
        self.assertEqual(self._nomes(), ['Aveia e Mel', 'Karité Hidratante', 'Leite de Cabra'])

    def test_alergia_remove_o_produto_com_o_ingrediente(self):
        nomes = self._nomes(tipo_pele='oleosa', sensibilidade='nao', ressecamento='nao',
                            preferencia='limpeza_suave', evita_fragrancia=0, alergia_ingrediente=['menta'])
        self.assertNotIn('Argila Verde', nomes)
        self.assertEqual(nomes, ['Alecrim e Capim-limão', 'Carvão Ativado'])

    def test_alergia_sempre_exclui_mesmo_o_mais_compativel(self):
        nomes = self._nomes(alergia_ingrediente=['mel'])
        self.assertNotIn('Aveia e Mel', nomes)
        self.assertIn('Karité Hidratante', nomes)

    def test_quer_vegano_nunca_retorna_nao_vegano(self):
        resultado = recomendar(respostas=_respostas(quer_vegano=1), queryset=Produto.objects.all())
        self.assertTrue(resultado)
        self.assertTrue(all(r['produto'].vegano for r in resultado))

    def test_produto_inativo_nao_aparece(self):
        self.assertNotIn('Seca Inativo', self._nomes())

    def test_nenhum_resultado_abaixo_da_prob_minima_e_respeita_top_n(self):
        resultado = recomendar(respostas=_respostas(), queryset=Produto.objects.all(), top_n=2)
        self.assertEqual(len(resultado), 2)
        self.assertTrue(all(r['prob'] >= PROB_MINIMA for r in resultado))

    def test_lista_vazia_quando_nada_passa_na_seguranca(self):
        todos_ingredientes = list(Ingrediente.objects.values_list('nome', flat=True))
        with mock.patch('recommendations.services.carregar_modelo') as carregar:
            resultado = recomendar(respostas=_respostas(alergia_ingrediente=todos_ingredientes),
                                   queryset=Produto.objects.all())
        self.assertEqual(resultado, [])
        carregar.assert_not_called()

    def test_lista_vazia_quando_nenhum_produto_atinge_prob_minima(self):
        resultado = recomendar(respostas=_respostas(), queryset=Produto.objects.filter(pk=self.carvao.pk))
        self.assertEqual(resultado, [])


class CarregarModeloTests(SimpleTestCase):
    def setUp(self):
        carregar_modelo.cache_clear()
        self.addCleanup(carregar_modelo.cache_clear)

    def test_carrega_uma_vez_por_processo(self):
        self.assertIs(carregar_modelo(), carregar_modelo())
        self.assertEqual(carregar_modelo.cache_info().misses, 1)

    def test_arquivo_ausente_gera_modelo_indisponivel(self):
        with mock.patch.object(constants, 'CAMINHO_MODELO', constants.CAMINHO_MODELO.with_name('nao_existe.pkl')), \
                self.assertLogs('recommendations.services', level='ERROR'):
            with self.assertRaises(ModeloIndisponivel):
                carregar_modelo()
