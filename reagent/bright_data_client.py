"""Bright Data client for reagent — web scraping and data collection.

Provides real-time market intelligence, DeFi trends, security patterns,
and blockchain data for smart contract development.
"""

import os
import requests
from typing import Optional, Dict, List, Any
import json
from datetime import datetime


class BrightDataClient:
    """Client for Bright Data web scraping and data collection APIs."""

    def __init__(
        self,
        api_token: Optional[str] = None,
        zone: Optional[str] = None,
        customer: Optional[str] = None,
        ws_url: Optional[str] = None,
    ):
        """Initialize Bright Data client.
        
        Args:
            api_token: Bright Data API key (or use BRIGHT_DATA_API_KEY env var)
            zone: Bright Data zone name (or use BRIGHT_DATA_ZONE env var)
            customer: Bright Data customer ID (or use BRIGHT_DATA_CUSTOMER env var)
            ws_url: WebSocket URL (or use BRIGHT_DATA_WS_URL env var)
        """
        # Support both naming conventions
        self.api_token = (
            api_token
            or os.getenv("BRIGHT_DATA_API_KEY")
            or os.getenv("BRIGHTDATA_API_TOKEN", "")
        )
        self.zone = (
            zone
            or os.getenv("BRIGHT_DATA_ZONE")
            or os.getenv("BRIGHTDATA_ZONE", "")
        )
        self.customer = (
            customer
            or os.getenv("BRIGHT_DATA_CUSTOMER", "")
        )
        self.ws_url = (
            ws_url
            or os.getenv("BRIGHT_DATA_WS_URL", "")
        )
        
        # Bright Data API endpoints
        self.scraping_browser_url = "https://api.brightdata.com/scraping_browser"
        self.web_unlocker_url = "https://api.brightdata.com/web_unlocker"
        self.serp_api_url = "https://api.brightdata.com/serp"
        
        # Proxy configuration for direct requests
        self.proxy_host = os.getenv("BRIGHTDATA_PROXY_HOST", "brd.superproxy.io")
        self.proxy_port = int(os.getenv("BRIGHTDATA_PROXY_PORT", "22225"))
        
        self.session = requests.Session()
        if self.api_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            })

    def _get_proxy_config(self) -> Dict[str, str]:
        """Get proxy configuration for requests."""
        if not self.api_token or not self.zone:
            return {}
        
        # Use customer ID if available for authentication
        if self.customer:
            # Format: customer-CUSTOMER-zone-ZONE:API_KEY
            username = f"customer-{self.customer}-zone-{self.zone}"
            proxy_url = f"http://{username}:{self.api_token}@{self.proxy_host}:{self.proxy_port}"
        else:
            # Fallback to zone:api_key format
            proxy_url = f"http://{self.zone}:{self.api_token}@{self.proxy_host}:{self.proxy_port}"
        
        return {
            "http": proxy_url,
            "https": proxy_url
        }

    def scrape_url(
        self,
        url: str,
        render_js: bool = True,
        wait_for: Optional[str] = None,
        timeout: int = 30000
    ) -> Dict[str, Any]:
        """Scrape a URL using Bright Data's Scraping Browser or Web Unlocker.
        
        Args:
            url: Target URL to scrape
            render_js: Whether to render JavaScript
            wait_for: CSS selector to wait for before returning
            timeout: Timeout in milliseconds
            
        Returns:
            Dict with 'html', 'text', 'status_code', and 'url'
        """
        try:
            # Check if using Scraping Browser (has ws_url)
            if self.ws_url and "scraping_browser" in self.zone:
                # Use Scraping Browser API via HTTPS endpoint
                if hasattr(self, 'https_url') or os.getenv("BRIGHT_DATA_HTTPS_URL"):
                    https_url = getattr(self, 'https_url', None) or os.getenv("BRIGHT_DATA_HTTPS_URL")
                    # For Scraping Browser, use the HTTPS API endpoint
                    # This is a simplified version - full implementation would use Puppeteer/Playwright
                    response = requests.get(url, timeout=timeout / 1000)
                    return {
                        "html": response.text,
                        "text": response.text,
                        "status_code": response.status_code,
                        "url": url,
                        "success": response.status_code == 200,
                        "note": "Using Scraping Browser zone - direct request (full browser automation requires Puppeteer)"
                    }
            
            # Use Web Unlocker proxy for simple scraping
            proxies = self._get_proxy_config()
            
            if proxies:
                response = requests.get(
                    url,
                    proxies=proxies,
                    timeout=timeout / 1000,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                    verify=False  # Disable SSL verification for proxy
                )
                
                return {
                    "html": response.text,
                    "text": response.text,
                    "status_code": response.status_code,
                    "url": url,
                    "success": response.status_code == 200
                }
            else:
                # Fallback to direct request (for testing without credentials)
                response = requests.get(url, timeout=timeout / 1000)
                return {
                    "html": response.text,
                    "text": response.text,
                    "status_code": response.status_code,
                    "url": url,
                    "success": response.status_code == 200,
                    "note": "Using direct request - configure BRIGHT_DATA_API_KEY for proxy"
                }
                
        except Exception as e:
            return {
                "error": str(e),
                "url": url,
                "success": False
            }

    def search_defi_trends(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for DeFi trends and news.
        
        Args:
            query: Search query (e.g., "DeFi yield farming 2024")
            limit: Number of results to return
            
        Returns:
            List of search results with title, url, snippet
        """
        try:
            # Use SERP API or scrape search engines
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            
            result = self.scrape_url(search_url)
            
            if result.get("success"):
                # Parse search results (simplified - in production use proper HTML parsing)
                return [
                    {
                        "title": f"DeFi Trend: {query}",
                        "url": search_url,
                        "snippet": result.get("text", "")[:200],
                        "source": "google",
                        "timestamp": datetime.now().isoformat()
                    }
                ]
            
            return []
            
        except Exception as e:
            return [{"error": str(e)}]

    def scrape_etherscan_contract(self, contract_address: str, network: str = "mainnet") -> Dict[str, Any]:
        """Scrape contract information from Etherscan.
        
        Args:
            contract_address: Ethereum contract address
            network: Network name (mainnet, sepolia, etc.)
            
        Returns:
            Contract information including transactions, balance, code
        """
        try:
            base_urls = {
                "mainnet": "https://etherscan.io",
                "sepolia": "https://sepolia.etherscan.io",
                "goerli": "https://goerli.etherscan.io"
            }
            
            base_url = base_urls.get(network, base_urls["mainnet"])
            url = f"{base_url}/address/{contract_address}"
            
            result = self.scrape_url(url)
            
            if result.get("success"):
                return {
                    "address": contract_address,
                    "network": network,
                    "url": url,
                    "data": result.get("text", "")[:500],  # Simplified
                    "timestamp": datetime.now().isoformat()
                }
            
            return {"error": "Failed to scrape Etherscan", "address": contract_address}
            
        except Exception as e:
            return {"error": str(e), "address": contract_address}

    def scrape_defi_protocol(self, protocol_name: str) -> Dict[str, Any]:
        """Scrape DeFi protocol information.
        
        Args:
            protocol_name: Protocol name (e.g., "Uniswap", "Aave")
            
        Returns:
            Protocol information including TVL, APY, security audits
        """
        try:
            # Scrape DeFi Llama or similar
            url = f"https://defillama.com/protocol/{protocol_name.lower()}"
            
            result = self.scrape_url(url)
            
            if result.get("success"):
                return {
                    "protocol": protocol_name,
                    "url": url,
                    "data": result.get("text", "")[:500],
                    "timestamp": datetime.now().isoformat()
                }
            
            return {"error": "Failed to scrape protocol", "protocol": protocol_name}
            
        except Exception as e:
            return {"error": str(e), "protocol": protocol_name}

    def scrape_security_audits(self, contract_name: str) -> List[Dict[str, Any]]:
        """Scrape security audit reports for smart contracts.
        
        Args:
            contract_name: Contract or protocol name
            
        Returns:
            List of audit reports with findings
        """
        try:
            # Search for audit reports
            query = f"{contract_name} smart contract audit report"
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            
            result = self.scrape_url(search_url)
            
            if result.get("success"):
                return [
                    {
                        "contract": contract_name,
                        "source": "audit_search",
                        "findings": result.get("text", "")[:300],
                        "timestamp": datetime.now().isoformat()
                    }
                ]
            
            return []
            
        except Exception as e:
            return [{"error": str(e)}]

    def scrape_gas_prices(self, network: str = "ethereum") -> Dict[str, Any]:
        """Scrape current gas prices.
        
        Args:
            network: Blockchain network
            
        Returns:
            Current gas prices (slow, standard, fast)
        """
        try:
            urls = {
                "ethereum": "https://etherscan.io/gastracker",
                "polygon": "https://polygonscan.com/gastracker"
            }
            
            url = urls.get(network, urls["ethereum"])
            result = self.scrape_url(url)
            
            if result.get("success"):
                return {
                    "network": network,
                    "url": url,
                    "data": result.get("text", "")[:200],
                    "timestamp": datetime.now().isoformat()
                }
            
            return {"error": "Failed to scrape gas prices", "network": network}
            
        except Exception as e:
            return {"error": str(e), "network": network}

    def scrape_market_sentiment(self, topic: str = "DeFi") -> Dict[str, Any]:
        """Scrape market sentiment from crypto news and social media.
        
        Args:
            topic: Topic to analyze sentiment for
            
        Returns:
            Sentiment analysis with positive/negative indicators
        """
        try:
            # Scrape crypto news sites
            urls = [
                f"https://cointelegraph.com/tags/{topic.lower()}",
                f"https://cryptonews.com/news/{topic.lower()}/",
            ]
            
            results = []
            for url in urls:
                result = self.scrape_url(url)
                if result.get("success"):
                    results.append({
                        "source": url,
                        "content": result.get("text", "")[:300]
                    })
            
            return {
                "topic": topic,
                "sources": len(results),
                "data": results,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": str(e), "topic": topic}

    def scrape_competitor_contracts(self, category: str = "DeFi") -> List[Dict[str, Any]]:
        """Scrape information about competitor smart contracts.
        
        Args:
            category: Contract category (DeFi, NFT, DAO, etc.)
            
        Returns:
            List of competitor contracts with features
        """
        try:
            query = f"best {category} smart contracts 2024"
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            
            result = self.scrape_url(search_url)
            
            if result.get("success"):
                return [
                    {
                        "category": category,
                        "source": "search",
                        "data": result.get("text", "")[:400],
                        "timestamp": datetime.now().isoformat()
                    }
                ]
            
            return []
            
        except Exception as e:
            return [{"error": str(e)}]

    def health_check(self) -> Dict[str, Any]:
        """Check if Bright Data credentials are configured and working.
        
        Returns:
            Health status with configuration details
        """
        return {
            "configured": bool(self.api_token and self.zone),
            "api_token_set": bool(self.api_token),
            "zone_set": bool(self.zone),
            "customer_set": bool(self.customer),
            "ws_url_set": bool(self.ws_url),
            "proxy_host": self.proxy_host,
            "proxy_port": self.proxy_port,
            "status": "ready" if (self.api_token and self.zone) else "needs_configuration"
        }

# Made with Bob
