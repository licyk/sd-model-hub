import json
import os
from pathlib import Path

import pytest

from sd_model_hub.core.errors import ConflictError, InvalidPathError, NotFoundError
from sd_model_hub.core.events.models import LibraryChangedEvent
from sd_model_hub.core.library.layouts import default_folder, folder_kind
from sd_model_hub.core.library.models import DeleteRequest, FolderCreate, ImportRequest, MoveRequest, PathRef, RenameRequest, RootCreate
from sd_model_hub.core.library.safety import resolve_in_root, validate_name
from tests.conftest import LORA_SD1, LORA_SDXL, write_safetensors

# -- path safety -----------------------------------------------------------------


@pytest.mark.parametrize("name", ["", ".", "..", "a/b", "a\\b", "CON", "nul.txt", "COM1.safetensors", "bad\x00", "x:y", "trailing.", " lead"])
def test_invalid_names(name):
    with pytest.raises(InvalidPathError):
        validate_name(name)


def test_resolve_rejects_traversal_and_absolute(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    for bad in ("../x", "a/../../x", "/etc/passwd", "C:/Windows"):
        with pytest.raises(InvalidPathError):
            resolve_in_root(root, bad)
    assert resolve_in_root(root, "a/b") == root.resolve() / "a" / "b"


def test_resolve_rejects_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, root / "link")
    with pytest.raises(InvalidPathError):
        resolve_in_root(root, "link/file")
    # With follow_symlinks the path is kept as written, so the client keeps navigating by it.
    assert resolve_in_root(root, "link/file", follow_symlinks=True) == root.resolve() / "link" / "file"
    # Traversal and absolute paths are still refused in either mode.
    for bad in ("../x", "/etc/passwd"):
        with pytest.raises(InvalidPathError):
            resolve_in_root(root, bad, follow_symlinks=True)


# -- layouts -----------------------------------------------------------------------


def test_layout_folder_kinds():
    assert folder_kind("comfyui", "loras/style/sub") == "lora"
    assert folder_kind("comfyui", "unet") == "diffusion_model"
    assert folder_kind("comfyui", "models/clip") == "text_encoder"
    assert folder_kind("sd-webui", "models/Lora") == "lora"
    assert folder_kind("sd-webui", "embeddings") == "embedding"
    assert folder_kind("custom", "loras") is None


def test_default_folder(tmp_path):
    (tmp_path / "models" / "Lora").mkdir(parents=True)
    assert default_folder("sd-webui", tmp_path, "lora") == "models/Lora"
    assert default_folder("sd-webui", tmp_path, "embedding") == "embeddings"
    assert default_folder("comfyui", tmp_path / "models", "lora") == "loras"


# -- roots and browsing --------------------------------------------------------------


def test_roots_crud(services, root_dir, root):
    assert [r.id for r in services.library.list_roots()] == [root.id]
    with pytest.raises(ConflictError):
        services.library.add_root(RootCreate(path=str(root_dir)))
    with pytest.raises(NotFoundError):
        services.library.add_root(RootCreate(path=str(root_dir / "missing")))
    services.library.remove_root(root.id)
    assert services.library.list_roots() == []
    assert root_dir.exists()


def test_listing_groups_companions_and_previews(services, root_dir, root):
    lora = root_dir / "loras" / "style"
    write_safetensors(lora / "a.safetensors", LORA_SDXL)
    write_safetensors(lora / "a.b.safetensors", LORA_SD1)
    (lora / "a.preview.png").write_bytes(b"png")
    (lora / "a.b.png").write_bytes(b"png")
    (lora / "a.civitai.info").write_text(json.dumps({"baseModel": "SD 1.5", "model": {"type": "LORA"}}))
    (lora / "a.safetensors.part").write_bytes(b"x")
    (lora / ".hidden").mkdir()
    (lora / "diffusers-model").mkdir()
    (lora / "diffusers-model" / "model_index.json").write_text("{}")
    listing = services.library.list_entries(root.id, "loras/style")
    by_name = {m.name: m for m in listing.models}
    assert set(by_name) == {"a.safetensors", "a.b.safetensors", "diffusers-model"}
    assert by_name["a.safetensors"].preview == "loras/style/a.preview.png"
    assert by_name["a.b.safetensors"].preview == "loras/style/a.b.png"
    assert "a.b.png" not in by_name["a.safetensors"].companions
    assert by_name["a.safetensors"].detection.base_model == "sdxl"
    assert by_name["a.safetensors"].folder_kind == "lora"
    # The civitai.info says SD 1.5 while the file is SDXL: the entry is flagged.
    assert by_name["a.safetensors"].mismatch is True
    assert by_name["a.b.safetensors"].mismatch is False
    assert listing.folders == []


