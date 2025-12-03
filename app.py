from flask import Flask, request, Response, redirect
import requests
import os
import re

app = Flask(__name__)

SYNOLOGY_URL = os.environ.get('SYNOLOGY_URL', 'http://privado.dyndns.org:5052')

def rewrite_all_urls(content):
    """Reescribe URLs solo si el contenido es texto y evita exponer /epg"""
    if isinstance(content, bytes):
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            return content  # contenido binario → no tocar
    else:
        text = content

    # Reescribir todas las referencias a /epg/... como rutas relativas sin /epg
    transformations = [
        (r'["\']/epg/([^"\']*)["\']', r'"/\1"'),
        (r'["\']/epg["\']', r'"/"'),
        # Asegurar que en JS/CSS también se normalicen
        (r'window\.location\.href\s*=\s*["\']/epg/([^"\']*)["\']', r'window.location.href = "/\1"'),
        (r'window\.open\(["\']/epg/([^"\']*)["\']', r'window.open("/\1"'),
        (r'action=["\']/epg/([^"\']*)["\']', r'action="/\1"'),
        (r'url\(["\']?/epg/([^"\'\)]*)["\']?\)', r'url(/\1)'),
    ]
    
    for pattern, replacement in transformations:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text.encode('utf-8')


@app.route('/')
@app.route('/<path:subpath>')
def proxy_epg(subpath=''):
    # Si por error alguien pone /epg/... en la URL pública, normalizamos
    if subpath.startswith('epg/'):
        new_path = subpath[4:]
        return redirect(f'/{new_path}' if new_path else '/')

    # ✅ TODAS las peticiones se proxyean dentro de /epg/ → aislamiento garantizado
    target_url = f"{SYNOLOGY_URL}/epg/{subpath}" if subpath else f"{SYNOLOGY_URL}/epg/"

    print(f"🔁 Proxy seguro: /{subpath} -> {target_url}")

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

        # Solo reescribir contenido textual
        if any(t in content_type for t in ['text/html', 'text/css', 'application/javascript', 'application/json']):
            content = rewrite_all_urls(content)

        # Eliminar headers que interfieren con la respuesta modificada
        excluded_headers = {'content-encoding', 'content-length', 'transfer-encoding', 'connection', 'keep-alive'}
        headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded_headers]

        return Response(content, resp.status_code, headers)

    except Exception as e:
        error_msg = f"Proxy Error: {str(e)}"
        print(error_msg)
        return error_msg, 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)