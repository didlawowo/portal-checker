"""
Utility functions for Portal Checker
"""
import asyncio
import os
import ssl
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
import tomllib

# Disable SSL warnings for development environment
import urllib3
import yaml
from loguru import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .config import (
    CUSTOM_CERT,
    FLASK_ENV,
    MAX_CONCURRENT_REQUESTS,
    REQUEST_TIMEOUT,
    SLACK_WEBHOOK_URL,
    ENABLE_SLACK_NOTIFICATIONS,
)


def get_app_version() -> str:
    """Get application version from pyproject.toml"""
    possible_paths = [
        "pyproject.toml",
        "/app/pyproject.toml",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "pyproject.toml"),
    ]
    
    for path in possible_paths:
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", "unknown")
        except (FileNotFoundError, KeyError):
            continue
    
    return "unknown"


def get_ssl_context() -> ssl.SSLContext:
    """Create SSL context with custom certificate if provided"""
    ssl_context = ssl.create_default_context()

    if CUSTOM_CERT and os.path.exists(CUSTOM_CERT):
        ssl_context.load_verify_locations(CUSTOM_CERT)
        logger.info(f"✅ Certificat SSL personnalisé chargé: {CUSTOM_CERT}")
    elif FLASK_ENV == "development":
        # En développement, désactiver la vérification SSL
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        logger.warning("⚠️ Vérification SSL désactivée en mode développement")

    return ssl_context


async def get_ssl_cert_info(url: str) -> Optional[Dict[str, Any]]:
    """Get SSL certificate information for a URL"""
    try:
        parsed = urlparse(url if url.startswith('http') else f'https://{url}')
        hostname = parsed.hostname
        port = parsed.port or 443

        if not hostname or parsed.scheme != 'https':
            return None

        # Create SSL context for certificate retrieval
        # IMPORTANT: We need to verify SSL to get certificate info, even in dev mode
        ssl_context = ssl.create_default_context()

        # Load custom cert if provided, but keep verification enabled
        if CUSTOM_CERT and os.path.exists(CUSTOM_CERT):
            ssl_context.load_verify_locations(CUSTOM_CERT)

        # In development, we still need to get the cert, so don't disable verification
        # The certificate info retrieval needs SSL to be active

        # Connect and get certificate
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(hostname, port, ssl=ssl_context),
            timeout=5
        )

        # Get SSL object from transport
        ssl_object = writer.get_extra_info('ssl_object')
        if not ssl_object:
            writer.close()
            await writer.wait_closed()
            return None

        # Get certificate
        cert = ssl_object.getpeercert()
        writer.close()
        await writer.wait_closed()

        if not cert:
            return None

        # Parse expiration date
        not_after = cert.get('notAfter')
        if not not_after:
            return None

        # Parse date format: 'Jan 1 00:00:00 2025 GMT'
        expiry_date = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
        days_remaining = (expiry_date - datetime.now()).days

        return {
            'expiry_date': expiry_date.isoformat(),
            'days_remaining': days_remaining,
            'issuer': cert.get('issuer', []),
            'subject': cert.get('subject', [])
        }

    except asyncio.TimeoutError:
        logger.debug(f"Timeout lors de la récupération du certificat SSL pour {url}")
        return None
    except Exception as e:
        logger.debug(f"Erreur lors de la récupération du certificat SSL pour {url}: {e}")
        return None


def load_urls_from_file(filepath: str) -> List[Dict[str, Any]]:
    """Load URLs from YAML file"""
    try:
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)
            
        if isinstance(data, dict) and "urls" in data:
            return data["urls"]
        elif isinstance(data, list):
            return data
        else:
            return []
    except FileNotFoundError:
        logger.warning(f"⚠️ Fichier des URLs non trouvé: {filepath}")
        return []
    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement des URLs: {e}")
        return []


