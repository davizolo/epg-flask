from flask import Flask, request, Response
import requests
import os

app = Flask(__name__)

# URL oculta de tu Synology - usa variable de entorno para mayor seguridad
SYNOLOGY_URL = os.environ.get('SYNOLOGY_URL', 'http://privado.dyndns.org:5052/epg')

@app.route('/')
@app.route('/<path:subpath>')
def proxy_epg(subpath=''):
    # Construir URL destino
    if subpath:
        target_url = f"{SYNOLOGY_URL}/{subpath}"
    else:
        target_url = SYNOLOGY_URL
    
    # Log para debugging (opcional)
    print(f"🔁 Proxy: {request.path} -> {target_url}")
    
    # Forward todos los parámetros y headers
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
        
        # Filtrar headers sensibles
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(name, value) for name, value in resp.raw.headers.items()
                          if name.lower() not in excluded_headers]
        
        return Response(resp.content, resp.status_code, response_headers)
        
    except requests.exceptions.Timeout:
        return "Timeout connecting to backend", 504
    except requests.exceptions.ConnectionError:
        return "Cannot connect to backend", 502
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)