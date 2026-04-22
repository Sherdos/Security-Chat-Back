from django.urls import path

from .views import ChatListCreateView, ChatMessageListCreateView

urlpatterns = [
    path("", ChatListCreateView.as_view(), name="chat_list_create"),
    path(
        "<int:chat_id>/messages/",
        ChatMessageListCreateView.as_view(),
        name="chat_messages",
    ),
]
