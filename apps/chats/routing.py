from django.urls import path

from .views import ChatConsumer

websocket_urlpatterns = [
    path("ws/chats/<int:chat_id>/", ChatConsumer.as_asgi()),
]
