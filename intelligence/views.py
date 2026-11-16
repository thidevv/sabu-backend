import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import PrevisaoPrecoSerializer
from .ml.predictor import prever_preco
from .services.precificacao import analisar_precificacao


logger = logging.getLogger(__name__)


class PreverPrecoView(APIView):

    def post(self, request):
        serializer = PrevisaoPrecoSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        dados = serializer.validated_data

        try:
            # 1. Preparar os dados para o modelo
            dados_modelo = serializer.para_modelo()

            # 2. Gerar previsão usando Machine Learning
            previsao = prever_preco(dados_modelo)

            resposta = {
                "previsao": previsao
            }

            # 3. Executar análise financeira,
            # quando o custo for informado
            if "custo_unitario" in dados:

                analise = analisar_precificacao(
                    previsao=previsao,
                    custo_unitario=dados["custo_unitario"],
                    quantidade=dados["unidade"],
                    margem_desejada=dados.get(
                        "margem_desejada"
                    )
                )

                resposta["analise_financeira"] = analise

            return Response(
                resposta,
                status=status.HTTP_200_OK
            )

        except ValueError as erro:
            return Response(
                {"erro": str(erro)},
                status=status.HTTP_400_BAD_REQUEST
            )

        except FileNotFoundError:
            logger.exception("Modelo ML não encontrado")

            return Response(
                {
                    "erro": "Modelo de precificação indisponível."
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
