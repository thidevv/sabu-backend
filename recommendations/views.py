from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from catalog.models import Produto
from recommendations.constants import AVISO
from recommendations.schema import recomendacao_schema
from recommendations.serializers import QuizSerializer, RecomendacaoSerializer
from recommendations.services import recomendar


class QuizAnonThrottle(AnonRateThrottle):
    scope = 'quiz'


@recomendacao_schema
class RecomendacaoView(APIView):
    permission_classes = [AllowAny]
    # Rota pública: sem autenticação, para um token expirado não virar 401 e o limite ser sempre por IP
    authentication_classes = []
    throttle_classes = [QuizAnonThrottle]

    def post(self, request):
        serializer = QuizSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        produtos = recomendar(respostas=serializer.validated_data, queryset=Produto.objects.all())

        return Response(
            RecomendacaoSerializer({'produtos': produtos, 'aviso': AVISO}, context={'request': request}).data
        )