def test_listing_cached_mode_schedules_scan(services, root_dir, root):
    write_safetensors(root_dir / "loras" / "x.safetensors", LORA_SD1)
    events = []
    services.events.subscribe(events.append)
    listing = services.library.list_entries(root.id, "loras", detect="cached")
    assert listing.pending_detection == 1 and listing.models[0].detection is None
    for _ in range(100):
        if any(isinstance(e, LibraryChangedEvent) for e in events):
            break
        import time

        time.sleep(0.02)
    assert services.library.list_entries(root.id, "loras", detect="cached").pending_detection == 0


def _link_outside(tmp_path: Path, root_dir: Path) -> Path:
    """A folder of models outside the root, linked to from inside it, as a WebUI install does."""
    outside = tmp_path / "elsewhere"
    write_safetensors(outside / "linked.safetensors", LORA_SDXL)
    os.symlink(outside, root_dir / "loras" / "linked")
    return outside


def test_symlinked_folder_hidden_by_default(services, root_dir, root, tmp_path):
    _link_outside(tmp_path, root_dir)
    listing = services.library.list_entries(root.id, "loras")
    assert [f.name for f in listing.folders] == ["style"]
    with pytest.raises(InvalidPathError):
        services.library.list_entries(root.id, "loras/linked")
    assert "linked" not in [c.name for c in services.library.tree(root.id).children[0].children]


def test_follow_symlinks_setting_opens_linked_folders(services, root_dir, root, tmp_path):
    outside = _link_outside(tmp_path, root_dir)
    services.settings.update({"library": {"follow_symlinks": True}})

    listing = services.library.list_entries(root.id, "loras")
    assert sorted(f.name for f in listing.folders) == ["linked", "style"]

    inside = services.library.list_entries(root.id, "loras/linked")
    entry = inside.models[0]
    # The path stays the one relative to the root, not the real location.
    assert entry.path == "loras/linked/linked.safetensors"
    assert entry.detection.base_model == "sdxl"
    assert services.library.model_info(root.id, entry.path).entry.name == "linked.safetensors"
    assert [m.path for m in services.library.walk_models(root.id, "loras")] == ["loras/linked/linked.safetensors"]

    # A file reached through the link is found under the root by the path as written.
    assert services.library.locate(root_dir / "loras" / "linked" / "linked.safetensors") == (root.id, "loras/linked/linked.safetensors")
    # Renaming acts on the real file.
    services.library.rename(RenameRequest(root_id=root.id, path="loras/linked/linked.safetensors", new_name="renamed"))
    assert (outside / "renamed.safetensors").exists()


def test_symlink_loop_is_walked_once(services, root_dir, root):
    os.symlink(root_dir / "loras", root_dir / "loras" / "style" / "loop")
    services.settings.update({"library": {"follow_symlinks": True}})
    write_safetensors(root_dir / "loras" / "m.safetensors", LORA_SD1)
    models = list(services.library.walk_models(root.id, "loras"))
    assert [m.name for m in models] == ["m.safetensors"]
    assert services.library.tree(root.id) is not None


def test_kind_filter_and_walk(services, root_dir, root):
    write_safetensors(root_dir / "loras" / "style" / "l.safetensors", LORA_SD1)
    (root_dir / "checkpoints" / "old.ckpt").write_bytes(b"x")
    all_models = list(services.library.walk_models(root.id))
    assert {m.name for m in all_models} == {"l.safetensors", "old.ckpt"}
    assert [m.name for m in services.library.walk_models(root.id, kind="lora")] == ["l.safetensors"]
    # A pickle is unknown to detection, so the folder decides.
    assert [m.name for m in services.library.walk_models(root.id, kind="checkpoint")] == ["old.ckpt"]


def test_model_info_with_sidecars_and_hash(services, root_dir, root):
    path = write_safetensors(root_dir / "loras" / "m.safetensors", LORA_SDXL)
    (root_dir / "loras" / "m.json").write_text(json.dumps({"description": "d", "sd version": "SDXL", "activation text": "trig", "junk": 1}))
    (root_dir / "loras" / "m.txt").write_text("hello")
    info = services.library.model_info(root.id, "loras/m.safetensors", compute_hash=True)
    assert info.webui == {"description": "d", "sd version": "SDXL", "activation text": "trig"}
    assert info.description == "hello"
    import hashlib

    assert info.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


# -- operations ------------------------------------------------------------------------


def test_rename_carries_companions(services, root_dir, root):
    lora = root_dir / "loras"
    write_safetensors(lora / "old.safetensors", LORA_SD1)
    (lora / "old.preview.png").write_bytes(b"p")
    (lora / "old.json").write_text("{}")
    result = services.library.rename(RenameRequest(root_id=root.id, path="loras/old.safetensors", new_name="new.safetensors"))
    assert result.paths[0].path == "loras/new.safetensors"
    assert sorted(p.name for p in lora.iterdir() if p.is_file()) == ["new.json", "new.preview.png", "new.safetensors"]


