from django.db import models
from core.utils import CaminhoImagem

class Categoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    nome = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'categoria'

    def __str__(self):
        return self.nome

class TipoPele(models.Model):
    id = models.BigAutoField(primary_key=True)
    nome = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'tipo_pele'

    def __str__(self):
        return self.nome

class Ingrediente(models.Model):
    id = models.BigAutoField(primary_key=True)
    nome = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'ingrediente'

    def __str__(self):
        return self.nome

    # Nome sempre minúsculo e sem espaços nas pontas: a regra de alergia compara por item exato
    def clean(self):
        self.nome = (self.nome or '').strip().lower()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class TipoPeleIndicado(models.TextChoices):
    SECA = 'SECA', 'Seca'
    OLEOSA = 'OLEOSA', 'Oleosa'
    MISTA = 'MISTA', 'Mista'
    NORMAL = 'NORMAL', 'Normal'
    TODOS = 'TODOS', 'Todos'

class BaseProduto(models.TextChoices):
    PROCESSO_A_FRIO = 'PROCESSO_A_FRIO', 'Processo a frio'
    GLICERINA = 'GLICERINA', 'Glicerina'
    BASE_VEGETAL = 'BASE_VEGETAL', 'Base vegetal'

class Produto(models.Model):
    id = models.BigAutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    imagem = models.ImageField(upload_to=CaminhoImagem('produtos'), null=True, blank=True)
    esta_ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    tipo_pele = models.ManyToManyField(TipoPele, through='ProdutoTipoPele', related_name='produtos')
    categorias = models.ManyToManyField(Categoria, through='ProdutoCategoria', related_name='produtos')
    tipo_pele_indicado = models.CharField(
        max_length=20, choices=TipoPeleIndicado.choices, default=TipoPeleIndicado.TODOS)
    base = models.CharField(max_length=30, choices=BaseProduto.choices, blank=True)
    essencia = models.CharField(max_length=50, blank=True)
    sem_fragrancia = models.BooleanField(default=False)
    vegano = models.BooleanField(default=False)
    ingredientes = models.ManyToManyField(
        Ingrediente, through='ProdutoIngrediente', related_name='produtos', blank=True)

    class Meta:
        db_table = 'produto'

    def __str__(self):
        return self.nome


class ProdutoCategoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)

    class Meta:
        db_table = 'produto_categoria'
        constraints = [
            models.UniqueConstraint(
                fields=['produto', 'categoria'],
                name='uq_produto_categoria',
            ),
        ]

class ProdutoTipoPele(models.Model):
    id = models.BigAutoField(primary_key=True)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    tipo_pele = models.ForeignKey(TipoPele, on_delete=models.CASCADE)

    class Meta:
        db_table = 'produto_tipo_pele'
        constraints = [
            models.UniqueConstraint(
                fields=['produto', 'tipo_pele'],
                name='uq_produto_tipo_pele',
            )
        ]

class ProdutoIngrediente(models.Model):
    id = models.BigAutoField(primary_key=True)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    # PROTECT: apagar um ingrediente em uso tiraria a informação de alergia dos produtos
    ingrediente = models.ForeignKey(Ingrediente, on_delete=models.PROTECT)

    class Meta:
        db_table = 'produto_ingrediente'
        constraints = [
            models.UniqueConstraint(
                fields=['produto', 'ingrediente'],
                name='uq_produto_ingrediente',
            )
        ]

class ProdutoVariacao(models.Model):
    id = models.BigAutoField(primary_key=True)
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='variacoes')
    sku = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=50)
    imagem = models.ImageField(upload_to=CaminhoImagem('variacoes'), null=True, blank=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    preco_promo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    inicio_promo = models.DateTimeField(blank=True, null=True)
    fim_promo = models.DateTimeField(blank=True, null=True)
    peso_gramas = models.PositiveIntegerField(blank=True, null=True)
    quantidade_estoque = models.PositiveIntegerField(default=0, editable=False)
    apagado_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'produto_variacao'
        constraints = [
            models.UniqueConstraint(
                fields=['produto', 'nome'],
                name='uq_produto_nome',
            ),
            models.CheckConstraint(
                condition=models.Q(peso_gramas__isnull=True) | models.Q(peso_gramas__gt=0),
                name='ck_variacao_peso_positivo',
            ),
            models.CheckConstraint(
                name='ck_variacao_preco_nao_negativo',
                condition=models.Q(preco__gte=0)
            ),
            models.CheckConstraint(
                name='ck_variacao_preco_promo_nulo_ou_nao_negativo',
                condition=models.Q(preco_promo__isnull=True) |
                models.Q(preco_promo__gte=0)
            ),
            models.CheckConstraint(
                name='ck_variacao_preco_promo_menor_que_preco',
                condition=(
                        models.Q(preco_promo__isnull=True)
                        | models.Q(preco_promo__lt=models.F('preco'))
                ),
            ),
            models.CheckConstraint(
                name='ck_variacao_promo_exige_periodo',
                condition=(
                        models.Q(preco_promo__isnull=True)
                        | (
                                models.Q(inicio_promo__isnull=False)
                                & models.Q(fim_promo__isnull=False)
                        )
                ),
            ),
            models.CheckConstraint(
                name='ck_variacao_inicio_promo_antes_do_fim',
                condition=(
                        models.Q(inicio_promo__isnull=True)
                        | models.Q(fim_promo__isnull=True)
                        | models.Q(inicio_promo__lt=models.F('fim_promo'))
                ),
            )
        ]

    def __str__(self):
        return f"{self.produto.nome} - {self.nome}"

    @property
    def preco_final(self):
        return self.preco_promo if self.preco_promo is not None else self.preco
