from decimal import Decimal

from django.db import models

from accounts.models import Usuario
from catalog.models import ProdutoVariacao
from orders.models import Pedido

NUMERO_LOTE_NAO_INFORMADO = 'Não informado'


class StatusCompraFornecedor(models.TextChoices):
    CONCLUIDO = 'CONCLUIDO', 'Concluido'
    DEVOLVIDO = 'DEVOLVIDO', 'Devolvido ao Fornecedor'

TRANSICOES_PERMITIDAS_COMPRA_FORNECEDOR = {
    StatusCompraFornecedor.CONCLUIDO: {StatusCompraFornecedor.DEVOLVIDO},
    StatusCompraFornecedor.DEVOLVIDO: set(),
}

CATEGORIA_MATERIA_PRIMA_CHOICES = (
        ('OLEOS_E_GORDURAS', 'Óleos e gorduras'),
        ('AGENTES_SAPONIFICANTES', 'Agentes saponificantes'),
        ('LIQUIDOS_DILUICAO', 'Líquidos de diluição'),
        ('AROMAS_E_FRAGANCIAS', 'Aromas e fragâncias'),
        ('CORANTES_E_PIGMENTOS', 'Corantes e pigmentos'),
        ('ADITIVOS_E_ATIVOS', 'Aditivos e ativos'),
        ('EMBALAGENS_E_ROTULOS', 'Embalagens e rótulos'),
        ('MATERIAL_DE_APOIO', 'Material de apoio'),
    )

UNIDADE_CHOICES = (
        ('KG', 'Quilograma'),
        ('G', 'Grama'),
        ('MG', 'Miligrama'),
        ('L', 'Litro'),
        ('ML', 'Mililitro'),
        ('UN', 'Unidade'),
    )

class MateriaPrima(models.Model):
    id = models.BigAutoField(primary_key=True)
    sku = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(max_length=50, choices=CATEGORIA_MATERIA_PRIMA_CHOICES)
    unidade_medida = models.CharField(max_length=10, choices=UNIDADE_CHOICES)
    quantidade_estoque = models.DecimalField(default=0, editable=False, max_digits=10, decimal_places=3)
    custo_unitario_referencia = models.DecimalField(max_digits=10, decimal_places=4)
    apagada_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'materia_prima'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantidade_estoque__gte=0),
                name='ck_materia_prima_estoque_nao_negativo',
            ),
            models.CheckConstraint(
                condition=models.Q(custo_unitario_referencia__gte=0),
                name='ck_materia_prima_custo_nao_negativo',
            )
        ]

    def __str__(self):
        return self.nome


class Fornecedor(models.Model):
    id = models.BigAutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    plataforma = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    prazo_medio_entrega_em_dias = models.PositiveIntegerField()
    forma_pagamento = models.CharField(max_length=50, blank=True)
    link = models.URLField(blank=True)
    favorito = models.BooleanField(default=False)
    apagado_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'fornecedor'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(prazo_medio_entrega_em_dias__gt=0),
                name='ck_fornecedor_prazo_medio_entrega_positivo',
            )
        ]


class FornecedorCategoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, related_name='categorias')
    categoria = models.CharField(max_length=50, choices=CATEGORIA_MATERIA_PRIMA_CHOICES)

    class Meta:
        db_table = 'fornecedor_categoria'
        constraints = [
            models.UniqueConstraint(
                fields=['fornecedor', 'categoria'],
                name='uq_fornecedor_categoria',
            ),
        ]


class CompraFornecedor(models.Model):
    id = models.BigAutoField(primary_key=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT, related_name='compra_fornecedor')
    status = models.CharField(max_length=30, choices=StatusCompraFornecedor.choices, default='CONCLUIDO')
    valor_total = models.DecimalField(max_digits=10, decimal_places=4)
    observacao = models.TextField(blank=True)
    compra_realizada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)


class CompraFornecedorItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    compra_fornecedor = models.ForeignKey('CompraFornecedor', on_delete=models.PROTECT, related_name='fornecedor_itens')
    materia_prima = models.ForeignKey(MateriaPrima, on_delete=models.PROTECT, related_name='fornecedor_itens')
    quantidade_item = models.DecimalField(max_digits=10, decimal_places=3)
    custo_unitario_momento_compra = models.DecimalField(max_digits=10, decimal_places=4)

    class Meta:
        db_table = 'compra_fornecedor_item'
        constraints = [
            models.UniqueConstraint(
                fields=['materia_prima', 'compra_fornecedor'],
                name='uq_materia_prima_fornecedor',
            ),
            models.CheckConstraint(
                condition=models.Q(quantidade_item__gt=0),
                name='ck_fornecedor_item_quantidade_positiva',
            ),
            models.CheckConstraint(
                condition=models.Q(quantidade_item__lte=999),
                name='ck_fornecedor_item_quantidade_limite_maximo',
            )
        ]


