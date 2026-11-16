from django.shortcuts import render

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import PrevisaoPrecoSerializer
from .ml.predictor import prever_preco


logger = logging.getLogger(__name__)


class PreverPrecoView(APIView):

    def post(self, request):
        serializer = PrevisaoPrecoSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        dados_modelo = serializer.para_modelo()

        try:
            resultado = prever_preco(dados_modelo)

            return Response(
                resultado,
                status=status.HTTP_200_OK
            )

        except ValueError as erro:
            return Response(
                {"erro": str(erro)},
                status=status.HTTP_400_BAD_REQUEST
            )

        except FileNotFoundError:
            logger.exception("Modelo de precificação não encontrado")

            return Response(
                {"erro": "Modelo de precificação indisponível."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
