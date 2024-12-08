from flask import Flask, render_template, redirect, request, send_from_directory

import requests
from kubernetes import client, config
from loguru import logger
from typing import Union

# from ddtrace import tracer
# import ddtrace
from werkzeug.middleware.proxy_fix import ProxyFix

import os

app = Flask(__name__)

# Network sockets
# tracer.configure(
#     https=False,
#     hostname="custom-hostname",
#     port="1234",
# )

# # Unix domain socket configuration
# tracer.configure(
#     uds_path="/var/run/datadog/apm.socket",
# )


# def tracer_injection(log: dict):
#     """Get correlation ids from current tracer context.

#     Docs:
#         https://docs.datadoghq.com/tracing/connect_logs_and_traces/python/
#     """
#     span = tracer.current_span()
#     trace_id, span_id = (span.trace_id, span.span_id) if span else (None, None)

#     log["dd.trace_id"] = str(trace_id or 0)
#     log["dd.span_id"] = str(span_id or 0)
#     log["dd.env"] = ddtrace.config.env or ""
#     log["dd.service"] = ddtrace.config.service or ""
#     log["dd.version"] = ddtrace.config.version or ""


# Configuration
SLACK_NOTIFICATIONS_ENABLED = (
    os.getenv("ENABLE_SLACK_NOTIFICATIONS", "false").lower() == "true"
)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


def send_slack_alert(url: str, status_code: Union[int, str], details: str = "") -> None:
    """
    Envoie une alerte sur Slack si un ingress a un problème

    Args:
        url (str): L'URL qui a un problème
        status_code (Union[int, str]): Le code de statut HTTP
        details (str, optional): Détails supplémentaires. Defaults to "".
    """
    if not SLACK_NOTIFICATIONS_ENABLED or not SLACK_WEBHOOK_URL:
        return

    try:
        # Conversion du status_code en int si c'est une string
        if isinstance(status_code, str):
            try:
                status_code = int(status_code)
            except ValueError:
                # Si le status n'est pas un nombre, c'est probablement une erreur
                status_code = 500

        # On n'envoie pas d'alerte pour les codes 2xx et 4xx
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

        response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=5)
        response.raise_for_status()

    except Exception as e:
        print(f"Erreur lors de l'envoi de l'alerte Slack: {str(e)}")


@app.route("/refresh", methods=["GET"])
def get_all_ingress_urls():
    """Get all ingress URLs and write them to a file."""
    if os.getenv("FLASK_ENV") == "development":
        config.load_kube_config()
    else:
        config.load_incluster_config()
    v1 = client.NetworkingV1Api()

    ingress_list = v1.list_ingress_for_all_namespaces()

    urls = [rule.host for ingress in ingress_list.items for rule in ingress.spec.rules]
    logger.info(f"🌟 {len(urls)} URLs found!")
    if urls is None:
        return "No ingress found!"
    # filter portal-checker url from list
    urls = [url for url in urls if "portal-checker" not in url]
    # config_map_data = {"urls.txt": "\n".join(urls)}
    # write url.txt to disk
    with open("urls.txt", "w", encoding="utf-8") as file:
        file.write("\n".join(urls))
    logger.success("🌟 urls.txt updated!")

    origin_url = request.referrer
    if origin_url:
        return redirect(origin_url)

    return redirect("/")


def test_urls(file_path):
    """test URLs from a file and return formatted results for the new template

    Args:
        file_path (str): Path to the file containing URLs

    Returns:
        list: List of dictionaries containing URL status information
    """
    with open(file_path, "r", encoding="utf-8") as file:
        urls = file.read().splitlines()

    formatted_results = []
    for url in urls:
        try:
            full_url = f"https://{url}" if not url.startswith("http") else url
            response = requests.get(full_url, timeout=1)
            status_code = response.status_code

            details = ""
            # Ajout des détails en fonction du status code
            if status_code != 200 and status_code != 401:
                details = "❌ Not Authorized or Not Found"

            formatted_results.append(
                {"url": url, "status": status_code, "details": details}
            )
            send_slack_alert(url, status_code, details)

        except requests.RequestException as e:
            # Gestion des erreurs de requête
            formatted_results.append(
                {
                    "url": url,
                    "status": 500,  # ou un autre code d'erreur approprié
                    "details": f"❌ Error: {str(e)}",
                }
            )

    return formatted_results


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


@app.route("/")
def index():
    """show ingress in cluster

    Returns:
        _type_: _description_
    """
    file_path = "urls.txt"  # Change this to your input file path
    results = test_urls(file_path)

    # results_json = json.dumps(results)
    return render_template("index.html", results=results)


if __name__ == "__main__":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    ingress_urls = get_all_ingress_urls()
    app.run(host="0.0.0.0", port=5000)
