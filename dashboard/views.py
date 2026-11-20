from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminUserCargo

from .serializers import ResumoDashboardSerializer
from .services import obter_resumo


class ResumoDashboardView(APIView):
    permission_classes = [IsAdminUserCargo]

    def get(self, request):
        return Response(ResumoDashboardSerializer(obter_resumo()).data)