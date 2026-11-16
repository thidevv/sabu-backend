from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from accounts.models import Usuario
from catalog.models import ProdutoVariacao

class StatusPedido(models.TextChoices):
    PENDENTE = 'PENDENTE', 'Pendente'
    CONCLUIDO = 'CONCLUIDO', 'Concluido'
    CANCELADO = 'CANCELADO', 'Cancelado'
    ESTORNADO_COM_DEVOLUCAO = 'ESTORNADO_COM_DEVOLUCAO', 'Estornado com Devolução'
    ESTORNADO_SEM_DEVOLUCAO = 'ESTORNADO_SEM_DEVOLUCAO', 'Estornado sem Devolução'

TRANSICOES_PERMITIDAS_PEDIDO = {
    StatusPedido.PENDENTE: {StatusPedido.CONCLUIDO, StatusPedido.CANCELADO},
    StatusPedido.CONCLUIDO: {StatusPedido.ESTORNADO_COM_DEVOLUCAO, StatusPedido.ESTORNADO_SEM_DEVOLUCAO},
    StatusPedido.CANCELADO: set(),
    StatusPedido.ESTORNADO_COM_DEVOLUCAO: set(),
    StatusPedido.ESTORNADO_SEM_DEVOLUCAO: set(),
}


class Cliente(models.Model):
    id = models.BigAutoField(primary_key=True)
    nome = models.CharField(max_length=100, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    cpf_cnpj = models.CharField(max_length=20, unique=True, blank=True, null=True)
    ultimo_pedido_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cliente'

    def __str__(self):
        return self.nome


SIGLAS_ESTADOS_PERMITIDAS = (
    ('AC', 'Acre'),
    ('AL', 'Alagoas'),
    ('AP', 'Amapá'),
    ('AM', 'Amazonas'),
    ('BA', 'Bahia'),
    ('CE', 'Ceará'),
    ('DF', 'Distrito Federal'),
    ('ES', 'Espírito Santo'),
    ('GO', 'Goiás'),
    ('MA', 'Maranhão'),
    ('MT', 'Mato Grosso'),
    ('MS', 'Mato Grosso do Sul'),
    ('MG', 'Minas Gerais'),
    ('PA', 'Pará'),
    ('PB', 'Paraíba'),
    ('PR', 'Paraná'),
    ('PE', 'Pernambuco'),
    ('PI', 'Piauí'),
    ('RJ', 'Rio de Janeiro'),
    ('RN', 'Rio Grande do Norte'),
    ('RS', 'Rio Grande do Sul'),
    ('RO', 'Rondônia'),
    ('RR', 'Roraima'),
    ('SC', 'Santa Catarina'),
    ('SP', 'São Paulo'),
    ('SE', 'Sergipe'),
    ('TO', 'Tocantins'),
)


class TipoDesconto(models.TextChoices):
    FIXO = 'FIXO', 'Valor fixo (R$)'
    PERCENTUAL = 'PERCENTUAL', 'Percentual (%)'


class Pedido(models.Model):
    id = models.BigAutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos')
    cep = models.CharField(max_length=10, blank=True)
    logradouro = models.CharField(max_length=150, blank=True)
    numero_residencia = models.CharField(max_length=20, blank=True)
    complemento = models.CharField(max_length=50, blank=True)
    bairro = models.CharField(max_length=50, blank=True)
    cidade = models.CharField(max_length=50, blank=True)
    sigla_estado = models.CharField(max_length=2, blank=True, choices=SIGLAS_ESTADOS_PERMITIDAS)
    status = models.CharField(max_length=30, choices=StatusPedido.choices, default='PENDENTE')

    valor_subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tipo_desconto = models.CharField(max_length=10, choices=TipoDesconto.choices, blank=True, default='')
    desconto = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
    )
    valor_desconto = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    valor_total = models.DecimalField(max_digits=10,
                                      decimal_places=2)
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pedido'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=StatusPedido.values),
                name='ck_pedido_status_valido',
            ),
            models.CheckConstraint(
                condition=models.Q(valor_total__gte=0),
                name='ck_pedido_valor_total_nao_negativo',
            ),
            models.CheckConstraint(
                condition=models.Q(tipo_desconto__in=[*TipoDesconto.values, '']),
                name='ck_pedido_tipo_desconto_valido',
            ),
            models.CheckConstraint(
                condition=models.Q(desconto__gte=0) & models.Q(valor_desconto__gte=0),
                name='ck_pedido_desconto_nao_negativo',
            ),
            models.CheckConstraint(
                condition=~models.Q(tipo_desconto=TipoDesconto.PERCENTUAL) | models.Q(desconto__lte=100),
                name='ck_pedido_desconto_percentual_max_100',
            ),
            models.CheckConstraint(
                condition=models.Q(valor_desconto__lte=models.F('valor_subtotal')),
                name='ck_pedido_valor_desconto_lte_subtotal',
            ),
        ]

    def __str__(self):
        return f"Pedido #{self.id} - Status: {self.get_status_display()}"


class PedidoItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    pedido = models.ForeignKey(Pedido, on_delete=models.PROTECT, related_name='pedido_itens')
    variacao = models.ForeignKey(ProdutoVariacao, on_delete=models.PROTECT, related_name='pedido_itens')
    quantidade_item = models.PositiveIntegerField()
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    valor_desconto = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        db_table = 'pedido_item'
        constraints = [
            models.UniqueConstraint(
                fields=['pedido', 'variacao'],
                name='uq_pedido_variacao',
            ),
            models.CheckConstraint(
                condition=models.Q(quantidade_item__gt=0),
                name='ck_pedido_item_quantidade_positiva',
            ),
            models.CheckConstraint(
                condition=models.Q(quantidade_item__lte=999),
                name='ck_pedido_item_quantidade_limite_maximo',
            ),
            models.CheckConstraint(
                condition=models.Q(valor_desconto__gte=0),
                name='ck_pedido_item_desconto_nao_negativo',
            ),
        ]

    @property
    def valor_final(self):
        return self.quantidade_item * self.valor_unitario - self.valor_desconto