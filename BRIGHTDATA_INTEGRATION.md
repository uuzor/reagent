# Bright Data Integration Guide

## Overview

Reagent uses **Bright Data** for real-time web scraping and market intelligence to enhance smart contract development with:

- 🔍 **Market Research**: Real-time DeFi trends and competitor analysis
- 📊 **On-Chain Monitoring**: Etherscan data scraping for contract activity
- 🔐 **Security Intelligence**: Audit report collection and vulnerability research
- ⛽ **Gas Price Tracking**: Real-time gas price monitoring across networks
- 📈 **Sentiment Analysis**: Crypto news and social media sentiment

## Setup

### 1. Get Bright Data Credits

Claim your free credits for the AI Builders hackathon:
```
https://get.brightdata.com/aibuilders10
```

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Bright Data Configuration
BRIGHTDATA_API_TOKEN=your_token_here
BRIGHTDATA_ZONE=your_zone_name
BRIGHTDATA_PROXY_HOST=brd.superproxy.io
BRIGHTDATA_PROXY_PORT=22225
```

### 3. Install Dependencies

```bash
pip install requests
```

## Features

### Market Research (Ideation Phase)

The ideation router uses Bright Data to gather real-time market intelligence:

```python
# Automatically called during contract spec generation
POST /reasoners/ideation_generate_contract_spec
{
  "input": {
    "requirements": "DeFi yield aggregator with auto-compounding"
  }
}

# Response includes market research
{
  "name": "YieldOptimizer",
  "features": [...],
  "market_research": {
    "trends_analyzed": 5,
    "sentiment_sources": 3,
    "competitors_found": 2
  }
}
```

### Manual Market Research

```python
# Research specific topics
POST /skills/ideation_research_market_trends
{
  "input": {
    "topic": "DeFi lending protocols"
  }
}

# Analyze competitors
POST /skills/ideation_analyze_competitors
{
  "input": {
    "category": "DeFi"
  }
}

# Research security patterns
POST /skills/ideation_research_security_patterns
{
  "input": {
    "contract_type": "ERC20"
  }
}
```

### Contract Monitoring

Monitor deployed contracts by scraping Etherscan:

```python
# Monitor contract activity
POST /reasoners/monitoring_monitor_contract
{
  "input": {
    "contract_address": "0x1234...",
    "network": "mainnet"
  }
}

# Track gas prices
POST /skills/monitoring_monitor_gas_prices
{
  "input": {
    "network": "ethereum"
  }
}
```

## Available Endpoints

### Ideation Router

| Endpoint | Type | Description |
|----------|------|-------------|
| `ideation_generate_contract_spec` | Reasoner | Generate spec with market research |
| `ideation_research_market_trends` | Skill | Research DeFi trends |
| `ideation_research_security_patterns` | Skill | Find security best practices |
| `ideation_analyze_competitors` | Skill | Analyze competitor contracts |
| `ideation_research_defi_protocol` | Skill | Research specific protocols |
| `ideation_check_brightdata_status` | Skill | Check Bright Data connection |

### Monitoring Router

| Endpoint | Type | Description |
|----------|------|-------------|
| `monitoring_monitor_contract` | Reasoner | Monitor contract with AI analysis |
| `monitoring_analyze_contract_usage` | Skill | Analyze contract usage patterns |
| `monitoring_monitor_gas_prices` | Skill | Track current gas prices |
| `monitoring_check_monitoring_status` | Skill | Check monitoring system status |

## Bright Data Client API

The `BrightDataClient` class provides low-level access:

```python
from bright_data_client import BrightDataClient

bd = BrightDataClient()

# Scrape any URL
result = bd.scrape_url("https://example.com", render_js=True)

# Search DeFi trends
trends = bd.search_defi_trends("yield farming", limit=10)

# Scrape Etherscan
contract_data = bd.scrape_etherscan_contract("0x1234...", "mainnet")

# Get DeFi protocol info
protocol = bd.scrape_defi_protocol("Uniswap")

# Scrape security audits
audits = bd.scrape_security_audits("ERC20")

# Monitor gas prices
gas = bd.scrape_gas_prices("ethereum")

# Analyze market sentiment
sentiment = bd.scrape_market_sentiment("DeFi")

