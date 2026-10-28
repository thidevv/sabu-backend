from core.exceptions import ErroDeDominio


class EstoqueInsuficiente(ErroDeDominio):
    status_code = 409
    codigo = 'estoque_insuficiente'

    def __init__(self, *, ids, sku, produto, saldo, solicitado):
        self.ids = ids
        self.sku = sku
        self.produto = produto
        self.saldo = saldo
        self.solicitado = solicitado
        super().__init__(
            f'Estoque insuficiente para "{produto}" (SKU {sku or '[sem SKU]'}). '
            f'Saldo atual: {saldo}, solicitado: {solicitado}.',
            ids=ids, sku=sku, produto=produto,
            saldo=saldo, solicitado=solicitado,
        )


class TipoMovimentacaoInvalido(ErroDeDominio):
    codigo = 'tipo_movimentacao_invalido'
    mensagem_padrao = 'Tipo de movimentação inválido.'


class MovimentacaoIncoerente(ErroDeDominio):
    codigo = 'movimentacao_incoerente'
    mensagem_padrao = 'Venda/estorno exigem pedido, os demais tipos não aceitam.'


class CompraFornecedorSemItem(ErroDeDominio):
    codigo = 'compra_fornecedor_sem_item'
    mensagem_padrao = 'A compra deve conter pelo menos um item.'


class ItemDesativado(ErroDeDominio):
    codigo = 'item_desativado'

    def __init__(self, *, ids, sku, produto):
        self.ids = ids
        self.sku = sku
        self.produto = produto
        super().__init__(
            f'O item "{produto}" (SKU {sku or '[sem SKU]'}) está desativado.',
            ids=ids, sku=sku, produto=produto,
        )


class FichaTecnicaInexistente(ErroDeDominio):
    codigo = 'ficha_tecnica_inexistente'
    mensagem_padrao = 'A variação não possui ficha técnica ativa.'


class LoteIndisponivel(ErroDeDominio):
    status_code = 409
    codigo = 'lote_indisponivel'
    mensagem_padrao = 'O lote não aceita esta movimentação.'