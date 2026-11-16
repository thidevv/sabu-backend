from django.contrib import admin

from .models import (
    Categoria, Ingrediente, Produto, ProdutoCategoria, ProdutoIngrediente,
    ProdutoTipoPele, TipoPele,
)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['id', 'nome']
    search_fields = ['nome']


@admin.register(TipoPele)
class TipoPeleAdmin(admin.ModelAdmin):
    list_display = ['id', 'nome']
    search_fields = ['nome']


@admin.register(Ingrediente)
class IngredienteAdmin(admin.ModelAdmin):
    list_display = ['id', 'nome']
    search_fields = ['nome']


class ProdutoCategoriaInline(admin.TabularInline):
    model = ProdutoCategoria
    extra = 0
    autocomplete_fields = ['categoria']


class ProdutoTipoPeleInline(admin.TabularInline):
    model = ProdutoTipoPele
    extra = 0
    autocomplete_fields = ['tipo_pele']


class ProdutoIngredienteInline(admin.TabularInline):
    model = ProdutoIngrediente
    extra = 0
    autocomplete_fields = ['ingrediente']


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ['id', 'nome', 'tipo_pele_indicado', 'base', 'sem_fragrancia', 'vegano', 'esta_ativo']
    list_filter = ['esta_ativo', 'tipo_pele_indicado', 'base', 'sem_fragrancia', 'vegano']
    search_fields = ['nome']
    fieldsets = [
        (None, {'fields': ['nome', 'descricao', 'imagem', 'esta_ativo']}),
        ('Perfil de pele', {'fields': ['tipo_pele_indicado', 'base', 'essencia', 'sem_fragrancia', 'vegano']}),
    ]
    inlines = [ProdutoIngredienteInline, ProdutoTipoPeleInline, ProdutoCategoriaInline]
