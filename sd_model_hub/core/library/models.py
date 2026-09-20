"""Library records returned by the service."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from sd_model_hub.core.detection.models import DetectionResult
from sd_model_hub.core.record import Record
from sd_model_hub.core.settings.models import LayoutName


class RootInfo(Record):
    id: str
    name: str
    path: str
    layout: LayoutName
    exists: bool


class RootCreate(Record):
    name: str | None = None
    path: str
    layout: LayoutName = "custom"


class RootUpdate(Record):
    name: str | None = None
    path: str | None = None
    layout: LayoutName | None = None


class FolderEntry(Record):
    name: str
    path: str
    folder_kind: str | None = None


class SidecarHint(Record):
    """What a sidecar file says the model is."""

    source: str
    kind: str | None = None
    base_model: str | None = None


class ModelEntry(Record):
    name: str
    stem: str
    path: str
    is_dir: bool = False
    size: int
    mtime: datetime
    preview: str | None = None
    folder_kind: str | None = None
    detection: DetectionResult | None = None
    sidecar: SidecarHint | None = None
    mismatch: bool = False
    companions: list[str] = Field(default_factory=list)


class FolderListing(Record):
    root_id: str
    path: str
    folder_kind: str | None
    folders: list[FolderEntry]
    models: list[ModelEntry]
    pending_detection: int = 0


class TreeNode(Record):
    name: str
    path: str
    folder_kind: str | None = None
    children: list["TreeNode"] = Field(default_factory=list)


class ModelInfo(Record):
    root_id: str
    entry: ModelEntry
    sha256: str | None = None
    header_metadata: dict[str, Any] = Field(default_factory=dict)
    sdmodelhub: dict[str, Any] | None = None
    webui: dict[str, Any] | None = None
    description: str | None = None
    civitai_info: dict[str, Any] | None = None


class PathRef(Record):
    root_id: str
    path: str


class ImportRequest(Record):
    """Copy or move files already on the server's machine into a root."""

    sources: list[str]
    root_id: str
    rel_dir: str = ""
    move: bool = False
    on_conflict: Literal["error", "rename"] = "error"


class MoveRequest(Record):
    items: list[PathRef]
    dest_root_id: str
    dest_dir: str = ""
    on_conflict: Literal["error", "rename"] = "error"


class RenameRequest(Record):
    root_id: str
    path: str
    new_name: str


class DeleteRequest(Record):
    items: list[PathRef]
    permanent: bool = False


class FolderCreate(Record):
    root_id: str
    path: str = ""
    name: str


class OperationResult(Record):
    """Paths affected by an operation, relative to their roots."""

    paths: list[PathRef] = Field(default_factory=list)
    trashed_to: list[str] = Field(default_factory=list)
