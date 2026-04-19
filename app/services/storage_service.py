import hashlib
import os
import uuid
from pathlib import Path
from typing import Iterable

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


class StorageService:
    def __init__(self, root_folder: str):
        self.root = Path(root_folder)

    def save_profile_upload(self, profile_id: int, version: int, uploaded_file: FileStorage):
        safe_name = secure_filename(uploaded_file.filename or "profile.tar")
        profile_folder = self.root / str(profile_id)
        profile_folder.mkdir(parents=True, exist_ok=True)

        extension = Path(safe_name).suffix.lower() or ".tar"
        filename = f"v{version}_{uuid.uuid4().hex}{extension}"
        final_path = profile_folder / filename

        uploaded_file.save(final_path)

        hasher = hashlib.sha256()
        with open(final_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)

        return {
            "original_filename": safe_name,
            "stored_path": str(final_path),
            "file_size": os.path.getsize(final_path),
            "sha256": hasher.hexdigest(),
            "mime_type": uploaded_file.mimetype,
        }

    def delete_files(self, stored_paths: Iterable[str]) -> None:
        for stored_path in stored_paths:
            path = Path(stored_path)
            try:
                path.unlink()
            except FileNotFoundError:
                continue

            try:
                if path.parent != self.root and path.parent.is_dir() and not any(path.parent.iterdir()):
                    path.parent.rmdir()
            except OSError:
                continue
