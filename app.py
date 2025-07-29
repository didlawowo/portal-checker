import asyncio
import os
import ssl
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Optional, Union

import aiohttp
import certifi
import tomllib
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
    # Nettoyage du message pour supprimer les icônes indésirables
    message = record["message"]
    # Supprimer les icônes courantes (ladybug, etc.)
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

    # Ajout des informations supplémentaires si elles existent
    if record["extra"]:
        subset["extra"] = record["extra"]

    if record["exception"] is not None:
        subset["exception"] = record["exception"]

    return subset


def get_app_version() -> str:
    """Get application version from pyproject.toml"""
    # Try multiple possible locations
    possible_paths = [
        "pyproject.toml",
        "/app/pyproject.toml",
        os.path.join(os.path.dirname(__file__), "pyproject.toml"),
    ]

    for path in possible_paths:
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", "unknown")
        except (FileNotFoundError, tomllib.TOMLDecodeError):
            continue

    return "unknown"


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
            serialize=serialize_record,  # Utilise notre fonction personnalisée
            format="{message}",  # Format minimal car géré par serialize_record
            enqueue=True,  # Rend le logging thread-safe
            backtrace=True,  # Inclut les stack traces détaillées
            diagnose=False,  # Désactive l'affichage des variables locales dans les traces
            catch=True,  # Capture les erreurs de logging
        )
    else:
        # Configuration pour le format texte lisible (sans icônes)
        def clean_message(record):
            # Nettoyer le message des icônes
            message = record["message"]
            message = message.replace("🐞", "").replace("🔧", "").replace("⚠️", "").replace("❌", "").replace("✅", "")
            message = message.replace("🔄", "").replace("📊", "").replace("🚀", "").replace("💾", "").replace("ℹ️", "")
            record["message"] = message.strip()
            return True
            
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
            level=log_level,
            colorize=True,
            enqueue=True,
            backtrace=True,
            diagnose=True,
            catch=True,
            filter=clean_message,
        )


# Configuration initiale du logger
# En développement, utiliser le format texte, sinon JSON
flask_env = os.getenv("FLASK_ENV", "")
default_format = "text" if flask_env == "development" else "json"
LOG_FORMAT = os.getenv("LOG_FORMAT", default_format)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Debug de la configuration
print(f"FLASK_ENV: {flask_env}")
print(f"LOG_FORMAT: {LOG_FORMAT}")

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

# 🚀 Cache configuration pour optimiser CPU
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))  # 5 minutes par défaut
KUBERNETES_POLL_INTERVAL = int(
    os.getenv("KUBERNETES_POLL_INTERVAL", "600")
)  # 10 minutes
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))  # 30 secondes par défaut

# 💾 Cache global pour les ressources Kubernetes
_kubernetes_cache: dict[str, Any] = {"data": None, "last_updated": None, "expiry": None}

# 🔄 Cache global pour les résultats de test des URLs
_test_results_cache: dict[str, Any] = {"results": [], "last_updated": None}

# 🔄 Variables pour le timer périodique
_background_task = None
_stop_background_task = False

URLS_FILE = os.getenv(
    "URLS_FILE",
    "config/urls.yaml"
    if os.getenv("FLASK_ENV") == "development"
    else "/app/data/urls.yaml",
)
EXCLUDED_URLS_FILE = os.getenv(
    "EXCLUDED_URLS_FILE",
    "config/excluded-urls.yaml"
    if os.getenv("FLASK_ENV") == "development"
    else "/app/config/excluded-urls.yaml",
)

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
            SLACK_WEBHOOK_URL,
            json=message,
            timeout=aiohttp.ClientTimeout(total=TIMEOUT),
        ) as response:
            await response.text()

    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'alerte Slack: {str(e)}")


