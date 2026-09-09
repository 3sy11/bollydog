"""RegistryService: destination -> Command class index.

Events live in Exchange, not here.
"""
from typing import Dict, Optional, Type

from bollydog.config import DOMAIN
from bollydog.globals import services
from bollydog.models.base import BaseCommand
from bollydog.models.service import AppService


class RegistryService(AppService):
    domain = DOMAIN

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._commands: Dict[str, Type[BaseCommand]] = {}

    def all_commands(self) -> Dict[str, Type[BaseCommand]]:
        """Return full command registry."""
        return self._commands

    def add_command(self, destination: str, cls: Type[BaseCommand]):
        """Bind a Command class to its destination."""
        self._commands[destination] = cls

    def resolve(self, destination: str) -> Type[BaseCommand]:
        """Exact destination lookup. Raises KeyError if not found."""
        if destination not in self._commands: raise KeyError(f"Command '{destination}' not found")
        return self._commands[destination]

    def resolve_app(self, msg: BaseCommand) -> Optional[AppService]:
        """Resolve owning AppService from message's class-level destination."""
        dest = type(msg).destination
        if not dest: return None
        return services.get('.'.join(dest.split('.')[:2]))

    def get_app(self, service_key: str) -> Optional[AppService]:
        """Lookup AppService by service_key (domain.alias)."""
        return services.get(service_key)
