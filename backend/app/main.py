
from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.integrations.providers.google_workspace import (
    register_google_workspace_providers,
)
from app.services.tool_registry import tool_registry


# Register Google Workspace tool providers.
# Avoid duplicate registration if the module is initialized more than once.
registered_providers = set(tool_registry.list_providers())

if "gmail" not in registered_providers:
    from app.integrations.providers.google_workspace import GmailToolProvider

    tool_registry.register(GmailToolProvider())

if "calendar" not in registered_providers:
    from app.integrations.providers.google_workspace import (
        GoogleCalendarToolProvider,
    )

    tool_registry.register(GoogleCalendarToolProvider())


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

# Make the registry accessible to application services and routes.
app.state.tool_registry = tool_registry

app.include_router(
    api_router,
    prefix=settings.api_v1_prefix,
)


@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "status": "running",
        "docs": "/docs",
    }