async def check_single_url(session: aiohttp.ClientSession, data: dict) -> dict:
    """Test une seule URL de manière asynchrone

    Args:
        session: Session aiohttp pour réutiliser les connexions
        data: Dictionnaire contenant les données de l'URL à tester
    Returns:
        Dict avec le statut du test
    """
    url = data.get("url", "")  # Récupérer l'URL de manière sécurisée
    start_time = time.time()

    try:
        logger.debug(f"Test de l'URL {url}")
        full_url = f"https://{url}" if not url.startswith("http") else url

        async with session.get(
            full_url, timeout=aiohttp.ClientTimeout(total=TIMEOUT), ssl=ssl_context
        ) as response:
            response_time = round(
                (time.time() - start_time) * 1000
            )  # ms, arrondi à l'unité
            status_code = response.status

            details = ""
            if status_code != 200 and status_code != 401:
                details = f"❌ {response.reason}"
                logger.debug(f"Erreur pour l'URL {full_url} - Status: {status_code}")
                if SLACK_NOTIFICATIONS_ENABLED:
                    await send_slack_alert_async(session, url, status_code, details)

            if status_code == 404:
                details = "❓ Not Found"
                # Envoyer une alerte Slack
                if SLACK_NOTIFICATIONS_ENABLED:
                    await send_slack_alert_async(session, url, status_code, details)

            # Mettre à jour le dictionnaire original avec les résultats
            data["status"] = status_code
            data["details"] = details
            data["response_time"] = response_time

            logger.debug(
                f"Test de l'URL {url} : {status_code}, {response_time}ms, data: {data}"
            )

            return data

    except asyncio.TimeoutError:
        response_time = round((time.time() - start_time) * 1000)
        result = data.copy()
        result.update(
            {
                "status": 504,  # 🕒 Gateway Timeout plus approprié que 500
                "details": "❌ Timeout Error",
                "response_time": response_time,
            }
        )
        return result

    except Exception as e:
        response_time = round((time.time() - start_time) * 1000)
        result = data.copy()
        result.update(
            {
                "status": 500,
                "details": f"❌ Error: {str(e)}",
                "response_time": response_time,
            }
        )
        return result


