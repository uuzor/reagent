"""Tests for the compute abstraction layer."""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from compute import (
    ComputeTier,
    ComputeCapability,
    ComputeResult,
    ComputeRouter,
    CodespaceComputeBackend,
    NosanaComputeBackend,
    LocalComputeBackend,
    get_compute_router,
)


class TestComputeModels:
    def test_compute_result_success(self):
        result = ComputeResult(
            exit_code=0, stdout="ok", stderr="", success=True, backend=ComputeTier.LOCAL
        )
        assert result.success
        assert result.backend == ComputeTier.LOCAL

    def test_compute_result_failure(self):
        result = ComputeResult(
            exit_code=1, stdout="", stderr="error", success=False, backend=ComputeTier.NOSANA
        )
        assert not result.success
        assert result.backend == ComputeTier.NOSANA


class TestComputeRouterTierSelection:
    def setup_method(self):
        self.router = ComputeRouter()

    def test_gpu_always_nosana(self):
        """GPU tasks always route to Nosana when available."""
        nosana_mock = MagicMock(spec=NosanaComputeBackend)
        nosana_mock.tier = ComputeTier.NOSANA
        self.router.set_nosana_backend(nosana_mock)

        codespace_mock = MagicMock(spec=CodespaceComputeBackend)
        codespace_mock.tier = ComputeTier.CODESPACES
        self.router.set_codespaces_backend(codespace_mock)

        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.GPU, ComputeCapability.COMPILE},
            user_tier="free",
            github_connected=True,
        )
        assert backend.tier == ComputeTier.NOSANA

    def test_free_user_codespaces(self):
        """Free users with Codespaces connected get Codespaces backend."""
        codespace_mock = MagicMock(spec=CodespaceComputeBackend)
        codespace_mock.tier = ComputeTier.CODESPACES
        self.router.set_codespaces_backend(codespace_mock)

        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.COMPILE},
            user_tier="free",
            github_connected=True,
        )
        assert backend.tier == ComputeTier.CODESPACES

    def test_free_user_no_codespaces_falls_to_nosana_if_available(self):
        """Free users without Codespaces but with Nosana available get Nosana."""
        nosana_mock = MagicMock(spec=NosanaComputeBackend)
        nosana_mock.tier = ComputeTier.NOSANA
        self.router.set_nosana_backend(nosana_mock)

        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.COMPILE},
            user_tier="free",
            github_connected=False,
        )
        assert backend.tier == ComputeTier.NOSANA

    def test_free_user_no_codespaces_no_nosana_falls_to_local(self):
        """Free users without any cloud backend get local."""
        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.COMPILE},
            user_tier="free",
            github_connected=False,
        )
        assert backend.tier == ComputeTier.LOCAL

    def test_premium_user_nosana(self):
        """Premium users get Nosana when available."""
        nosana_mock = MagicMock(spec=NosanaComputeBackend)
        nosana_mock.tier = ComputeTier.NOSANA
        self.router.set_nosana_backend(nosana_mock)

        codespace_mock = MagicMock(spec=CodespaceComputeBackend)
        codespace_mock.tier = ComputeTier.CODESPACES
        self.router.set_codespaces_backend(codespace_mock)

        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.COMPILE},
            user_tier="premium",
        )
        assert backend.tier == ComputeTier.NOSANA

    def test_premium_user_no_nosana_falls_to_codespaces(self):
        """Premium users without Nosana fall back to Codespaces."""
        codespace_mock = MagicMock(spec=CodespaceComputeBackend)
        codespace_mock.tier = ComputeTier.CODESPACES
        self.router.set_codespaces_backend(codespace_mock)

        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.COMPILE},
            user_tier="premium",
        )
        assert backend.tier == ComputeTier.CODESPACES

    def test_no_backends_local_fallback(self):
        """No backends configured returns local."""
        backend = self.router.select_backend(
            required_capabilities=set(),
            user_tier="free",
        )
        assert backend.tier == ComputeTier.LOCAL

    def test_gpu_without_nosana_falls_to_local(self):
        """GPU task without Nosana falls to local (with warning)."""
        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.GPU},
            user_tier="free",
        )
        assert backend.tier == ComputeTier.LOCAL


class TestLocalComputeBackend:
    def setup_method(self):
        self.backend = LocalComputeBackend()

    @pytest.mark.asyncio
    async def test_execute_success(self):
        result = await self.backend.execute("echo hello")
        assert result.success
        assert "hello" in result.stdout
        assert result.backend == ComputeTier.LOCAL

    @pytest.mark.asyncio
    async def test_execute_failure(self):
        result = await self.backend.execute("exit 1")
        assert not result.success
        assert result.exit_code == 1

    @pytest.mark.asyncio
    async def test_is_available(self):
        assert await self.backend.is_available()

    @pytest.mark.asyncio
    async def test_upload_download_file(self, tmp_path):
        file_path = str(tmp_path / "test.txt")
        await self.backend.upload_file(file_path, "test content")
        content = await self.backend.download_file(file_path)
        assert content == "test content"


class TestGetComputeRouter:
    def test_singleton(self):
        router1 = get_compute_router()
        router2 = get_compute_router()
        assert router1 is router2
