from flask import Flask, request, Response, redirect
import requests
import os
import re

app = Flask(__name__)

SYNOLOGY_URL = os.environ.get('SYNOLOGY_URL', 'http://privado.dyndns.org:5052')

def rewrite_all_urls(content):
    """Reescribe TODAS las URLs posibles"""
    if isinstance(content, bytes):
        content = content.decode('utf-8')
    
    # Lista de transformaciones más completa
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
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
    
    return content.encode('utf-8')

@app.route('/')
@app.route('/<path:subpath>')
def proxy_epg(subpath=''):
    # Si alguien intenta acceder directamente a /epg/, redirigir
    if subpath.startswith('epg/'):
        new_path = subpath[4:]  # Quitar 'epg/'
        return redirect(f'/{new_path}' if new_path else '/')
    
    # Determinar URL destino
    if subpath.startswith('static/'):
        target_url = f"{SYNOLOGY_URL}/{subpath}"
    else:
        target_url = f"{SYNOLOGY_URL}/epg/{subpath}" if subpath else f"{SYNOLOGY_URL}/epg/"
    
    print(f"🔁 Proxy: /{subpath} -> {target_url}")
    
    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            params=request.args,
            headers={k: v for k, v in request.headers if k.lower() != 'host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=30
        )
        
        content = resp.content
        
        # Reescribir URLs en HTML, CSS y JavaScript
        content_type = resp.headers.get('content-type', '').lower()
        if any(t in content_type for t in ['text/html', 'text/css', 'application/javascript']):
            content = rewrite_all_urls(content)
        
        # Filtrar headers
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded_headers]
        
        return Response(content, resp.status_code, headers)
        
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)