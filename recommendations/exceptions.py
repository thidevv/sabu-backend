from core.exceptions import ErroDeDominio


class ModeloIndisponivel(ErroDeDominio):
    status_code = 503
    codigo = 'modelo_indisponivel'
    mensagem_padrao = 'O modelo de recomendação está indisponível no momento.'