def test_rename_conflict(services, root_dir, root):
    write_safetensors(root_dir / "loras" / "a.safetensors", LORA_SD1)
    (root_dir / "loras" / "b.png").write_bytes(b"p")
    write_safetensors(root_dir / "loras" / "a2.safetensors", LORA_SD1)
    (root_dir / "loras" / "a.png").write_bytes(b"p")
    with pytest.raises(ConflictError):
        services.library.rename(RenameRequest(root_id=root.id, path="loras/a.safetensors", new_name="b"))
    assert (root_dir / "loras" / "a.safetensors").exists()
    with pytest.raises(InvalidPathError):
        services.library.rename(RenameRequest(root_id=root.id, path="loras/a.safetensors", new_name="../x"))


def test_move_between_roots_with_rename_on_conflict(services, root_dir, root, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    other_root = services.library.add_root(RootCreate(path=str(other)))
    write_safetensors(root_dir / "loras" / "m.safetensors", LORA_SD1)
    (root_dir / "loras" / "m.png").write_bytes(b"p")
    write_safetensors(other / "m.safetensors", LORA_SD1)
    with pytest.raises(ConflictError):
        services.library.move(MoveRequest(items=[PathRef(root_id=root.id, path="loras/m.safetensors")], dest_root_id=other_root.id))
    result = services.library.move(MoveRequest(items=[PathRef(root_id=root.id, path="loras/m.safetensors")], dest_root_id=other_root.id, on_conflict="rename"))
    assert result.paths[0].path == "m_1.safetensors"
    assert (other / "m_1.png").exists() and not (root_dir / "loras" / "m.png").exists()


def test_move_folder_into_itself_refused(services, root_dir, root):
    with pytest.raises(InvalidPathError):
        services.library.move(MoveRequest(items=[PathRef(root_id=root.id, path="loras")], dest_root_id=root.id, dest_dir="loras/style"))


def test_delete_permanent_and_to_trash_fallback(services, root_dir, root, monkeypatch):
    write_safetensors(root_dir / "loras" / "gone.safetensors", LORA_SD1)
    (root_dir / "loras" / "gone.png").write_bytes(b"p")
    services.library.delete(DeleteRequest(items=[PathRef(root_id=root.id, path="loras/gone.safetensors")], permanent=True))
    assert list((root_dir / "loras").glob("gone*")) == []

    write_safetensors(root_dir / "loras" / "t.safetensors", LORA_SD1)
    import send2trash

    def fail(_path):
        raise OSError("no trash here")

    monkeypatch.setattr(send2trash, "send2trash", fail)
    result = services.library.delete(DeleteRequest(items=[PathRef(root_id=root.id, path="loras/t.safetensors")]))
    trash_dir = Path(result.trashed_to[0])
    assert (trash_dir / "t.safetensors").exists()
    assert trash_dir.is_relative_to(services.settings.data_dir)


def test_cannot_delete_root(services, root):
    with pytest.raises(InvalidPathError):
        services.library.delete(DeleteRequest(items=[PathRef(root_id=root.id, path="")], permanent=True))


def test_import_copy_with_companions(services, root_dir, root, tmp_path):
    src = tmp_path / "incoming"
    write_safetensors(src / "new.safetensors", LORA_SDXL)
    (src / "new.preview.webp").write_bytes(b"w")
    result = services.library.import_paths(ImportRequest(sources=[str(src / "new.safetensors")], root_id=root.id, rel_dir="loras"))
    assert result.paths[0].path == "loras/new.safetensors"
    assert (root_dir / "loras" / "new.preview.webp").exists()
    assert (src / "new.safetensors").exists()
    with pytest.raises(ConflictError):
        services.library.import_paths(ImportRequest(sources=[str(src / "new.safetensors")], root_id=root.id, rel_dir="loras"))


def test_create_folder(services, root_dir, root):
    ref = services.library.create_folder(FolderCreate(root_id=root.id, path="loras", name="new"))
    assert ref.path == "loras/new" and (root_dir / "loras" / "new").is_dir()
    with pytest.raises(ConflictError):
        services.library.create_folder(FolderCreate(root_id=root.id, path="loras", name="new"))


def test_upload_writer(services, root_dir, root):
    writer = services.library.open_upload(root.id, "loras", "sub/up.bin", total=6)
    writer.write(b"abc")
    writer.write(b"def")
    ref = writer.commit()
    assert ref.path == "loras/sub/up.bin" and (root_dir / "loras" / "sub" / "up.bin").read_bytes() == b"abcdef"
    with pytest.raises(ConflictError):
        services.library.open_upload(root.id, "loras", "sub/up.bin")
    aborted = services.library.open_upload(root.id, "loras", "x.bin")
    aborted.write(b"1")
    aborted.abort()
    assert not (root_dir / "loras" / "x.bin.part").exists() and not (root_dir / "loras" / "x.bin").exists()
