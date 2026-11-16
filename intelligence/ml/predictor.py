
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd


CAMINHO_MODELO = Path(__file__).resolve().parent / "modelo_sabu.pkl"


@lru_cache(maxsize=1)
def carregar_modelo():
    """
    Carrega o modelo uma vez por processo.
    Use somente arquivos .pkl de origem confiável.
    """
    if not CAMINHO_MODELO.exists():
        raise FileNotFoundError(
            f"Arquivo do modelo não encontrado: {CAMINHO_MODELO}"
        )

    pacote = joblib.load(CAMINHO_MODELO)

    campos_obrigatorios = (
        "modelo",
        "variaveis",
        "fator_baixo",
        "fator_alto",
    )

    for campo in campos_obrigatorios:
        if campo not in pacote:
            raise ValueError(
                f"O modelo exportado não contém a chave: {campo}"
            )

    return pacote


def prever_preco(produto: dict) -> dict:
    """
    Estima o preço de mercado de um sabonete ou pacote.
    """
    pacote = carregar_modelo()

    variaveis = pacote["variaveis"]

    ausentes = [
        campo for campo in variaveis
        if campo not in produto
    ]

    if ausentes:
        raise ValueError(
            f"Campos obrigatórios ausentes: {ausentes}"
        )

    quantidade = float(produto["Unidade"])
    peso = float(produto["Peso (g)"])

    if quantidade < 1 or not quantidade.is_integer():
        raise ValueError(
            "Unidade deve ser um número inteiro maior que zero."
        )

    if peso <= 0:
        raise ValueError("Peso (g) deve ser maior que zero.")

    # Mantém exatamente as colunas exigidas pelo treinamento.
    entrada = pd.DataFrame([
        {campo: produto[campo] for campo in variaveis}
    ])

    # O modelo retorna o preço estimado por unidade.
    preco_unitario = float(
        pacote["modelo"].predict(entrada)[0]
    )

    preco_total = preco_unitario * int(quantidade)

    fator_baixo = float(pacote["fator_baixo"])
    fator_alto = float(pacote["fator_alto"])

    limite_1 = preco_total * fator_baixo
    limite_2 = preco_total * fator_alto

    return {
        "preco_unitario_estimado": round(preco_unitario, 2),
        "preco_total_estimado": round(preco_total, 2),
        "faixa_minima": round(min(limite_1, limite_2), 2),
        "faixa_maxima": round(max(limite_1, limite_2), 2),
    }
