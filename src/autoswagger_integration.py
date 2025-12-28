"""
Autoswagger Integration Module for Portal Checker
Integrates Autoswagger functionality to discover and analyze Swagger/OpenAPI endpoints
"""

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
import yaml
from bs4 import BeautifulSoup
from loguru import logger


# Configure SSL certificates for external dependencies
def _configure_ssl_for_dependencies():
    """Configure SSL certificates for external Python libraries"""
    custom_cert = os.getenv('CUSTOM_CERT')
    if custom_cert and os.path.exists(custom_cert):
        # Set environment variables for requests, urllib3, and other libraries
        os.environ['REQUESTS_CA_BUNDLE'] = custom_cert
        os.environ['SSL_CERT_FILE'] = custom_cert
        os.environ['CURL_CA_BUNDLE'] = custom_cert
        logger.debug(f"📋 SSL certificates configured for dependencies: {custom_cert}")

# Configure SSL on module import
_configure_ssl_for_dependencies()


@dataclass
class SwaggerEndpoint:
    """Represents a discovered Swagger endpoint"""
    url: str
    method: str
    path: str
    parameters: List[Dict[str, Any]]
    description: str = ""
    tags: List[str] = None
    security: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.security is None:
            self.security = []


@dataclass
class SwaggerDiscoveryResult:
    """Results of Swagger discovery for a single host"""
    host: str
    swagger_url: str
    endpoints: List[SwaggerEndpoint]
    version: str = ""
    title: str = ""
    description: str = ""
    pii_detected: List[str] = None
    secrets_detected: List[str] = None

    def __post_init__(self):
        if self.pii_detected is None:
            self.pii_detected = []
        if self.secrets_detected is None:
            self.secrets_detected = []


