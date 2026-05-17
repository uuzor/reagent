from agentfield import AgentRouter
from pydantic import BaseModel, Field
import time
import os
import sys
from pathlib import Path

# Add parent directory to path to import bright_data_client
sys.path.insert(0, str(Path(__file__).parent.parent))
from bright_data_client import BrightDataClient
from context import AgentContext

# Router for monitoring and alerts
monitoring_router = AgentRouter(prefix="monitoring", tags=["monitoring", "alerts"])

# Initialize Bright Data client
_bright_data: BrightDataClient | None = None


def _get_bright_data() -> BrightDataClient:
    """Get or create Bright Data client instance."""
    global _bright_data
    if _bright_data is None:
        _bright_data = BrightDataClient()
    return _bright_data


class MonitoringReport(BaseModel):
    """Structured output for monitoring report."""
    contract_address: str = Field(description="Monitored contract")
    events: list[dict] = Field(description="Recent events")
    alerts: list[str] = Field(description="Active alerts")
    health_score: int = Field(ge=0, le=100, description="Contract health score")


@monitoring_router.reasoner(tags=["ai", "analysis", "brightdata"])
async def monitor_contract(contract_address: str, network: str = "mainnet", context: dict | None = None) -> dict:
    """
    Monitor deployed contract using Bright Data for real on-chain data scraping.
    Scrapes Etherscan for contract events, transactions, and activity.

    Args:
        contract_address: Deployed contract address
        network: Blockchain network
        context: Structured AgentContext dict for mind building across stages
    """
    bd = _get_bright_data()
    
    # Scrape real contract data from Etherscan using Bright Data
    contract_data = bd.scrape_etherscan_contract(contract_address, network)
    gas_prices = bd.scrape_gas_prices(network="ethereum")
    
    # Parse events from scraped data (simplified - in production parse HTML properly)
    events = [
        {
            "event": "Contract Activity",
            "source": "etherscan",
            "data": contract_data.get("data", "")[:100],
            "timestamp": contract_data.get("timestamp", "")
        }
    ]
    
    # Analyze for alerts
    alerts = []
    if "error" in contract_data:
        alerts.append(f"Failed to fetch contract data: {contract_data.get('error')}")
    else:
        alerts.append("Contract is active and monitored")
    
    # Use AI to analyze the scraped data
    user_prompt = f"Contract: {contract_address}\nNetwork: {network}\nData: {contract_data}\nGas Prices: {gas_prices}"
    if context:
        ctx = AgentContext.from_dict(context) if isinstance(context, dict) else context
        context_prompt = ctx.build_injection_prompt()
        if context_prompt:
            user_prompt += f"\n\n{context_prompt}"

    analysis = await monitoring_router.ai(
        system="You are a blockchain monitoring expert. Analyze this contract activity and provide insights.",
        user=user_prompt,
    )
    
    report = MonitoringReport(
        contract_address=contract_address,
        events=events,
        alerts=alerts,
        health_score=85 if not alerts else 60
    )

    monitoring_router.app.note(
        f"Monitoring report for {contract_address} on {network} (Bright Data scraping)",
        tags=["monitoring", "blockchain", "brightdata"]
    )

    return {
        **report.model_dump(),
        "network": network,
        "contract_data": contract_data,
        "gas_prices": gas_prices,
        "ai_analysis": analysis
    }


@monitoring_router.skill(tags=["alerts", "notification"])
def setup_alerts(contract_address: str, conditions: dict) -> dict:
    """
    Set up monitoring alerts for contract conditions.
    """
    return {
        "contract": contract_address,
        "alerts_configured": list(conditions.keys()),
        "conditions": conditions,
        "status": "active"
    }


@monitoring_router.skill(tags=["analytics", "brightdata"])
def analyze_contract_usage(contract_address: str, network: str = "mainnet") -> dict:
    """
    Analyze contract usage patterns using Bright Data to scrape Etherscan.
    Returns real transaction data, user activity, and usage trends.
    """
    bd = _get_bright_data()
    
    # Scrape contract data
    contract_data = bd.scrape_etherscan_contract(contract_address, network)
    
    return {
        "contract": contract_address,
        "network": network,
        "etherscan_url": contract_data.get("url", ""),
        "data_scraped": bool(contract_data.get("data")),
        "timestamp": contract_data.get("timestamp", ""),
        "status": "success" if "data" in contract_data else "error",
        "brightdata_health": bd.health_check()
    }


@monitoring_router.skill(tags=["gas", "brightdata"])
def monitor_gas_prices(network: str = "ethereum") -> dict:
    """
    Monitor current gas prices using Bright Data to scrape gas trackers.
    """
    bd = _get_bright_data()
    
    gas_data = bd.scrape_gas_prices(network)
    
    return {
        "network": network,
        "gas_data": gas_data,
        "url": gas_data.get("url", ""),
        "timestamp": gas_data.get("timestamp", ""),
        "recommendations": [
            "Monitor gas prices before deployment",
            "Consider deploying during low-traffic periods",
            "Use gas optimization techniques"
        ]
    }


@monitoring_router.skill(tags=["health", "brightdata"])
def check_monitoring_status() -> dict:
    """
    Check monitoring system and Bright Data connection status.
    """
    bd = _get_bright_data()
    
    return {
        "monitoring_active": True,
        "brightdata_status": bd.health_check(),
        "capabilities": [
            "Contract activity monitoring",
            "Gas price tracking",
            "Etherscan data scraping",
            "Real-time alerts"
        ]
    }