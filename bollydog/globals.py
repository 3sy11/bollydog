from mode.locals import Proxy
from mode.utils.locals import LocalStack

_protocol_ctx_stack = LocalStack()
_hub_ctx_stack = LocalStack()
_message_ctx_stack = LocalStack()
_session_ctx_stack = LocalStack()
_app_ctx_stack = LocalStack()

hub = Proxy(lambda: _hub_ctx_stack.top, name='message_hub')
message = Proxy(lambda: _message_ctx_stack.top, name='message')
protocol = Proxy(lambda: _protocol_ctx_stack.top, name='protocol')
session = Proxy(lambda: _session_ctx_stack.top, name='session')
app = Proxy(lambda: _app_ctx_stack.top, name='app')
