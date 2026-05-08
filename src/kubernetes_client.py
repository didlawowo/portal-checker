"""
Kubernetes client for discovering and managing ingress/routes
"""

import fnmatch
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml
from kubernetes import client, config
from loguru import logger

from .config import (
    EXCLUDE_SELF,
    EXCLUDED_URLS_FILE,
    KUBE_ENV,
    KUBERNETES_POLL_INTERVAL,
    SELF_APP_NAME,
    SELF_POD_NAME,
    SELF_POD_NAMESPACE,
)

# Cache global pour les ressources Kubernetes
_kubernetes_cache: Dict[str, Any] = {"data": None, "last_updated": None, "expiry": None}

# Exclusions cache
_excluded_patterns_cache: Optional[List[str]] = None
_excluded_patterns_last_loaded: Optional[datetime] = None


def init_kubernetes() -> None:
    """Initialize Kubernetes client configuration"""
    try:
        if KUBE_ENV == "production":
            config.load_incluster_config()
            logger.info("✅ Configuration Kubernetes in-cluster chargée")
        else:
            config.load_kube_config()
            logger.info("✅ Configuration Kubernetes locale chargée")
    except Exception as e:
        logger.error(
            f"❌ Erreur lors du chargement de la configuration Kubernetes: {e}"
        )
        raise


def _load_excluded_patterns() -> List[str]:
    """Charge les patterns d'exclusion depuis le fichier YAML avec cache de 5 minutes"""
    global _excluded_patterns_cache, _excluded_patterns_last_loaded

    # Vérifier si le cache est encore valide (5 minutes)
    if (
        _excluded_patterns_cache is not None
        and _excluded_patterns_last_loaded is not None
        and datetime.now() - _excluded_patterns_last_loaded < timedelta(minutes=5)
    ):
        return _excluded_patterns_cache

    patterns = []
    try:
        with open(EXCLUDED_URLS_FILE, "r") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict) and "excluded_urls" in data:
                patterns = data["excluded_urls"]
            elif isinstance(data, list):
                patterns = data

            # Mettre à jour le cache
            _excluded_patterns_cache = patterns
            _excluded_patterns_last_loaded = datetime.now()

            logger.info(
                f"✅ {len(patterns)} patterns d'exclusion chargés depuis {EXCLUDED_URLS_FILE}"
            )
            logger.debug(f"Patterns d'exclusion: {patterns}")
    except FileNotFoundError:
        logger.warning(f"⚠️ Fichier d'exclusions non trouvé: {EXCLUDED_URLS_FILE}")
    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement des exclusions: {e}")

    return patterns


def invalidate_excluded_patterns_cache() -> None:
    """Invalide le cache des patterns d'exclusion pour forcer un rechargement"""
    global _excluded_patterns_cache, _excluded_patterns_last_loaded
    _excluded_patterns_cache = None
    _excluded_patterns_last_loaded = None
    logger.debug("🔄 Cache des patterns d'exclusion invalidé")


def _is_cache_valid() -> bool:
    """Check if Kubernetes cache is still valid"""
    if _kubernetes_cache["expiry"] is None:
        return False
    return datetime.now() < _kubernetes_cache["expiry"]


def _get_cached_urls() -> Optional[List[Dict[str, Any]]]:
    """Get cached URLs if valid"""
    if _is_cache_valid() and _kubernetes_cache["data"] is not None:
        logger.debug("🚀 Utilisation du cache Kubernetes")
        return _kubernetes_cache["data"]
    return None


def _update_cache(data: List[Dict[str, Any]]) -> None:
    """Update Kubernetes cache"""
    now = datetime.now()
    expiry_time = now + timedelta(seconds=KUBERNETES_POLL_INTERVAL)

    _kubernetes_cache["data"] = data
    _kubernetes_cache["last_updated"] = now
    _kubernetes_cache["expiry"] = expiry_time

    logger.info(
        f"💾 Cache Kubernetes mis à jour, expiration: {expiry_time.strftime('%H:%M:%S')}"
    )


def _filter_annotations(annotations: Dict[str, str]) -> Dict[str, str]:
    """Filter and limit annotations to essential ones"""
    if not annotations:
        return {}

    # Annotations essentielles à garder
    essential_annotations = {
        "cert-manager.io/cluster-issuer",
        "cert-manager.io/issuer",
        "kubernetes.io/ingress.class",
        "nginx.ingress.kubernetes.io/backend-protocol",
        "nginx.ingress.kubernetes.io/ssl-redirect",
        "portal-checker.io/exclude",
        "traefik.ingress.kubernetes.io/router.tls",
        "traefik.ingress.kubernetes.io/router.entrypoints",
    }

    result = {}
    other_annotations = {}

    for key, value in annotations.items():
        # Garder les annotations essentielles en priorité
        if key in essential_annotations:
            result[key] = value
        # Pour les autres, filtrer celles avec des valeurs trop longues
        elif len(str(value)) <= 50:
            other_annotations[key] = value

    # Ajouter d'autres annotations jusqu'à la limite de 10
    remaining_slots = 10 - len(result)
    if remaining_slots > 0:
        for key, value in list(other_annotations.items())[:remaining_slots]:
            result[key] = value

    return result


