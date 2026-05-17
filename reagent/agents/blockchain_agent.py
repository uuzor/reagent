"""Blockchain recommendation agent.

Replaces hardcoded defaults (ethereum, sepolia, mainnet) across 8+ files.
Agent recommends blockchain and network based on use case, cost, and throughput needs.
"""

from pydantic import BaseModel, Field

# Blockchain registry
_BLOCKCHAINS = {
    "ethereum": {
        "security": 10, "cost": "high", "throughput": "low",
        "testnet": "sepolia", "mainnet_alias": "mainnet",
        "chain_id": 1, "gas_token": "ETH",
        "best_for": ["high-value", "defi", "nft-premium", "governance"],
    },
    "polygon": {
        "security": 7, "cost": "low", "throughput": "high",
        "testnet": "amoy", "mainnet_alias": "mainnet",
        "chain_id": 137, "gas_token": "MATIC",
        "best_for": ["gaming", "nft-mass", "social", "micropayments"],
    },
    "arbitrum": {
        "security": 9, "cost": "medium", "throughput": "high",
        "testnet": "sepolia", "mainnet_alias": "mainnet",
        "chain_id": 42161, "gas_token": "ETH",
        "best_for": ["defi", "dex", "lending", "derivatives"],
    },
    "optimism": {
        "security": 9, "cost": "medium", "throughput": "high",
        "testnet": "sepolia", "mainnet_alias": "mainnet",
        "chain_id": 10, "gas_token": "ETH",
        "best_for": ["defi", "social", "identity"],
    },
    "base": {
        "security": 9, "cost": "low", "throughput": "high",
        "testnet": "sepolia", "mainnet_alias": "mainnet",
        "chain_id": 8453, "gas_token": "ETH",
        "best_for": ["consumer-apps", "social", "gaming"],
    },
    "avalanche": {
        "security": 8, "cost": "low", "throughput": "high",
        "testnet": "fuji", "mainnet_alias": "mainnet",
        "chain_id": 43114, "gas_token": "AVAX",
        "best_for": ["gaming", "defi", "enterprise"],
    },
    "bnb": {
        "security": 7, "cost": "low", "throughput": "medium",
        "testnet": "testnet", "mainnet_alias": "mainnet",
        "chain_id": 56, "gas_token": "BNB",
        "best_for": ["defi", "nft", "trading"],
    },
}


class BlockchainRecommendation(BaseModel):
    """Recommendation for blockchain selection."""
    blockchain: str = Field(description="Recommended blockchain")
    testnet: str = Field(description="Recommended test network")
    chain_id: int = Field(description="Chain ID")
    gas_token: str = Field(description="Native gas token")
    reason: str = Field(description="Why this blockchain was recommended")


def recommend_blockchain(
    use_case: str = "general",
    cost_preference: str = "medium",  # low, medium, high
    throughput_need: str = "medium",  # low, medium, high
    security_need: int = 7,  # 1-10
) -> BlockchainRecommendation:
    """
    Recommend a blockchain based on use case and constraints.

    Args:
        use_case: Application domain (e.g., "defi", "nft", "gaming", "governance")
        cost_preference: Preferred gas cost level
        throughput_need: Required transaction throughput
        security_need: Required security level (1-10)

    Returns:
        BlockchainRecommendation with selection and reasoning.
    """
    scored = []
    for name, info in _BLOCKCHAINS.items():
        score = 0

        # Use case match
        if use_case in info["best_for"] or use_case == "general":
            score += 3

        # Cost match
        cost_map = {"low": 2, "medium": 1, "high": 0}
        if info["cost"] == cost_preference:
            score += cost_map.get(cost_preference, 0)

        # Throughput match
        tp_map = {"low": 1, "medium": 2, "high": 3}
        if info["throughput"] == throughput_need:
            score += tp_map.get(throughput_need, 0)

        # Security threshold
        if info["security"] >= security_need:
            score += info["security"]

        scored.append((name, score, info))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    if scored:
        name, _, info = scored[0]
        return BlockchainRecommendation(
            blockchain=name,
            testnet=info["testnet"],
            chain_id=info["chain_id"],
            gas_token=info["gas_token"],
            reason=f"Best match for {use_case} with {cost_preference} cost preference (score: {scored[0][1]})",
        )

    # Fallback to Ethereum
    eth = _BLOCKCHAINS["ethereum"]
    return BlockchainRecommendation(
        blockchain="ethereum",
        testnet=eth["testnet"],
        chain_id=eth["chain_id"],
        gas_token=eth["gas_token"],
        reason="Default fallback to Ethereum",
    )


def resolve_network(network_alias: str, blockchain: str = "ethereum") -> str:
    """
    Resolve a network alias to its canonical name.

    Args:
        network_alias: "mainnet", "testnet", "sepolia", etc.
        blockchain: Target blockchain

    Returns:
        Canonical network name.
    """
    info = _BLOCKCHAINS.get(blockchain, _BLOCKCHAINS["ethereum"])

    aliases = {
        "main": info["mainnet_alias"],
        "mainnet": info["mainnet_alias"],
        "test": info["testnet"],
        "testnet": info["testnet"],
        "dev": "localhost",
        "local": "localhost",
    }

    return aliases.get(network_alias.lower(), network_alias)


def get_block_explorer_url(network: str, blockchain: str = "ethereum") -> str:
    """Get the block explorer URL for a network."""
    explorers = {
        "ethereum": {
            "mainnet": "https://etherscan.io",
            "sepolia": "https://sepolia.etherscan.io",
            "holesky": "https://holesky.etherscan.io",
        },
        "polygon": {
            "mainnet": "https://polygonscan.com",
            "amoy": "https://amoy.polygonscan.com",
        },
        "arbitrum": {
            "mainnet": "https://arbiscan.io",
            "sepolia": "https://sepolia.arbiscan.io",
        },
        "optimism": {
            "mainnet": "https://optimistic.etherscan.io",
            "sepolia": "https://sepolia-optimism.etherscan.io",
        },
        "base": {
            "mainnet": "https://basescan.org",
            "sepolia": "https://sepolia.basescan.org",
        },
        "avalanche": {
            "mainnet": "https://snowtrace.io",
            "fuji": "https://testnet.snowtrace.io",
        },
        "bnb": {
            "mainnet": "https://bscscan.com",
            "testnet": "https://testnet.bscscan.com",
        },
    }

    chain_explorers = explorers.get(blockchain, explorers["ethereum"])
    return chain_explorers.get(network, chain_explorers.get("mainnet", "https://etherscan.io"))
