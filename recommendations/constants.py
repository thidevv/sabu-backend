from pathlib import Path

# Opções do quiz: os valores são os mesmos usados no treino do modelo
OPCOES_TIPO_PELE = (
    ('seca', 'Seca'),
    ('oleosa', 'Oleosa'),
    ('mista', 'Mista'),
    ('normal', 'Normal'),
    ('nao_sei', 'Não sei'),
)

OPCOES_SENSIBILIDADE = (
    ('sim', 'Sim'),
    ('nao', 'Não'),
    ('as_vezes', 'Às vezes'),
)

OPCOES_RESSECAMENTO = (
    ('sim', 'Sim'),
    ('nao', 'Não'),
    ('as_vezes', 'Às vezes'),
)

OPCOES_PREFERENCIA = (
    ('hidratacao', 'Hidratação'),
    ('limpeza_suave', 'Limpeza suave'),
    ('cuidados_gerais', 'Cuidados gerais'),
    ('fragrancia_suave', 'Fragrância suave'),
)

OPCOES_SIM_NAO = (
    (0, 'Não'),
    (1, 'Sim'),
)

SEM_ALERGIA = 'nenhuma'

# Recomendação
PROB_MINIMA = 0.5
TOP_N_PADRAO = 3

# Modelo (árvore de decisão treinada em ML_Sabu_Perfil_v2.ipynb)
CAMINHO_MODELO = Path(__file__).resolve().parent / 'ml' / 'modelo_sabu_perfil.pkl'
VARIAVEIS_MODELO = [
    'tipo_pele', 'sensibilidade', 'ressecamento', 'preferencia', 'tipo_pele_indicado', 'base', 'pele_bate',
    'evita_fragrancia', 'sem_fragrancia', 'vegano',
]

AVISO = 'Não realiza diagnóstico dermatológico nem recomenda tratamento.'
