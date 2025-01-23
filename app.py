from flask import Flask, render_template, redirect, request, send_from_directory
import asyncio
import aiohttp  # 🚀 Plus rapide que requests pour les appels HTTP async
from kubernetes import client, config
from loguru import logger
from typing import Union, List, Dict
import os
import sys 

app = Flask(__name__)
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

logger.add(
    sys.stderr, 
    level=log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | {level} | {message}"
)
# Configuration
SLACK_NOTIFICATIONS_ENABLED = (
    os.getenv("ENABLE_SLACK_NOTIFICATIONS", "false").lower() == "true"
)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))  # ⚙️ Timeout configurable
MAX_CONCURRENT_REQUESTS = int(
    os.getenv("MAX_CONCURRENT_REQUESTS", "10")
)  # 🔄 Contrôle de la concurrence


async def send_slack_alert_async(
    session: aiohttp.ClientSession,
    url: str,
    status_code: Union[int, str],
    details: str = "",
) -> None:
    """Version asynchrone de l'alerte Slack"""
    if not SLACK_NOTIFICATIONS_ENABLED or not SLACK_WEBHOOK_URL:
        return

    try:
        if isinstance(status_code, str):
            try:
                status_code = int(status_code)
            except ValueError:
                status_code = 500

        if 200 <= status_code < 300 or 400 <= status_code < 500:
            return

        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🚨 Alerte Ingress",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*URL:*\n{url}"},
                        {"type": "mrkdwn", "text": f"*Status:*\n{status_code}"},
                    ],
                },
            ]
        }

        if details:
            message["blocks"].append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Détails:*\n{details}"},
                }
            )

        async with session.post(
            SLACK_WEBHOOK_URL, json=message, timeout=TIMEOUT
        ) as response:
            await response.text()

    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'alerte Slack: {str(e)}")


async def test_single_url(session: aiohttp.ClientSession, url: str) -> Dict:
    """Test une seule URL de manière asynchrone

    Args:
        session: Session aiohttp pour réutiliser les connexions
        url: URL à tester
    Returns:
        Dict avec le statut du test
    """
    try:
        full_url = f"https://{url}" if not url.startswith("http") else url
        async with session.get(full_url, timeout=TIMEOUT) as response:
            status_code = response.status

            details = ""
            if status_code != 200 and status_code != 401:
                details = "❌ Not Authorized or Not Found"

            await send_slack_alert_async(session, url, status_code, details)
            return {"url": url, "status": status_code, "details": details}

    except asyncio.TimeoutError:
        return {
            "url": url,
            "status": 504,  # 🕒 Gateway Timeout plus approprié que 500
            "details": "❌ Timeout Error",
        }
    except Exception as e:
        return {
            "url": url,
            "status": 500,
            "details": f"❌ Error: {str(e)}",
        }


async def test_urls_async(file_path: str) -> List[Dict]:
    """Test plusieurs URLs en parallèle avec limitation de concurrence

    Args:
        file_path: Chemin du fichier contenant les URLs
    Returns:
        Liste des résultats de test
    """
    with open(file_path, "r", encoding="utf-8") as file:
        urls = file.read().splitlines()

    # ⚡ Utilisation d'un connector TCP avec réutilisation des connexions
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS, force_close=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        # 🔀 Création des tâches avec semaphore pour limiter la concurrence
        sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        async def bounded_test(url):
            async with sem:
                return await test_single_url(session, url)

        # Exécution parallèle des tests
        tasks = [bounded_test(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    return [r for r in results if isinstance(r, dict)]


@app.route("/health")
def health():
    """Endpoint de santé pour vérifier que l'application est en ligne"""
    logger.debug("ok")
    return  {"status": "ok"}, 200


@app.route("/")
async def index():
    """Point d'entrée principal avec gestion asynchrone"""
    file_path = "urls.txt"
    results = await test_urls_async(file_path)
    return render_template("index.html", results=results)


@app.route("/refresh", methods=["GET"])
def get_all_ingress_urls():
    """Get all ingress URLs and write them to a file."""
    if os.getenv("FLASK_ENV") == "development":
        config.load_kube_config()
    else:
        config.load_incluster_config()
    v1 = client.NetworkingV1Api()
    v1Gateway = client.CustomObjectsApi()

    ingress_list = v1.list_ingress_for_all_namespaces()
    httproute_list = v1Gateway.list_namespaced_custom_object(
        group="gateway.networking.k8s.io",
        version="v1",
        plural="httproutes"
    )

    urls_httproute = [rule.host for httproute in httproute_list.items for rule in httproute.spec.hostnames]
    urls_ingress = [rule.host for ingress in ingress_list.items for rule in ingress.spec.rules]
    # sum
    urls = urls_httproute + urls_ingress
    # remove duplicates
    urls = list(set(urls))
    
    logger.info(f"🌟 {len(urls)} URLs found!")
    if urls is None:
        return "No ingress found!"
    # filter portal-checker url from list
    urls = [url for url in urls if "portal-checker" not in url]
    # write url.txt to disk
    with open("urls.txt", "w", encoding="utf-8") as file:
        file.write("\n".join(urls))
    logger.success("🌟 urls.txt updated!")

    origin_url = request.referrer
    if origin_url:
        return redirect(origin_url)

    return redirect("/")


@app.route("/static/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"), "favicon.ico", mimetype="image/ico"
    )


@app.route("/static/image.png")
def logo():
    return send_from_directory(
        os.path.join(app.root_path, "static"), "image.png", mimetype="image/png"
    )


if __name__ == "__main__":
    # 🔧 Configuration pour supporter asyncio avec Flask
    from asgiref.wsgi import WsgiToAsgi
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    asgi_app = WsgiToAsgi(app)

    asyncio.run(serve(asgi_app, Config()))
