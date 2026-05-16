#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script for Bright Data integration.

Run this to verify your Bright Data configuration and test the client.
"""

import os
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load environment variables
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from bright_data_client import BrightDataClient


def test_health_check():
    """Test Bright Data configuration."""
    print("=" * 60)
    print("Testing Bright Data Configuration")
    print("=" * 60)
    
    bd = BrightDataClient()
    status = bd.health_check()
    
    print(f"\n✓ Configuration Status:")
    print(f"  - Configured: {status['configured']}")
    print(f"  - API Token Set: {status['api_token_set']}")
    print(f"  - Zone Set: {status['zone_set']}")
    print(f"  - Proxy Host: {status['proxy_host']}")
    print(f"  - Proxy Port: {status['proxy_port']}")
    print(f"  - Status: {status['status']}")
    
    if not status['configured']:
        print("\n⚠️  Warning: Bright Data not fully configured")
        print("   Set BRIGHTDATA_API_TOKEN and BRIGHTDATA_ZONE in .env")
        print("   Get credits at: https://get.brightdata.com/aibuilders10")
    
    return status['configured']


def test_scraping():
    """Test basic web scraping."""
    print("\n" + "=" * 60)
    print("Testing Web Scraping")
    print("=" * 60)
    
    bd = BrightDataClient()
    
    # Test simple URL scraping
    print("\n→ Scraping example.com...")
    result = bd.scrape_url("https://example.com")
    
    if result.get("success"):
        print(f"✓ Success! Status: {result['status_code']}")
        print(f"  Content length: {len(result.get('text', ''))} characters")
        if "note" in result:
            print(f"  Note: {result['note']}")
    else:
        print(f"✗ Failed: {result.get('error', 'Unknown error')}")
    
    return result.get("success", False)


def test_defi_trends():
    """Test DeFi trends scraping."""
    print("\n" + "=" * 60)
    print("Testing DeFi Trends Research")
    print("=" * 60)
    
    bd = BrightDataClient()
    
    print("\n→ Searching for DeFi trends...")
    trends = bd.search_defi_trends("DeFi yield farming", limit=3)
    
    if trends:
        print(f"✓ Found {len(trends)} results")
        for i, trend in enumerate(trends, 1):
            print(f"\n  {i}. {trend.get('title', 'No title')}")
            print(f"     Source: {trend.get('source', 'Unknown')}")
            if 'snippet' in trend:
                print(f"     Snippet: {trend['snippet'][:80]}...")
    else:
        print("✗ No trends found")
    
    return len(trends) > 0


def test_etherscan():
    """Test Etherscan scraping."""
    print("\n" + "=" * 60)
    print("Testing Etherscan Contract Scraping")
    print("=" * 60)
    
    bd = BrightDataClient()
    
    # Use a well-known contract (USDT on Ethereum)
    contract_address = "0xdac17f958d2ee523a2206206994597c13d831ec7"
    
    print(f"\n→ Scraping contract {contract_address[:10]}...")
    result = bd.scrape_etherscan_contract(contract_address, "mainnet")
    
    if "error" not in result:
        print(f"✓ Success!")
        print(f"  Address: {result.get('address', 'N/A')}")
        print(f"  Network: {result.get('network', 'N/A')}")
        print(f"  URL: {result.get('url', 'N/A')}")
        print(f"  Data length: {len(result.get('data', ''))} characters")
    else:
        print(f"✗ Failed: {result.get('error', 'Unknown error')}")
    
    return "error" not in result


def test_gas_prices():
    """Test gas price scraping."""
    print("\n" + "=" * 60)
    print("Testing Gas Price Monitoring")
    print("=" * 60)
    
    bd = BrightDataClient()
    
    print("\n→ Fetching current gas prices...")
    result = bd.scrape_gas_prices("ethereum")
    
    if "error" not in result:
        print(f"✓ Success!")
        print(f"  Network: {result.get('network', 'N/A')}")
        print(f"  URL: {result.get('url', 'N/A')}")
        print(f"  Data length: {len(result.get('data', ''))} characters")
    else:
        print(f"✗ Failed: {result.get('error', 'Unknown error')}")
    
    return "error" not in result


def test_market_sentiment():
    """Test market sentiment analysis."""
    print("\n" + "=" * 60)
    print("Testing Market Sentiment Analysis")
    print("=" * 60)
    
    bd = BrightDataClient()
    
    print("\n→ Analyzing DeFi sentiment...")
    result = bd.scrape_market_sentiment("DeFi")
    
    if "error" not in result:
        print(f"✓ Success!")
        print(f"  Topic: {result.get('topic', 'N/A')}")
        print(f"  Sources: {result.get('sources', 0)}")
        print(f"  Timestamp: {result.get('timestamp', 'N/A')}")
    else:
        print(f"✗ Failed: {result.get('error', 'Unknown error')}")
    
    return "error" not in result


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("BRIGHT DATA INTEGRATION TEST SUITE")
    print("=" * 60)
    
    results = {
        "Health Check": test_health_check(),
        "Web Scraping": test_scraping(),
        "DeFi Trends": test_defi_trends(),
        "Etherscan": test_etherscan(),
        "Gas Prices": test_gas_prices(),
        "Market Sentiment": test_market_sentiment(),
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Bright Data integration is working.")
    elif passed > 0:
        print(f"\n⚠️  {total - passed} test(s) failed. Check configuration.")
    else:
        print("\n❌ All tests failed. Please configure Bright Data credentials.")
        print("   Set BRIGHTDATA_API_TOKEN and BRIGHTDATA_ZONE in .env")
        print("   Get credits at: https://get.brightdata.com/aibuilders10")
    
    print("\n" + "=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

# Made with Bob