# Find competitors
competitors = bd.scrape_competitor_contracts("DeFi")

# Health check
status = bd.health_check()
```

## Configuration Options

### Proxy Configuration

Bright Data uses proxy servers for web scraping:

```python
# Automatic proxy configuration
bd = BrightDataClient(
    api_token="your_token",
    zone="your_zone"
)

# Custom proxy settings
BRIGHTDATA_PROXY_HOST=custom.proxy.io
BRIGHTDATA_PROXY_PORT=8080
```

### Scraping Options

```python
# Render JavaScript
result = bd.scrape_url(
    url="https://example.com",
    render_js=True,
    wait_for=".content",  # CSS selector
    timeout=30000  # milliseconds
)
```

## Testing Without Credentials

The client works without credentials for testing (uses direct requests):

```python
bd = BrightDataClient()  # No credentials
result = bd.scrape_url("https://example.com")
# Returns: {"note": "Using direct request - configure BRIGHTDATA_API_TOKEN for proxy"}
```

## Best Practices

### 1. Rate Limiting

Bright Data has rate limits. Use caching for repeated requests:

```python
import time

# Cache results
cache = {}

def get_trends_cached(topic):
    if topic in cache:
        return cache[topic]
    
    result = bd.search_defi_trends(topic)
    cache[topic] = result
    return result
```

### 2. Error Handling

Always check for errors:

```python
result = bd.scrape_url(url)

if result.get("success"):
    data = result["html"]
else:
    error = result.get("error", "Unknown error")
    print(f"Scraping failed: {error}")
```

### 3. Timeout Configuration

Set appropriate timeouts for different operations:

```python
# Quick scrape
result = bd.scrape_url(url, timeout=10000)  # 10 seconds

# Complex page with JS
result = bd.scrape_url(url, timeout=60000)  # 60 seconds
```

## Troubleshooting

### Connection Issues

```bash
# Check Bright Data status
curl -X POST http://localhost:8001/skills/ideation_check_brightdata_status

# Response shows configuration
{
  "configured": true,
  "api_token_set": true,
  "zone_set": true,
  "status": "ready"
}
```

### Proxy Errors

If you see proxy errors:

1. Verify your API token and zone name
2. Check proxy host and port settings
3. Ensure your Bright Data account has credits
4. Try direct requests (without proxy) for testing

### Scraping Failures

Common issues:

- **Timeout**: Increase timeout value
- **JavaScript not rendered**: Set `render_js=True`
- **Rate limited**: Add delays between requests
- **Blocked**: Use different proxy zones

## Integration with Workflow

Bright Data is automatically used in the orchestration workflow:

```
1. Ideation Phase
   └─> Bright Data scrapes market trends
   └─> AI generates spec with market context

2. Coding Phase
   └─> (No Bright Data - uses AI for code generation)

3. Testing Phase
   └─> (No Bright Data - uses GitLab CI)

4. Auditing Phase
   └─> Bright Data scrapes security audit reports
   └─> AI analyzes with security context

5. Deployment Phase
   └─> (No Bright Data - uses GitLab CI)

6. Monitoring Phase
   └─> Bright Data scrapes Etherscan for contract activity
   └─> Bright Data tracks gas prices
   └─> AI analyzes monitoring data
```

## Example: Full Workflow with Bright Data

```python
# 1. Generate contract spec with market research
spec_response = await app.call(
    "reagent.ideation_generate_contract_spec",
    requirements="DeFi yield optimizer"
)
# Bright Data automatically scrapes trends, sentiment, competitors

# 2. Monitor deployed contract
monitor_response = await app.call(
    "reagent.monitoring_monitor_contract",
    contract_address="0x1234...",
    network="mainnet"
)
# Bright Data scrapes Etherscan for real activity data
```

## Resources

- [Bright Data Documentation](https://docs.brightdata.com/)
- [Claim Hackathon Credits](https://get.brightdata.com/aibuilders10)
- [Web Scraper API](https://docs.brightdata.com/scraping-automation/web-scraper-api/overview)
- [Proxy Networks](https://docs.brightdata.com/general/account/proxy-networks)

## Support

For Bright Data integration issues:
1. Check the health status endpoint
2. Verify environment variables
3. Review Bright Data dashboard for usage/errors
4. Contact Bright Data support with your zone ID