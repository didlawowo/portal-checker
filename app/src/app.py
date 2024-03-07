from flask import Flask, render_template, redirect, request
import requests
from kubernetes import client, config


app = Flask(__name__)


@app.route("/refresh", methods=["GET"])
def get_all_ingress_urls():
    config.load_incluster_config()
    v1 = client.NetworkingV1Api()

    ingress_list = v1.list_ingress_for_all_namespaces()
    print(ingress_list.items)
    urls = [rule.host for ingress in ingress_list.items for rule in ingress.spec.rules]
    print(urls)
    if urls == None:
        return "No ingress found!"
    # config_map_data = {"urls.txt": "\n".join(urls)}
    # write url.txt to disk
    with open("urls.txt", "w", encoding="utf-8") as file:
        file.write("\n".join(urls))
    print("🌟 urls.txt updated!")

    origin_url = request.referrer
    if origin_url:
        return redirect(origin_url)

    return redirect("/")


def test_urls(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        urls = file.read().splitlines()

    results = []
    for url in urls:
        try:
            response = requests.get(
                f"https://{url}" if not url.startswith("http") else url, timeout=10
            )
            status_code = response.status_code
            results.append((url, status_code))
        except requests.RequestException as e:
            results.append((url, str(e)))

    return results


@app.route("/")
def index():
    file_path = "urls.txt"  # Change this to your input file path
    results = test_urls(file_path)
    return render_template("index.html", results=results)


if __name__ == "__main__":
    ingress_urls = get_all_ingress_urls()
    app.run(host="0.0.0.0", port=5000)
