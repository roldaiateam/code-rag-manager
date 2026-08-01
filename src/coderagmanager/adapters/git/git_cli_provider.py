from __future__ import annotations

import subprocess


class GitCliProvider:
    def head(self, repo_path: str) -> str | None:
        result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None  # no es un repo git (o sin commits): el manifest lo refleja como null
        return result.stdout.strip()