def serialize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize log record for JSON output"""
    message = record["message"]
    # Remove common icons
    message = message.replace("🐞", "").replace("🔧", "").replace("⚠️", "").replace("❌", "").replace("✅", "")
    
    subset = {
        "timestamp": record["time"].strftime("%Y-%m-%d %H:%M:%S.%f"),
        "level": record["level"].name,
        "message": message.strip(),
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "process": {"id": record["process"].id, "name": record["process"].name},
        "thread": {"id": record["thread"].id, "name": record["thread"].name},
    }
    
    if record["extra"]:
        subset["extra"] = record["extra"]
    
    if record["exception"] is not None:
        subset["exception"] = record["exception"]
    
    return subset


async def send_slack_alert_async(session: aiohttp.ClientSession, url: str, status_code: int, details: str) -> None:
    """Send Slack alert for critical errors"""
    if not ENABLE_SLACK_NOTIFICATIONS or not SLACK_WEBHOOK_URL:
        return
    
    try:
        message = {
            "text": f"🚨 Portal Checker Alert",
            "attachments": [
                {
                    "color": "danger",
                    "fields": [
                        {"title": "URL", "value": url, "short": False},
                        {"title": "Status", "value": f"{status_code}", "short": True},
                        {"title": "Details", "value": details, "short": True},
                        {"title": "Time", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "short": True},
                    ],
                }
            ],
        }
        
        await session.post(SLACK_WEBHOOK_URL, json=message)
        logger.debug(f"📧 Alerte Slack envoyée pour {url}")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'envoi de l'alerte Slack: {e}")


async def check_single_url(session: aiohttp.ClientSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """Check a single URL and return results"""
    url = data.get("url", "")

    if not url.startswith(("http://", "https://")):
        full_url = f"https://{url}"
    else:
        full_url = url

    start_time = time.time()

    try:
        async with session.get(full_url, allow_redirects=True) as response:
            response_time = int((time.time() - start_time) * 1000)  # ms
            status_code = response.status

            details = ""
            # OK or warning codes (not critical errors)
            ok_warning_codes = {200, 301, 302, 401, 403, 405, 429}

            if status_code not in ok_warning_codes:
                details = f"❌ {response.reason}"
                logger.debug(f"Erreur pour l'URL {full_url}: {status_code} {response.reason}")
                if ENABLE_SLACK_NOTIFICATIONS:
                    await send_slack_alert_async(session, url, status_code, details)

            # Add specific messages for common status codes
            if status_code == 401:
                details = "🔐 Authentification requise"
            elif status_code == 403:
                details = "🚫 Accès interdit"
            elif status_code == 404:
                details = "❓ Page non trouvée"
                if ENABLE_SLACK_NOTIFICATIONS:
                    await send_slack_alert_async(session, url, status_code, details)
            elif status_code == 405:
                details = "⚠️ Méthode non autorisée"
            elif status_code == 429:
                details = "⏳ Trop de requêtes"
            elif status_code in [301, 302]:
                details = "↗️ Redirection"

            # Get SSL certificate info for HTTPS URLs
            ssl_info = None
            if full_url.startswith('https://'):
                ssl_info = await get_ssl_cert_info(full_url)
                if ssl_info:
                    logger.debug(f"✅ SSL info récupérée pour {url}: {ssl_info.get('days_remaining')} jours restants")
                else:
                    logger.debug(f"⚠️ Pas d'info SSL pour {url}")
            else:
                # HTTP URL - mark explicitly as no SSL
                ssl_info = {"http_only": True}

            # Update original dict with results
            data["status"] = status_code
            data["details"] = details
            data["response_time"] = response_time
            data["ssl_info"] = ssl_info

            logger.debug(f"Test de l'URL {url} : {status_code}, {response_time}ms, SSL: {ssl_info is not None}")

            return data
    
    except asyncio.TimeoutError:
        data["status"] = 408
        data["details"] = "⏱️ Timeout"
        data["response_time"] = int((time.time() - start_time) * 1000)
        return data
    
    except aiohttp.ClientError as e:
        error_msg = str(e)
        if "certificate" in error_msg.lower():
            data["status"] = 495
            data["details"] = "🔒 SSL Certificate Error"
        else:
            data["status"] = 503
            data["details"] = f"🔌 Connection Error: {error_msg[:50]}"
        data["response_time"] = int((time.time() - start_time) * 1000)
        return data
    
    except Exception as e:
        data["status"] = 500
        data["details"] = f"❌ Error: {str(e)[:50]}"
        data["response_time"] = int((time.time() - start_time) * 1000)
        logger.error(f"Erreur inattendue pour {url}: {e}")
        return data


async def check_urls_async(
    data_urls: List[Dict[str, Any]], 
    update_cache: bool = True,
    is_url_excluded_func: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """Check all URLs asynchronously"""
    ssl_context = get_ssl_context()
    
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        connector=aiohttp.TCPConnector(ssl=ssl_context, limit=50)
    ) as session:
        sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        
        async def bounded_test(data):
            async with sem:
                return await check_single_url(session, data)
        
        # Filter excluded URLs before testing
        filtered_data_urls = data_urls
        if is_url_excluded_func:
            filtered_data_urls = [
                data for data in data_urls
                if not is_url_excluded_func(data.get("url", ""))
            ]
            excluded_count = len(data_urls) - len(filtered_data_urls)
            if excluded_count > 0:
                logger.info(
                    f"🔍 {len(data_urls)} URLs à tester, "
                    f"{excluded_count} exclues supplémentaires filtrées"
                )
            else:
                logger.debug(
                    f"🔍 {len(data_urls)} URLs à tester "
                    f"(exclusions déjà appliquées en amont)"
                )
        
        # Execute tests in parallel
        tasks = [bounded_test(data) for data in filtered_data_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    final_results = [r for r in results if isinstance(r, dict)]
    
    # Create summary
    status_counts = {
        "success": 0,
        "client_errors": 0,
        "server_errors": 0,
        "total": len(final_results)
    }
    
    error_summary = {}
    
    for result in final_results:
        status = result.get('status', 0)
        if 200 <= status < 300:
            status_counts["success"] += 1
        elif 400 <= status < 500:
            status_counts["client_errors"] += 1
        elif 500 <= status < 600:
            status_counts["server_errors"] += 1
        
        if status >= 400:
            error_type = f"{status}"
            error_summary[error_type] = error_summary.get(error_type, 0) + 1
    
    # Log summary
    logger.info(
        f"📊 Récapitulatif: ✅ {status_counts['success']} OK | "
        f"⚠️ {status_counts['client_errors']} 4xx | "
        f"❌ {status_counts['server_errors']} 5xx"
    )
    
    if error_summary:
        error_details = ", ".join([f"{code}: {count}" for code, count in sorted(error_summary.items())])
        logger.info(f"🔍 Détail erreurs: {error_details}")
    
    return final_results