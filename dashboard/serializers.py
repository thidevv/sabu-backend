from rest_framework import serializers


class ResumoDashboardSerializer(serializers.Serializer):
    pedidos_pendentes = serializers.IntegerField()
    lotes_materia_prima_vencidos = serializers.IntegerField()
    lotes_produto_vencidos = serializers.IntegerField()
    atualizado_em = serializers.DateTimeField()