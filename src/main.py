"""
Main entry point for Portal Checker application
"""
import asyncio
import sys
import threading
from datetime import datetime

import hypercorn.asyncio
from hypercorn import Config as HypercornConfig
from loguru import logger

from .config import LOG_FORMAT, LOG_LEVEL, PORT, CHECK_INTERVAL, FLASK_ENV
from .api import app, refresh_urls_if_needed, _run_url_tests
from .kubernetes_client import init_kubernetes
from .utils import serialize_record


def setup_logger(log_format: str = "text", log_level: str = "INFO") -> None:
    """
    Configure logger according to desired format (text or JSON)
    """
    # Remove existing handlers to avoid duplication
    logger.remove()

    if log_format.lower() == "json":
        # JSON format configuration
        logger.add(
            sys.stdout,
            level=log_level,
            serialize=True,  # Enable native JSON serialization
            format="{message}",
            enqueue=True,  # Make logging thread-safe
            backtrace=True,  # Include detailed stack traces
            diagnose=False,  # Disable local variable display in traces
            catch=True,  # Capture logging errors
        )
    else:
        # Human-readable text format (without icons)
        def clean_message(record):
            # Clean message from icons
            message = record["message"]
            message = message.replace("🐞", "").replace("🔧", "").replace("⚠️", "").replace("❌", "").replace("✅", "")
            message = message.replace("🔄", "").replace("📊", "").replace("🚀", "").replace("💾", "").replace("ℹ️", "")
            record["message"] = message.strip()
            return True

        # Configure colored text logging with cleaned messages
        logger.add(
            sys.stdout,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
            enqueue=True,
            backtrace=True,
            diagnose=True,
            catch=True,
            filter=clean_message,  # Apply message cleaning
        )

    logger.info(f"🔧 Logger configuré en mode {log_format.upper()}")


async def periodic_url_tests():
    """Background task to periodically test URLs"""
    global _stop_background_task
    
    while not _stop_background_task:
        try:
            logger.debug(f"🔄 Démarrage du test périodique (intervalle: {CHECK_INTERVAL}s)")
            
            # Run tests with cache update
            await _run_url_tests(update_cache=True)
            
            if not _stop_background_task:
                logger.info(f"✅ Test périodique terminé, prochaine exécution dans {CHECK_INTERVAL}s")
                
        except Exception as e:
            logger.error(f"❌ Erreur lors du test périodique: {e}")
            
        # Wait for next interval or until stop signal
        for _ in range(CHECK_INTERVAL):
            if _stop_background_task:
                break
            await asyncio.sleep(1)


def start_background_tasks():
    """Start background tasks in a separate thread"""
    def run_background():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(periodic_url_tests())
        except Exception as e:
            logger.error(f"❌ Erreur dans la tâche de fond: {e}")
        finally:
            loop.close()
    
    global _background_task
    _background_task = threading.Thread(target=run_background, daemon=True)
    _background_task.start()
    logger.info(f"🚀 Tâche de fond démarrée (tests toutes les {CHECK_INTERVAL}s)")


# Global variables for background task management
_background_task = None
_stop_background_task = False


def main():
    """Main application entry point"""
    # Setup logging
    setup_logger(LOG_FORMAT, LOG_LEVEL)
    logger.info("🚀 Démarrage de Portal Checker...")
    
    # Initialize Kubernetes client
    try:
        init_kubernetes()
    except Exception as e:
        logger.error(f"❌ Impossible d'initialiser Kubernetes: {e}")
        sys.exit(1)
    
    # Auto-refresh URLs if needed
    refresh_urls_if_needed()
    
    # Start background tasks
    start_background_tasks()
    
    if FLASK_ENV == "development":
        # Development mode with Flask dev server
        logger.info(f"🔧 Mode développement - Serveur Flask sur http://0.0.0.0:{PORT}")
        app.run(debug=True, host="0.0.0.0", port=PORT)
    else:
        # Production mode with Hypercorn
        from asgiref.wsgi import WsgiToAsgi
        
        config = HypercornConfig()
        config.bind = [f"0.0.0.0:{PORT}"]
        config.use_reloader = False
        config.accesslog = "-"
        config.errorlog = "-"
        config.worker_class = "asyncio"
        
        logger.info(f"🚀 Mode production - Serveur Hypercorn sur http://0.0.0.0:{PORT}")
        
        try:
            # Convert Flask WSGI app to ASGI
            asgi_app = WsgiToAsgi(app)
            asyncio.run(hypercorn.asyncio.serve(asgi_app, config))
        except KeyboardInterrupt:
            logger.info("🛑 Arrêt du serveur...")
            global _stop_background_task
            _stop_background_task = True
        except Exception as e:
            logger.error(f"❌ Erreur du serveur: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()