class AutoswaggerIntegration:
    """Main class for Autoswagger integration"""

    def __init__(self, rate_limit: int = 30, timeout: int = 10, max_concurrent: int = 10):
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.session = None
        self.semaphore = None

        # Common Swagger/OpenAPI paths to check (ordered by likelihood)
        self.swagger_paths = [
            '/openapi.json',      # Most common modern path
            '/swagger.json',      # Most common classic path
            '/api/swagger.json',  # Common API path
            '/api/openapi.json',  # Common API path
            '/docs',              # Swagger UI path
            '/redoc',             # ReDoc path
            '/api-docs',          # Spring Boot default
            '/api-docs.json',     # Spring Boot JSON
            '/v1/swagger.json',   # Versioned paths
            '/v2/swagger.json',
            '/v3/swagger.json',
            '/swagger.yaml',      # YAML variants
            '/openapi.yaml',
            '/swagger.yml',
            '/openapi.yml',
            '/docs/swagger.json',
            '/swagger-ui.html'
        ]

    async def __aenter__(self):
        """Async context manager entry"""
        # Handle SSL certificate verification like the main app
        import ssl
        ssl_context = ssl.create_default_context()

        # Check for custom certificate
        custom_cert = os.getenv('CUSTOM_CERT')
        if custom_cert and os.path.exists(custom_cert):
            ssl_context.load_verify_locations(custom_cert)
            logger.info(f"✅ Using custom SSL certificate: {custom_cert}")
        else:
            # In development or enterprise environments, disable SSL verification
            if os.getenv('FLASK_ENV') == 'development':
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                logger.warning("⚠️ SSL verification disabled for development environment")

        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            connector=aiohttp.TCPConnector(
                limit=self.max_concurrent,
                ssl=ssl_context
            )
        )
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def discover_swagger_for_urls(self, urls: List[str]) -> List[SwaggerDiscoveryResult]:
        """Discover Swagger documentation for a list of URLs"""
        results = []

        # Group URLs by host to avoid duplicate checks
        hosts = set()
        for url in urls:
            parsed = urlparse(f"https://{url}" if not url.startswith('http') else url)
            hosts.add(f"{parsed.scheme}://{parsed.netloc}")

        # Discover Swagger for each unique host
        tasks = []
        for host in hosts:
            task = asyncio.create_task(self._discover_swagger_for_host(host))
            tasks.append(task)

        # Execute with rate limiting
        for task in tasks:
            async with self.semaphore:
                try:
                    result = await task
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.debug(f"Failed to discover Swagger for host: {e}")

        return results

    async def _discover_swagger_for_host(self, host: str) -> Optional[SwaggerDiscoveryResult]:
        """Discover Swagger documentation for a single host"""
        logger.debug(f"🔍 Discovering Swagger for {host}")

        # Try each common Swagger path
        for path in self.swagger_paths:
            swagger_url = urljoin(host, path)

            try:
                async with self.session.get(swagger_url) as response:
                    logger.debug(f"🔍 Testing {swagger_url} -> {response.status}")
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '').lower()
                        content = await response.text()

                        # Try to parse as JSON first
                        if 'json' in content_type or path.endswith('.json'):
                            try:
                                swagger_data = json.loads(content)
                                result = await self._parse_swagger_data(host, swagger_url, swagger_data)
                                if result:
                                    logger.info(f"📋 Found Swagger documentation at {swagger_url}")
                                    return result
                            except json.JSONDecodeError:
                                continue

                        # Try to parse as YAML
                        elif 'yaml' in content_type or path.endswith(('.yaml', '.yml')):
                            try:
                                swagger_data = yaml.safe_load(content)
                                result = await self._parse_swagger_data(host, swagger_url, swagger_data)
                                if result:
                                    logger.info(f"📋 Found Swagger documentation at {swagger_url}")
                                    return result
                            except yaml.YAMLError:
                                continue

                        # Try to extract from Swagger UI HTML
                        elif 'html' in content_type:
                            swagger_data = self._extract_swagger_from_html(content)
                            if swagger_data:
                                result = await self._parse_swagger_data(host, swagger_url, swagger_data)
                                if result:
                                    logger.info(f"📋 Found Swagger documentation at {swagger_url}")
                                    return result

            except Exception as e:
                logger.debug(f"Failed to fetch {swagger_url}: {e}")
                continue

        logger.debug(f"🔍 No Swagger found for {host}")
        return None

    def _extract_swagger_from_html(self, html_content: str) -> Optional[Dict[str, Any]]:
        """Extract Swagger JSON from HTML (Swagger UI pages)"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Look for swagger config in script tags
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # Look for swagger spec URL
                    if 'swagger' in script.string.lower() or 'openapi' in script.string.lower():
                        # Extract JSON data if embedded
                        json_match = re.search(r'({.*?"swagger".*?})', script.string, re.DOTALL)
                        if json_match:
                            try:
                                return json.loads(json_match.group(1))
                            except json.JSONDecodeError:
                                continue

            return None

        except Exception as e:
            logger.debug(f"Failed to extract Swagger from HTML: {e}")
            return None

    async def _parse_swagger_data(self, host: str, swagger_url: str, data: Dict[str, Any]) -> Optional[SwaggerDiscoveryResult]:
        """Parse Swagger/OpenAPI data and extract endpoints"""
        try:
            # Validate it's actually a Swagger/OpenAPI spec
            if not any(key in data for key in ['swagger', 'openapi', 'paths']):
                return None

            info = data.get('info', {})
            title = info.get('title', 'Unknown API')
            version = info.get('version', 'Unknown')
            description = info.get('description', '')

            endpoints = []
            paths = data.get('paths', {})

            for path, methods in paths.items():
                if not isinstance(methods, dict):
                    continue

                for method, endpoint_data in methods.items():
                    if method.lower() in ['get', 'post', 'put', 'patch', 'delete', 'options', 'head']:
                        endpoint = SwaggerEndpoint(
                            url=urljoin(host, path),
                            method=method.upper(),
                            path=path,
                            parameters=endpoint_data.get('parameters', []),
                            description=endpoint_data.get('description', ''),
                            tags=endpoint_data.get('tags', []),
                            security=endpoint_data.get('security', [])
                        )
                        endpoints.append(endpoint)

            result = SwaggerDiscoveryResult(
                host=host,
                swagger_url=swagger_url,
                endpoints=endpoints,
                version=version,
                title=title,
                description=description
            )

            # Analyze for PII and secrets
            await self._analyze_swagger_content(result, data)

            return result

        except Exception as e:
            logger.debug(f"Failed to parse Swagger data: {e}")
            return None

    async def _analyze_swagger_content(self, result: SwaggerDiscoveryResult, swagger_data: Dict[str, Any]):
        """Analyze Swagger content for PII and secrets using regex patterns"""
        try:
            # Convert swagger data to string for analysis
            content = json.dumps(swagger_data, indent=2)

            # Detect PII using regex patterns
            self._detect_pii(content, result)

            # Detect secrets using regex patterns
            self._detect_secrets(content, result)

        except Exception as e:
            logger.debug(f"Failed to analyze Swagger content: {e}")

    def _detect_pii(self, content: str, result: SwaggerDiscoveryResult):
        """Detect PII using regex patterns"""
        pii_patterns = {
            'EMAIL_ADDRESS': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'PHONE_NUMBER': r'(\+?\d{1,3}[-.\s]?)?(\d{3})[-.\s]?(\d{3,4})[-.\s]?(\d{4})',
            'PERSON': r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b',
            'SSN': r'\b\d{3}-\d{2}-\d{4}\b',
            'CREDIT_CARD': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
        }

        for pii_type, pattern in pii_patterns.items():
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Only include if it looks like actual data, not just examples
                pii_value = match.group(0)
                if not any(example in pii_value.lower() for example in ['example', 'test', 'sample', 'demo']):
                    result.pii_detected.append(f"{pii_type}: {pii_value}")

    def _detect_secrets(self, content: str, result: SwaggerDiscoveryResult):
        """Detect secrets using regex patterns"""
        secret_patterns = {
            'API Key': r'["\']?api[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9]{20,})["\']?',
            'JWT Token': r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
            'AWS Access Key': r'AKIA[0-9A-Z]{16}',
            'Database URL': r'(mongodb|mysql|postgresql)://[^\s"\']+',
            'Private Key': r'-----BEGIN (RSA )?PRIVATE KEY-----',
            'Bearer Token': r'Bearer\s+[a-zA-Z0-9_-]{20,}',
            'Basic Auth': r'Basic\s+[A-Za-z0-9+/]+=*'
        }

        for secret_type, pattern in secret_patterns.items():
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                secret_value = match.group(0)[:50]
                if len(match.group(0)) > 50:
                    secret_value += "..."
                result.secrets_detected.append(f"{secret_type}: {secret_value}")


# Configuration helper functions
def get_autoswagger_config() -> Dict[str, Any]:
    """Get Autoswagger configuration from environment variables"""
    return {
        'enabled': os.getenv('ENABLE_AUTOSWAGGER', 'false').lower() == 'true',
        'rate_limit': int(os.getenv('AUTOSWAGGER_RATE_LIMIT', '30')),
        'timeout': int(os.getenv('AUTOSWAGGER_TIMEOUT', '3')),
        'max_concurrent': int(os.getenv('AUTOSWAGGER_MAX_CONCURRENT', '5')),
        'brute_force': os.getenv('AUTOSWAGGER_BRUTE_FORCE', 'false').lower() == 'true',
        'include_non_get': os.getenv('AUTOSWAGGER_INCLUDE_NON_GET', 'false').lower() == 'true'
    }


async def discover_swagger_for_portal_checker(urls: List[str]) -> List[Dict[str, Any]]:
    """Main function to discover Swagger documentation for Portal Checker"""
    config = get_autoswagger_config()

    if not config['enabled']:
        return []

    async with AutoswaggerIntegration(
        rate_limit=config['rate_limit'],
        timeout=config['timeout'],
        max_concurrent=config['max_concurrent']
    ) as swagger_scanner:

        results = await swagger_scanner.discover_swagger_for_urls(urls)

        # Convert results to dictionaries for JSON serialization
        swagger_results = []
        for result in results:
            swagger_data = {
                'host': result.host,
                'swagger_url': result.swagger_url,
                'title': result.title,
                'version': result.version,
                'description': result.description,
                'endpoint_count': len(result.endpoints),
                'endpoints': [
                    {
                        'url': ep.url,
                        'method': ep.method,
                        'path': ep.path,
                        'description': ep.description,
                        'tags': ep.tags,
                        'parameter_count': len(ep.parameters),
                        'has_security': len(ep.security) > 0
                    }
                    for ep in result.endpoints
                ],
                'pii_detected': result.pii_detected,
                'secrets_detected': result.secrets_detected,
                'security_issues': len(result.pii_detected) + len(result.secrets_detected)
            }
            swagger_results.append(swagger_data)

    return swagger_results
