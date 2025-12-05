from flask import Flask, request, Response, redirect
import requests
import os
import re

# Desactivamos static_folder por precaución
app = Flask(__name__, static_folder=None)

# Tu nueva URL principal SIN /epg
SYNOLOGY_URL = os.environ.get('SYNOLOGY_URL', 'http://privado.dyndns.org:5062')

def rewrite_all_urls(content):
    """
    Reescribe todas las rutas internas que estén codificadas con / algo
    y las convierte para funcionar detrás del proxy.
    """

    if isinstance(content, bytes):
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            return content
    else:
        text = content

    # 🔥 Transformaciones ajustadas: ya no usamos /epg en ningún sitio
    transformations = [
        # href="/algo" -> href="/algo" (nada cambia salvo quitar prefijos heredados)
        (r'["\']/epg/([^"\']*)["\']', r'"/\1"'),
        (r'["\']/epg["\']', r'"/"'),

        # JS redirect
        (r'window\.location\.href\s*=\s*["\']/epg/([^"\']*)["\']', r'window.location.href = "/\1"'),

        # window.open
        (r'window\.open\(["\']/epg/([^"\']*)["\']', r'window.open("/\1"'),

        # Formularios
        (r'action=["\']/epg/([^"\']*)["\']', r'action="/\1"'),

        # CSS url()
        (r'url\(["\']?/epg/([^"\'\)]*)["\']?\)', r'url(/\1)'),
    ]

    for pattern, replacement in transformations:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text.encode('utf-8')


# 📌 Captura explícita de /static/...
@app.route('/static/<path:filename>')
def proxy_static(filename):
    return proxy_generic(filename)


# 📌 Ruta principal SIN /epg
@app.route('/')
@app.route('/<path:subpath>')
def proxy_generic(subpath=''):
    # Para debug
    if subpath:
        print(f"🔁 Proxy: /{subpath}  →  {SYNOLOGY_URL}/{subpath}")
        target_url = f"{SYNOLOGY_URL}/{subpath}"
    else:
        print(f"🔁 Proxy: /  →  {SYNOLOGY_URL}/")
        target_url = f"{SYNOLOGY_URL}/"

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

        content = resp.content
        content_type = resp.headers.get('content-type', '').lower()

        # Reescritura de HTML, CSS, JS, JSON
        if any(t in content_type for t in ['text/html', 'text/css', 'application/javascript', 'application/json']):
            content = rewrite_all_urls(content)

        excluded_headers = {'content-encoding', 'content-length', 'transfer-encoding', 'connection', 'keep-alive'}
        headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded_headers]

        return Response(content, resp.status_code, headers)

    except Exception as e:
        print(f"❌ Proxy Error: {e}")
        return f"Proxy Error: {str(e)}", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)