"""
Utility functions for Portal Checker
"""
import asyncio
import os
import ssl
import time
import tomllib
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
import yaml
from loguru import logger

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
        # En dev, essayer d'abord le certificat ZScaler puis désactiver SSL
        zscaler_cert = "zscalerroot.crt"
        if os.path.exists(zscaler_cert):
            ssl_context.load_verify_locations(zscaler_cert)
            logger.info(f"✅ Certificat ZScaler chargé: {zscaler_cert}")
        else:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            logger.warning("⚠️ Vérification SSL désactivée en mode développement")
    
    return ssl_context


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
            
            if status_code == 404:
                details = "❓ Not Found"
                if ENABLE_SLACK_NOTIFICATIONS:
                    await send_slack_alert_async(session, url, status_code, details)
            
            # Update original dict with results
            data["status"] = status_code
            data["details"] = details
            data["response_time"] = response_time
            
            logger.debug(f"Test de l'URL {url} : {status_code}, {response_time}ms, data: {data}")
            
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
            logger.info(
                f"🔍 {len(data_urls)} URLs totales, "
                f"{len(data_urls) - len(filtered_data_urls)} exclues, "
                f"{len(filtered_data_urls)} à tester"
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