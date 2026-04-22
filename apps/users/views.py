from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.views import APIView

from .models import UserProfile
from .serialazer import (
    PublicKeySerializer,
    PublicKeyUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    schema = AutoSchema(tags=["Users"], operation_id_base="register")


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Users"], operation_id_base="me")

    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Users"], operation_id_base="user_list")

    def get_queryset(self):
        return User.objects.exclude(id=self.request.user.id).order_by("username")


class MyPublicKeyView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Users"], operation_id_base="my_public_key")

    def get_serializer_class(self):
        request = getattr(self, "request", None)
        method = getattr(request, "method", None)
        if method == "PUT":
            return PublicKeyUpdateSerializer
        return PublicKeySerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def get(self, request):
        profile = UserProfile.objects.filter(user=request.user).first()
        if profile is None:
            return Response(
                {"detail": "Public key not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = PublicKeySerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        profile, _ = UserProfile.objects.update_or_create(
            user=request.user,
            defaults={"public_key": request.data.get("public_key", "")},
        )
        serializer = PublicKeySerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserPublicKeyView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Users"], operation_id_base="user_public_key")

    def get_serializer_class(self):
        return PublicKeySerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def get(self, request, user_id):
        profile = UserProfile.objects.filter(user_id=user_id).first()
        if profile is None:
            return Response(
                {"detail": "Public key not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = PublicKeySerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)
