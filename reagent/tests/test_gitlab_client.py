"""Tests for gitlab_client.py — mocked against python-gitlab."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# We must patch before importing the module, because GitLabClient.__init__
# calls gitlab.Gitlab(...) and gl.projects.get(...) at import-time.
# Instead, we'll mock the gitlab module and construct the client carefully.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_project():
    """Build a mock GitLab project object with all sub-resources."""
    project = MagicMock()

    # -- Issues --
    mock_issue = MagicMock()
    mock_issue.iid = 42
    mock_issue.web_url = "https://gitlab.com/project/-/issues/42"
    mock_issue.title = "Test issue"
    mock_issue.description = "desc"
    mock_issue.state = "opened"

    mock_note = MagicMock()
    mock_note.id = 99
    mock_note.body = "note body"
    mock_issue.notes.create.return_value = mock_note

    project.issues.create.return_value = mock_issue
    project.issues.get.return_value = mock_issue

    # -- Merge Requests --
    mock_mr = MagicMock()
    mock_mr.iid = 7
    mock_mr.web_url = "https://gitlab.com/project/-/merge_requests/7"
    mock_mr.state = "opened"
    mock_mr.merge_status = "can_be_merged"
    mock_mr.source_branch = "feature"
    mock_mr.target_branch = "main"

    mock_pipeline_summary = MagicMock()
    mock_pipeline_summary.id = 100
    mock_pipeline_summary.status = "success"
    mock_pipeline_summary.ref = "feature"
    mock_pipeline_summary.web_url = "https://gitlab.com/project/-/pipelines/100"
    mock_mr.pipelines.list.return_value = [mock_pipeline_summary]

    project.mergerequests.create.return_value = mock_mr
    project.mergerequests.get.return_value = mock_mr

    # -- Pipelines --
    mock_pipeline = MagicMock()
    mock_pipeline.id = 100
    mock_pipeline.status = "running"
    mock_pipeline.ref = "main"
    mock_pipeline.web_url = "https://gitlab.com/project/-/pipelines/100"
    mock_pipeline.created_at = "2025-01-01T00:00:00Z"
    mock_pipeline.updated_at = "2025-01-01T00:01:00Z"

    mock_job = MagicMock()
    mock_job.id = 200
    mock_job.name = "compile"
    mock_job.status = "success"
    mock_job.stage = "build"
    mock_job.web_url = "https://gitlab.com/project/-/jobs/200"
    mock_pipeline.jobs.list.return_value = [mock_job]

    project.pipelines.create.return_value = mock_pipeline
    project.pipelines.get.return_value = mock_pipeline

    # -- Branches --
    mock_branch = MagicMock()
    mock_branch.name = "feature-branch"
    mock_branch.web_url = "https://gitlab.com/project/-/tree/feature-branch"
    project.branches.create.return_value = mock_branch

    # -- Files --
    mock_file = MagicMock()
    mock_file.content = "file content"
    mock_file.decode.return_value = b"decoded content"
    project.files.create.return_value = mock_file
    project.files.get.return_value = mock_file

    # -- Labels --
    mock_label = MagicMock()
    mock_label.name = "reagent"
    mock_label.color = "#FF0000"
    project.labels.list.return_value = [mock_label]

    # -- Search --
    mock_result = MagicMock()
    mock_result.id = "abc"
    mock_result.name = "DeFiYieldToken.sol"
    mock_result.path = "contracts/DeFiYieldToken.sol"
    project.search.return_value = [mock_result]

    # -- Repository tree --
    mock_tree_item_file = MagicMock()
    mock_tree_item_file.name = "DeFiYieldToken.sol"
    mock_tree_item_file.path = "contracts/DeFiYieldToken.sol"
    mock_tree_item_file.type = "blob"

    mock_tree_item_dir = MagicMock()
    mock_tree_item_dir.name = "contracts"
    mock_tree_item_dir.path = "contracts"
    mock_tree_item_dir.type = "tree"

    project.repository_tree.return_value = [mock_tree_item_dir, mock_tree_item_file]

    return project


def _make_client(mock_project):
    """Construct a GitLabClient with a fully mocked gitlab lib."""
    with patch("gitlab.Gitlab") as MockGitlab:
        mock_gl_instance = MagicMock()
        mock_gl_instance.projects.get.return_value = mock_project
        MockGitlab.return_value = mock_gl_instance

        from gitlab_client import GitLabClient
        client = GitLabClient(
            url="https://gitlab.example.com",
            token="fake-token",
            project_id="123",
        )
    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_project():
    return _make_mock_project()


@pytest.fixture
def client(mock_project):
    return _make_client(mock_project)


# ---------------------------------------------------------------------------
# Tests: __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_reads_env_defaults(self):
        """When no args are given, reads from env vars."""
        with patch("gitlab.Gitlab") as MockGitlab, \
             patch.dict(os.environ, {
                 "GITLAB_URL": "https://custom.gitlab.com",
                 "GITLAB_TOKEN": "env-token",
                 "GITLAB_PROJECT_ID": "999",
             }):
            mock_gl_instance = MagicMock()
            mock_gl_instance.projects.get.return_value = MagicMock()
            MockGitlab.return_value = mock_gl_instance

            from gitlab_client import GitLabClient
            client = GitLabClient()

            MockGitlab.assert_called_once_with(
                "https://custom.gitlab.com", private_token="env-token"
            )
            assert client.project_id == 999

    def test_explicit_args_override_env(self, mock_project):
        client = _make_client(mock_project)
        assert client.url == "https://gitlab.example.com"
        assert client.token == "fake-token"
        assert client.project_id == 123


# ---------------------------------------------------------------------------
# Tests: Issues
# ---------------------------------------------------------------------------

class TestIssues:
    def test_create_issue(self, client):
        result = client.create_issue("Bug", "Something broke", labels=["bug"])
        assert result["iid"] == 42
        assert result["title"] == "Test issue"
        client.project.issues.create.assert_called_once_with({
            "title": "Bug",
            "description": "Something broke",
            "labels": ["bug"],
        })

    def test_create_issue_default_labels(self, client):
        result = client.create_issue("Title", "Desc")
        call_kwargs = client.project.issues.create.call_args
        assert call_kwargs[0][0]["labels"] == ["reagent"]

    def test_get_issue(self, client):
        result = client.get_issue(42)
        assert result["iid"] == 42
        assert result["state"] == "opened"
        assert result["title"] == "Test issue"
        client.project.issues.get.assert_called_once_with(42)

    def test_add_issue_note(self, client):
        result = client.add_issue_note(42, "Stage complete")
        assert result["id"] == 99
        assert result["body"] == "note body"
        # The issue was fetched, then a note was created on it
        issue = client.project.issues.get.return_value
        issue.notes.create.assert_called_once_with({"body": "Stage complete"})


# ---------------------------------------------------------------------------
# Tests: Merge Requests
# ---------------------------------------------------------------------------

class TestMergeRequests:
    def test_create_merge_request(self, client):
        result = client.create_merge_request(
            "Add contract", "feature", description="New contract code"
        )
        assert result["iid"] == 7
        assert result["source_branch"] == "feature"
        assert result["target_branch"] == "main"
        client.project.mergerequests.create.assert_called_once()

    def test_create_merge_request_default_labels(self, client):
        client.create_merge_request("Add contract", "feature")
        call_args = client.project.mergerequests.create.call_args[0][0]
        assert call_args["labels"] == ["reagent", "contract"]

    def test_create_merge_request_custom_labels(self, client):
        client.create_merge_request("Add contract", "feature", labels=["custom"])
        call_args = client.project.mergerequests.create.call_args[0][0]
        assert call_args["labels"] == ["custom"]

    def test_get_merge_request(self, client):
        result = client.get_merge_request(7)
        assert result["merge_status"] == "can_be_merged"
        client.project.mergerequests.get.assert_called_once_with(7)

    def test_get_mr_pipelines(self, client):
        result = client.get_mr_pipelines(7)
        assert len(result) == 1
        assert result[0]["id"] == 100
        assert result[0]["status"] == "success"


# ---------------------------------------------------------------------------
# Tests: CI/CD Pipelines
# ---------------------------------------------------------------------------

class TestPipelines:
    def test_trigger_pipeline(self, client):
        result = client.trigger_pipeline(ref="main", variables={"KEY": "VAL"})
        assert result["id"] == 100
        assert result["status"] == "running"
        assert result["ref"] == "main"

    def test_get_pipeline(self, client):
        result = client.get_pipeline(100)
        assert result["status"] == "running"
        assert result["created_at"] == "2025-01-01T00:00:00Z"

    def test_get_pipeline_jobs(self, client):
        result = client.get_pipeline_jobs(100)
        assert len(result) == 1
        assert result[0]["name"] == "compile"
        assert result[0]["stage"] == "build"

    def test_retry_pipeline(self, client):
        result = client.retry_pipeline(100)
        assert result["status"] == "retried"
        pipeline = client.project.pipelines.get.return_value
        pipeline.retry.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: Repository operations
# ---------------------------------------------------------------------------

class TestRepository:
    def test_create_branch(self, client):
        result = client.create_branch("feature-branch", ref="main")
        assert result["name"] == "feature-branch"
        client.project.branches.create.assert_called_once_with(
            {"branch": "feature-branch", "ref": "main"}
        )

    def test_create_file(self, client):
        result = client.create_file(
            "contracts/Token.sol", "pragma solidity...", "main", "Add token"
        )
        assert result["file_path"] == "contracts/Token.sol"
        assert result["branch"] == "main"
        client.project.files.create.assert_called_once_with({
            "file_path": "contracts/Token.sol",
            "branch": "main",
            "content": "pragma solidity...",
            "commit_message": "Add token",
        })

    def test_update_file_sets_content_before_save(self, client):
        client.update_file("contracts/Token.sol", "updated content", "main", "Fix bug")
        f = client.project.files.get.return_value
        assert f.content == "updated content"
        f.save.assert_called_once_with(branch="main", commit_message="Fix bug")

    def test_update_file_reads_from_correct_branch(self, client):
        client.update_file("contracts/Token.sol", "new", "develop", "Update")
        client.project.files.get.assert_called_once_with(
            file_path="contracts/Token.sol", ref="develop"
        )


# ---------------------------------------------------------------------------
# Tests: Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_get_issue_not_found(self, client):
        client.project.issues.get.side_effect = Exception("404 Not Found")
        with pytest.raises(Exception, match="404"):
            client.get_issue(999)

    def test_get_merge_request_not_found(self, client):
        client.project.mergerequests.get.side_effect = Exception("404 Not Found")
        with pytest.raises(Exception, match="404"):
            client.get_merge_request(999)

    def test_get_pipeline_not_found(self, client):
        client.project.pipelines.get.side_effect = Exception("404 Not Found")
        with pytest.raises(Exception, match="404"):
            client.get_pipeline(999)

    def test_trigger_pipeline_with_no_variables(self, client):
        result = client.trigger_pipeline(ref="main")
        client.project.pipelines.create.assert_called_once_with({
            "ref": "main",
            "variables": [],
        })
        assert result["id"] == 100


# ---------------------------------------------------------------------------
# Tests: Labels & Search
# ---------------------------------------------------------------------------

class TestLabelsAndSearch:
    def test_search_labels(self, client):
        result = client.search_labels("reagent")
        assert len(result) == 1
        assert result[0]["name"] == "reagent"
        assert result[0]["color"] == "#FF0000"

    def test_search_code(self, client):
        result = client.search_code("DeFiYieldToken")
        assert len(result) == 1
        assert result[0]["path"] == "contracts/DeFiYieldToken.sol"
        client.project.search.assert_called_once_with("blobs", search="DeFiYieldToken")


# ---------------------------------------------------------------------------
# Tests: Repository tree (used by FileManager)
# ---------------------------------------------------------------------------

class TestRepositoryTree:
    def test_repository_tree_accessible(self, client):
        """Verify the project mock supports repository_tree for FileManager."""
        items = client.project.repository_tree(
            path="", ref="main", recursive=True, get_all=True
        )
        assert len(items) == 2
        assert items[0].type == "tree"
        assert items[1].type == "blob"
