"""
Flask API routes for Portal Checker
"""
import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request, send_from_directory
from loguru import logger

from .config import PORT, URLS_FILE, AUTO_REFRESH_ON_START, ENABLE_AUTOSWAGGER
from .kubernetes_client import get_all_urls_with_details, is_url_excluded, save_urls_to_file
from .utils import check_urls_async, get_app_version, load_urls_from_file

# Import autoswagger si disponible et activé
AUTOSWAGGER_AVAILABLE = False
if ENABLE_AUTOSWAGGER:
    try:
        from .autoswagger_integration import discover_swagger_for_portal_checker, get_autoswagger_config
        AUTOSWAGGER_AVAILABLE = True
        logger.debug("✅ Module autoswagger_integration chargé")
    except ImportError as e:
        logger.debug(f"⚠️ Module autoswagger_integration non disponible: {e}")
else:
    logger.debug("⚠️ Autoswagger désactivé via ENABLE_AUTOSWAGGER=false")

app = Flask(__name__, 
    template_folder="../templates",
    static_folder="../static"
)

# Cache for test results
_test_results_cache: Dict[str, Any] = {"results": [], "last_updated": None}

# Cache for swagger results
_swagger_cache: Dict[str, Any] = {"results": [], "last_updated": None}


def _is_url_excluded_wrapper(url: str) -> bool:
    """Wrapper for is_url_excluded to match expected signature"""
    return is_url_excluded(url, {})


async def _run_url_tests(update_cache: bool = True) -> List[Dict[str, Any]]:
    """Run URL tests with optional cache update"""
    data_urls = load_urls_from_file(URLS_FILE)
    results = await check_urls_async(data_urls, update_cache, _is_url_excluded_wrapper)
    
    if update_cache:
        _test_results_cache["results"] = results
        _test_results_cache["last_updated"] = datetime.now()
        
        # Also run Swagger discovery if enabled and available
        if AUTOSWAGGER_AVAILABLE:
            try:
                config = get_autoswagger_config()
                if config.get('enabled', False):
                    unique_urls = list(set(data['url'] for data in data_urls))
                    swagger_results = await discover_swagger_for_portal_checker(unique_urls)
                    _swagger_cache["results"] = swagger_results
                    _swagger_cache["last_updated"] = datetime.now()
            except Exception as e:
                logger.debug(f"⚠️ Erreur lors de la découverte Swagger: {e}")
    
    return results


def _prepare_template_data(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Prepare data for template rendering"""
    # Calculate status counts
    status_counts = {
        "success": 0,
        "client_errors": 0,
        "server_errors": 0,
        "total": len(results)
    }
    
    for result in results:
        status = result.get('status', 0)
        if 200 <= status < 300:
            status_counts["success"] += 1
        elif 400 <= status < 500:
            status_counts["client_errors"] += 1
        elif 500 <= status < 600:
            status_counts["server_errors"] += 1
    
    # Calculate swagger counts
    swagger_results = _swagger_cache.get("results", [])
    swagger_counts = {
        "apis_found": len(swagger_results),
        "security_issues": sum(
            len(api.get("pii_detected", [])) + len(api.get("secrets_detected", []))
            for api in swagger_results
        )
    }
    
    return {
        "results": results,
        "status_counts": status_counts,
        "swagger_counts": swagger_counts,
        "swagger_data": swagger_results,
        "version": get_app_version(),
        "last_updated": _test_results_cache.get("last_updated"),
    }


@app.route("/")
def index():
    """Main page showing URL check results"""
    if not _test_results_cache["results"]:
        # Run initial test if no cached results
        asyncio.run(_run_url_tests())
    
    data = _prepare_template_data(_test_results_cache["results"])
    return render_template("index.html", **data)


@app.route("/api/urls")
def api_urls():
    """API endpoint returning URL check results as JSON"""
    if not _test_results_cache["results"]:
        asyncio.run(_run_url_tests())
    
    return jsonify({
        "results": _test_results_cache["results"],
        "last_updated": _test_results_cache["last_updated"].isoformat() if _test_results_cache["last_updated"] else None,
        "total": len(_test_results_cache["results"])
    })


@app.route("/api/swagger")
def api_swagger():
    """API endpoint returning Swagger discovery results"""
    swagger_results = _swagger_cache.get("results", [])
    return jsonify({
        "results": swagger_results,
        "last_updated": _swagger_cache["last_updated"].isoformat() if _swagger_cache["last_updated"] else None,
        "total": len(swagger_results)
    })


@app.route("/refresh")
def refresh():
    """Force refresh of URL discovery and checks"""
    try:
        # Discover URLs from Kubernetes
        urls_data = get_all_urls_with_details()
        save_urls_to_file(urls_data, URLS_FILE)
        
        # Run tests
        asyncio.run(_run_url_tests())
        
        return jsonify({
            "message": "Cache forcé refresh",
            "urls_count": len(urls_data),
            "status": "ok"
        })
    except Exception as e:
        logger.error(f"❌ Erreur lors du refresh: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500


@app.route("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok"}, 200


@app.route("/memory")
def memory():
    """Memory usage endpoint"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()
        
        return jsonify({
            "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
            "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
            "percent": round(memory_percent, 2),
            "status": "ok"
        })
    except ImportError:
        return jsonify({"error": "psutil not installed", "status": "error"}), 500
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500


@app.route("/static/favicon.ico")
def favicon():
    """Serve favicon"""
    return send_from_directory(
        os.path.join(app.root_path, "..", "static"),
        "favicon.ico",
        mimetype="image/ico"
    )


def refresh_urls_if_needed():
    """Auto-refresh URLs on startup if configured"""
    if not AUTO_REFRESH_ON_START:
        logger.info("🔄 Auto-refresh désactivé au démarrage")
        return
    
    try:
        if not os.path.exists(URLS_FILE):
            logger.info("🔄 Fichier des URLs non trouvé, génération automatique...")
            urls_data = get_all_urls_with_details()
            save_urls_to_file(urls_data, URLS_FILE)
            logger.info(f"✅ {len(urls_data)} URLs découvertes et sauvegardées")
        else:
            logger.info("📋 Fichier des URLs existant trouvé")
    except Exception as e:
        logger.error(f"❌ Erreur lors du refresh automatique: {e}")