import asyncio
import os
import ssl
import sys
from typing import Dict, List, Union

import aiohttp
import certifi
import yaml
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
)
from icecream import ic
from kubernetes import client, config
from loguru import logger


def serialize_record(record):
    """
    Personnalise la sérialisation des records pour le format JSON.
    Cette fonction est appelée pour chaque enregistrement de log quand serialize=True.
    Elle transforme les attributs du record en un format JSON compatible.
    """
    subset = {
        "timestamp": record["time"].strftime("%Y-%m-%d %H:%M:%S.%f"),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "process": {"id": record["process"].id, "name": record["process"].name},
        "thread": {"id": record["thread"].id, "name": record["thread"].name},
    }

    # Ajout des informations supplémentaires si elles existent
    if record["extra"]:
        subset["extra"] = record["extra"]

    if record["exception"] is not None:
        subset["exception"] = record["exception"]

    return subset


def setup_logger(log_format: str = "text", log_level: str = "INFO") -> None:
    """
    Configure le logger selon le format souhaité (texte ou JSON).

    Le mode texte est optimisé pour la lisibilité humaine avec des couleurs,
    tandis que le mode JSON est conçu pour être parsé par des outils d'analyse de logs.
    """
    # Supprime les handlers existants pour éviter la duplication
    logger.remove()

    if log_format.lower() == "json":
        # Configuration pour le format JSON
        logger.add(
            sys.stdout,
            level=log_level,
            serialize=True,  # Active la sérialisation JSON
            format="{message}",  # Format minimal car géré par serialize_record
            enqueue=True,  # Rend le logging thread-safe
            backtrace=True,  # Inclut les stack traces détaillées
            diagnose=False,  # Désactive l'affichage des variables locales dans les traces
            catch=True,  # Capture les erreurs de logging
        )
    else:
        # Configuration pour le format texte lisible
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
            level=log_level,
            colorize=True,
            enqueue=True,
            backtrace=True,
            diagnose=True,
            catch=True,
        )


# Configuration initiale du logger
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
setup_logger(LOG_FORMAT, LOG_LEVEL)


# Configuration
SLACK_NOTIFICATIONS_ENABLED = (
    os.getenv("ENABLE_SLACK_NOTIFICATIONS", "false").lower() == "true"
)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))  # ⚙️ Timeout configurable
MAX_CONCURRENT_REQUESTS = int(
    os.getenv("MAX_CONCURRENT_REQUESTS", "10")
)  # 🔄 Contrôle de la concurrence

URLS_FILE = os.getenv("URLS_FILE", "config/urls.yaml" if os.getenv("FLASK_ENV") == "development" else "/app/config/urls.yaml")
EXCLUDED_URLS_FILE = os.getenv("EXCLUDED_URLS_FILE", "config/excluded-urls.yaml" if os.getenv("FLASK_ENV") == "development" else "/app/config/excluded-urls.yaml")

# 🚀 Auto-refresh activé par défaut
AUTO_REFRESH_ON_START = os.getenv("AUTO_REFRESH_ON_START", "true").lower() == "true"


def sslMode():
    if os.getenv("CUSTOM_CERT"):
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        custom_cert_path = os.getenv("CUSTOM_CERT", "certs/")
        ic(custom_cert_path)
        if os.path.exists(custom_cert_path):
            try:
                ssl_context.load_verify_locations(capath=custom_cert_path)
                logger.info(
                    f"✅ Certificat personnalisé chargé: {len(ssl_context.get_ca_certs())}"
                )
            except Exception as e:
                logger.warning(
                    f"⚠️ Impossible de charger le certificat personnalisé: {str(e)}"
                )
        return ssl_context
    else:
        logger.info("⚠️  Vérification SSL désactivée")
        return False


