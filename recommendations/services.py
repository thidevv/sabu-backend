import logging
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from recommendations import constants
from recommendations.constants import PROB_MINIMA, SEM_ALERGIA, TOP_N_PADRAO, VARIAVEIS_MODELO
from recommendations.exceptions import ModeloIndisponivel

logger = logging.getLogger(__name__)


def _normalizar(valor):
    return (valor or '').strip().lower()


def _produto_para_linha(produto):
    # Converte o Produto do banco para o formato do treino (ex.: PROCESSO_A_FRIO -> "processo a frio")
    return {
        'produto': produto,
        'tipo_pele_indicado': _normalizar(produto.tipo_pele_indicado),
        'base': _normalizar(produto.base).replace('_', ' '),
        'sem_fragrancia': int(produto.sem_fragrancia),
        'vegano': int(produto.vegano),
        'ingredientes_lista': [_normalizar(i.nome) for i in produto.ingredientes.all()],
    }


def passa_regras_seguranca(perfil, produto):
    # Regras fixas, fora do modelo: uma alergia declarada nunca depende de probabilidade.
    # A comparação é por item da lista, nunca por substring ("mel" não casa com "caramelo").
    alergias = {_normalizar(a) for a in perfil.get('alergia_ingrediente') or []} - {SEM_ALERGIA, ''}
    if alergias & set(produto['ingredientes_lista']):
        return False
    if perfil['quer_vegano'] == 1 and produto['vegano'] == 0:
        return False
    return True


def combinacao_pele(df):
    return np.select(
        [df['tipo_pele'] == 'nao_sei',
         df['tipo_pele_indicado'] == 'todos',
         df['tipo_pele'] == df['tipo_pele_indicado']],
        ['perfil_nao_sabe', 'produto_todos', 'sim'], default='nao')


@lru_cache(maxsize=1)
def carregar_modelo():
    # Carrega uma vez por processo. Só use .pkl de origem confiável: joblib.load executa código.
    try:
        pacote = joblib.load(constants.CAMINHO_MODELO)
    except Exception as exc:
        logger.exception('Falha ao carregar o modelo de recomendação em %s', constants.CAMINHO_MODELO)
        raise ModeloIndisponivel() from exc

    if not isinstance(pacote, dict) or 'modelo' not in pacote or pacote.get('variaveis') != VARIAVEIS_MODELO:
        logger.error('Modelo de recomendação em formato inesperado: %s', constants.CAMINHO_MODELO)
        raise ModeloIndisponivel()

    return pacote['modelo']


def recomendar(*, respostas, queryset, top_n=TOP_N_PADRAO):
    produtos = queryset.filter(esta_ativo=True).prefetch_related('ingredientes')
    candidatos = [
        linha for linha in map(_produto_para_linha, produtos)
        if passa_regras_seguranca(respostas, linha)
    ]
    if not candidatos:
        return []

    modelo = carregar_modelo()

    df = pd.DataFrame(candidatos)
    for campo in ['tipo_pele', 'sensibilidade', 'ressecamento', 'preferencia', 'evita_fragrancia']:
        df[campo] = respostas[campo]
    df['pele_bate'] = combinacao_pele(df)

    indice_compativel = list(modelo.classes_).index(1)
    df['prob'] = modelo.predict_proba(df[VARIAVEIS_MODELO])[:, indice_compativel]

    df['nome'] = [p.nome for p in df['produto']]
    df = df[df['prob'] >= PROB_MINIMA].sort_values(['prob', 'nome'], ascending=[False, True])

    return [
        {'produto': linha.produto, 'prob': round(float(linha.prob), 2)}
        for linha in df.head(top_n).itertuples()
    ]
