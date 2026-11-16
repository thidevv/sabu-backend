from unittest import mock

import pandas as pd
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from catalog.models import BaseProduto, Ingrediente, Produto, TipoPeleIndicado
from recommendations import constants
from recommendations.constants import AVISO, PROB_MINIMA
from recommendations.exceptions import ModeloIndisponivel
from recommendations.services import carregar_modelo, combinacao_pele, passa_regras_seguranca, recomendar
from recommendations.views import QuizAnonThrottle

URL_QUIZ = '/api/v1/recommendations/quiz/'


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


def _criar_produto(nome, tipo_pele, base, sem_fragrancia, vegano, ingredientes, esta_ativo=True):
    produto = Produto.objects.create(
        nome=nome, tipo_pele_indicado=tipo_pele, base=base,
        sem_fragrancia=sem_fragrancia, vegano=vegano, esta_ativo=esta_ativo,
    )
    produto.ingredientes.set([Ingrediente.objects.get_or_create(nome=i)[0] for i in ingredientes])
    return produto


class CatalogoDeTesteMixin:
    # Subconjunto do catalogo_sabu.csv usado no treino
    @classmethod
    def setUpTestData(cls):
        criar = _criar_produto
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


class RecomendarTests(CatalogoDeTesteMixin, TestCase):
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


class RecomendacaoViewTests(CatalogoDeTesteMixin, TestCase):
    def setUp(self):
        # O throttle guarda o histórico no cache; sem limpar, um teste afetaria o outro
        cache.clear()
        self.addCleanup(cache.clear)
        self.client = APIClient()

    def _post(self, **extra):
        return self.client.post(URL_QUIZ, {**_respostas(), **extra}, format='json')

    def _nomes(self, resposta):
        return [p['nome'] for p in resposta.data['produtos']]

    def test_resposta_valida_retorna_produtos_e_aviso(self):
        resposta = self._post()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self._nomes(resposta), ['Aveia e Mel', 'Karité Hidratante', 'Leite de Cabra'])
        self.assertEqual(resposta.data['aviso'], AVISO)
        self.assertEqual(
            set(resposta.data['produtos'][0]),
            {'id', 'nome', 'imagem', 'tipo_pele_indicado', 'base', 'essencia', 'prob'},
        )

    def test_opcao_fora_da_lista_retorna_400(self):
        resposta = self._post(tipo_pele='muito_seca')
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data['code'], 'validation_error')
        self.assertIn('tipo_pele', resposta.data['errors'])

    def test_sim_nao_aceita_apenas_0_ou_1(self):
        resposta = self._post(quer_vegano=2)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('quer_vegano', resposta.data['errors'])

    def test_campo_obrigatorio_ausente_retorna_400(self):
        resposta = self.client.post(URL_QUIZ, {'tipo_pele': 'seca'}, format='json')
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(
            set(resposta.data['errors']),
            {'sensibilidade', 'ressecamento', 'preferencia', 'evita_fragrancia', 'quer_vegano'},
        )

    def test_ingrediente_nao_cadastrado_retorna_400(self):
        resposta = self._post(alergia_ingrediente=['abacate'])
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('alergia_ingrediente', resposta.data['errors'])

    def test_alergia_remove_o_produto_certo(self):
        oleosa = dict(tipo_pele='oleosa', sensibilidade='nao', ressecamento='nao',
                      preferencia='limpeza_suave', evita_fragrancia=0)
        sem_alergia = self._nomes(self._post(**oleosa))
        com_alergia = self._nomes(self._post(**oleosa, alergia_ingrediente=[' Menta ']))

        self.assertIn('Argila Verde', sem_alergia)
        self.assertNotIn('Argila Verde', com_alergia)
        self.assertEqual(com_alergia, [n for n in sem_alergia if n != 'Argila Verde'])

    def test_quer_vegano_nao_retorna_nao_vegano(self):
        resposta = self._post(quer_vegano=1)
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('Aveia e Mel', self._nomes(resposta))
        self.assertNotIn('Leite de Cabra', self._nomes(resposta))

    def test_lista_vazia_tambem_traz_o_aviso(self):
        todos = list(Ingrediente.objects.values_list('nome', flat=True))
        resposta = self._post(alergia_ingrediente=todos)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data, {'produtos': [], 'aviso': AVISO})

    def test_rota_publica_ignora_token_invalido(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer token.invalido')
        self.assertEqual(self._post().status_code, 200)

    def test_get_nao_permitido(self):
        self.assertEqual(self.client.get(URL_QUIZ).status_code, 405)

    def test_limite_por_ip_retorna_429(self):
        with mock.patch.object(QuizAnonThrottle, 'THROTTLE_RATES', {'quiz': '2/min'}):
            self.assertEqual(self._post().status_code, 200)
            self.assertEqual(self._post().status_code, 200)
            resposta = self._post()

        self.assertEqual(resposta.status_code, 429)
        self.assertEqual(resposta.data['code'], 'throttled')
        self.assertIn('Retry-After', resposta.headers)

    def test_limite_e_separado_por_ip(self):
        with mock.patch.object(QuizAnonThrottle, 'THROTTLE_RATES', {'quiz': '1/min'}):
            self.assertEqual(self._post().status_code, 200)
            self.assertEqual(self._post().status_code, 429)
            outro_ip = self.client.post(URL_QUIZ, _respostas(), format='json', REMOTE_ADDR='10.0.0.2')

        self.assertEqual(outro_ip.status_code, 200)

    def test_modelo_indisponivel_retorna_503(self):
        with mock.patch('recommendations.services.carregar_modelo', side_effect=ModeloIndisponivel()):
            resposta = self._post()
        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta.data['code'], 'modelo_indisponivel')