def load_excluded_urls():
    """
    🔧 Charge les URLs exclues avec gestion robuste des formats
    Supporte: liste YAML, fichier vide, format incorrect
    """
    excluded_urls = set()

    if not os.path.exists(EXCLUDED_URLS_FILE):
        logger.info(f"ℹ️ Aucun fichier d'exclusion trouvé à {EXCLUDED_URLS_FILE}")
        return excluded_urls

    try:
        with open(EXCLUDED_URLS_FILE, "r", encoding="utf-8") as file:
            content = file.read().strip()

            # 🔍 Fichier vide ou contenant seulement des espaces
            if not content:
                logger.info(
                    "ℹ️ Fichier d'exclusions vide, toutes les URLs seront testées"
                )
                return excluded_urls

            # 📝 Chargement du YAML
            data = yaml.safe_load(content)

            # ✅ Vérification du format attendu (liste)
            if data is None:
                logger.info(
                    "ℹ️ Fichier d'exclusions vide (null), toutes les URLs seront testées"
                )
                return excluded_urls
            elif isinstance(data, list):
                excluded_urls = set(data)
                logger.info(
                    f"✅ {len(excluded_urls)} URLs exclues chargées depuis {EXCLUDED_URLS_FILE}"
                )
                for url in excluded_urls:
                    logger.debug(f"🚫 URL exclue: {url}")
                return excluded_urls
            else:
                logger.error(
                    f"❌ Format YAML incorrect dans {EXCLUDED_URLS_FILE} - Attendu: liste, Reçu: {type(data)}"
                )
                logger.error(f"❌ Contenu: {data}")
                return excluded_urls

    except yaml.YAMLError as e:
        logger.error(f"❌ Erreur YAML lors du chargement des exclusions: {str(e)}")
        return excluded_urls
    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement des URLs exclues: {str(e)}")
        return excluded_urls


app = Flask(__name__)

excluded_urls = load_excluded_urls()
ssl_context = sslMode()


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


async def test_single_url(session: aiohttp.ClientSession, data: dict) -> Dict:
    """Test une seule URL de manière asynchrone

    Args:
        session: Session aiohttp pour réutiliser les connexions
        data: Dictionnaire contenant les données de l'URL à tester
    Returns:
        Dict avec le statut du test
    """
    url = data.get("url", "")  # Récupérer l'URL de manière sécurisée

    try:
        logger.debug(f"Test de l'URL {url}")
        full_url = f"https://{url}" if not url.startswith("http") else url

        async with session.get(full_url, timeout=aiohttp.ClientTimeout(total=TIMEOUT), ssl=ssl_context) as response:
            status_code = response.status
            # ic(response)

            details = ""
            if status_code != 200 and status_code != 401:
                details = f"❌ {response.reason}"
                logger.error(f"Erreur pour l'URL {full_url}")
                if SLACK_NOTIFICATIONS_ENABLED:
                    await send_slack_alert_async(session, url, status_code, details)

            if status_code == 404:
                details = "❓ Not Found"
                # Envoyer une alerte Slack
                if SLACK_NOTIFICATIONS_ENABLED:
                    await send_slack_alert_async(session, url, status_code, details)

            # Mettre à jour le dictionnaire original avec les résultats
            data["status"] = status_code
            data["details"] = (
                details  # Assurez-vous d'utiliser "details" et non "result"
            )

            logger.debug(f"Test de l'URL {url} : {status_code}, data: {data}")

            return data

    except asyncio.TimeoutError:
        # Créer un nouveau dictionnaire qui préserve les données d'origine
        result = data.copy()
        result.update(
            {
                "status": 504,  # 🕒 Gateway Timeout plus approprié que 500
                "details": "❌ Timeout Error",
            }
        )
        return result

    except Exception as e:
        # Créer un nouveau dictionnaire qui préserve les données d'origine
        result = data.copy()
        result.update({"status": 500, "details": f"❌ Error: {str(e)}"})
        return result