class StatusLote(models.TextChoices):
    ATIVO = 'ATIVO', 'Ativo'
    ESGOTADO = 'ESGOTADO', 'Esgotado'
    VENCIDO = 'VENCIDO', 'Vencido'

class LoteMateriaPrima(models.Model):
    id = models.BigAutoField(primary_key=True)
    materia_prima = models.ForeignKey(MateriaPrima, on_delete=models.PROTECT, related_name='lotes')
    compra_fornecedor_item = models.ForeignKey(CompraFornecedorItem, on_delete=models.PROTECT, null=True, blank=True, related_name='lote_materiais',)
    numero_lote_fabricante = models.CharField(max_length=50, blank=True, default=NUMERO_LOTE_NAO_INFORMADO)
    quantidade_inicial = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    quantidade_atual = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    status = models.CharField(max_length=20, choices=StatusLote.choices, default=StatusLote.ATIVO)
    data_validade = models.DateField(null=True, blank=True)
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lote_materia_prima'
        constraints = [
            models.UniqueConstraint(
                fields=['compra_fornecedor_item'],
                name='uq_lote_materia_prima_compra_fornecedor_item',
            ),
            models.CheckConstraint(
                condition=models.Q(quantidade_atual__gte=0),
                name='ck_lote_materia_prima_quantidade_nao_negativa',
            ),
            models.CheckConstraint(
                condition=models.Q(quantidade_inicial__gte=models.F('quantidade_atual')),
                name='ck_lote_materia_prima_atual_lte_inicial',
            ),
        ]
        indexes = [
            models.Index(fields=['materia_prima', 'status', 'data_validade'], name='ix_lote_mp_fefo'),
        ]

    def save(self, *args, **kwargs):
        self.numero_lote_fabricante = (self.numero_lote_fabricante or '').strip() or NUMERO_LOTE_NAO_INFORMADO
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Lote {self.numero_lote_fabricante} - {self.materia_prima}"


class LoteProdutoVariacao(models.Model):
    id = models.BigAutoField(primary_key=True)
    variacao = models.ForeignKey(ProdutoVariacao, on_delete=models.PROTECT, related_name='lote_variacoes')
    numero_lote = models.CharField(max_length=50, unique=True)
    data_fabricacao = models.DateField()
    data_validade = models.DateField()
    quantidade_inicial = models.PositiveIntegerField(default=0)
    quantidade_atual = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=StatusLote.choices, default=StatusLote.ATIVO)
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lote_produto_variacao'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantidade_atual__gte=0),
                name='ck_lote_produto_variacao_quantidade_nao_negativa',
            ),
            models.CheckConstraint(
                condition=models.Q(quantidade_inicial__gte=models.F('quantidade_atual')),
                name='ck_lote_produto_variacao_atual_lte_inicial',
            )
        ]
        indexes = [
            models.Index(fields=['variacao', 'status', 'data_validade'], name='ix_lote_variacao_fefo'),
        ]

    def __str__(self):
        return f"Lote {self.numero_lote} - {self.variacao}"


class VinculoFornecedor(models.Model):
    id = models.BigAutoField(primary_key=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT, related_name='vinculos')
    materia_prima = models.ForeignKey(MateriaPrima, on_delete=models.PROTECT, related_name='vinculos')
    custo_unitario_fornecedor = models.DecimalField(max_digits=10, decimal_places=4)
    sku_materia_prima_fornecedor = models.CharField(max_length=50, blank=True)
    apagado_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'vinculo_fornecedor'

        constraints = [
            models.UniqueConstraint(
                fields=['fornecedor', 'materia_prima'],
                name='uq_vinculo_fornecedor_materia_prima',
            ),
            models.CheckConstraint(
                condition=models.Q(custo_unitario_fornecedor__gte=0),
                name='ck_vinculo_fornecedor_custo_nao_negativo',
            )
        ]


class FichaTecnica(models.Model):
    id = models.BigAutoField(primary_key=True)
    variacao = models.ForeignKey(ProdutoVariacao, on_delete=models.PROTECT, related_name='fichas_tecnicas')
    materia_prima = models.ForeignKey(MateriaPrima, on_delete=models.PROTECT)
    quantidade_necessaria = models.DecimalField(max_digits=10, decimal_places=3)
    apagada_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'ficha_tecnica'
        constraints = [
            models.UniqueConstraint(
                fields=['variacao', 'materia_prima'],
                name='uq_ficha_tecnica_variacao_materia_prima',
            ),
            models.CheckConstraint(
                condition=models.Q(quantidade_necessaria__gte=Decimal('0.001')),
                name='ck_ficha_tecnica_quantidade_necessaria_positiva',
            )
        ]


