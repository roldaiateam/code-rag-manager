from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone

from coderagmanager.domain.models import IndexManifest

CRM_DIR = ".crm"
MANIFEST_FILE = "manifest.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def crm_dir(root_path: str) -> str:
    path = os.path.join(root_path, CRM_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def write_manifest(root_path: str, manifest: IndexManifest) -> None:
    path = os.path.join(crm_dir(root_path), MANIFEST_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(asdict(manifest), fh, indent=2, ensure_ascii=False)


def read_manifest(root_path: str) -> IndexManifest | None:
    path = os.path.join(root_path, CRM_DIR, MANIFEST_FILE)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return IndexManifest(**data)
