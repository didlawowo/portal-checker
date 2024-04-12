from flask import Flask, render_template, redirect, request
import requests
from kubernetes import client, config
from loguru import logger
import os

app = Flask(__name__)


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
    logger.info("🌟 urls.txt updated!")

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
    ingress_urls = get_all_ingress_urls()
    app.run(host="0.0.0.0", port=5000)
