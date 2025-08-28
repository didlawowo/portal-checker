"""
Configuration settings for Portal Checker
"""
import os
from typing import Optional

# Flask Configuration
FLASK_ENV = os.getenv("FLASK_ENV", "production")
PORT = int(os.getenv("PORT", "5000"))

# Logging Configuration
LOG_FORMAT = os.getenv("LOG_FORMAT", "text")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Request Configuration
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))

# Cache Configuration
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))  # 5 minutes
KUBERNETES_POLL_INTERVAL = int(os.getenv("KUBERNETES_POLL_INTERVAL", "600"))  # 10 minutes
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))  # 30 seconds

# Swagger Discovery Configuration
SWAGGER_DISCOVERY_INTERVAL = int(os.getenv("SWAGGER_DISCOVERY_INTERVAL", "3600"))  # 1 hour

# File Paths
URLS_FILE = os.getenv(
    "URLS_FILE",
    "config/urls.yaml" if FLASK_ENV == "development" else "/app/data/urls.yaml",
)
EXCLUDED_URLS_FILE = os.getenv(
    "EXCLUDED_URLS_FILE",
    "config/excluded-urls.yaml" if FLASK_ENV == "development" else "/app/config/excluded-urls.yaml",
)

# SSL Configuration
CUSTOM_CERT: Optional[str] = os.getenv("CUSTOM_CERT", "zscalerroot.crt")

# Kubernetes Configuration
KUBE_ENV = os.getenv("KUBE_ENV", "production")

# Features
AUTO_REFRESH_ON_START = os.getenv("AUTO_REFRESH_ON_START", "true").lower() == "true"
ENABLE_SLACK_NOTIFICATIONS = os.getenv("ENABLE_SLACK_NOTIFICATIONS", "false").lower() == "true"
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
ENABLE_AUTOSWAGGER = os.getenv("ENABLE_AUTOSWAGGER", "true").lower() == "true"

# Development/Debug
DEBUG = FLASK_ENV == "development"