"""Request-scoped context proxies."""
from typing import TYPE_CHECKING

from mode.locals import Proxy, MutableMappingProxy
from mode.utils.locals import LocalStack

if TYPE_CHECKING:
    from bollydog.bootstrap import BollydogServices
    from bollydog.models.base import BaseCommand
    from bollydog.models.protocol import Protocol
    from bollydog.models.service import AppService
    from bollydog.service.app import HubService
    from bollydog.service.registry import RegistryService
    from bollydog.service.session import Session

_protocol_ctx_stack = LocalStack()
_hub_ctx_stack = LocalStack()
_message_ctx_stack = LocalStack()
_session_ctx_stack = LocalStack()
_app_ctx_stack = LocalStack()
_services_ctx_stack = LocalStack()
_registry_ctx_stack = LocalStack()

hub: 'HubService' = Proxy(lambda: _hub_ctx_stack.top, name='hub')
message: 'BaseCommand' = Proxy(lambda: _message_ctx_stack.top, name='message')
protocol: 'Protocol' = Proxy(lambda: _protocol_ctx_stack.top, name='protocol')
session: 'Session' = Proxy(lambda: _session_ctx_stack.top, name='session')
app: 'AppService' = Proxy(lambda: _app_ctx_stack.top, name='app')
services: 'BollydogServices' = MutableMappingProxy(lambda: _services_ctx_stack.top, name='services')
registry: 'RegistryService' = Proxy(lambda: _registry_ctx_stack.top, name='registry')
