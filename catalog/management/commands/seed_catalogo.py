import csv
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Usuario
from catalog.models import (
    BaseProduto, Ingrediente, Produto, ProdutoIngrediente, ProdutoVariacao, TipoPeleIndicado,
)
from inventory.models import TipoMovimentacaoEstoque
from inventory.services import criar_lote_variacao, registrar_movimentacao_estoque

ARQUIVO_PADRAO = Path(__file__).resolve().parents[2] / 'seeds' / 'catalogo_sabu.csv'
COLUNAS = {'nome', 'tipo_pele_indicado', 'base', 'essencia', 'sem_fragrancia', 'vegano', 'ingredientes'}
# Opcionais, mas todas juntas: sem elas o seed cria só os produtos
COLUNAS_VARIACAO = {'produto_id', 'variacao', 'peso_gramas', 'preco', 'estoque'}
VALIDADE_DIAS = 365


def _choice(valor, choices, campo):
    # CSV usa o formato do treino ('processo a frio'); o model guarda 'PROCESSO_A_FRIO'
    convertido = valor.strip().upper().replace(' ', '_')
    if convertido not in choices.values:
        raise ValueError(f'{campo} inválido: "{valor}"')
    return convertido


def _booleano(valor, campo):
    if valor.strip() not in ('0', '1'):
        raise ValueError(f'{campo} deve ser 0 ou 1: "{valor}"')
    return valor.strip() == '1'


def _inteiro_positivo(valor, campo, *, aceita_zero=False):
    try:
        numero = int(valor.strip())
    except ValueError:
        raise ValueError(f'{campo} deve ser um número inteiro: "{valor}"')
    if numero < 0 or (numero == 0 and not aceita_zero):
        raise ValueError(f'{campo} inválido: "{valor}"')
    return numero


def _linha_para_produto(linha):
    nome = linha['nome'].strip()
    if not nome:
        raise ValueError('nome vazio')
    dados = {
        'tipo_pele_indicado': _choice(linha['tipo_pele_indicado'], TipoPeleIndicado, 'tipo_pele_indicado'),
        'base': _choice(linha['base'], BaseProduto, 'base'),
        'essencia': linha['essencia'].strip(),
        'sem_fragrancia': _booleano(linha['sem_fragrancia'], 'sem_fragrancia'),
        'vegano': _booleano(linha['vegano'], 'vegano'),
    }
    ingredientes = [i.strip().lower() for i in linha['ingredientes'].split(';') if i.strip()]
    return nome, dados, ingredientes


def _linha_para_variacao(linha):
    nome = linha['variacao'].strip()
    if not nome:
        raise ValueError('variacao vazia')
    peso = _inteiro_positivo(linha['peso_gramas'], 'peso_gramas')
    try:
        preco = Decimal(linha['preco'].strip())
    except InvalidOperation:
        raise ValueError(f'preco inválido: "{linha["preco"]}"')
    if preco < 0:
        raise ValueError(f'preco inválido: "{linha["preco"]}"')
    estoque = _inteiro_positivo(linha['estoque'], 'estoque', aceita_zero=True)
    # SKU fixo por linha do CSV: é o que impede duplicar a variação ao rodar de novo
    sku = f'SEED-{_inteiro_positivo(linha["produto_id"], "produto_id"):03d}-{peso}G'
    return {'sku': sku, 'nome': nome, 'peso_gramas': peso, 'preco': preco}, estoque


