"""Integration tests for compute tier routing."""
import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from compute import (
    ComputeRouter,
    ComputeTier,
    ComputeCapability,
    CodespaceComputeBackend,
    NosanaComputeBackend,
    LocalComputeBackend,
)


class TestComputeTierSelection:
    def setup_method(self):
        self.router = ComputeRouter()

    def test_free_user_defaults_to_codespaces(self):
        """Free users with GitHub connected should get Codespaces."""
        codespace_mock = _mock_codespace_backend()
        self.router.set_codespaces_backend(codespace_mock)

        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.COMPILE},
            user_tier="free",
            github_connected=True,
        )
        assert backend.tier == ComputeTier.CODESPACES

    def test_gpu_task_routes_to_nosana(self):
        """GPU tasks always go to Nosana regardless of tier."""
        nosana_mock = _mock_nosana_backend()
        codespace_mock = _mock_codespace_backend()
        self.router.set_nosana_backend(nosana_mock)
        self.router.set_codespaces_backend(codespace_mock)

        # Free user with GPU need
        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.GPU},
            user_tier="free",
            github_connected=True,
        )
        assert backend.tier == ComputeTier.NOSANA

    def test_premium_user_defaults_to_nosana(self):
        """Premium users with Nosana available get Nosana."""
        nosana_mock = _mock_nosana_backend()
        codespace_mock = _mock_codespace_backend()
        self.router.set_nosana_backend(nosana_mock)
        self.router.set_codespaces_backend(codespace_mock)

        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.TEST},
            user_tier="premium",
        )
        assert backend.tier == ComputeTier.NOSANA

    def test_escalation_codespaces_to_nosana(self):
        """When Codespaces unavailable, escalate to Nosana."""
        nosana_mock = _mock_nosana_backend()
        self.router.set_nosana_backend(nosana_mock)
        # No Codespaces backend set

        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.COMPILE},
            user_tier="free",
            github_connected=False,
        )
        assert backend.tier == ComputeTier.NOSANA

    def test_full_fallback_chain(self):
        """When nothing available, falls to local."""
        router = ComputeRouter()
        # Nothing configured

        backend = router.select_backend(
            required_capabilities={ComputeCapability.SHELL},
            user_tier="free",
        )
        assert backend.tier == ComputeTier.LOCAL

    def test_nosana_available_when_both_tiers_configured(self):
        """Premium with both tiers -> Nosana wins."""
        nosana_mock = _mock_nosana_backend()
        codespace_mock = _mock_codespace_backend()
        self.router.set_nosana_backend(nosana_mock)
        self.router.set_codespaces_backend(codespace_mock)

        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.COMPILE},
            user_tier="premium",
        )
        assert backend.tier == ComputeTier.NOSANA

    def test_compile_capability_no_gpu(self):
        """Compile tasks (non-GPU) should not force Nosana."""
        codespace_mock = _mock_codespace_backend()
        self.router.set_codespaces_backend(codespace_mock)

        backend = self.router.select_backend(
            required_capabilities={ComputeCapability.COMPILE},
            user_tier="free",
            github_connected=True,
        )
        assert backend.tier == ComputeTier.CODESPACES

    def test_all_capabilities_on_codespaces(self):
        """Codespaces supports compile, test, deploy, shell — not GPU."""
        codespace_mock = _mock_codespace_backend()
        assert ComputeCapability.GPU not in codespace_mock.capabilities
        assert ComputeCapability.COMPILE in codespace_mock.capabilities
        assert ComputeCapability.TEST in codespace_mock.capabilities
        assert ComputeCapability.DEPLOY in codespace_mock.capabilities
        assert ComputeCapability.SHELL in codespace_mock.capabilities

    def test_all_capabilities_on_nosana(self):
        """Nosana supports all capabilities including GPU."""
        nosana_mock = _mock_nosana_backend()
        assert ComputeCapability.GPU in nosana_mock.capabilities


def _mock_codespace_backend():
    mock = __import__("unittest.mock").mock.MagicMock(spec=CodespaceComputeBackend)
    mock.tier = ComputeTier.CODESPACES
    mock.capabilities = {ComputeCapability.COMPILE, ComputeCapability.TEST, ComputeCapability.DEPLOY, ComputeCapability.SHELL}
    mock.is_available = lambda: True
    return mock


def _mock_nosana_backend():
    mock = __import__("unittest.mock").mock.MagicMock(spec=NosanaComputeBackend)
    mock.tier = ComputeTier.NOSANA
    mock.capabilities = {ComputeCapability.COMPILE, ComputeCapability.TEST, ComputeCapability.GPU, ComputeCapability.DEPLOY, ComputeCapability.SHELL}
    mock.is_available = lambda: True
    return mock
