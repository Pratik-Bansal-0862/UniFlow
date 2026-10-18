from typing import Any, Protocol

from app.schemas.tool import ToolRequest, ToolResult


class ToolProvider(Protocol):
    name: str

    async def execute(
        self,
        request: ToolRequest,
    ) -> ToolResult:
        ...

    async def health_check(self) -> bool:
        ...