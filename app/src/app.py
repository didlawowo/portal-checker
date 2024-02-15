from flask import Flask, render_template, redirect, request
import requests
from kubernetes import client, config
from kubernetes.client.rest import ApiException


app = Flask(__name__)


def create_or_update_config_map(api_instance, config_map):
    try:
        api_instance.create_namespaced_config_map(
            namespace="portal-checker", body=config_map
        )
        print("🌟 ConfigMap created!")
    except ApiException as e:
        if e.status == 409:  # Conflict, the resource already exists
            api_instance.replace_namespaced_config_map(
                name=config_map["metadata"]["name"],
                namespace="portal-checker",
                body=config_map,
            )
            print("🔄 ConfigMap updated!")
        else:
            print("🚨 Error creating ConfigMap: %s\n" % e)


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
    print("🌟 urls.txt created!")
    # config_map = {
    #     "apiVersion": "v1",
    #     "kind": "ConfigMap",
    #     "metadata": {"name": "portal-checker", "namespace": "portal-checker"},
    #     "data": config_map_data,
    # }
    # print(config_map)
    # create_or_update_config_map(api_instance, config_map)
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
