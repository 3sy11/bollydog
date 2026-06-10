from mode.locals import Proxy
from mode.utils.locals import LocalStack

_protocol_ctx_stack = LocalStack()
_hub_ctx_stack = LocalStack()
_message_ctx_stack = LocalStack()
_session_ctx_stack = LocalStack()
_app_ctx_stack = LocalStack()
_apps_ctx_stack = LocalStack()


class DictProxy:
    """Proxy for a dict on LocalStack, forwarding dict operations (__getitem__, __setitem__, __contains__, etc.)."""
    __slots__ = ('_stack', '_name')
    def __init__(self, stack, name=None):
        object.__setattr__(self, '_stack', stack)
        object.__setattr__(self, '_name', name)
    def _get_current_object(self):
        return object.__getattribute__(self, '_stack').top
    def __getitem__(self, key): return self._get_current_object()[key]
    def __setitem__(self, key, value): self._get_current_object()[key] = value
    def __delitem__(self, key): del self._get_current_object()[key]
    def __contains__(self, key): return key in self._get_current_object()
    def __iter__(self): return iter(self._get_current_object())
    def __len__(self): return len(self._get_current_object())
    def __bool__(self): obj = self._get_current_object(); return obj is not None and bool(obj)
    def __repr__(self): return f'<DictProxy {self._name}: {self._get_current_object()!r}>'
    def __getattr__(self, name): return getattr(self._get_current_object(), name)


hub = Proxy(lambda: _hub_ctx_stack.top, name='message_hub')
message = Proxy(lambda: _message_ctx_stack.top, name='message')
protocol = Proxy(lambda: _protocol_ctx_stack.top, name='protocol')
session = Proxy(lambda: _session_ctx_stack.top, name='session')
app = Proxy(lambda: _app_ctx_stack.top, name='app')
apps = DictProxy(_apps_ctx_stack, name='apps')
