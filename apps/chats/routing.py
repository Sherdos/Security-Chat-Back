from django.urls import path

from .views import ChatConsumer, GroupConsumer, GroupTopicConsumer

websocket_urlpatterns = [
    path("ws/chats/<int:chat_id>/", ChatConsumer.as_asgi()),
    path("ws/groups/<int:group_id>/", GroupConsumer.as_asgi()),
    path(
        "ws/groups/<int:group_id>/topics/<int:topic_id>/",
        GroupTopicConsumer.as_asgi(),
    ),
]
