from flask import Flask, request, Response, redirect
import requests
import os
import re

app = Flask(__name__, static_folder=None)

# Nueva URL base sin /epg
TARGET_BASE = os.environ.get("TARGET_BASE", "http://privado.dyndns.org:5062")


def rewrite_urls(content):
    """Reescribe cualquier URL absoluta para que funcione detrás del proxy."""

    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return content
    else:
        text = content

    # Como ya NO hay /epg, solo limpiamos rutas absolutas si existen
    replacements = [
        (r'http://privado\.dyndns\.org:5062', ""),  # limpiar hardcodeos
        (r'https://privado\.dyndns\.org:5062', "")
    ]

    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    return text.encode("utf-8")


# ---------- MANEJO DE STATIC ----------

@app.route("/static/<path:filename>")
def static_files(filename):
    """Proxy específico para imágenes, CSS, JS, etc."""
    url = f"{TARGET_BASE}/static/{filename}"
    return proxy_generic(url)


# ---------- RUTA GENERAL DE PROXY ----------

@app.route("/", defaults={"subpath": ""})
@app.route("/<path:subpath>")
def proxy(subpath):
    # Construimos ruta final (ya NO existe /epg)
    url = f"{TARGET_BASE}/{subpath}"
    return proxy_generic(url)


# ---------- FUNCIÓN CENTRAL DE PROXY ----------

def proxy_generic(url):
    print(f"🔁 Proxy -> {url}")

    try:
        upstream = requests.request(
            method=request.method,
            url=url,
            params=request.args,
            headers={k: v for k, v in request.headers.items()
                     if k.lower() not in ["host", "content-length"]},
            data=request.get_data(),
            cookies=request.cookies,
            timeout=30,
            allow_redirects=False,
        )

        content = upstream.content
        content_type = upstream.headers.get("content-type", "").lower()

        # Reescritura solo en archivos HTML / CSS / JS / JSON
        if any(t in content_type for t in [
            "text/html", "text/css", "application/javascript", "application/json"
        ]):
            content = rewrite_urls(content)

        blocked_headers = {
            "content-encoding", "content-length",
            "transfer-encoding", "connection"
        }

        headers = [(k, v) for k, v in upstream.headers.items()
                   if k.lower() not in blocked_headers]

        return Response(content, upstream.status_code, headers)

    except Exception as e:
        msg = f"Proxy Error: {e}"
        print(msg)
        return msg, 500


# ---------- MAIN ----------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)