"""ERC compliance validator agent.

Replaces the hardcoded string-based ERC checks in auditing_router.py:126-143.
Uses comprehensive pattern matching for ERC-20, ERC-721, ERC-1155, ERC-4626, and more.
"""

from pydantic import BaseModel, Field
from typing import Optional

# ERC standard requirements — required functions, events, and patterns
_ERC_STANDARDS = {
    "ERC-20": {
        "functions": ["totalSupply", "balanceOf", "transfer", "approve", "allowance", "transferFrom"],
        "events": ["Transfer", "Approval"],
        "patterns": ["uint256", "address"],
        "description": "Fungible token standard",
    },
    "ERC-721": {
        "functions": ["balanceOf", "ownerOf", "transferFrom", "approve", "setApprovalForAll", "getApproved", "isApprovedForAll"],
        "events": ["Transfer", "Approval", "ApprovalForAll"],
        "patterns": ["uint256", "address", "tokenURI"],
        "description": "Non-fungible token standard",
    },
    "ERC-1155": {
        "functions": ["balanceOf", "balanceOfBatch", "safeTransferFrom", "safeBatchTransferFrom", "setApprovalForAll", "isApprovedForAll"],
        "events": ["TransferSingle", "TransferBatch", "ApprovalForAll", "URI"],
        "patterns": ["uint256", "address", "id"],
        "description": "Multi-token standard",
    },
    "ERC-4626": {
        "functions": ["asset", "totalAssets", "convertToShares", "convertToAssets", "maxDeposit", "maxMint", "maxWithdraw", "maxRedeem", "deposit", "mint", "withdraw", "redeem"],
        "events": ["Deposit", "Withdraw"],
        "patterns": ["uint256", "address", "shares", "assets"],
        "description": "Tokenized vault standard",
    },
    "ERC-2612": {
        "functions": ["permit", "nonces", "DOMAIN_SEPARATOR", "approve", "allowance"],
        "events": ["Approval"],
        "patterns": ["permit", "deadline", "v", "r", "s"],
        "description": "ERC-20 permit extension (gasless approvals)",
    },
    "ERC-777": {
        "functions": ["name", "symbol", "totalSupply", "balanceOf", "transfer", "burn", "send", "operatorSend", "operatorBurn", "isOperatorFor", "authorizeOperator", "revokeOperator"],
        "events": ["Sent", "Burned", "Minted", "AuthorizedOperator", "RevokedOperator"],
        "patterns": ["bytes", "userData", "operatorData"],
        "description": "Advanced token standard with hooks",
    },
}


class ERCComplianceResult(BaseModel):
    """Result of ERC compliance check for a single standard."""
    standard: str
    compliant: bool
    compliance_score: float = Field(ge=0, le=100)
    missing_functions: list[str] = Field(default_factory=list)
    missing_events: list[str] = Field(default_factory=list)
    present_functions: list[str] = Field(default_factory=list)
    description: str = ""


class ComplianceReport(BaseModel):
    """Complete compliance report across all checked standards."""
    results: list[ERCComplianceResult] = Field(default_factory=list)
    overall_score: float = Field(ge=0, le=100)
    likely_standard: str = Field(default="unknown")


def validate_erc_compliance(
    code: str,
    standards: Optional[list[str]] = None,
) -> ComplianceReport:
    """
    Validate Solidity code against ERC standards using pattern analysis.

    Checks for required functions, events, and structural patterns.

    Args:
        code: Solidity source code
        standards: List of ERC standards to check (checks all if None)

    Returns:
        ComplianceReport with per-standard results.
    """
    standards_to_check = standards or list(_ERC_STANDARDS.keys())
    results = []
    scores = []

    for standard in standards_to_check:
        spec = _ERC_STANDARDS.get(standard)
        if not spec:
            results.append(ERCComplianceResult(
                standard=standard,
                compliant=False,
                compliance_score=0,
                description=f"Unknown standard: {standard}",
            ))
            continue

        # Check functions
        missing_functions = []
        present_functions = []
        for func in spec["functions"]:
            # Look for function declaration patterns
            if f"function {func}" in code or f"function  {func}" in code:
                present_functions.append(func)
            else:
                missing_functions.append(func)

        # Check events
        missing_events = []
        for event in spec["events"]:
            if f"event {event}" in code or f"emit {event}" in code:
                pass  # Event declared or emitted
            else:
                missing_events.append(event)

        # Check structural patterns
        pattern_score = sum(1 for p in spec["patterns"] if p in code) / max(len(spec["patterns"]), 1)

        # Calculate compliance score
        func_score = len(present_functions) / max(len(spec["functions"]), 1)
        event_score = 1.0 - (len(missing_events) / max(len(spec["events"]), 1))
        total_score = round((func_score * 0.6 + event_score * 0.2 + pattern_score * 0.2) * 100, 1)

        compliant = len(missing_functions) == 0 and len(missing_events) == 0

        results.append(ERCComplianceResult(
            standard=standard,
            compliant=compliant,
            compliance_score=total_score,
            missing_functions=missing_functions,
            missing_events=missing_events,
            present_functions=present_functions,
            description=spec["description"],
        ))
        scores.append(total_score)

    # Determine likely standard (highest score)
    likely_standard = "unknown"
    if results:
        best = max(results, key=lambda r: r.compliance_score)
        if best.compliance_score > 50:
            likely_standard = best.standard

    return ComplianceReport(
        results=results,
        overall_score=round(sum(scores) / max(len(scores), 1), 1),
        likely_standard=likely_standard,
    )
