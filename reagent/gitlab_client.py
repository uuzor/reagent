"""GitLab client for reagent — wraps python-gitlab for CI/CD pipeline orchestration."""

import os
from typing import Optional

import gitlab


class GitLabClient:
    """Thin wrapper around python-gitlab tailored for the smart contract pipeline."""

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        self.url = url or os.getenv("GITLAB_URL", "https://gitlab.com")
        self.token = token or os.getenv("GITLAB_TOKEN", "")
        self.project_id = int(project_id or os.getenv("GITLAB_PROJECT_ID", "0"))

        self.gl = gitlab.Gitlab(self.url, private_token=self.token)
        self.project = self.gl.projects.get(self.project_id)

    # -- Project creation --

    def create_project(self, name: str, **kwargs) -> dict:
        """Create a new GitLab project."""
        project = self.gl.projects.create({"name": name, **kwargs})
        return {
            "id": project.id,
            "name": project.name,
            "web_url": project.web_url,
            "default_branch": getattr(project, "default_branch", "main"),
        }

    # -- Issues (workflow tracking) --

    def create_issue(self, title: str, description: str, labels: list[str] | None = None) -> dict:
        """Create a tracking issue for a workflow run."""
        issue = self.project.issues.create({
            "title": title,
            "description": description,
            "labels": labels or ["reagent"],
        })
        return {
            "iid": issue.iid,
            "web_url": issue.web_url,
            "title": issue.title,
        }

    def get_issue(self, issue_iid: int) -> dict:
        """Retrieve issue details."""
        issue = self.project.issues.get(issue_iid)
        return {
            "iid": issue.iid,
            "state": issue.state,
            "title": issue.title,
            "description": issue.description,
            "web_url": issue.web_url,
        }

    def add_issue_note(self, issue_iid: int, body: str) -> dict:
        """Add a comment to a tracking issue (e.g. stage completion updates)."""
        issue = self.project.issues.get(issue_iid)
        note = issue.notes.create({"body": body})
        return {"id": note.id, "body": note.body}

    # -- Merge Requests (code submission) --

    def create_merge_request(
        self,
        title: str,
        source_branch: str,
        target_branch: str = "main",
        description: str = "",
        labels: list[str] | None = None,
    ) -> dict:
        """Open an MR with generated contract code."""
        mr = self.project.mergerequests.create({
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
            "labels": labels or ["reagent", "contract"],
        })
        return {
            "iid": mr.iid,
            "web_url": mr.web_url,
            "state": mr.state,
            "source_branch": mr.source_branch,
            "target_branch": mr.target_branch,
        }

    def get_merge_request(self, mr_iid: int) -> dict:
        """Retrieve MR details."""
        mr = self.project.mergerequests.get(mr_iid)
        return {
            "iid": mr.iid,
            "state": mr.state,
            "merge_status": mr.merge_status,
            "web_url": mr.web_url,
            "source_branch": mr.source_branch,
        }

    def get_mr_pipelines(self, mr_iid: int) -> list[dict]:
        """Get CI pipelines attached to an MR."""
        mr = self.project.mergerequests.get(mr_iid)
        pipelines = mr.pipelines.list()
        return [
            {"id": p.id, "status": p.status, "ref": p.ref, "web_url": p.web_url}
            for p in pipelines
        ]

    def merge_merge_request(self, mr_iid: int, **kwargs) -> dict:
        """Accept/merge a merge request."""
        mr = self.project.mergerequests.get(mr_iid)
        result = mr.merge(**kwargs)
        if isinstance(result, dict):
            return {
                "iid": result.get("iid", mr_iid),
                "state": result.get("state", "merged"),
                "merged": True,
            }
        return {
            "iid": getattr(result, "iid", mr_iid),
            "state": getattr(result, "state", "merged"),
            "merged": True,
        }

    # -- CI/CD Pipelines (testing & deployment) --

    def trigger_pipeline(
        self,
        ref: str = "main",
        variables: dict | None = None,
    ) -> dict:
        """Trigger a CI pipeline (for testing or deployment)."""
        pipeline = self.project.pipelines.create({
            "ref": ref,
            "variables": variables or [],
        })
        return {
            "id": pipeline.id,
            "status": pipeline.status,
            "ref": pipeline.ref,
            "web_url": pipeline.web_url,
        }

    def get_pipeline(self, pipeline_id: int) -> dict:
        """Get pipeline status."""
        pipeline = self.project.pipelines.get(pipeline_id)
        return {
            "id": pipeline.id,
            "status": pipeline.status,
            "ref": pipeline.ref,
            "web_url": pipeline.web_url,
            "created_at": pipeline.created_at,
            "updated_at": pipeline.updated_at,
        }

    def get_pipeline_jobs(self, pipeline_id: int) -> list[dict]:
        """Get jobs within a pipeline (test results, deploy status)."""
        pipeline = self.project.pipelines.get(pipeline_id)
        jobs = pipeline.jobs.list()
        return [
            {
                "id": j.id,
                "name": j.name,
                "status": j.status,
                "stage": j.stage,
                "web_url": j.web_url,
            }
            for j in jobs
        ]

    def retry_pipeline(self, pipeline_id: int) -> dict:
        """Retry a failed pipeline."""
        pipeline = self.project.pipelines.get(pipeline_id)
        pipeline.retry()
        return {"id": pipeline_id, "status": "retried"}

    # -- Repository operations --

    def create_branch(self, branch_name: str, ref: str = "main") -> dict:
        """Create a new branch for contract code."""
        branch = self.project.branches.create({"branch": branch_name, "ref": ref})
        return {"name": branch.name, "web_url": branch.web_url}

    def create_file(
        self,
        file_path: str,
        content: str,
        branch: str,
        commit_message: str,
    ) -> dict:
        """Push a file to a branch (e.g. generated contract)."""
        self.project.files.create({
            "file_path": file_path,
            "branch": branch,
            "content": content,
            "commit_message": commit_message,
        })
        return {"file_path": file_path, "branch": branch}

    def update_file(
        self,
        file_path: str,
        content: str,
        branch: str,
        commit_message: str,
    ) -> dict:
        """Update an existing file."""
        file = self.project.files.get(file_path=file_path, ref=branch)
        file.content = content
        file.save(branch=branch, commit_message=commit_message)
        return {"file_path": file_path, "branch": branch}

    def read_file(self, file_path: str, ref: str = "main") -> str:
        """Read a file's decoded content from the repository."""
        f = self.project.files.get(file_path=file_path, ref=ref)
        return f.decode().decode("utf-8")

    def delete_file(
        self,
        file_path: str,
        branch: str,
        commit_message: str,
    ) -> dict:
        """Delete a file from the repository."""
        f = self.project.files.get(file_path=file_path, ref=branch)
        f.delete(commit_message=commit_message, branch=branch)
        return {"file_path": file_path, "branch": branch, "deleted": True}

    def delete_branch(self, branch_name: str) -> dict:
        """Delete a branch from the repository."""
        branch = self.project.branches.get(branch_name)
        branch.delete()
        return {"branch": branch_name, "deleted": True}

    def list_branches(self, search: str | None = None) -> list[dict]:
        """List branches in the project."""
        kwargs = {}
        if search:
            kwargs["search"] = search
        branches = self.project.branches.list(**kwargs)
        return [{"name": b.name, "merged": getattr(b, "merged", None), "default": getattr(b, "default", False)} for b in branches]

    def commit_files(
        self,
        branch: str,
        commit_message: str,
        actions: list[dict],
    ) -> dict:
        """Create a commit with multiple file actions.

        Each action dict: {"action": "create"|"update"|"delete", "file_path": "...", "content": "..."}
        """
        result = self.project.commits.create({
            "branch": branch,
            "commit_message": commit_message,
            "actions": actions,
        })
        return {
            "id": result.id,
            "short_id": result.short_id,
            "title": result.title,
            "web_url": getattr(result, "web_url", ""),
        }

    def get_repo_tree(self, path: str = "", ref: str = "main", recursive: bool = False) -> list[dict]:
        """Get the repository file tree."""
        items = self.project.repository_tree(path=path, ref=ref, recursive=recursive, get_all=True)
        result = []
        for item in items:
            if isinstance(item, dict):
                result.append({"name": item["name"], "path": item["path"], "type": item["type"]})
            else:
                result.append({"name": item.name, "path": item.path, "type": item.type})
        return result

    # -- Labels --

    def search_labels(self, query: str) -> list[dict]:
        """Search labels in the project."""
        labels = self.project.labels.list(search=query)
        return [{"name": l.name, "color": l.color} for l in labels]

    # -- Search --

    def search_code(self, query: str, scope: str = "blobs") -> list[dict]:
        """Search for code snippets in the project."""
        results = self.project.search(scope, search=query)
        out = []
        for r in results:
            if isinstance(r, dict):
                out.append({"id": r.get("id", ""), "name": r.get("name", ""), "path": r.get("path", "")})
            else:
                out.append({"id": r.id, "name": r.name, "path": getattr(r, "path", "")})
        return out
