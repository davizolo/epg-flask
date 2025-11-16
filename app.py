from flask import Flask, request, Response
import requests
import os
import urllib.parse

app = Flask(__name__)

# URL oculta de tu Synology
SYNOLOGY_URL = os.environ.get('SYNOLOGY_URL', 'http://privado.dyndns.org:5052')

@app.route('/')
@app.route('/<path:subpath>')
def proxy_epg(subpath=''):
    # Determinar la URL destino
    if subpath.startswith('static/'):
        # Archivos estáticos - van directamente al Synology
        target_url = f"{SYNOLOGY_URL}/{subpath}"
    else:
        # Rutas de la EPG - van a /epg/
        if subpath:
            target_url = f"{SYNOLOGY_URL}/epg/{subpath}"
        else:
            target_url = f"{SYNOLOGY_URL}/epg/"
    
    print(f"🔁 Proxy: {request.path} -> {target_url}")
    
    # Forward todos los parámetros
    params = request.args.to_dict()
    headers = {key: value for key, value in request.headers if key.lower() != 'host'}
    
    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            params=params,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=30
        )
        
        # Filtrar headers
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(name, value) for name, value in resp.raw.headers.items()
                          if name.lower() not in excluded_headers]
        
        # Reescribir URLs en el contenido HTML para que apunten a nuestro proxy
        content = resp.content
        if resp.headers.get('content-type', '').startswith('text/html'):
            content_str = content.decode('utf-8')
            # Reescribir rutas estáticas
            content_str = content_str.replace('/epg/static/', '/static/')
            content_str = content_str.replace('/static/epg/', '/static/')
            content = content_str.encode('utf-8')
        
        return Response(content, resp.status_code, response_headers)
        
    except requests.exceptions.Timeout:
        return "Timeout connecting to backend", 504
    except requests.exceptions.ConnectionError:
        return "Cannot connect to backend", 502
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)