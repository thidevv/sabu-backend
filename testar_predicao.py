
from intelligence.ml.predictor import prever_preco

produto = {
    "Peso (g)": 100,
    "Unidade": 1,
    "Formato_norm": "Barra",
    "Tipo do Sabonete": "Corporal",
    "Tipo de pele": "Todos os tipos",
    "Embalagem_norm": "Não informado",
    "Base do sabonete": "Processo a frio",
    "Tipo de vendedor": "Artesanal",
}

resultado = prever_preco(produto)

print("\n=== PRECIFICAÇÃO SABÚ ===")
print(f"Preço unitário: R$ {resultado['preco_unitario_estimado']:.2f}")
print(f"Preço total: R$ {resultado['preco_total_estimado']:.2f}")
print(f"Faixa mínima: R$ {resultado['faixa_minima']:.2f}")
print(f"Faixa máxima: R$ {resultado['faixa_maxima']:.2f}")
