"""Tests for file_manager.py — mocked against GitLabClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from file_manager import FileManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_gl():
    """Build a mock GitLabClient."""
    gl = MagicMock()

    # create_file / update_file return minimal dicts
    gl.create_file.return_value = {"file_path": "x", "branch": "main"}
    gl.update_file.return_value = {"file_path": "x", "branch": "main"}

    # get_pipeline / get_pipeline_jobs
    gl.get_pipeline.return_value = {
        "id": 10, "status": "success", "ref": "main",
        "web_url": "https://gitlab.com/pipeline/10",
    }
    gl.get_pipeline_jobs.return_value = [
        {"id": 20, "name": "compile", "stage": "build", "status": "success", "web_url": "https://gitlab.com/jobs/20"},
        {"id": 21, "name": "test", "stage": "test", "status": "success", "web_url": "https://gitlab.com/jobs/21"},
    ]

    # project.files.get — for read_file and delete_file
    mock_file = MagicMock()
    mock_file.decode.return_value = b"contract content"
    mock_file.content = "content"
    gl.project.files.get.return_value = mock_file

    # project.repository_tree
    mock_item1 = MagicMock()
    mock_item1.name = "contracts"
    mock_item1.path = "contracts"
    mock_item1.type = "tree"

    mock_item2 = MagicMock()
    mock_item2.name = "Token.sol"
    mock_item2.path = "contracts/Token.sol"
    mock_item2.type = "blob"

    mock_item3 = MagicMock()
    mock_item3.name = "artifact.json"
    mock_item3.path = "artifacts/artifact.json"
    mock_item3.type = "blob"

    mock_item4 = MagicMock()
    mock_item4.name = "README.md"
    mock_item4.path = "README.md"
    mock_item4.type = "blob"

    gl.project.repository_tree.return_value = [mock_item1, mock_item2, mock_item3, mock_item4]

    return gl


@pytest.fixture
def fm():
    gl = _make_mock_gl()
    return FileManager(gitlab=gl)


# ---------------------------------------------------------------------------
# Tests: Category helpers
# ---------------------------------------------------------------------------

class TestCategoryHelpers:
    def test_file_category_contract(self):
        assert FileManager.file_category("Foo.sol") == "contract"

    def test_file_category_vyper(self):
        assert FileManager.file_category("Bar.vy") == "contract"

    def test_file_category_artifact(self):
        assert FileManager.file_category("out.json") == "artifact"

    def test_file_category_config(self):
        assert FileManager.file_category("foundry.toml") == "config"

    def test_file_category_script(self):
        assert FileManager.file_category("deploy.py") == "script"

    def test_file_category_doc(self):
        assert FileManager.file_category("README.md") == "doc"

    def test_file_category_unknown(self):
        assert FileManager.file_category("Makefile") == "other"

    def test_is_contract(self):
        assert FileManager.is_contract("Token.sol") is True
        assert FileManager.is_contract("test.js") is False

    def test_is_artifact(self):
        assert FileManager.is_artifact("abi.json") is True
        assert FileManager.is_artifact("Token.sol") is False


# ---------------------------------------------------------------------------
# Tests: CRUD
# ---------------------------------------------------------------------------

class TestCRUD:
    def test_create_file(self, fm):
        result = fm.create_file("contracts/A.sol", "pragma solidity", "main", "Add A")
        fm.gl.create_file.assert_called_once_with(
            "contracts/A.sol", "pragma solidity", "main", "Add A"
        )
        assert result["path"] == "contracts/A.sol"
        assert result["category"] == "contract"

    def test_create_file_default_message(self, fm):
        fm.create_file("x.txt", "hi", "main")
        fm.gl.create_file.assert_called_once_with(
            "x.txt", "hi", "main", "add x.txt"
        )

    def test_read_file(self, fm):
        content = fm.read_file("contracts/Token.sol", branch="main")
        fm.gl.project.files.get.assert_called_once_with(
            file_path="contracts/Token.sol", ref="main"
        )
        assert content == "contract content"

    def test_update_file(self, fm):
        result = fm.update_file("contracts/A.sol", "new content", "main", "Update A")
        fm.gl.update_file.assert_called_once()
        assert result["category"] == "contract"

    def test_update_file_default_message(self, fm):
        fm.update_file("contracts/A.sol", "new content", "main")
        fm.gl.update_file.assert_called_once_with(
            "contracts/A.sol", "new content", "main", "update contracts/A.sol"
        )

    def test_create_file_category_detection(self, fm):
        result = fm.create_file("out/abi.json", "{}", "main")
        assert result["category"] == "artifact"

    def test_delete_file(self, fm):
        result = fm.delete_file("old.sol", "main")
        assert result["deleted"] is True
        f = fm.gl.project.files.get.return_value
        f.delete.assert_called_once()

    def test_delete_file_default_message(self, fm):
        fm.delete_file("old.sol", "main")
        f = fm.gl.project.files.get.return_value
        f.delete.assert_called_once_with(
            commit_message="delete old.sol", branch="main"
        )


# ---------------------------------------------------------------------------
# Tests: Tree operations
# ---------------------------------------------------------------------------

class TestTree:
    def test_list_tree(self, fm):
        items = fm.list_tree(branch="main")
        assert len(items) == 4
        # First item is a directory
        assert items[0]["type"] == "tree"
        assert items[0]["category"] == "directory"
        # Second is a Solidity file
        assert items[1]["type"] == "blob"
        assert items[1]["category"] == "contract"

    def test_tree_ascii(self, fm):
        tree_str = fm.tree_ascii(branch="main")
        assert "contracts" in tree_str
        assert "Token.sol" in tree_str

    def test_find_contracts(self, fm):
        contracts = fm.find_contracts(branch="main")
        assert contracts == ["contracts/Token.sol"]

    def test_find_artifacts(self, fm):
        artifacts = fm.find_artifacts(branch="main")
        assert artifacts == ["artifacts/artifact.json"]


# ---------------------------------------------------------------------------
# Tests: Batch operations
# ---------------------------------------------------------------------------

class TestBatch:
    def test_create_batch(self, fm):
        files = [
            {"path": "a.sol", "content": "code_a"},
            {"path": "b.sol", "content": "code_b"},
        ]
        results = fm.create_batch(files, "main", commit_message="Batch add")
        assert len(results) == 2
        assert fm.gl.create_file.call_count == 2

    def test_read_batch(self, fm):
        contents = fm.read_batch(["a.sol", "b.sol"], branch="main")
        assert contents == {"a.sol": "contract content", "b.sol": "contract content"}
        assert fm.gl.project.files.get.call_count == 2


# ---------------------------------------------------------------------------
# Tests: CI/CD artifacts
# ---------------------------------------------------------------------------

class TestCICD:
    def test_get_pipeline_artifacts(self, fm):
        result = fm.get_pipeline_artifacts(10)
        assert len(result) == 2
        assert result[0]["job_name"] == "compile"

    def test_get_pipeline_artifacts_filter_job(self, fm):
        result = fm.get_pipeline_artifacts(10, job_name="test")
        assert len(result) == 1
        assert result[0]["job_name"] == "test"

    def test_get_file_from_branch_exists(self, fm):
        content = fm.get_file_from_branch("contracts/Token.sol", "main")
        assert content == "contract content"

    def test_get_file_from_branch_missing(self, fm):
        fm.gl.project.files.get.side_effect = Exception("404")
        content = fm.get_file_from_branch("missing.sol", "main")
        assert content is None
