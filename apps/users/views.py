from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.views import APIView

from .models import UserProfile
from .serialazer import (
    PublicKeySerializer,
    PublicKeyUpdateSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
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


class UserSearchView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Users"], operation_id_base="user_search")

    def get_queryset(self):
        query = self.request.query_params.get("q", "").strip()
        if not query:
            return User.objects.none()
        return (
            User.objects.filter(username__icontains=query)
            .exclude(id=self.request.user.id)
            .order_by("username")
        )


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


class MyProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    schema = AutoSchema(tags=["Users"], operation_id_base="my_profile")

    def get_serializer_class(self):
        request = getattr(self, "request", None)
        method = getattr(request, "method", None)
        if method == "PUT":
            return UserProfileUpdateSerializer
        return UserProfileSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = UserProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        if "avatar" in serializer.validated_data:
            profile.avatar = serializer.validated_data["avatar"]
        if "description" in serializer.validated_data:
            profile.description = serializer.validated_data["description"]
        if "status" in serializer.validated_data:
            profile.status = serializer.validated_data["status"]

        profile.save()
        output = UserProfileSerializer(profile, context={"request": request})
        return Response(output.data, status=status.HTTP_200_OK)


class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(tags=["Users"], operation_id_base="user_profile")

    def get_serializer_class(self):
        return UserProfileSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def get(self, request, user_id):
        profile = UserProfile.objects.filter(user_id=user_id).first()
        if profile is None:
            return Response(
                {"detail": "Profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = UserProfileSerializer(profile, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
