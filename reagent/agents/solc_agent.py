"""Solc version resolver agent.

Replaces hardcoded solc_version = "0.8.20" in nosana_router.py, nosana_client.py.
Agent resolves the appropriate Solidity compiler version based on contract pragma.
"""

import re
from typing import Optional

# Known solc version compatibility
_SOLC_VERSIONS = {
    "0.8.28": {"min_pragma": "0.8.28", "features": ["latest", "via-ir-optimizations"]},
    "0.8.27": {"min_pragma": "0.8.27", "features": ["transient", "via-ir-optimizations"]},
    "0.8.26": {"min_pragma": "0.8.26", "features": ["via-ir-optimizations"]},
    "0.8.25": {"min_pragma": "0.8.25", "features": []},
    "0.8.24": {"min_pragma": "0.8.24", "features": []},
    "0.8.23": {"min_pragma": "0.8.23", "features": []},
    "0.8.22": {"min_pragma": "0.8.22", "features": []},
    "0.8.21": {"min_pragma": "0.8.21", "features": []},
    "0.8.20": {"min_pragma": "0.8.20", "features": ["immutable-arguments"]},
    "0.8.19": {"min_pragma": "0.8.19", "features": ["user-defined-value-types"]},
    "0.8.18": {"min_pragma": "0.8.18", "features": ["using-for-global"]},
    "0.8.17": {"min_pragma": "0.8.17", "features": []},
    "0.8.13": {"min_pragma": "0.8.13", "features": []},
    "0.8.7": {"min_pragma": "0.8.7", "features": []},
    "0.8.4": {"min_pragma": "0.8.4", "features": []},
    "0.8.0": {"min_pragma": "0.8.0", "features": ["custom-errors"]},
    "0.7.6": {"min_pragma": "0.7.0", "features": []},
    "0.6.12": {"min_pragma": "0.6.0", "features": []},
}

# Recommended stable version
_DEFAULT_VERSION = "0.8.28"


def resolve_solc_version(
    contract_code: str,
    preferred_version: Optional[str] = None,
) -> str:
    """
    Resolve the appropriate Solidity compiler version for a contract.

    Parses the pragma directive and selects the latest compatible solc version.

    Args:
        contract_code: Solidity source code
        preferred_version: Preferred version if compatible

    Returns:
        Solc version string (e.g., "0.8.28").
    """
    # Extract pragma from contract
    pragma_match = re.search(r"pragma\s+solidity\s+([^\s;]+);", contract_code)
    if not pragma_match:
        # Try older pragma format
        pragma_match = re.search(r"pragma\s+solidity\s*\^?([^\s;]+);", contract_code)
    if not pragma_match:
        # Fallback to ^0.x.y format
        pragma_match = re.search(r"pragma\s+solidity\s+\^?(\d+\.\d+\.?\d*)", contract_code)

    if not pragma_match:
        return preferred_version or _DEFAULT_VERSION

    pragma = pragma_match.group(1)

    # Extract minimum version from pragma
    # Handle ^0.8.0 (>=0.8.0 <0.9.0), >=0.8.0, =0.8.20, etc.
    version_match = re.search(r"(\d+\.\d+\.?\d*)", pragma)
    if not version_match:
        return preferred_version or _DEFAULT_VERSION

    min_version = version_match.group(1)

    # If preferred version is specified, check compatibility
    if preferred_version:
        if _is_compatible(preferred_version, min_version, pragma):
            return preferred_version

    # Find the latest compatible version
    for version, info in sorted(_SOLC_VERSIONS.items(), reverse=True):
        if _is_compatible(version, min_version, pragma):
            return version

    return _DEFAULT_VERSION


def _is_compatible(version: str, min_version: str, pragma: str) -> bool:
    """Check if a solc version is compatible with a pragma constraint."""
    # Simple version comparison
    v_parts = [int(x) for x in version.split(".")]
    m_parts = [int(x) for x in min_version.split(".")]

    # Pad to 3 parts
    while len(v_parts) < 3: v_parts.append(0)
    while len(m_parts) < 3: m_parts.append(0)

    # Version must be >= minimum
    if tuple(v_parts) < tuple(m_parts):
        return False

    # Handle ^ caret constraint: ^0.8.0 means >=0.8.0 <0.9.0
    if pragma.startswith("^"):
        if pragma.startswith("^0."):
            # ^0.x.y means <0.(x+1).0
            if v_parts[0] == m_parts[0] and v_parts[1] == m_parts[1]:
                return True
            return False
        else:
            # ^x.y.z means <(x+1).0.0
            if v_parts[0] != m_parts[0]:
                return False

    return True
