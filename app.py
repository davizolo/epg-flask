from flask import Flask, request, Response, redirect
import requests
import os
import re

app = Flask(__name__)

SYNOLOGY_URL = os.environ.get('SYNOLOGY_URL', 'http://privado.dyndns.org:5052')

def rewrite_all_urls(content):
    """Reescribe URLs solo si el contenido es texto válido UTF-8"""
    # Si es bytes, intentamos decodificar; si falla, devolvemos intacto (es binario)
    if isinstance(content, bytes):
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            # Contenido binario → no modificar
            return content
    else:
        text = content

    # Lista de transformaciones más completa para URLs
    transformations = [
        # URLs de la EPG
        (r'["\']/epg/([^"\']*)["\']', r'"/\1"'),
        (r'["\']/epg["\']', r'"/"'),
        
        # URLs estáticas
        (r'["\']/static/epg/([^"\']*)["\']', r'"/static/\1"'),
        
        # URLs en JavaScript
        (r'window\.location\.href\s*=\s*["\']/epg/([^"\']*)["\']', r'window.location.href = "/\1"'),
        (r'window\.open\(["\']/epg/([^"\']*)["\']', r'window.open("/\1"'),
        
        # Form actions
        (r'action=["\']/epg/([^"\']*)["\']', r'action="/\1"'),
        
        # URLs en CSS
        (r'url\(["\']?/epg/([^"\'\)]*)["\']?\)', r'url(/\1)'),
    ]
    
    for pattern, replacement in transformations:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text.encode('utf-8')


@app.route('/')
@app.route('/<path:subpath>')
def proxy_epg(subpath=''):
    # Redirigir rutas que comienzan con /epg/ para normalizar
    if subpath.startswith('epg/'):
        new_path = subpath[4:]  # Quitar 'epg/'
        return redirect(f'/{new_path}' if new_path else '/')

    # Construir la URL de destino en el servidor Synology
    if subpath.startswith('static/'):
        target_url = f"{SYNOLOGY_URL}/{subpath}"
    else:
        target_url = f"{SYNOLOGY_URL}/epg/{subpath}" if subpath else f"{SYNOLOGY_URL}/epg/"

    print(f"🔁 Proxy: /{subpath} -> {target_url}")

    try:
        # Realizar la petición al backend
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

        # Solo reescribir contenido textual conocido
        text_content_types = [
            'text/html',
            'text/css',
            'application/javascript',
            'application/json',
            'text/plain'  # opcional: solo si estás seguro de que el plain es texto
        ]

        if any(t in content_type for t in text_content_types):
            content = rewrite_all_urls(content)
        # Si no es texto, se deja como bytes originales (imágenes, etc.)

        # Filtrar headers que no deben reenviarse
        excluded_headers = {'content-encoding', 'content-length', 'transfer-encoding', 'connection', 'keep-alive'}
        headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded_headers]

        return Response(content, resp.status_code, headers)

    except Exception as e:
        error_msg = f"Proxy Error: {str(e)}"
        print(error_msg)
        return error_msg, 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)