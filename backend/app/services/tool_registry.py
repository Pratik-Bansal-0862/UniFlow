from app.integrations.interfaces.tools import ToolProvider
from app.schemas.tool import ToolRequest, ToolResult


class ToolRegistryError(Exception):
    """Raised when a tool cannot be registered or resolved."""


class ToolRegistry:
    """Central registry for UniFlow integration tool providers."""

    def __init__(self) -> None:
        self._providers: dict[str, ToolProvider] = {}

    def register(self, provider: ToolProvider) -> None:
        name = provider.name.strip().lower()

        if not name:
            raise ToolRegistryError("Provider name cannot be empty.")

        if name in self._providers:
            raise ToolRegistryError(
                f"Provider '{name}' is already registered."
            )

        self._providers[name] = provider

    def get_provider(self, name: str) -> ToolProvider:
        provider = self._providers.get(name.strip().lower())

        if provider is None:
            raise ToolRegistryError(
                f"Provider '{name}' is not registered."
            )

        return provider

    def list_providers(self) -> list[str]:
        return sorted(self._providers.keys())

    async def execute(self, request: ToolRequest) -> ToolResult:
        if "." not in request.tool_name:
            raise ToolRegistryError(
                "Tool name must use the provider.tool_name format."
            )

        provider_name = request.tool_name.split(".", 1)[0]
        provider = self.get_provider(provider_name)

        return await provider.execute(request)

    async def health_check(self) -> dict[str, bool]:
        results = {}

        for name, provider in self._providers.items():
            try:
                results[name] = await provider.health_check()
            except Exception:
                results[name] = False

        return results


tool_registry = ToolRegistry()
