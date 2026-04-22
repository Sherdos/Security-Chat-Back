from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token):
    try:
        validated_token = AccessToken(token)
        user_id = validated_token.get("user_id")
        return User.objects.filter(id=user_id).first() or AnonymousUser()
    except (TokenError, ValueError):
        return AnonymousUser()


class JwtAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token is None:
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.lower().startswith("bearer "):
                token = auth_header.split(" ", 1)[1].strip()

        scope["user"] = await get_user_from_token(token) if token else AnonymousUser()
        return await self.inner(scope, receive, send)
