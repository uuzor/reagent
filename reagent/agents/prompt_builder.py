"""Dynamic prompt builder tool.

Replaces 7 static system prompts across routers with a composable
tool that assembles context-aware prompts based on task type, style,
and security requirements.
"""

from typing import Optional

# ──────────────────────────────────────────────────────────────
# Prompt templates
# ──────────────────────────────────────────────────────────────

_BASE_PROMPTS = {
    "code": "You are an expert Solidity developer.",
    "audit": "You are a senior smart contract auditor.",
    "review": "You are a senior Solidity reviewer.",
    "plan": "You are a senior smart contract architect and planner.",
    "test": "You are an expert smart contract testing engineer.",
    "deploy": "You are a smart contract deployment engineer.",
    "ideation": "You are a smart contract product analyst.",
}

_SECURITY_LEVELS = {
    "basic": "Follow basic security practices.",
    "standard": "Follow security best practices and use OpenZeppelin libraries where appropriate.",
    "high": "Follow strict security practices. Consider reentrancy, overflow, access control, oracle manipulation, and flash loan attacks.",
    "audit": "Perform deep security analysis including formal verification considerations, economic attack vectors, and composability risks.",
}

_STYLE_GUIDES = {
    "concise": "Generate clean, minimal code with essential comments only.",
    "detailed": "Generate well-commented code with detailed explanations for each function and state variable.",
    "natspec": "Use NatSpec documentation format for all public and external functions.",
}

_FRAMEWORK_PREFS = {
    "openzeppelin": "Use OpenZeppelin libraries for standard implementations.",
    "solady": "Use Solady for gas-optimized implementations.",
    "custom": "Implement custom logic without external dependencies.",
}


def build_system_prompt(
    task_type: str = "code",
    style_guide: str = "detailed",
    security_level: str = "standard",
    library_pref: str = "openzeppelin",
    additional_instructions: Optional[str] = None,
) -> str:
    """
    Build a context-aware system prompt for code generation.

    Args:
        task_type: "code", "test", "deploy"
        style_guide: "concise", "detailed", "natspec"
        security_level: "basic", "standard", "high", "audit"
        library_pref: "openzeppelin", "solady", "custom"
        additional_instructions: Extra instructions to append

    Returns:
        Assembled system prompt string.
    """
    parts = [
        _BASE_PROMPTS.get(task_type, _BASE_PROMPTS["code"]),
        _SECURITY_LEVELS.get(security_level, _SECURITY_LEVELS["standard"]),
        _STYLE_GUIDES.get(style_guide, _STYLE_GUIDES["detailed"]),
        _FRAMEWORK_PREFS.get(library_pref, _FRAMEWORK_PREFS["openzeppelin"]),
        "Optimize for gas efficiency where possible without compromising security.",
    ]

    if additional_instructions:
        parts.append(additional_instructions)

    return "\n".join(parts)


def build_audit_prompt(
    contract_type: str = "general",
    known_risk_areas: Optional[list[str]] = None,
    compliance_requirements: Optional[list[str]] = None,
) -> str:
    """
    Build a context-aware system prompt for security audits.

    Args:
        contract_type: Type of contract (e.g., "erc20", "nft", "defi", "governance")
        known_risk_areas: Specific risk areas to focus on
        compliance_requirements: Compliance standards to check

    Returns:
        Assembled audit system prompt.
    """
    parts = [
        _BASE_PROMPTS["audit"],
        "Analyze code for vulnerabilities, gas optimization, and best practices.",
    ]

    # Contract-type-specific guidance
    type_guidance = {
        "erc20": "Focus on transfer mechanics, totalSupply invariants, and approval patterns.",
        "nft": "Focus on ownership tracking, transfer mechanics, and royalty implementations.",
        "defi": "Focus on price oracle manipulation, flash loan attacks, slippage, and liquidity risks.",
        "governance": "Focus on voting mechanisms, proposal lifecycle, timelocks, and privilege escalation.",
        "bridge": "Focus on message verification, replay protection, and cross-chain state consistency.",
    }
    if contract_type in type_guidance:
        parts.append(type_guidance[contract_type])

    if known_risk_areas:
        parts.append(f"Pay special attention to: {', '.join(known_risk_areas)}.")

    if compliance_requirements:
        parts.append(f"Verify compliance with: {', '.join(compliance_requirements)}.")

    return "\n".join(parts)


def build_review_prompt(
    review_scope: str = "general",
    severity_threshold: str = "medium",
    checklist: Optional[list[str]] = None,
) -> str:
    """
    Build a system prompt for code review.

    Args:
        review_scope: "general", "security", "gas", "style"
        severity_threshold: Minimum severity to report ("low", "medium", "high", "critical")
        checklist: Specific items to check

    Returns:
        Assembled review system prompt.
    """
    parts = [
        _BASE_PROMPTS["review"],
        f"Review scope: {review_scope}. Report issues at {severity_threshold} severity or above.",
    ]

    scope_focus = {
        "security": "Prioritize security vulnerabilities, access control issues, and attack vectors.",
        "gas": "Prioritize gas optimization opportunities, storage patterns, and expensive operations.",
        "style": "Prioritize code style consistency, naming conventions, and documentation quality.",
    }
    if scope_focus.get(review_scope):
        parts.append(scope_focus[review_scope])

    if checklist:
        parts.append(f"Checklist: {'; '.join(checklist)}.")

    return "\n".join(parts)


def build_planning_prompt(
    domain: str = "general",
    complexity_level: str = "detailed",
    team_size: str = "solo",
) -> str:
    """
    Build a system prompt for development planning.

    Args:
        domain: Contract domain (e.g., "defi", "nft", "governance")
        complexity_level: "summary", "detailed", "comprehensive"
        team_size: "solo", "small", "enterprise"

    Returns:
        Assembled planning system prompt.
    """
    parts = [
        _BASE_PROMPTS["plan"],
        "Analyze requirements and produce a detailed development plan.",
        "Focus on security best practices, gas optimization, and proven patterns.",
        "Be specific about ERC standards, architecture decisions, and risk mitigation.",
    ]

    depth_guidance = {
        "summary": "Provide a high-level overview with key milestones only.",
        "detailed": "Provide step-by-step plan with specific implementation details.",
        "comprehensive": "Provide exhaustive plan including edge cases, testing strategy, and deployment checklist.",
    }
    if depth_guidance.get(complexity_level):
        parts.append(depth_guidance[complexity_level])

    team_guidance = {
        "solo": "Optimize for a single developer — minimize complexity and dependencies.",
        "small": "Designed for a small team — include code review and testing steps.",
        "enterprise": "Designed for enterprise — include formal audit, compliance, and CI/CD steps.",
    }
    if team_guidance.get(team_size):
        parts.append(team_guidance[team_size])

    return "\n".join(parts)