async def test_urls_async(file_path: str = None) -> List[Dict]:
    """Test plusieurs URLs en parallèle avec limitation de concurrence

    Args:
        file_path: Chemin du fichier YAML contenant les URLs
    Returns:
        Liste des résultats de test
    """
    if file_path is None:
        file_path = URLS_FILE

    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file)
                if isinstance(data, list):
                    data_urls = data
                else:
                    logger.error(
                        "❌ Format YAML incorrect pour les URLs (doit être une liste)"
                    )
                    data_urls = []
        else:
            logger.error(f"❌ Fichier URLs non trouvé: {file_path}")
            data_urls = []
    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement des URLs: {str(e)}")
        data_urls = []

    # ⚡ Utilisation d'un connector TCP avec réutilisation des connexions
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS, force_close=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        # 🔀 Création des tâches avec semaphore pour limiter la concurrence
        sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        async def bounded_test(data):
            async with sem:
                return await test_single_url(session, data)

        # Filtrer les URLs exclues avant de lancer les tests
        filtered_data_urls = [data for data in data_urls if not _is_url_excluded(data.get('url', ''))]
        logger.info(f"🔍 {len(data_urls)} URLs totales, {len(data_urls) - len(filtered_data_urls)} exclues, {len(filtered_data_urls)} à tester")
        
        # Exécution parallèle des tests
        tasks = [bounded_test(data) for data in filtered_data_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    return [r for r in results if isinstance(r, dict)]


def _get_http_routes():
    """
    Récupère toutes les HTTPRoutes à travers les namespaces
    Returns: list des HTTPRoutes avec leurs paths
    """
    urls_with_paths = []  # 📝 Liste pour stocker les URLs et leurs paths
    try:
        # 🔌 Initialisation des clients K8s
        core = client.CoreV1Api()
        v1Gateway = client.CustomObjectsApi()

        # 🔄 Parcours des namespaces
        for ns in core.list_namespace().items:
            try:
                routes = v1Gateway.list_namespaced_custom_object(
                    group="gateway.networking.k8s.io",
                    version="v1beta1",
                    plural="httproutes",
                    namespace=ns.metadata.name,
                )

                # ✨ Traitement de chaque HTTPRoute
                for route in routes["items"]:
                    if not route.get("spec"):
                        continue

                    # 🏷️ Extraction des hostnames
                    hostnames = route["spec"].get("hostnames", [])

                    # 🛣️ Extraction des paths depuis les rules
                    paths = []
                    for rule in route["spec"].get("rules", []):
                        for match in rule.get("matches", []):
                            if path_data := match.get(
                                "path"
                            ):  # Using assignment expression
                                paths.append(
                                    {
                                        "type": path_data.get("type", "PathPrefix"),
                                        "value": path_data.get("value", "/"),
                                    }
                                )
                                logger.debug(f"Found path: {path_data}")

                    # 📝 Pour chaque hostname, ajouter les paths
                    for hostname in hostnames:
                        if (
                            not paths
                        ):  # Si pas de paths définis, ajouter le path par défaut
                            paths = [{"type": "PathPrefix", "value": "/"}]

                        urls_with_paths.append(
                            {
                                "hostname": hostname,
                                "paths": paths,
                                "namespace": ns.metadata.name,
                                "annotations": route["metadata"].get("annotations", {}),
                                "name": route["metadata"]["name"],
                            }
                        )
                        logger.debug(f"Added HTTPRoute: {hostname} with paths: {paths}")

            except Exception as e:
                logger.warning(
                    f"❌ Erreur lors de la lecture du namespace {ns.metadata.name}: {e}"
                )
                continue

    except Exception as e:
        logger.error(f"❌ Erreur générale: {e}")
        raise

    logger.info(f"📊 Total HTTPRoutes processed: {len(urls_with_paths)}")
    return urls_with_paths


def _is_url_excluded(url, annotations=None):
    """

    Args:
        url: URL à vérifier
        annotations: Annotations de la ressource Kubernetes (optionnel)
    """
    # 🎯 SOLUTION 3: Vérification via annotation
    if (
        annotations
        and annotations.get("portal-checker.io/exclude", "").lower() == "true"
    ):
        logger.debug(f"🚫 URL exclue via annotation: {url}")
        return True

    # Normaliser l'URL en supprimant le slash final si présent
    normalized_url = url[:-1] if url.endswith("/") and len(url) > 1 else url

    # Vérification directe avec URL normalisée
    for excluded in excluded_urls:
        # Normaliser aussi l'URL exclue
        normalized_excluded = (
            excluded[:-1]
            if excluded.endswith("/") and not excluded.endswith("*/")
            else excluded
        )

        # Vérification exacte
        if normalized_url == normalized_excluded:
            logger.debug(f"🚫 URL exclue (exacte): {url}")
            return True

        # Vérification avec wildcards
        if normalized_excluded.endswith("*") and normalized_url.startswith(
            normalized_excluded[:-1]
        ):
            logger.debug(f"🚫 URL exclue (wildcard): {url}")
            return True
            
        # Vérification avec patterns complexes (*.internal/*)
        if "*" in normalized_excluded:
            import fnmatch
            if fnmatch.fnmatch(normalized_url, normalized_excluded):
                logger.debug(f"🚫 URL exclue (pattern): {url}")
                return True

    return False


# 📝 Liste pour stocker toutes les URLs
def _get_all_urls_with_details():
    """
    Récupère toutes les URLs avec leurs détails depuis les HTTPRoutes et Ingress
    Returns: list[dict] Liste des dictionnaires contenant les détails des URLs
    """
    url_details = []  # 📊 Liste pour stocker les dictionnaires de détails
    filtered_count = 0  # 🔍 Compteur pour les URLs filtrées

    try:
        # 🌐 Récupération et traitement des HTTPRoutes
        httproute_list = _get_http_routes()
        logger.info(f"✅ {len(httproute_list)} HTTPRoutes récupérées")

        # Traitement des HTTPRoutes
        for route in httproute_list:
            hostname = route["hostname"]
            paths = route["paths"]
            name = route["name"]
            namespace = route["namespace"]
            annotations = route["annotations"]
            status = route.get("status", "unknown")

            if not paths:
                full_url = f"{hostname}/"
                if not _is_url_excluded(full_url, annotations):
                    url_details.append(
                        {
                            "name": name,
                            "namespace": namespace,
                            "annotations": annotations,
                            "type": "HTTPRoute",
                            "url": full_url,
                            "status": status,
                            "info": "Default path",
                        }
                    )
                    logger.debug(f"Added default path for {hostname}")
                else:
                    filtered_count += 1
                    logger.debug(f"🚫 URL exclue: {full_url}")
            else:
                # 🛣️ Traitement de chaque path pour ce hostname
                for path in paths:
                    path_value = path.get("value", "/")
                    if not path_value.startswith("/"):
                        path_value = f"/{path_value}"

                    full_url = f"{hostname}{path_value}"
                    if not _is_url_excluded(full_url, annotations):
                        url_details.append(
                            {
                                "name": name,
                                "namespace": namespace,
                                "type": "HTTPRoute",
                                "annotations": annotations,
                                "url": full_url,
                                "status": status,
                                "info": f"Path: {path_value}",
                            }
                        )
                        logger.debug(f"Added HTTPRoute URL: {full_url}")
                    else:
                        filtered_count += 1
                        logger.debug(f"🚫 URL exclue: {full_url}")

        logger.info(f"✅ {len(url_details)} URLs HTTPRoute générées")

        # 🔄 Traitement des Ingress classiques
        try:
            v1 = client.NetworkingV1Api()
            ingress_list = v1.list_ingress_for_all_namespaces()

            for ingress in ingress_list.items:
                if not ingress.spec.rules:
                    continue

                ingress_name = ingress.metadata.name
                ingress_namespace = ingress.metadata.namespace
                ingress_status = (
                    "Active" if ingress.status.load_balancer.ingress else "Pending"
                )
                annotations = ingress.metadata.annotations or {}
                labels = ingress.metadata.labels or {}

                for rule in ingress.spec.rules:
                    if not rule.host:
                        continue

                    # Si pas de paths définis, on ajoute le hostname avec /
                    if not rule.http or not rule.http.paths:
                        full_url = f"{rule.host}/"
                        if not _is_url_excluded(full_url, annotations):
                            url_details.append(
                                {
                                    "name": ingress_name,
                                    "namespace": ingress_namespace,
                                    "annotations": annotations,
                                    "labels": labels,
                                    "type": "Ingress",
                                    "url": full_url,
                                    "status": ingress_status,
                                    "info": "Default path",
                                }
                            )
                            logger.debug(f"Added default Ingress path for {rule.host}")
                        else:
                            filtered_count += 1
                        continue

                    # Ajout de chaque path pour ce hostname
                    for path in rule.http.paths:
                        path_value = path.path if path.path else "/"
                        if not path_value.startswith("/"):
                            path_value = f"/{path_value}"

                        full_url = f"{rule.host}{path_value}"
                        backend_info = (
                            f"Service: {path.backend.service.name}"
                            if hasattr(path.backend, "service") and path.backend.service
                            else "No service"
                        )

                        if not _is_url_excluded(full_url, annotations):
                            url_details.append(
                                {
                                    "name": ingress_name,
                                    "namespace": ingress_namespace,
                                    "annotations": annotations,
                                    "labels": labels,
                                    "type": "Ingress",
                                    "url": full_url,
                                    "status": ingress_status,
                                    "info": f"Path: {path_value}, Backend: {backend_info}",
                                }
                            )
                            logger.debug(f"Added Ingress URL: {full_url}")
                        else:
                            filtered_count += 1

            logger.info(
                f"✅ {len(url_details)} URLs totales générées, {filtered_count} URLs exclues"
            )

        except client.exceptions.ApiException as e:
            logger.error(f"❌ Erreur lors de la récupération des Ingress: {e}")

    except Exception as e:
        logger.error(f"❌ Erreur inattendue: {e}")
        logger.exception(e)  # 📝 Log complet de l'erreur avec stack trace

    return url_details  # 📊 Retour de la liste de dictionnaires


def _refresh_urls_if_needed():
    """
    🚀 SOLUTION AUTO-REFRESH: Effectue un refresh automatique au démarrage si nécessaire
    """
    if not AUTO_REFRESH_ON_START:
        logger.info("🔄 Auto-refresh désactivé au démarrage")
        return

    # Vérifier si le fichier URLs existe et n'est pas vide
    urls_exist = False
    if os.path.exists(URLS_FILE):
        try:
            with open(URLS_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, list) and len(data) > 0:
                    urls_exist = True
                    logger.info(f"✅ {len(data)} URLs déjà présentes dans {URLS_FILE}")
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de la lecture du fichier URLs: {e}")

    if not urls_exist:
        logger.info("🚀 Création du fichier URLs manquant - Récupération des URLs...")
        try:
            # Initialisation de la configuration Kubernetes
            if os.getenv("FLASK_ENV") == "development":
                config.load_kube_config()
            else:
                config.load_incluster_config()

            # Récupération et sauvegarde des URLs
            data_urls = _get_all_urls_with_details()

            # Créer le répertoire si nécessaire (même en dev mode pour ce cas)
            config_dir = os.path.dirname(URLS_FILE)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)

            # Créer le fichier URLs même en mode dev si il n'existe pas
            with open(URLS_FILE, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    data_urls, f, default_flow_style=False, allow_unicode=True
                )

            logger.info(
                f"✅ {len(data_urls)} URLs sauvegardées automatiquement dans {URLS_FILE}"
            )

        except Exception as e:
            logger.error(f"❌ Erreur lors de la création du fichier URLs: {e}")