async def check_urls_async(file_path: str | None = None, update_cache: bool = True) -> list[dict]:
    """Test plusieurs URLs en parallèle avec limitation de concurrence

    Args:
        file_path: Chemin du fichier YAML contenant les URLs
        update_cache: Si True, met à jour le cache des résultats
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
                return await check_single_url(session, data)

        # Filtrer les URLs exclues avant de lancer les tests
        filtered_data_urls = [
            data for data in data_urls if not _is_url_excluded(data.get("url", ""))
        ]
        logger.info(
            f"🔍 {len(data_urls)} URLs totales, {len(data_urls) - len(filtered_data_urls)} exclues, {len(filtered_data_urls)} à tester"
        )

        # Exécution parallèle des tests
        tasks = [bounded_test(data) for data in filtered_data_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    final_results = [r for r in results if isinstance(r, dict)]
    
    # Compteur OK / WARN / ERROR
    ok_count = len([r for r in final_results if r.get("status") == 200])
    warn_count = len([r for r in final_results if 400 <= r.get("status", 0) < 500])
    error_count = len([r for r in final_results if r.get("status", 0) >= 500 or (r.get("status", 0) < 400 and r.get("status", 0) != 200)])
    
    logger.info(f"📊 Résultats des tests: {ok_count} OK / {warn_count} WARN / {error_count} ERROR sur {len(final_results)} URLs")
    
    # Mettre à jour le cache des résultats si demandé
    if update_cache:
        _test_results_cache["results"] = final_results
        _test_results_cache["last_updated"] = datetime.now()
        logger.debug(f"🔄 Cache des résultats mis à jour avec {len(final_results)} URLs")

    return final_results


def _get_http_routes():
    """
    Récupère toutes les HTTPRoutes à travers les namespaces
    Returns: list des HTTPRoutes avec leurs paths
    """
    urls_with_paths = []  # 📝 Liste pour stocker les URLs et leurs paths
    total_namespaces = 0
    httproutes_found = 0
    
    try:
        # 🔌 Initialisation des clients K8s
        core = client.CoreV1Api()
        v1Gateway = client.CustomObjectsApi()

        # 🔄 Parcours des namespaces
        namespaces = core.list_namespace().items
        total_namespaces = len(namespaces)
        logger.info(f"🔍 Début de la recherche HTTPRoute dans {total_namespaces} namespaces")
        
        for ns in namespaces:
            namespace_name = ns.metadata.name
            try:
                logger.debug(f"🔍 Recherche HTTPRoute dans le namespace: {namespace_name}")
                routes = v1Gateway.list_namespaced_custom_object(
                    group="gateway.networking.k8s.io",
                    version="v1beta1",
                    plural="httproutes",
                    namespace=namespace_name,
                )

                routes_in_ns = len(routes["items"])
                if routes_in_ns > 0:
                    logger.info(f"✅ Trouvé {routes_in_ns} HTTPRoute(s) dans le namespace {namespace_name}")
                    httproutes_found += routes_in_ns
                else:
                    logger.debug(f"➖ Aucune HTTPRoute dans le namespace {namespace_name}")

                # ✨ Traitement de chaque HTTPRoute
                for route in routes["items"]:
                    if not route.get("spec"):
                        continue

                    # 📋 Extraction des métadonnées complètes
                    route_metadata = route.get("metadata", {})
                    route_name = route_metadata.get("name", "unknown")
                    route_namespace = ns.metadata.name

                    # 🏷️ Annotations et labels avec gestion d'erreur
                    annotations = route_metadata.get("annotations", {})
                    labels = route_metadata.get("labels", {})

                    # 📊 Informations de statut et création
                    creation_timestamp = route_metadata.get("creationTimestamp")
                    resource_version = route_metadata.get("resourceVersion")

                    # 🏷️ Extraction des hostnames
                    hostnames = route["spec"].get("hostnames", [])

                    # 🏃 Extraction de la gateway depuis gatewayRefs
                    gateway_refs = route["spec"].get("gatewayRefs", [])

                    logger.debug(
                        f"Processing HTTPRoute {route_name} in {route_namespace} with {len(annotations)} annotations, gateway_refs: {gateway_refs}"
                    )
                    gateway_name = None
                    if gateway_refs:
                        # Prendre la première gateway référencée
                        gateway_ref = gateway_refs[0]
                        gateway_name = gateway_ref.get("name", "unknown")
                        # Ajouter le namespace si disponible
                        if gateway_ref.get("namespace"):
                            gateway_name = f"{gateway_ref['namespace']}/{gateway_name}"
                    
                    logger.debug(f"HTTPRoute {route_name}: gateway_name = {gateway_name}")

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
                                "namespace": route_namespace,
                                "annotations": annotations,
                                "labels": labels,
                                "name": route_name,
                                "creation_timestamp": creation_timestamp,
                                "resource_version": resource_version,
                                "resource_type": "HTTPRoute",
                                "gateway": gateway_name,
                            }
                        )
                        logger.debug(
                            f"Added HTTPRoute: {hostname} with {len(annotations)} annotations and paths: {paths}"
                        )

            except Exception as e:
                logger.warning(
                    f"❌ Erreur lors de la lecture du namespace {namespace_name}: {e}"
                )
                continue

    except Exception as e:
        logger.error(f"❌ Erreur générale lors de la récupération HTTPRoute: {e}")
        raise

    logger.info(f"📊 HTTPRoute - Trouvé {httproutes_found} routes dans {total_namespaces} namespaces, généré {len(urls_with_paths)} URLs")
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
def _deduplicate_urls(url_details):
    """
    Supprime les URLs dupliquées en gardant la première occurrence
    Args:
        url_details: Liste des dictionnaires contenant les détails des URLs
    Returns:
        Liste dédupliquée des URLs
    """
    seen = set()
    unique_urls = []
    duplicates_count = 0

    for url_data in url_details:
        # Créer une clé unique basée sur URL, namespace et nom
        key = (
            url_data.get("url", ""),
            url_data.get("namespace", ""),
            url_data.get("name", ""),
        )

        if key not in seen:
            seen.add(key)
            unique_urls.append(url_data)
        else:
            duplicates_count += 1
            logger.debug(f"🔄 URL dupliquée ignorée: {url_data.get('url', 'unknown')}")

    if duplicates_count > 0:
        logger.info(f"🔄 {duplicates_count} URLs dupliquées supprimées")

    return unique_urls


def _extract_essential_annotations(annotations):
    """
    Extrait seulement les annotations essentielles pour réduire l'usage mémoire
    Args:
        annotations: Dictionnaire complet des annotations
    Returns:
        Dictionnaire avec seulement les annotations importantes
    """
    if not annotations:
        return {}

    # Garder seulement les annotations importantes pour le portail checker
    essential_keys = {
        # Portal checker
        "portal-checker.io/exclude",
        # Certificats et TLS
        "cert-manager.io/cluster-issuer",
        "cert-manager.io/issuer",
        # Ingress/Gateway configurations
        "ingress.kubernetes.io/ssl-redirect",
        "nginx.ingress.kubernetes.io/cors-allow-origin",
        "kubernetes.io/ingress.class",
        # Gateway API annotations
        "gateway.networking.k8s.io/gateway-name",
        "external-dns.alpha.kubernetes.io/hostname",
        "external-dns.alpha.kubernetes.io/target",
        # Traefik annotations
        "traefik.ingress.kubernetes.io/router.entrypoints",
        "traefik.ingress.kubernetes.io/router.tls",
        # Security & Auth
        "nginx.ingress.kubernetes.io/auth-type",
        "nginx.ingress.kubernetes.io/auth-realm",
        # Rate limiting
        "nginx.ingress.kubernetes.io/rate-limit",
        "nginx.ingress.kubernetes.io/rate-limit-qps",
    }

    # D'abord, garder toutes les annotations essentielles
    essential_annotations = {}
    other_annotations = {}

    for key, value in annotations.items():
        if key in essential_keys:
            essential_annotations[key] = value
        # Garder les annotations courtes (moins de 50 caractères)
        elif len(str(value)) < 50:
            other_annotations[key] = value

    # Combiner les annotations, en priorisant les essentielles
    result = essential_annotations.copy()

    # Ajouter les autres annotations jusqu'à la limite de 10
    remaining_slots = 10 - len(result)
    if remaining_slots > 0:
        for key, value in list(other_annotations.items())[:remaining_slots]:
            result[key] = value

    return result


def _analyze_httproute_annotations(annotations, labels=None):
    """
    Analyse les annotations HTTPRoute et enrichit les données avec des informations utiles
    Args:
        annotations: Dict des annotations de la HTTPRoute
        labels: Dict des labels de la HTTPRoute (optionnel)
    Returns:
        Dict avec les annotations analysées et des méta-informations
    """
    if not annotations:
        return {"annotations": {}, "analysis": {}, "total_annotations": 0}

    analysis = {
        "has_tls": False,
        "has_auth": False,
        "has_rate_limiting": False,
        "has_cors": False,
        "gateway_config": None,
        "cert_issuer": None,
        "excluded": False,
    }

    # Analyse des annotations
    for key, value in annotations.items():
        # TLS et certificats
        if "tls" in key.lower() or "cert-manager" in key:
            analysis["has_tls"] = True
            if "issuer" in key:
                analysis["cert_issuer"] = value

        # Authentification
        elif "auth" in key.lower():
            analysis["has_auth"] = True

        # Rate limiting
        elif "rate-limit" in key.lower():
            analysis["has_rate_limiting"] = True

        # CORS
        elif "cors" in key.lower():
            analysis["has_cors"] = True

        # Gateway configuration
        elif "gateway" in key.lower():
            analysis["gateway_config"] = value

        # Exclusion portal-checker
        elif key == "portal-checker.io/exclude" and value.lower() == "true":
            analysis["excluded"] = True

    # Analyse des labels si disponibles
    if labels:
        for key, value in labels.items():
            if "gateway" in key.lower():
                analysis["gateway_config"] = f"label:{value}"

    return {
        "annotations": _extract_essential_annotations(annotations),
        "analysis": analysis,
        "total_annotations": len(annotations),
    }


def _is_cache_valid():
    """Vérifier si le cache Kubernetes est encore valide"""
    if _kubernetes_cache["expiry"] is None:
        return False
    return datetime.now() < _kubernetes_cache["expiry"]


def _get_cached_urls():
    """Récupérer les URLs depuis le cache si valide"""
    if _is_cache_valid():
        logger.debug("🚀 Utilisation du cache Kubernetes valide")
        return _kubernetes_cache["data"]

    # Alerte si le cache est expiré depuis trop longtemps
    if _kubernetes_cache["expiry"]:
        expired_since = datetime.now() - _kubernetes_cache["expiry"]
        if expired_since.total_seconds() > 600:  # Plus de 10 minutes d'expiration
            logger.warning(
                f"⚠️ Cache expiré depuis {int(expired_since.total_seconds())}s - problème possible!"
            )

    return None


def _update_cache(data):
    """Mettre à jour le cache avec les nouvelles données"""
    now = datetime.now()
    expiry_time = now + timedelta(seconds=CACHE_TTL_SECONDS)

    _kubernetes_cache["data"] = data
    _kubernetes_cache["last_updated"] = now
    _kubernetes_cache["expiry"] = expiry_time

    logger.info(
        f"💾 Cache Kubernetes mis à jour, expiration: {expiry_time.strftime('%H:%M:%S')}"
    )


def _reset_cache():
    """Réinitialiser le cache - utilisé principalement pour les tests"""
    global _kubernetes_cache
    _kubernetes_cache = {"data": None, "last_updated": None, "expiry": None}
    logger.debug("🗑️ Cache réinitialisé")


def _get_all_urls_with_details():
    """
    Récupère toutes les URLs avec leurs détails depuis les HTTPRoutes et Ingress
    Utilise un cache pour réduire la charge CPU des appels Kubernetes API
    Returns: list[dict] Liste des dictionnaires contenant les détails des URLs
    """
    # 🚀 Vérifier le cache en premier
    cached_data = _get_cached_urls()
    if cached_data is not None:
        return cached_data

    logger.info("🔄 Cache expiré, récupération des données Kubernetes...")
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
            gateway_name = route.get("gateway", "unknown")

            if not paths:
                full_url = f"{hostname}/"
                if not _is_url_excluded(full_url, annotations):
                    url_details.append(
                        {
                            "name": name,
                            "namespace": namespace,
                            "type": "HTTPRoute",
                            "annotations": _extract_essential_annotations(annotations),
                            "labels": _extract_essential_annotations(route.get("labels", {})),
                            "url": full_url,
                            "status": status,
                            "info": "Default path",
                            "gateway": gateway_name,
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
                                "annotations": _extract_essential_annotations(annotations),
                                "labels": _extract_essential_annotations(route.get("labels", {})),
                                "url": full_url,
                                "status": status,
                                "info": f"Path: {path_value}",
                                "gateway": gateway_name,
                            }
                        )
                        logger.debug(f"Added HTTPRoute URL: {full_url}")
                    else:
                        filtered_count += 1
                        logger.debug(f"🚫 URL exclue: {full_url}")

        logger.info(f"✅ {len(url_details)} URLs HTTPRoute générées")

        # 🔄 Traitement des Ingress classiques
        ingress_count = 0
        try:
            v1 = client.NetworkingV1Api()
            ingress_list = v1.list_ingress_for_all_namespaces()

            for ingress in ingress_list.items:
                if not ingress.spec.rules:
                    continue

                ingress_count += 1
                ingress_name = ingress.metadata.name
                ingress_namespace = ingress.metadata.namespace
                ingress_status = (
                    "Active" if ingress.status.load_balancer.ingress else "Pending"
                )
                annotations = ingress.metadata.annotations or {}
                labels = ingress.metadata.labels or {}
                
                # 🏃 Extraction de l'ingress class
                ingress_class = None
                # Méthode 1: depuis la spec.ingressClassName (moderne)
                if hasattr(ingress.spec, 'ingress_class_name') and ingress.spec.ingress_class_name:
                    ingress_class = ingress.spec.ingress_class_name
                elif hasattr(ingress.spec, 'ingressClassName') and ingress.spec.ingressClassName:
                    ingress_class = ingress.spec.ingressClassName
                # Méthode 2: depuis l'annotation (légacy)
                elif annotations.get('kubernetes.io/ingress.class'):
                    ingress_class = annotations.get('kubernetes.io/ingress.class')
                # Méthode 3: depuis nginx.ingress.kubernetes.io/ingress.class
                elif annotations.get('nginx.ingress.kubernetes.io/ingress.class'):
                    ingress_class = annotations.get('nginx.ingress.kubernetes.io/ingress.class')
                
                logger.debug(f"Ingress {ingress_name}: ingress_class = {ingress_class}")

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
                                    "annotations": _extract_essential_annotations(
                                        annotations
                                    ),
                                    "labels": _extract_essential_annotations(
                                        labels
                                    ),  # Also optimize labels
                                    "type": "Ingress",
                                    "url": full_url,
                                    "status": ingress_status,
                                    "info": "Default path",
                                    "ingress_class": ingress_class,
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
                                    "annotations": _extract_essential_annotations(
                                        annotations
                                    ),
                                    "labels": _extract_essential_annotations(
                                        labels
                                    ),  # Also optimize labels
                                    "type": "Ingress",
                                    "url": full_url,
                                    "status": ingress_status,
                                    "info": f"Path: {path_value}, Backend: {backend_info}",
                                    "ingress_class": ingress_class,
                                }
                            )
                            logger.debug(f"Added Ingress URL: {full_url}")
                        else:
                            filtered_count += 1

            logger.info(f"📊 Ingress - Traité {ingress_count} ingress, généré {len(url_details)} URLs totales, {filtered_count} URLs exclues")

        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des Ingress: {e}")

    except Exception as e:
        logger.error(f"❌ Erreur inattendue: {e}")
        logger.exception(e)  # 📝 Log complet de l'erreur avec stack trace

    # 🔄 Déduplication des URLs avant retour
    url_details = _deduplicate_urls(url_details)
    # Calculer le nombre de HTTPRoute depuis les données
    httproute_count = len([url for url in url_details if url.get("type") == "HTTPRoute"])
    logger.info(f"✅ Résumé final: {httproute_count} HTTPRoute(s) + {ingress_count} Ingress = {len(url_details)} URLs uniques")

    # 💾 Mettre à jour le cache avec les nouvelles données
    _update_cache(url_details)

    return url_details  # 📊 Retour de la liste de dictionnaires


async def _periodic_url_check():
    """
    🔄 Tâche de fond qui teste les URLs périodiquement
    """
    global _stop_background_task
    
    while not _stop_background_task:
        try:
            logger.debug(f"🔄 Démarrage du test périodique (intervalle: {CHECK_INTERVAL}s)")
            await check_urls_async(update_cache=True)
            logger.info(f"✅ Test périodique terminé, prochaine exécution dans {CHECK_INTERVAL}s")
        except Exception as e:
            logger.error(f"❌ Erreur lors du test périodique: {e}")
        
        # Attendre l'intervalle configuré
        await asyncio.sleep(CHECK_INTERVAL)


def _start_background_task():
    """
    🚀 Démarre la tâche de fond pour les tests périodiques
    """
    global _background_task, _stop_background_task
    
    if _background_task is not None:
        logger.warning("⚠️ Tâche de fond déjà en cours")
        return
    
    _stop_background_task = False
    
    def run_background():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_periodic_url_check())
        finally:
            loop.close()
    
    import threading
    _background_task = threading.Thread(target=run_background, daemon=True)
    _background_task.start()
    logger.info(f"🚀 Tâche de fond démarrée (tests toutes les {CHECK_INTERVAL}s)")


def _stop_background_task_func():
    """
    🛑 Arrête la tâche de fond
    """
    global _stop_background_task
    _stop_background_task = True
    logger.info("🛑 Arrêt de la tâche de fond demandé")


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

    # Assurez-vous que le répertoire config existe
    config_dir = os.path.dirname(URLS_FILE)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)

    try:
        with open(URLS_FILE, "w", encoding="utf-8") as f:
            yaml.safe_dump(data_urls, f, default_flow_style=False, allow_unicode=True)
        logger.info(f"✅ {len(data_urls)} URLs sauvegardées dans {URLS_FILE}")
    except (PermissionError, OSError) as e:
        logger.warning(f"⚠️ Impossible d'écrire dans {URLS_FILE}: {e}")
        logger.info(f"✅ {len(data_urls)} URLs générées (fichier non sauvegardé)")

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


@app.route("/memory")
def memory_status():
    """Memory usage endpoint for monitoring"""
    try:
        import psutil

        process = psutil.Process()
        memory_info = process.memory_info()

        return jsonify(
            {
                "memory_rss_mb": round(memory_info.rss / 1024 / 1024, 2),
                "memory_vms_mb": round(memory_info.vms / 1024 / 1024, 2),
                "memory_percent": round(process.memory_percent(), 2),
                "status": "ok",
            }
        )
    except ImportError:
        return jsonify({"error": "psutil not available - add it to dependencies"}), 500


@app.route("/cache/clear", methods=["POST"])
def cache_clear():
    """Force la suppression du cache pour debugging"""
    global _kubernetes_cache
    _kubernetes_cache = {"data": None, "last_updated": None, "expiry": None}
    logger.warning("🗑️ Cache forcé à zéro via /cache/clear")
    return jsonify({"message": "Cache cleared", "status": "ok"})


@app.route("/cache/force-refresh", methods=["POST"])
def cache_force_refresh():
    """Force un refresh immédiat du cache"""
    try:
        # Invalider le cache
        _kubernetes_cache["expiry"] = datetime.now() - timedelta(seconds=1)

        # Forcer un nouveau fetch
        data = _get_all_urls_with_details()

        return jsonify(
            {"message": "Cache forcé refresh", "urls_count": len(data), "status": "ok"}
        )
    except Exception as e:
        logger.error(f"❌ Erreur lors du force refresh: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/cache")
def cache_status():
    """Cache status endpoint for monitoring CPU optimizations"""
    now = datetime.now()
    cache_data = _kubernetes_cache

    # Calculs pour diagnostics
    is_valid = _is_cache_valid()
    urls_count = len(cache_data["data"]) if cache_data["data"] else 0

    # Détection de problèmes
    issues = []
    if not is_valid and cache_data["expiry"]:
        expired_since = int((now - cache_data["expiry"]).total_seconds())
        if expired_since > 600:  # Plus de 10 min
            issues.append(f"Cache expiré depuis {expired_since}s")

    if urls_count == 0:
        issues.append("Aucune URL dans le cache")

    if not cache_data["last_updated"]:
        issues.append("Cache jamais initialisé")

    return jsonify(
        {
            "cache_valid": is_valid,
            "last_updated": cache_data["last_updated"].isoformat()
            if cache_data["last_updated"]
            else None,
            "expiry": cache_data["expiry"].isoformat()
            if cache_data["expiry"]
            else None,
            "ttl_seconds": CACHE_TTL_SECONDS,
            "cached_urls_count": urls_count,
            "seconds_until_expiry": int((cache_data["expiry"] - now).total_seconds())
            if cache_data["expiry"] and cache_data["expiry"] > now
            else 0,
            "issues": issues,
            "health": "ok" if not issues else "warning",
            "status": "ok",
        }
    )


@app.route("/")
def index():
    """Point d'entrée principal - affiche les résultats mis en cache"""
    
    # Récupérer les résultats depuis le cache
    results = _test_results_cache["results"]
    last_updated = _test_results_cache["last_updated"]
    
    # Si pas de résultats en cache, afficher un message
    if not results:
        logger.info("ℹ️ Aucun résultat en cache, en attente du premier test périodique")
        results = []
    else:
        logger.debug(f"📊 Affichage de {len(results)} résultats mis en cache")

    return render_template(
        "index.html", 
        results=results, 
        version=get_app_version(),
        last_updated=last_updated.strftime("%Y-%m-%d %H:%M:%S") if last_updated else "En attente..."
    )


# 🚀 Initialisation au démarrage
_refresh_urls_if_needed()

# 🔄 Démarrage de la tâche de fond pour les tests périodiques
try:
    if os.getenv("FLASK_ENV") == "development":
        config.load_kube_config()
    else:
        config.load_incluster_config()
    
    _start_background_task()
except Exception as e:
    logger.error(f"❌ Erreur lors du démarrage de la tâche de fond: {e}")
    logger.warning("⚠️ L'application fonctionne sans tests périodiques")


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
