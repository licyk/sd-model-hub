"""Add the event models to the OpenAPI schema, so the web UI types socket payloads from it."""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from sd_model_hub.core.events.models import EventBase


def install_openapi(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes, description=app.description)
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        events: dict[str, dict[str, str]] = {}
        for event_cls in EventBase.get_events():
            model_schema = event_cls.model_json_schema(ref_template="#/components/schemas/{model}")
            for name, sub in model_schema.pop("$defs", {}).items():
                components.setdefault(name, sub)
            components[event_cls.__name__] = model_schema
            events[event_cls.__event_name__] = {"$ref": f"#/components/schemas/{event_cls.__name__}"}
        components["ServerEvents"] = {"type": "object", "properties": events, "required": sorted(events)}
        schema["components"]["schemas"] = dict(sorted(components.items()))
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
