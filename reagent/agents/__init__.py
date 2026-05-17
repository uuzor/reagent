"""Agent tool layer — replaces hardcoded patterns with AI-driven tools.

Each tool is a function that can be called by LangChain agents or directly
by the graph nodes. Tools are organized by domain.
"""

from .compute_agent import select_compute_backend, get_backend_info
from .retry_agent import decide_retry_count, classify_error
from .prompt_builder import build_system_prompt, build_audit_prompt, build_review_prompt, build_planning_prompt
from .blockchain_agent import recommend_blockchain, resolve_network, get_block_explorer_url
from .file_agent import determine_file_structure, generate_branch_name, classify_file
from .security_agent import run_security_scan, multi_tool_analysis
from .erc_agent import validate_erc_compliance
from .test_agent import detect_test_framework, parse_test_output
from .pricing_agent import get_model_pricing, get_cost_summary
from .context_agent import score_context_relevance, calculate_context_budget
from .solc_agent import resolve_solc_version
from .devconfig_agent import generate_devcontainer_config, select_codespace_machine
from .port_agent import find_available_port

__all__ = [
    # Compute
    "select_compute_backend",
    "get_backend_info",
    # Retry
    "decide_retry_count",
    "classify_error",
    # Prompts
    "build_system_prompt",
    "build_audit_prompt",
    "build_review_prompt",
    "build_planning_prompt",
    # Blockchain
    "recommend_blockchain",
    "resolve_network",
    "get_block_explorer_url",
    # File
    "determine_file_structure",
    "generate_branch_name",
    "classify_file",
    # Security
    "run_security_scan",
    "multi_tool_analysis",
    # ERC
    "validate_erc_compliance",
    # Test
    "detect_test_framework",
    "parse_test_output",
    # Pricing
    "get_model_pricing",
    "get_cost_summary",
    # Context
    "score_context_relevance",
    "calculate_context_budget",
    # Solc
    "resolve_solc_version",
    # Devconfig
    "generate_devcontainer_config",
    "select_codespace_machine",
    # Port
    "find_available_port",
]
