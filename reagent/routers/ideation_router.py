from agentfield import AgentRouter
from pydantic import BaseModel, Field
import os
import sys
from pathlib import Path

# Add parent directory to path to import bright_data_client
sys.path.insert(0, str(Path(__file__).parent.parent))
from bright_data_client import BrightDataClient
from context import AgentContext

# Router for ideation and research
ideation_router = AgentRouter(prefix="ideation", tags=["research", "ideation"])

# Initialize Bright Data client
_bright_data: BrightDataClient | None = None


def _get_bright_data() -> BrightDataClient:
    """Get or create Bright Data client instance."""
    global _bright_data
    if _bright_data is None:
        _bright_data = BrightDataClient()
    return _bright_data


class ContractSpec(BaseModel):
    """Structured output for contract specification."""
    name: str = Field(description="Contract name")
    description: str = Field(description="Brief description")
    features: list[str] = Field(description="Key features")
    blockchain: str = Field(default="ethereum", description="Target blockchain")
    standards: list[str] = Field(description="ERC standards to implement")


@ideation_router.reasoner(tags=["ai", "qwen", "brightdata"])
async def generate_contract_spec(requirements: str, recovery_context: str | None = None, context: dict | None = None) -> dict:
    """
    Generate smart contract specification from requirements using AI reasoning.
    Integrates real market research via Bright Data web scraping.

    Args:
        requirements: User requirements for the contract
        recovery_context: Optional context from downstream failures to refine the specification
        context: Structured AgentContext dict for mind building across stages
    """
    bd = _get_bright_data()
    
    # Real market research using Bright Data
    market_trends = bd.search_defi_trends(f"DeFi {requirements}", limit=5)
    sentiment = bd.scrape_market_sentiment("DeFi")
    competitor_contracts = bd.scrape_competitor_contracts("DeFi")
    
    # Compile market intelligence
    market_data = f"""
Market Trends: {len(market_trends)} recent articles found
Sentiment: {sentiment.get('sources', 0)} sources analyzed
Competitor Analysis: {len(competitor_contracts)} similar contracts identified

Key Insights:
{market_trends[0].get('snippet', 'No data') if market_trends else 'No trends found'}
"""

    # Build prompt with recovery context if provided
    prompt = f"Requirements: {requirements}\n\nMarket Intelligence:\n{market_data}\n\nGenerate a structured contract specification that incorporates current market trends and best practices."
    if recovery_context:
        prompt += f"\n\nPrevious specification led to issues:\n{recovery_context}\nPlease refine the specification to address these concerns."

    # Inject structured context (mind building)
    if context:
        ctx = AgentContext.from_dict(context) if isinstance(context, dict) else context
        context_prompt = ctx.build_injection_prompt()
        if context_prompt:
            prompt += f"\n\n{context_prompt}"

    # Use AI for deep reasoning with real market context
    spec = await ideation_router.ai(
        system="You are an expert smart contract architect. Generate detailed specs for blockchain contracts based on real market data.",
        user=prompt,
        schema=ContractSpec
    )

    ideation_router.app.note(
        f"Generated spec for contract: {spec.name} (with Bright Data market research)",
        tags=["ideation", "spec", "brightdata"]
    )

    return {
        **spec.model_dump(),
        "market_research": {
            "trends_analyzed": len(market_trends),
            "sentiment_sources": sentiment.get('sources', 0),
            "competitors_found": len(competitor_contracts)
        }
    }


@ideation_router.skill(tags=["research", "web", "brightdata"])
def research_market_trends(topic: str) -> dict:
    """
    Research market trends using Bright Data web scraping.
    Returns real-time data from crypto news, DeFi protocols, and market analysis.
    """
    bd = _get_bright_data()
    
    # Scrape multiple sources
    trends = bd.search_defi_trends(topic, limit=10)
    sentiment = bd.scrape_market_sentiment(topic)
    
    return {
        "topic": topic,
        "trends": [
            {
                "title": t.get("title", ""),
                "snippet": t.get("snippet", ""),
                "source": t.get("source", ""),
                "timestamp": t.get("timestamp", "")
            }
            for t in trends
        ],
        "sentiment": sentiment,
        "sources": [t.get("source", "") for t in trends],
        "total_results": len(trends),
        "brightdata_status": bd.health_check()
    }


@ideation_router.skill(tags=["research", "security", "brightdata"])
def research_security_patterns(contract_type: str) -> dict:
    """
    Research security patterns and audit findings for similar contracts.
    Uses Bright Data to scrape audit reports and security best practices.
    """
    bd = _get_bright_data()
    
    # Scrape security audits
    audits = bd.scrape_security_audits(contract_type)
    
    return {
        "contract_type": contract_type,
        "audit_reports": audits,
        "total_audits": len(audits),
        "recommendations": [
            "Review common vulnerabilities in similar contracts",
            "Implement security patterns from audited contracts",
            "Follow best practices from recent audit reports"
        ]
    }


@ideation_router.skill(tags=["research", "competitor", "brightdata"])
def analyze_competitors(category: str = "DeFi") -> dict:
    """
    Analyze competitor smart contracts in the same category.
    Uses Bright Data to gather information about successful contracts.
    """
    bd = _get_bright_data()
    
    competitors = bd.scrape_competitor_contracts(category)
    
    return {
        "category": category,
        "competitors": competitors,
        "total_found": len(competitors),
        "insights": [
            "Common features across successful contracts",
            "Innovative approaches in the category",
            "Market gaps and opportunities"
        ]
    }


@ideation_router.skill(tags=["research", "protocol", "brightdata"])
def research_defi_protocol(protocol_name: str) -> dict:
    """
    Research a specific DeFi protocol for inspiration and best practices.
    Uses Bright Data to scrape protocol information, TVL, and features.
    """
    bd = _get_bright_data()
    
    protocol_data = bd.scrape_defi_protocol(protocol_name)
    
    return {
        "protocol": protocol_name,
        "data": protocol_data,
        "url": protocol_data.get("url", ""),
        "timestamp": protocol_data.get("timestamp", "")
    }


@ideation_router.skill(tags=["health", "brightdata"])
def check_brightdata_status() -> dict:
    """
    Check Bright Data configuration and connection status.
    """
    bd = _get_bright_data()
    return bd.health_check()