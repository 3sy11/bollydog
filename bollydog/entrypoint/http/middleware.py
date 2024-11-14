from starlette.authentication import AuthenticationBackend, UnauthenticatedUser, AuthCredentials, SimpleUser
from starlette.requests import Request

from .config import SERVICE_PRIVATE_KEY, SERVICE_PUBLIC_KEY, SERVICE_PRIVATE_KEY_PATH, \
    SERVICE_PUBLIC_KEY_PATH
from .utils import JWT


class BaseAuthBackend(AuthenticationBackend):
    _jwt: JWT = None
    private_key: str = SERVICE_PRIVATE_KEY
    public_key: str = SERVICE_PUBLIC_KEY
    public_key_path: str = SERVICE_PRIVATE_KEY_PATH
    private_key_path: str = SERVICE_PUBLIC_KEY_PATH

    async def authenticate(self, request: Request):
        user = request.session.get('user', None)
        token = request.headers.get('x-access-token', None) or request.session.get('token', None)

        if user:
            return AuthCredentials(["authenticated"]), SimpleUser(user)
        elif not user and token:
            payload = self.jwt.decode(token)
            return AuthCredentials(["authenticated"]), SimpleUser(payload['username'])
        else:
            return AuthCredentials(["unauthenticated"]), UnauthenticatedUser()

    @property
    def jwt(self):
        if not self._jwt:
            if self.private_key is None:
                self.private_key = open(self.private_key_path, 'r').read()
            if self.public_key is None:
                self.public_key = open(self.public_key_path, 'r').read()
            self._jwt = JWT(self.private_key, self.public_key)
        return self._jwt


base_auth_backend = BaseAuthBackend()


# BaseMiddleware
class ASGIMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)
