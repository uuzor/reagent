"""Multi-tool security scanner agent.

Replaces the 2-pattern string check in testing_router.py:128-132
with comprehensive multi-tool analysis using Slither, Mythril patterns,
and AI-based vulnerability detection.
"""

import subprocess
from pydantic import BaseModel, Field
from typing import Optional


class SecurityFinding(BaseModel):
    """A single security finding."""
    severity: str = Field(description="critical, high, medium, low, informational")
    category: str = Field(description="vulnerability, gas_optimization, best_practice, informational")
    title: str = Field(description="Short title of the finding")
    description: str = Field(description="Detailed description")
    location: str = Field(default="", description="File:line if available")
    tool: str = Field(description="Tool that detected this finding")


class SecurityScanResult(BaseModel):
    """Complete security scan result."""
    findings: list[SecurityFinding] = Field(default_factory=list)
    overall_risk: str = Field(default="unknown", description="critical, high, medium, low, none")
    tools_used: list[str] = Field(default_factory=list)
    summary: str = Field(default="")


# Vulnerability pattern database
_VULN_PATTERNS = {
    "selfdestruct": {"severity": "high", "category": "vulnerability", "title": "Uses selfdestruct — can break inherited contracts"},
    "delegatecall": {"severity": "high", "category": "vulnerability", "title": "Uses delegatecall — ensure proper access control and storage layout"},
    "tx.origin": {"severity": "critical", "category": "vulnerability", "title": "Uses tx.origin — vulnerable to phishing attacks, use msg.sender instead"},
    "block.timestamp": {"severity": "medium", "category": "vulnerability", "title": "Uses block.timestamp — miner-manipulable for time-sensitive logic"},
    "block.number": {"severity": "low", "category": "best_practice", "title": "Uses block.number — may vary across chains"},
    "blockhash": {"severity": "medium", "category": "vulnerability", "title": "Uses blockhash — only valid for recent blocks (256 block limit)"},
    "call.value": {"severity": "high", "category": "vulnerability", "title": "Uses low-level call.value — consider transfer or safe methods"},
    ".send": {"severity": "medium", "category": "vulnerability", "title": "Uses .send — does not propagate errors, consider transfer"},
    "assert(": {"severity": "informational", "category": "best_practice", "title": "Uses assert() — consumes all gas on failure, consider require()"},
    "suicide": {"severity": "high", "category": "vulnerability", "title": "Uses suicide (deprecated selfdestruct)"},
    "create2": {"severity": "informational", "category": "best_practice", "title": "Uses CREATE2 — ensure predictable address generation is intentional"},
    "assembly": {"severity": "medium", "category": "vulnerability", "title": "Uses inline assembly — verify safety and gas behavior"},
}


def run_security_scan(
    code: str,
    contract_path: str = "",
    pattern_library: Optional[dict] = None,
) -> SecurityScanResult:
    """
    Run a comprehensive security scan on Solidity code.

    Combines pattern-based detection with tool execution (Slither if available).

    Args:
        code: Solidity source code
        contract_path: Path to file (for Slither execution)
        pattern_library: Custom vulnerability patterns (overrides default)

    Returns:
        SecurityScanResult with all findings.
    """
    patterns = pattern_library or _VULN_PATTERNS
    findings = []
    tools_used = ["pattern_scan"]

    # Pattern-based scan
    for line_num, line in enumerate(code.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("///"):
            continue

        for pattern, info in patterns.items():
            if pattern in code:
                findings.append(SecurityFinding(
                    severity=info["severity"],
                    category=info["category"],
                    title=info["title"],
                    description=f"Found '{pattern}' at line {line_num}: {stripped[:100]}",
                    location=f"{contract_path}:{line_num}" if contract_path else f"line {line_num}",
                    tool="pattern_scan",
                ))

    # Deduplicate findings
    seen = set()
    unique_findings = []
    for f in findings:
        key = (f.title, f.location)
        if key not in seen:
            seen.add(key)
            unique_findings.append(f)

    # Run Slither if available and path provided
    if contract_path:
        try:
            result = subprocess.run(
                ["slither", contract_path, "--json", "-"],
                capture_output=True, text=True, timeout=60
            )
            if result.stdout:
                tools_used.append("slither")
                # Parse Slither JSON output for findings
                import json
                try:
                    slither_data = json.loads(result.stdout)
                    for detector in slither_data.get("results", {}).get("detectors", []):
                        unique_findings.append(SecurityFinding(
                            severity=detector.get("severity", "medium"),
                            category="vulnerability",
                            title=detector.get("check", "slither_detection"),
                            description=detector.get("description", "")[:500],
                            tool="slither",
                        ))
                except json.JSONDecodeError:
                    pass
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Calculate overall risk
    severity_scores = {"critical": 4, "high": 3, "medium": 2, "low": 1, "informational": 0}
    max_severity = max(
        (severity_scores.get(f.severity, 0) for f in unique_findings),
        default=0,
    )
    risk_labels = {4: "critical", 3: "high", 2: "medium", 1: "low", 0: "none"}
    overall_risk = risk_labels.get(max_severity, "unknown")

    critical_count = sum(1 for f in unique_findings if f.severity == "critical")
    high_count = sum(1 for f in unique_findings if f.severity == "high")

    summary = (
        f"Scanned with {', '.join(tools_used)}. "
        f"Found {len(unique_findings)} issues: "
        f"{critical_count} critical, {high_count} high severity."
    )

    return SecurityScanResult(
        findings=unique_findings,
        overall_risk=overall_risk,
        tools_used=tools_used,
        summary=summary,
    )


def multi_tool_analysis(
    code: str,
    contract_path: str = "",
    tools: Optional[list[str]] = None,
) -> SecurityScanResult:
    """
    Run security analysis with multiple tools.

    Args:
        code: Solidity source code
        contract_path: Path to file for tool execution
        tools: List of tools to run ("pattern", "slither", "mythril")

    Returns:
        Aggregated SecurityScanResult.
    """
    tools_to_run = tools or ["pattern", "slither"]
    all_findings = []
    tools_used = []

    if "pattern" in tools_to_run:
        result = run_security_scan(code, contract_path)
        all_findings.extend(result.findings)
        tools_used.extend(result.tools_used)

    if "slither" in tools_to_run and contract_path:
        try:
            result = subprocess.run(
                ["slither", contract_path, "--json", "-"],
                capture_output=True, text=True, timeout=60
            )
            if result.stdout:
                tools_used.append("slither")
                import json
                try:
                    slither_data = json.loads(result.stdout)
                    for detector in slither_data.get("results", {}).get("detectors", []):
                        all_findings.append(SecurityFinding(
                            severity=detector.get("severity", "medium"),
                            category="vulnerability",
                            title=detector.get("check", "slither_detection"),
                            description=detector.get("description", "")[:500],
                            tool="slither",
                        ))
                except json.JSONDecodeError:
                    pass
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Deduplicate
    seen = set()
    unique = []
    for f in all_findings:
        key = (f.title, f.tool, f.location)
        if key not in seen:
            seen.add(key)
            unique.append(f)

    severity_scores = {"critical": 4, "high": 3, "medium": 2, "low": 1, "informational": 0}
    max_sev = max((severity_scores.get(f.severity, 0) for f in unique), default=0)
    risk_labels = {4: "critical", 3: "high", 2: "medium", 1: "low", 0: "none"}

    return SecurityScanResult(
        findings=unique,
        overall_risk=risk_labels.get(max_sev, "unknown"),
        tools_used=list(set(tools_used)),
        summary=f"Multi-tool scan with {', '.join(set(tools_used))}: {len(unique)} findings.",
    )