class TipoMovimentacaoEstoque(models.TextChoices):
    ENTRADA = 'ENTRADA', 'Entrada'
    SAIDA_VENDA = 'SAIDA_VENDA', 'Saída por Venda'
    AJUSTE_OU_PERDA = 'AJUSTE_OU_PERDA', 'Ajuste / Perda'
    ESTORNO_VENDA = 'ESTORNO_VENDA', 'Estorno de Venda'

TIPOS_COM_PEDIDO = (TipoMovimentacaoEstoque.SAIDA_VENDA, TipoMovimentacaoEstoque.ESTORNO_VENDA)
TIPOS_QUE_AUMENTAM = {TipoMovimentacaoEstoque.ENTRADA, TipoMovimentacaoEstoque.ESTORNO_VENDA}
TIPOS_QUE_DIMINUEM = {TipoMovimentacaoEstoque.SAIDA_VENDA, TipoMovimentacaoEstoque.AJUSTE_OU_PERDA}

class MovimentacaoEstoque(models.Model):
    id = models.BigAutoField(primary_key=True)
    lote_produto_variacao = models.ForeignKey(LoteProdutoVariacao, on_delete=models.PROTECT, related_name='movimentacoes_estoque',)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='movimentacoes_estoque')
    pedido = models.ForeignKey(Pedido, on_delete=models.PROTECT, null=True, related_name='movimentacoes_estoque')
    tipo = models.CharField(max_length=20, choices=TipoMovimentacaoEstoque.choices)
    quantidade_movimentada = models.PositiveIntegerField()
    observacao = models.TextField(blank=True)
    movimentado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'movimentacao_estoque'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantidade_movimentada__gt=0),
                name='ck_movimentacao_estoque_quantidade_movimentada_positiva',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(tipo__in=TIPOS_COM_PEDIDO, pedido__isnull=False)
                    | (
                            ~models.Q(tipo__in=TIPOS_COM_PEDIDO)
                            & models.Q(pedido__isnull=True)
                    )
                ),
                name='ck_movimentacao_estoque_pedido_conforme_tipo',
            ),
        ]

    def __str__(self):
        return f"{self.tipo} - Lote ID: {self.lote_produto_variacao_id} ({self.quantidade_movimentada})"


class TipoMovimentacaoMaterial(models.TextChoices):
    ENTRADA = 'ENTRADA', 'Entrada'
    SAIDA_PRODUCAO = 'SAIDA_PRODUCAO' ,'Saída por Produção'
    AJUSTE_OU_PERDA = 'AJUSTE_OU_PERDA', 'Ajuste / Perda'
    SAIDA_DEVOLUCAO = 'SAIDA_DEVOLUCAO', 'Saída por Devolução'

TIPOS_MATERIAL_AUTOMATICOS_COM_FORNECEDOR = {TipoMovimentacaoMaterial.SAIDA_DEVOLUCAO}

TIPOS_MATERIAL_QUE_AUMENTAM = {TipoMovimentacaoMaterial.ENTRADA}
TIPOS_MATERIAL_QUE_DIMINUEM = {TipoMovimentacaoMaterial.SAIDA_PRODUCAO, TipoMovimentacaoMaterial.SAIDA_DEVOLUCAO,
                               TipoMovimentacaoMaterial.AJUSTE_OU_PERDA}

class MovimentacaoMaterial(models.Model):
    id = models.BigAutoField(primary_key=True)
    lote_materia_prima = models.ForeignKey(LoteMateriaPrima, on_delete=models.PROTECT, related_name='movimentacoes_material',)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='movimentacoes_material')
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT, null=True, related_name='movimentacoes_material')
    tipo = models.CharField(max_length=20, choices=TipoMovimentacaoMaterial.choices)
    quantidade_movimentada = models.DecimalField(max_digits=10, decimal_places=3)
    observacao = models.TextField(blank=True)
    movimentado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'movimentacao_material'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantidade_movimentada__gt=0),
                name='ck_movimentacao_material_quantidade_movimentada_positiva',
            ),
        ]

    def __str__(self):
        return f"{self.tipo} - Lote ID: {self.lote_materia_prima_id} ({self.quantidade_movimentada})"