def _is_self_resource(name: str, namespace: str, labels: Dict[str, str]) -> bool:
    """Detect whether the given Ingress/HTTPRoute belongs to the portal-checker
    deployment itself, so that it can be excluded from the URL list by default.

    Detection order:
      1. Match against POD_NAME/POD_NAMESPACE injected via the K8s downward API
         (the resource name typically equals the Helm release fullname, which is
         a prefix of the pod name).
      2. Fallback to a substring match on SELF_APP_NAME ("portal-checker").
    """
    if not EXCLUDE_SELF:
        return False

    if SELF_POD_NAMESPACE and namespace == SELF_POD_NAMESPACE:
        if SELF_POD_NAME and SELF_POD_NAME.startswith(name):
            return True
        if (
            labels.get("app.kubernetes.io/name") == SELF_APP_NAME
            or labels.get("app.kubernetes.io/part-of") == SELF_APP_NAME
        ):
            return True

    return SELF_APP_NAME in name


def _deduplicate_urls(urls_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate URLs based on (url, namespace, name) triplet"""
    seen: Set[Tuple[str, str, str]] = set()
    unique_urls = []

    for data in urls_data:
        key = (data.get("url", ""), data.get("namespace", ""), data.get("name", ""))
        if key not in seen:
            seen.add(key)
            unique_urls.append(data)

    return unique_urls


def get_all_urls_with_details(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Get all URLs with details from HTTPRoutes and Ingress
    Uses cache to reduce CPU load from Kubernetes API calls

    Args:
        force_refresh: If True, bypass cache and fetch fresh data from Kubernetes
    """
    # Check cache first (unless force_refresh is True)
    if not force_refresh:
        cached_data = _get_cached_urls()
        if cached_data is not None:
            return cached_data

    if force_refresh:
        logger.info(
            "🔄 Refresh forcé - récupération des données depuis l'API Kubernetes"
        )
    else:
        logger.debug("🔄 Récupération des données depuis l'API Kubernetes")

    v1 = client.NetworkingV1Api()
    v1_core = client.CoreV1Api()
    custom_api = client.CustomObjectsApi()

    all_urls_data = []

    # Get all namespaces
    try:
        namespaces = v1_core.list_namespace()
        namespace_names = [ns.metadata.name for ns in namespaces.items]
        logger.debug(f"📦 {len(namespace_names)} namespaces trouvés")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des namespaces: {e}")
        return []

    # Process Ingresses
    self_excluded_count = 0
    for namespace in namespace_names:
        try:
            ingresses = v1.list_namespaced_ingress(namespace)
            for ingress in ingresses.items:
                if _is_self_resource(
                    ingress.metadata.name,
                    namespace,
                    ingress.metadata.labels or {},
                ):
                    self_excluded_count += 1
                    logger.debug(
                        f"🚫 Auto-exclusion de l'Ingress portal-checker: "
                        f"{namespace}/{ingress.metadata.name}"
                    )
                    continue
                ingress_class = None
                if ingress.spec.ingress_class_name:
                    ingress_class = ingress.spec.ingress_class_name
                elif ingress.metadata.annotations:
                    ingress_class = ingress.metadata.annotations.get(
                        "kubernetes.io/ingress.class", "nginx"
                    )

                for rule in ingress.spec.rules or []:
                    host = rule.host
                    if not host:
                        continue

                    for path in rule.http.paths if rule.http else []:
                        url = (
                            f"https://{host}{path.path}"
                            if path.path != "/"
                            else f"https://{host}"
                        )

                        filtered_annotations = _filter_annotations(
                            ingress.metadata.annotations or {}
                        )

                        url_data = {
                            "url": url,
                            "namespace": namespace,
                            "name": ingress.metadata.name,
                            "type": "ingress",
                            "ingress_class": ingress_class,
                            "annotations": filtered_annotations,
                            "labels": ingress.metadata.labels or {},
                            "path": path.path,
                            "backend": {
                                "service": path.backend.service.name
                                if path.backend.service
                                else None,
                                "port": path.backend.service.port.number
                                if path.backend.service and path.backend.service.port
                                else None,
                            },
                        }
                        all_urls_data.append(url_data)
        except Exception as e:
            logger.debug(f"Pas d'Ingress dans {namespace}: {e}")

    # Process HTTPRoutes (Gateway API)
    for namespace in namespace_names:
        try:
            routes = custom_api.list_namespaced_custom_object(
                group="gateway.networking.k8s.io",
                version="v1beta1",
                namespace=namespace,
                plural="httproutes",
            )

            for route in routes.get("items", []):
                route_name = route["metadata"]["name"]
                if _is_self_resource(
                    route_name,
                    namespace,
                    route["metadata"].get("labels", {}),
                ):
                    self_excluded_count += 1
                    logger.debug(
                        f"🚫 Auto-exclusion de l'HTTPRoute portal-checker: "
                        f"{namespace}/{route_name}"
                    )
                    continue
                for hostname in route["spec"].get("hostnames", []):
                    for rule in route["spec"].get("rules", []):
                        for match in rule.get("matches", [{}]):
                            path = match.get("path", {}).get("value", "/")
                            url = (
                                f"https://{hostname}{path}"
                                if path != "/"
                                else f"https://{hostname}"
                            )

                            filtered_annotations = _filter_annotations(
                                route["metadata"].get("annotations", {})
                            )

                            backend_refs = rule.get("backendRefs", [])
                            backend_info = {
                                "service": backend_refs[0].get("name")
                                if backend_refs
                                else None,
                                "port": backend_refs[0].get("port")
                                if backend_refs
                                else None,
                            }

                            gateway_ref = route["spec"].get("parentRefs", [{}])[0]
                            gateway_name = gateway_ref.get("name", "unknown")

                            url_data = {
                                "url": url,
                                "namespace": namespace,
                                "name": route_name,
                                "type": "httproute",
                                "ingress_class": f"gateway/{gateway_name}",
                                "annotations": filtered_annotations,
                                "labels": route["metadata"].get("labels", {}),
                                "path": path,
                                "backend": backend_info,
                            }
                            all_urls_data.append(url_data)
        except Exception as e:
            logger.debug(f"Pas de HTTPRoute dans {namespace}: {e}")

    # Exclude URLs
    excluded_patterns = _load_excluded_patterns()
    filtered_urls = []
    excluded_count = 0

    for data in all_urls_data:
        if is_url_excluded(data["url"], data.get("annotations", {}), excluded_patterns):
            excluded_count += 1
            logger.debug(f"🚫 URL exclue: {data['url']}")
        else:
            filtered_urls.append(data)

    if self_excluded_count:
        logger.info(
            f"🚫 {self_excluded_count} ressource(s) portal-checker auto-exclue(s)"
        )

    logger.info(
        f"🔍 {len(all_urls_data)} URLs totales générées, {excluded_count} URLs exclues"
    )

    # Deduplicate URLs
    unique_urls = _deduplicate_urls(filtered_urls)
    logger.info(f"📋 {len(unique_urls)} URLs uniques après déduplication")

    # Update cache
    _update_cache(unique_urls)

    return unique_urls


def is_url_excluded(
    url: str, annotations: Dict[str, str], excluded_patterns: Optional[List[str]] = None
) -> bool:
    """Check if URL should be excluded based on patterns or annotations"""
    # Check Kubernetes annotation
    if (
        annotations
        and annotations.get("portal-checker.io/exclude", "").lower() == "true"
    ):
        return True

    # Load patterns if not provided
    if excluded_patterns is None:
        excluded_patterns = _load_excluded_patterns()

    # Normalize URL
    normalized_url = url.rstrip("/")
    if normalized_url.startswith("https://"):
        normalized_url = normalized_url[8:]
    elif normalized_url.startswith("http://"):
        normalized_url = normalized_url[7:]

    # Check patterns
    for pattern in excluded_patterns:
        pattern = pattern.strip()
        if not pattern:
            continue

        normalized_pattern = pattern.rstrip("/")

        # Exact match
        if normalized_url == normalized_pattern:
            return True

        # Pattern matching
        if fnmatch.fnmatch(normalized_url, normalized_pattern):
            return True

    return False


def save_urls_to_file(urls_data: List[Dict[str, Any]], filepath: str) -> None:
    """Save URLs data to YAML file"""
    try:
        # Create URLs file
        urls_dict = {
            "urls": [
                {
                    "url": data["url"],
                    "namespace": data["namespace"],
                    "name": data["name"],
                    "type": data["type"],
                    "ingress_class": data.get("ingress_class"),
                    "annotations": data.get("annotations", {}),
                    "labels": data.get("labels", {}),
                    "path": data.get("path", "/"),
                    "backend": data.get("backend", {}),
                }
                for data in urls_data
            ]
        }

        with open(filepath, "w") as f:
            yaml.dump(urls_dict, f, default_flow_style=False, sort_keys=False)

        logger.info(f"✅ {len(urls_data)} URLs sauvegardées dans {filepath}")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la sauvegarde des URLs: {e}")
        raise
