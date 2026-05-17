"""Test framework detector and output parser agent.

Replaces the hardcoded `forge test` in testing_router.py:85-86
with auto-detection of Foundry, Hardhat, Truffle, or Brownie.
"""

import os
import subprocess
from pydantic import BaseModel, Field
from typing import Optional


class TestFramework(BaseModel):
    """Detected test framework configuration."""
    name: str = Field(description="Framework name: foundry, hardhat, truffle, brownie")
    test_command: list[str] = Field(description="Command to run tests")
    test_pattern: str = Field(description="Glob pattern for test files")
    gas_report_flag: list[str] = Field(default_factory=list, description="Flag to enable gas reporting")
    config_file: str = Field(default="", description="Configuration file path")


_FRAMEWORKS = {
    "foundry": TestFramework(
        name="foundry",
        test_command=["forge", "test"],
        test_pattern="test/**/*.t.sol",
        gas_report_flag=["--gas-report"],
        config_file="foundry.toml",
    ),
    "hardhat": TestFramework(
        name="hardhat",
        test_command=["npx", "hardhat", "test"],
        test_pattern="test/**/*.test.ts",
        gas_report_flag=[],  # Gas reporter configured in hardhat.config
        config_file="hardhat.config.ts",
    ),
    "truffle": TestFramework(
        name="truffle",
        test_command=["npx", "truffle", "test"],
        test_pattern="test/**/*.js",
        gas_report_flag=[],
        config_file="truffle-config.js",
    ),
    "brownie": TestFramework(
        name="brownie",
        test_command=["brownie", "test"],
        test_pattern="tests/**/*.py",
        gas_report_flag=["--gas"],
        config_file="brownie-config.yaml",
    ),
}


def detect_test_framework(project_root: str = ".") -> Optional[TestFramework]:
    """
    Detect the test framework used in a project.

    Checks for configuration files and test file patterns.

    Args:
        project_root: Root directory of the project

    Returns:
        Detected TestFramework or None.
    """
    for name, framework in _FRAMEWORKS.items():
        # Check for config file
        config_path = os.path.join(project_root, framework.config_file)
        if os.path.exists(config_path):
            return framework

        # Check for test files matching pattern
        import glob
        pattern = os.path.join(project_root, framework.test_pattern)
        if glob.glob(pattern):
            return framework

    # Default to foundry (most common for Solidity)
    return _FRAMEWORKS.get("foundry")


def parse_test_output(
    raw_output: str,
    framework: str = "foundry",
) -> dict:
    """
    Parse test output from a framework into structured data.

    Args:
        raw_output: Raw stdout from test execution
        framework: "foundry", "hardhat", "truffle", "brownie"

    Returns:
        Structured test results dict.
    """
    if framework == "foundry":
        return _parse_foundry(raw_output)
    elif framework == "hardhat":
        return _parse_hardhat(raw_output)
    elif framework == "truffle":
        return _parse_truffle(raw_output)
    elif framework == "brownie":
        return _parse_brownie(raw_output)

    # Generic fallback
    return _parse_generic(raw_output)


def _parse_foundery(raw: str) -> dict:
    """Parse Foundry (forge) test output."""
    lines = raw.strip().split("\n")
    passed = "PASS" in raw
    failed = "FAIL" in raw

    tests_run = raw.count("[PASS]") + raw.count("[FAIL]") + raw.count("[SKIP]")
    passing = raw.count("[PASS]")
    failing = raw.count("[FAIL]")
    skipped = raw.count("[SKIP]")

    # Extract gas data if --gas-report was used
    gas_report = {}
    for line in lines:
        if "gas" in line.lower() and ":" in line:
            parts = line.split(":")
            if len(parts) >= 2:
                try:
                    gas_report[parts[0].strip()] = int(parts[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass

    return {
        "framework": "foundry",
        "success": passed and not failed,
        "tests_run": tests_run,
        "passing": passing,
        "failing": failing,
        "skipped": skipped,
        "gas_report": gas_report,
        "raw_output": raw[:2000],
    }


def _parse_hardhat(raw: str) -> dict:
    """Parse Hardhat/Mocha test output."""
    passing = raw.count("passing")
    failing = raw.count("failing")
    pending = raw.count("pending")

    # Try to extract numbers
    import re
    passing_match = re.search(r"(\d+) passing", raw)
    failing_match = re.search(r"(\d+) failing", raw)
    pending_match = re.search(r"(\d+) pending", raw)

    return {
        "framework": "hardhat",
        "success": failing == 0,
        "tests_run": (int(passing_match.group(1)) if passing_match else 0) +
                     (int(failing_match.group(1)) if failing_match else 0) +
                     (int(pending_match.group(1)) if pending_match else 0),
        "passing": int(passing_match.group(1)) if passing_match else 0,
        "failing": int(failing_match.group(1)) if failing_match else 0,
        "skipped": int(pending_match.group(1)) if pending_match else 0,
        "gas_report": {},
        "raw_output": raw[:2000],
    }


def _parse_truffle(raw: str) -> dict:
    """Parse Truffle test output."""
    return _parse_hardhat(raw)  # Similar Mocha-based format


def _parse_brownie(raw: str) -> dict:
    """Parse Brownie (pytest) test output."""
    import re
    passed_match = re.search(r"(\d+) passed", raw)
    failed_match = re.search(r"(\d+) failed", raw)
    error_match = re.search(r"(\d+) error", raw)

    return {
        "framework": "brownie",
        "success": not failed_match and not error_match,
        "tests_run": (int(passed_match.group(1)) if passed_match else 0) +
                     (int(failed_match.group(1)) if failed_match else 0) +
                     (int(error_match.group(1)) if error_match else 0),
        "passing": int(passed_match.group(1)) if passed_match else 0,
        "failing": int(failed_match.group(1)) if failed_match else 0,
        "skipped": 0,
        "gas_report": {},
        "raw_output": raw[:2000],
    }


def _parse_generic(raw: str) -> dict:
    """Generic fallback parser."""
    return {
        "framework": "unknown",
        "success": "fail" not in raw.lower() or "error" not in raw.lower(),
        "tests_run": 0,
        "passing": raw.lower().count("pass"),
        "failing": raw.lower().count("fail"),
        "skipped": 0,
        "gas_report": {},
        "raw_output": raw[:2000],
    }
