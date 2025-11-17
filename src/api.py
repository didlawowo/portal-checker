"""
Flask API routes for Portal Checker
"""
import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request, send_from_directory
from loguru import logger

from .config import AUTO_REFRESH_ON_START, ENABLE_AUTOSWAGGER, PORT, URLS_FILE
from .kubernetes_client import (
    get_all_urls_with_details,
    is_url_excluded,
    save_urls_to_file,
)
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
    from .kubernetes_client import _load_excluded_patterns

    # Load patterns explicitly to ensure they're fresh
    patterns = _load_excluded_patterns()
    result = is_url_excluded(url, {}, patterns)

    if result:
        logger.debug(f"🚫 URL exclue: {url}")

    return result


async def _run_url_tests(update_cache: bool = True, run_swagger: bool = False) -> List[Dict[str, Any]]:
    """Run URL tests with optional cache update"""
    data_urls = load_urls_from_file(URLS_FILE)
    results = await check_urls_async(data_urls, update_cache, _is_url_excluded_wrapper)

    if update_cache:
        _test_results_cache["results"] = results
        _test_results_cache["last_updated"] = datetime.now()

        # Only run Swagger discovery if explicitly requested
        if run_swagger and AUTOSWAGGER_AVAILABLE:
            try:
                config = get_autoswagger_config()
                if config.get('enabled', False):
                    unique_urls = list(set(data['url'] for data in data_urls))
                    logger.info(f"🔍 Lancement de la découverte Swagger pour {len(unique_urls)} URLs...")
                    swagger_results = await discover_swagger_for_portal_checker(unique_urls)
                    _swagger_cache["results"] = swagger_results
                    _swagger_cache["last_updated"] = datetime.now()
                    logger.info(f"✅ Découverte Swagger terminée: {len(swagger_results)} APIs trouvées")
            except Exception as e:
                logger.error(f"⚠️ Erreur lors de la découverte Swagger: {e}")

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
    # Return page immediately - let JavaScript load data via /api/urls
    # This prevents blocking the page render for 10+ seconds
    data = _prepare_template_data(_test_results_cache["results"])
    return render_template("index.html", **data)


@app.route("/api/urls")
def api_urls():
    """API endpoint returning URL check results as JSON"""
    # Only run tests if cache is completely empty
    # This avoids running tests on every page load
    if not _test_results_cache["results"] and not _test_results_cache.get("last_updated"):
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


@app.route("/api/swagger/scan/<path:url>", methods=["POST"])
def scan_swagger_url(url: str):
    """Scan a specific URL for Swagger documentation"""
    if not AUTOSWAGGER_AVAILABLE:
        return jsonify({
            "error": "Autoswagger non disponible",
            "status": "error"
        }), 503

    try:
        # Add protocol if not present
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"

        logger.info(f"🔍 Scan Swagger demandé pour: {url}")

        # Run Swagger discovery for this specific URL
        swagger_results = asyncio.run(discover_swagger_for_portal_checker([url]))

        if swagger_results:
            # Update cache with new result (merge with existing)
            existing_results = _swagger_cache.get("results", [])

            # Remove old result for this host if exists
            host_to_add = swagger_results[0]['host']
            existing_results = [r for r in existing_results if r['host'] != host_to_add]

            # Add new result
            existing_results.extend(swagger_results)
            _swagger_cache["results"] = existing_results
            _swagger_cache["last_updated"] = datetime.now()

            return jsonify({
                "message": f"Swagger trouvé pour {url}",
                "result": swagger_results[0],
                "status": "ok"
            })
        else:
            return jsonify({
                "message": f"Aucun Swagger trouvé pour {url}",
                "status": "ok"
            })

    except Exception as e:
        logger.error(f"❌ Erreur lors du scan Swagger: {e}")
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@app.route("/refresh")
def refresh():
    """Force refresh of URL discovery and checks"""
    from flask import redirect
    try:
        # Discover URLs from Kubernetes (force refresh to bypass cache)
        urls_data = get_all_urls_with_details(force_refresh=True)
        save_urls_to_file(urls_data, URLS_FILE)

        # Run tests
        asyncio.run(_run_url_tests())

        logger.info(f"✅ Refresh terminé: {len(urls_data)} URLs")

        # Redirect to home page
        return redirect('/')

    except Exception as e:
        logger.error(f"❌ Erreur lors du refresh: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500


@app.route("/api/refresh-async", methods=["POST"])
def refresh_async():
    """Trigger async refresh in background and return immediately"""
    # Simply return - the background task will handle periodic refreshes
    # Or the user can click the main Refresh button
    logger.info("🔄 Refresh asynchrone demandé - utilisez le bouton Refresh principal")

    return jsonify({
        "message": "Utilisez le bouton Refresh pour mettre à jour les données",
        "status": "ok"
    })


@app.route("/api/exclude", methods=["POST"])
def exclude_url():
    """Add URL to exclusion list"""
    try:
        data = request.get_json()
        url = data.get("url")

        if not url:
            return jsonify({"error": "URL required", "status": "error"}), 400

        # Extract just domain/path without protocol (to match existing format)
        from urllib.parse import urlparse
        if url.startswith(('http://', 'https://')):
            parsed = urlparse(url)
            # Format: domain/path (without protocol and query string)
            clean_url = parsed.netloc + parsed.path
            # Remove trailing slash if present
            clean_url = clean_url.rstrip('/')
        else:
            clean_url = url.rstrip('/')

        # Load current exclusions
        import yaml

        from .kubernetes_client import EXCLUDED_URLS_FILE

        try:
            with open(EXCLUDED_URLS_FILE, 'r') as f:
                excluded_urls = yaml.safe_load(f)
                # Handle both list format and dict format
                if isinstance(excluded_urls, dict):
                    excluded_urls = excluded_urls.get("excluded_urls", [])
                elif not isinstance(excluded_urls, list):
                    excluded_urls = []
        except FileNotFoundError:
            excluded_urls = []

        # Add URL if not already excluded
        if clean_url not in excluded_urls:
            excluded_urls.append(clean_url)

            # Save updated config (as list format to match existing)
            with open(EXCLUDED_URLS_FILE, 'w') as f:
                yaml.dump(excluded_urls, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"✅ URL ajoutée aux exclusions: {clean_url}")
            return jsonify({
                "message": f"URL {clean_url} ajoutée aux exclusions",
                "status": "ok"
            })
        else:
            return jsonify({
                "message": f"URL {clean_url} déjà exclue",
                "status": "ok"
            })

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'exclusion de l'URL: {e}")
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

        # Run initial URL tests with SSL info
        logger.info("🔄 Lancement des tests initiaux avec récupération SSL...")
        asyncio.run(_run_url_tests(update_cache=True))
        logger.info("✅ Tests initiaux terminés")

    except Exception as e:
        logger.error(f"❌ Erreur lors du refresh automatique: {e}")