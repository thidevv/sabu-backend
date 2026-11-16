
from pathlib import Path
import joblib

caminho = Path("intelligence/ml/modelo_sabu.pkl")

# Carregue somente arquivos que você criou ou cuja origem confia.
artefato = joblib.load(caminho)

print("Tipo do artefato:", type(artefato))

if isinstance(artefato, dict):
    print("Chaves disponíveis:", list(artefato.keys()))

    modelo = artefato.get("modelo")

    if modelo is not None:
        print("Tipo do modelo:", type(modelo))

        if hasattr(modelo, "feature_names_in_"):
            print("Variáveis:", list(modelo.feature_names_in_))

        if hasattr(modelo, "steps"):
            print("Etapas:", [nome for nome, _ in modelo.steps])
else:
    print("O arquivo não contém um dicionário.")

    if hasattr(artefato, "steps"):
        print("Etapas:", [nome for nome, _ in artefato.steps])
