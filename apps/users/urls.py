from django.urls import path

from .views import (
    MeView,
    MyPublicKeyView,
    RegisterView,
    UserListView,
    UserPublicKeyView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("me/public-key/", MyPublicKeyView.as_view(), name="my_public_key"),
    path("list/", UserListView.as_view(), name="user_list"),
    path(
        "<int:user_id>/public-key/", UserPublicKeyView.as_view(), name="user_public_key"
    ),
]
