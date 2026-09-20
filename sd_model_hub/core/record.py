"""Base class for records that cross the API boundary."""

from pydantic import BaseModel, ConfigDict


class Record(BaseModel):
    """In the OpenAPI output schema, a field with a default is still always present, so mark it required.

    Without this, generated TypeScript types make every defaulted field optional (``files?:``),
    although the server always sends it.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
