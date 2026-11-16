"""What a client sees when they sign in. Every query starts from the client linked to the signed-in account, so there is no id in
any URL a client could change to reach somebody else's data."""
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Client


class PortalClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "company_name", "contact_person", "phone", "email", "address"]
        read_only_fields = fields


def my_client(request):
    return get_object_or_404(Client, portal_user=request.user)


class PortalMeView(APIView):
    required_capabilities = ["portal.access"]
    denied_message = "This area is for clients."

    def get(self, request):
        client = my_client(request)
        return Response({"client": PortalClientSerializer(client).data})
