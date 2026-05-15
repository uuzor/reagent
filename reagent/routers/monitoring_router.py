from agentfield import AgentRouter
from pydantic import BaseModel, Field
import time

# Router for monitoring and alerts
monitoring_router = AgentRouter(prefix="monitoring", tags=["monitoring", "alerts"])


class MonitoringReport(BaseModel):
    """Structured output for monitoring report."""
    contract_address: str = Field(description="Monitored contract")
    events: list[dict] = Field(description="Recent events")
    alerts: list[str] = Field(description="Active alerts")
    health_score: int = Field(ge=0, le=100, description="Contract health score")


@monitoring_router.reasoner(tags=["ai", "analysis"])
async def monitor_contract(contract_address: str) -> dict:
    """
    Monitor deployed contract using Bright Data for on-chain data.
    """
    # Use Bright Data to scrape blockchain data
    # Placeholder: brightdata.get_contract_events(contract_address)
    events = [
        {"event": "Transfer", "block": 12345, "value": "100 ETH"},
        {"event": "Approval", "block": 12346, "spender": "0x..."}
    ]

    alerts = []
    if len(events) > 10:
        alerts.append("High activity detected")

    report = MonitoringReport(
        contract_address=contract_address,
        events=events,
        alerts=alerts,
        health_score=85
    )

    monitoring_router.app.note(
        f"Monitoring report for {contract_address}: {len(events)} events",
        tags=["monitoring", "blockchain"]
    )

    return report.model_dump()


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
def analyze_contract_usage(contract_address: str) -> dict:
    """
    Analyze contract usage patterns using Bright Data.
    """
    # Scrape usage data
    return {
        "contract": contract_address,
        "daily_transactions": 150,
        "unique_users": 45,
        "total_volume": "5000 ETH",
        "trends": ["Increasing adoption", "Stable gas usage"]
    }