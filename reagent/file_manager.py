"""file_manager — GitLab-backed file tree operations for reagent.

All file reads/writes go through GitLab so that both the orchestrator
and remote executors (Nosana, CI runners) operate on the same files.
"""

from __future__ import annotations

import os
from typing import Optional

from gitlab_client import GitLabClient


class FileManager:
    """Manages files in a GitLab project as a versioned file tree."""

    # Known file categories for type-aware operations
    EXTENSIONS = {
        ".sol": "contract",
        ".vy": "contract",
        ".json": "artifact",
        ".toml": "config",
        ".yaml": "config",
        ".yml": "config",
        ".md": "doc",
        ".txt": "doc",
        ".js": "script",
        ".ts": "script",
        ".sh": "script",
        ".py": "script",
    }

    def __init__(self, gitlab: Optional[GitLabClient] = None):
        self.gl = gitlab or GitLabClient()

    # -- Category helpers --

    @classmethod
    def file_category(cls, path: str) -> str:
        """Return the file category based on extension."""
        ext = os.path.splitext(path)[1].lower()
        return cls.EXTENSIONS.get(ext, "other")

    @classmethod
    def is_contract(cls, path: str) -> bool:
        return cls.file_category(path) == "contract"

    @classmethod
    def is_artifact(cls, path: str) -> bool:
        return cls.file_category(path) == "artifact"

    # -- CRUD --

    def create_file(
        self,
        file_path: str,
        content: str,
        branch: str,
        commit_message: str = "",
    ) -> dict:
        """Create or overwrite a file in the repository."""
        if not commit_message:
            commit_message = f"add {file_path}"
        self.gl.create_file(file_path, content, branch, commit_message)
        return {
            "path": file_path,
            "branch": branch,
            "category": self.file_category(file_path),
        }

    def read_file(self, file_path: str, branch: str = "main") -> str:
        """Read a file's content from the repository."""
        f = self.gl.project.files.get(file_path=file_path, ref=branch)
        return f.decode().decode("utf-8")

    def update_file(
        self,
        file_path: str,
        content: str,
        branch: str,
        commit_message: str = "",
    ) -> dict:
        """Update an existing file."""
        if not commit_message:
            commit_message = f"update {file_path}"
        self.gl.update_file(file_path, content, branch, commit_message)
        return {
            "path": file_path,
            "branch": branch,
            "category": self.file_category(file_path),
        }

    def delete_file(
        self,
        file_path: str,
        branch: str,
        commit_message: str = "",
    ) -> dict:
        """Delete a file from the repository."""
        if not commit_message:
            commit_message = f"delete {file_path}"
        file = self.gl.project.files.get(file_path=file_path, ref=branch)
        file.delete(commit_message=commit_message, branch=branch)
        return {"path": file_path, "branch": branch, "deleted": True}

    # -- Tree operations --

    def list_tree(
        self,
        branch: str = "main",
        path: str = "",
        recursive: bool = True,
    ) -> list[dict]:
        """List all files in the repository (or a subdirectory)."""
        items = self.gl.project.repository_tree(
            path=path, ref=branch, recursive=recursive, get_all=True
        )
        return [
            {
                "name": item.name,
                "path": item.path,
                "type": item.type,  # "tree" (dir) or "blob" (file)
                "category": self.file_category(item.path) if item.type == "blob" else "directory",
            }
            for item in items
        ]

    def tree_ascii(
        self,
        branch: str = "main",
        root_path: str = "",
    ) -> str:
        """Return an ASCII tree visualization of the repository."""
        items = self.list_tree(branch=branch, path=root_path, recursive=True)

        # Build nested structure
        tree: dict = {}
        for item in items:
            parts = item["path"].split("/")
            current = tree
            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]

        lines = []
        self._render_tree(tree, "", True, lines)
        return "\n".join(lines)

    def _render_tree(self, node: dict, prefix: str, is_last: bool, lines: list):
        """Recursively render a directory tree."""
        items = sorted(node.items(), key=lambda x: (x[1] != {}, x[0]))
        for i, (name, children) in enumerate(items):
            last = i == len(items) - 1
            connector = "\u2514\u2500\u2500 " if last else "\u251c\u2500\u2500 "
            lines.append(f"{prefix}{connector}{name}")
            if children:
                extension = "    " if last else "\u2502   "
                self._render_tree(children, prefix + extension, last, lines)

    def find_contracts(self, branch: str = "main") -> list[str]:
        """Find all Solidity contract files in the repository."""
        items = self.list_tree(branch=branch)
        return [
            item["path"]
            for item in items
            if item["type"] == "blob" and self.is_contract(item["path"])
        ]

    def find_artifacts(self, branch: str = "main") -> list[str]:
        """Find all JSON artifact files in the repository."""
        items = self.list_tree(branch=branch)
        return [
            item["path"]
            for item in items
            if item["type"] == "blob" and self.is_artifact(item["path"])
        ]

    # -- Batch operations --

    def create_batch(
        self,
        files: list[dict],
        branch: str,
        commit_message: str = "",
    ) -> list[dict]:
        """Create multiple files in sequence (GitLab API doesn't support multi-file commits natively).

        Each file dict: {"path": "...", "content": "..."}
        """
        results = []
        for f in files:
            result = self.create_file(
                f["path"], f["content"], branch,
                commit_message=commit_message or f"add {f['path']}",
            )
            results.append(result)
        return results

    def read_batch(
        self,
        paths: list[str],
        branch: str = "main",
    ) -> dict[str, str]:
        """Read multiple files at once."""
        return {path: self.read_file(path, branch) for path in paths}

    # -- CI/CD artifacts --

    def get_pipeline_artifacts(
        self,
        pipeline_id: int,
        job_name: Optional[str] = None,
    ) -> list[dict]:
        """Get artifact file metadata from a CI pipeline job."""
        pipeline = self.gl.get_pipeline(pipeline_id)
        jobs = self.gl.get_pipeline_jobs(pipeline_id)
        if job_name:
            jobs = [j for j in jobs if j["name"] == job_name]

        return [
            {
                "job_id": j["id"],
                "job_name": j["name"],
                "stage": j["stage"],
                "status": j["status"],
                "web_url": j["web_url"],
            }
            for j in jobs
        ]

    def get_file_from_branch(
        self,
        file_path: str,
        branch: str = "main",
    ) -> Optional[str]:
        """Safely read a file, returning None if it doesn't exist."""
        try:
            return self.read_file(file_path, branch)
        except Exception:
            return None
