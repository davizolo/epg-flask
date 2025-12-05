from flask import Flask, request, Response, redirect
import requests
import os

# Sin carpeta estática local
app = Flask(__name__, static_folder=None)

# Nueva URL base
SYNOLOGY_URL = os.environ.get('SYNOLOGY_URL', 'http://privado.dyndns.org:5062')


# --------------------------
# PROXY PARA STATIC/*
# --------------------------
@app.route('/static/<path:filename>')
def proxy_static(filename):
    target_url = f"{SYNOLOGY_URL}/static/{filename}"
    print(f"🔁 STATIC -> {target_url}")

    try:
        resp = requests.get(
            target_url,
            headers={k: v for k, v in request.headers if k.lower() != 'host'},
            stream=True,
            timeout=30
        )

        excluded = {'content-encoding', 'transfer-encoding', 'connection'}
        headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded]

        return Response(resp.content, resp.status_code, headers)

    except Exception as e:
        return f"Static proxy error: {e}", 500


# --------------------------
# PROXY GENERAL
# --------------------------
@app.route('/', defaults={'subpath': ''})
@app.route('/<path:subpath>')
def proxy_all(subpath):

    # Objetivo: misma ruta pero en el NAS
    target_url = f"{SYNOLOGY_URL}/{subpath}"

    print(f"🔁 PROXY: /{subpath} -> {target_url}")

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            params=request.args,
            headers={k: v for k, v in request.headers if k.lower() not in ('host', 'content-length')},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=30
        )

        excluded_headers = {'content-encoding', 'content-length', 'transfer-encoding', 'connection'}
        headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded_headers]

        return Response(resp.content, resp.status_code, headers)

    except Exception as e:
        return f"Proxy error: {e}", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)