@app.route("/refresh", methods=["GET"])
def check_all_urls():
    """Get all ingress URLs and write them to a YAML file."""
    if os.getenv("FLASK_ENV") == "development":
        config.load_kube_config()
    else:
        config.load_incluster_config()

    # Récupérer toutes les URLs
    data_urls = _get_all_urls_with_details()

    # Skip file writing in development mode to avoid read-only filesystem errors
    if os.getenv("FLASK_ENV") != "development":
        # Assurez-vous que le répertoire config existe
        config_dir = os.path.dirname(URLS_FILE)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)

        with open(URLS_FILE, "w", encoding="utf-8") as f:
            yaml.safe_dump(data_urls, f, default_flow_style=False, allow_unicode=True)

    if os.getenv("FLASK_ENV") != "development":
        logger.info(f"✅ {len(data_urls)} URLs sauvegardées dans {URLS_FILE}")
    else:
        logger.info(f"✅ {len(data_urls)} URLs générées (dev mode - skip file write)")

    origin_url = request.referrer
    return redirect(origin_url) if origin_url else redirect("/")


@app.route("/urls", methods=["GET"])
def get_urls():
    """Get all URLs from the YAML file."""
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            data_urls = yaml.safe_load(f)
        # drop all data except url and name
        data_urls = [{"url": url["url"], "name": url["name"]} for url in data_urls]
        return jsonify(data_urls)
    else:
        return jsonify([])


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


@app.route("/health")
def health():
    """Endpoint de santé pour vérifier que l'application est en ligne"""
    logger.debug("ok")
    return {"status": "ok"}, 200


@app.route("/")
async def index():
    """Point d'entrée principal avec gestion asynchrone"""

    results = await test_urls_async()
    logger.info(f"✅ {len(results)} URLs testées")

    return render_template("index.html", results=results)


# 🚀 Initialisation au démarrage
_refresh_urls_if_needed()


if __name__ == "__main__":
    if os.getenv("FLASK_ENV") == "development":
        # Mode développement avec auto-reload
        port = int(os.getenv("PORT", 5001))
        app.run(debug=True, host="0.0.0.0", port=port)
    else:
        # Mode production avec Hypercorn
        from asgiref.wsgi import WsgiToAsgi
        from hypercorn.asyncio import serve
        from hypercorn.config import Config
        from werkzeug.middleware.proxy_fix import ProxyFix

        logger.info("Application started with hypercorn")
        ic.disable()
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
        asgi_app = WsgiToAsgi(app)
        asyncio.run(serve(asgi_app, Config()))
