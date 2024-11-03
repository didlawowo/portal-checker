import traceback
from flask import Flask, render_template, redirect, request, send_from_directory

import requests
from kubernetes import client, config
from loguru import logger

# from ddtrace import tracer
# import ddtrace
import json
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


def serialize(record):
    """Serialize the JSON log.
    Notes:
    https://docs.datadoghq.com/tracing/connect_logs_and_traces/python/
    """

    log = {
        # expected by datadog
        "status": str(record["level"].name),
        "message": str(record["message"]),
        "logger": {"thread_name": str(record["thread"].name)},
        # from loguru
        "elapsed": f"{record['elapsed']}",
        "file": f"{record['file']}",
        "function": f"{record['function']}",
        "level": f"{record['level']}",
        "line": f"{record['line']}",
        "module": f"{record['module']}",
        "name": f"{record['name']}",
        "process": f"{record['process']}",
        "thread": f"{record['thread']}",
        "time": f"{record['time']}",
        "extra": f"{record['extra']}",  # used by notify
    }

    if record["exception"] is not None:
        error_data = {
            "error": {
                "stack": "".join(
                    traceback.format_exception(
                        record["exception"].type,
                        record["exception"].value,
                        record["exception"].traceback,
                    )
                ),
                "kind": getattr(record["exception"].type, "__name__", "None"),
                "message": str(record["exception"].value),
            },
        }
        log.update(error_data)

    # log.update(tracer_injection(log))

    return json.dumps(log)


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
    """test URLs from a file

    Args:
        file_path (_type_): _description_

    Returns:
        _type_: _description_
    """

    with open(file_path, "r", encoding="utf-8") as file:
        urls = file.read().splitlines()

    results = []
    for url in urls:
        try:
            response = requests.get(
                f"https://{url}" if not url.startswith("http") else url, timeout=1
            )
            status_code = response.status_code
            results.append((url, status_code))
        except requests.RequestException as e:
            results.append((url, str(e)))

    return results


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"), "favicon.ico", mimetype="image/ico"
    )


@app.route("/image.png")
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
    return render_template("index.html", results=results)


if __name__ == "__main__":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    ingress_urls = get_all_ingress_urls()
    app.run(host="0.0.0.0", port=5000)
