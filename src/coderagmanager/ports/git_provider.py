from __future__ import annotations

from typing import Protocol


class GitProvider(Protocol):
    """Sin diff_since ni working_tree_changes: no hay reindexado incremental en v1."""

    def head(self, repo_path: str) -> str | None: ...
