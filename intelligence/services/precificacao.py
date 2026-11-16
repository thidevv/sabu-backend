
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING


CENTAVOS = Decimal("0.01")


def dinheiro(valor):
    """Arredonda valores monetários para duas casas decimais."""
    return valor.quantize(
        CENTAVOS,
        rounding=ROUND_HALF_UP
    )


def analisar_precificacao(
    previsao: dict,
    custo_unitario,
    quantidade: int,
    margem_desejada=None
) -> dict:
    """
    Calcula a rentabilidade do sabonete com base
    no preço estimado pelo modelo de Machine Learning.
    """

    if (
        not isinstance(quantidade, int)
        or isinstance(quantidade, bool)
        or quantidade <= 0
    ):
        raise ValueError(
            "A quantidade deve ser um inteiro positivo."
        )

    custo = Decimal(str(custo_unitario))
    preco = Decimal(str(
        previsao["preco_unitario_estimado"]
    ))

    if not custo.is_finite() or custo < 0:
        raise ValueError("Custo unitário inválido.")

    if not preco.is_finite() or preco <= 0:
        raise ValueError("Preço estimado inválido.")

    # Cálculo dos custos e da receita
    custo_total = custo * quantidade
    receita_total = preco * quantidade

    # Cálculo do lucro
    lucro_unitario = preco - custo
    lucro_total = receita_total - custo_total

    # Margem de lucro sobre a receita
    margem_percentual = (
        lucro_total / receita_total
    ) * Decimal("100")

    resultado = {
        "custo_unitario": float(dinheiro(custo)),
        "custo_total": float(dinheiro(custo_total)),
        "receita_estimada": float(dinheiro(receita_total)),
        "lucro_unitario": float(dinheiro(lucro_unitario)),
        "lucro_total": float(dinheiro(lucro_total)),
        "margem_lucro_percentual": float(
            dinheiro(margem_percentual)
        ),
        "lucro_positivo": lucro_total > 0,
    }

    # Preço mínimo para alcançar a margem desejada
    if margem_desejada is not None:
        margem = Decimal(str(margem_desejada))

        if not margem.is_finite() or not 0 <= margem < 100:
            raise ValueError(
                "A margem desejada deve ser de 0 até menos de 100."
            )

        preco_minimo = custo / (
            Decimal("1") - margem / Decimal("100")
        )

        preco_minimo = preco_minimo.quantize(
            CENTAVOS,
            rounding=ROUND_CEILING
        )

        resultado["margem_desejada_percentual"] = float(
            margem
        )

        resultado["preco_minimo_margem_desejada"] = float(
            preco_minimo
        )

    return resultado
