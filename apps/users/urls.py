from django.urls import path

from .views import (
    MeView,
    MyProfileView,
    MyPublicKeyView,
    RegisterView,
    UserProfileView,
    UserListView,
    UserPublicKeyView,
    UserSearchView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("me/profile/", MyProfileView.as_view(), name="my_profile"),
    path("me/public-key/", MyPublicKeyView.as_view(), name="my_public_key"),
    path("list/", UserListView.as_view(), name="user_list"),
    path("search/", UserSearchView.as_view(), name="user_search"),
    path("<int:user_id>/profile/", UserProfileView.as_view(), name="user_profile"),
    path(
        "<int:user_id>/public-key/", UserPublicKeyView.as_view(), name="user_public_key"
    ),
]