class Command(BaseCommand):
    help = (
        'Carrega o catálogo de exemplo do quiz: produtos com perfil de pele, ingredientes e, se o CSV tiver as '
        'colunas, uma variação por produto com estoque inicial. Não duplica registros nem altera os existentes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--arquivo', type=Path, default=ARQUIVO_PADRAO, help='CSV a carregar.')
        parser.add_argument(
            '--usuario',
            help='E-mail do usuário que registra a entrada de estoque. Padrão: o primeiro ADMIN ativo.',
        )
        parser.add_argument('--sem-estoque', action='store_true', help='Cria as variações sem estoque.')

    def _usuario_do_estoque(self, email, sem_estoque):
        if sem_estoque:
            return None
        if email:
            usuario = Usuario.objects.filter(email=email).first()
            if usuario is None:
                raise CommandError(f'Usuário não encontrado: {email}')
            return usuario
        usuario = Usuario.objects.filter(cargo='ADMIN', esta_ativo=True).order_by('id').first()
        if usuario is None:
            self.stdout.write(self.style.WARNING(
                'Nenhum ADMIN ativo encontrado: as variações serão criadas sem estoque. '
                'Use --usuario para escolher quem registra a entrada.'
            ))
        return usuario

    def _criar_variacao(self, produto, dados, estoque, usuario):
        ja_existe = ProdutoVariacao.objects.filter(
            Q(sku=dados['sku']) | Q(produto=produto, nome=dados['nome'])
        ).exists()
        if ja_existe:
            return False

        variacao = ProdutoVariacao.objects.create(produto=produto, **dados)
        # O estoque entra só quando a variação nasce, pelo mesmo caminho do sistema (lote + movimentação)
        if estoque and usuario:
            lote = criar_lote_variacao(
                variacao=variacao,
                data_validade=timezone.localdate() + timedelta(days=VALIDADE_DIAS),
                observacao='Estoque inicial do seed de exemplo.',
            )
            registrar_movimentacao_estoque(
                lote_id=lote.pk,
                tipo=TipoMovimentacaoEstoque.ENTRADA,
                quantidade=estoque,
                usuario=usuario,
                observacao='Estoque inicial do seed de exemplo.',
            )
        return True

    @transaction.atomic
    def handle(self, *args, **options):
        arquivo = options['arquivo']
        if not arquivo.exists():
            raise CommandError(f'Arquivo não encontrado: {arquivo}')

        criados = existentes = variacoes_criadas = 0
        with arquivo.open(encoding='utf-8-sig', newline='') as f:
            leitor = csv.DictReader(f)
            colunas = set(leitor.fieldnames or [])
            faltando = COLUNAS - colunas
            if faltando:
                raise CommandError(f'Colunas ausentes no CSV: {", ".join(sorted(faltando))}')
            com_variacao = 'variacao' in colunas
            if com_variacao and COLUNAS_VARIACAO - colunas:
                faltando = ', '.join(sorted(COLUNAS_VARIACAO - colunas))
                raise CommandError(f'Colunas de variação incompletas no CSV, faltam: {faltando}')

            usuario = self._usuario_do_estoque(options['usuario'], options['sem_estoque']) if com_variacao else None

            for numero, linha in enumerate(leitor, start=2):
                try:
                    nome, dados, ingredientes = _linha_para_produto(linha)
                    variacao = _linha_para_variacao(linha) if com_variacao else None
                except ValueError as erro:
                    raise CommandError(f'Linha {numero}: {erro}. Nada foi salvo.')

                produto, criado = Produto.objects.get_or_create(nome=nome, defaults=dados)
                for nome_ingrediente in ingredientes:
                    ingrediente, _ = Ingrediente.objects.get_or_create(nome=nome_ingrediente)
                    ProdutoIngrediente.objects.get_or_create(produto=produto, ingrediente=ingrediente)

                nova_variacao = variacao is not None and self._criar_variacao(produto, *variacao, usuario)
                variacoes_criadas += nova_variacao

                situacao = 'criado' if criado else 'já existia'
                extra = ' (+ variação)' if nova_variacao else ''
                self.stdout.write(f'  {situacao}: {produto.nome}{extra}')
                if criado:
                    criados += 1
                else:
                    existentes += 1

        self.stdout.write(self.style.SUCCESS(
            f'{criados} produto(s) criado(s), {existentes} já existia(m), {variacoes_criadas} variação(ões) criada(s).'
        ))
