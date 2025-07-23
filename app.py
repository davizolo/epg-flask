from flask import Flask, request, Response
import requests
import xmltodict
from datetime import datetime, timedelta
import pytz
import gzip
import io
import os
import time

app = Flask(__name__)

CHANNELS_OFICIALES = [
    "La 1 HD", "La 2", "Antena 3 HD", "Cuatro HD", "Telecinco HD", "La Sexta HD", "TVG Europa HD", "Teledeporte", "M. LaLiga", "DAZN LaLiga", "#Vamos por M+", "Movistar Plus+", "DAZN 1",
    "DAZN 2", "LaLiga TV Hypermotion HD", "DAZN F1", "Eurosport 1", "Eurosport 2",
    "M. Deportes", "M. Deportes 2", "Liga de Campeones", "Liga de Campeones 2",
    "Liga de Campeones 3", "Liga de Campeones 4"
]

ALIAS_CANAL = {
    "La 1": "La 1 HD", "La 2": "La 2", "Antena 3": "Antena 3 HD", "Cuatro HD": "Cuatro HD", "Telecinco HD": "Telecinco HD", "La Sexta HD": "La Sexta HD", "Tvga": "TVG Europa HD", "tdp": "Teledeporte",

    "Movistar LaLiga": "M. LaLiga", "Movistar La Liga": "M. LaLiga", "M LaLiga": "M. LaLiga",
    "M+ LaLiga TV HD": "M. LaLiga", "DAZN LaLiga": "DAZN LaLiga", "Dazn Laliga": "DAZN LaLiga",
    "DAZN LaLiga HD": "DAZN LaLiga", "Vamos": "#Vamos por M+", "#Vamos": "#Vamos por M+",
    "M+ Vamos HD": "#Vamos por M+", "Vamos BAR": "#Vamos por M+", "Movistar Plus": "Movistar Plus+",
    "Movistar+": "Movistar Plus+", "Movistar Plus+ HD": "Movistar Plus+", "Dazn 1": "DAZN 1",
    "DAZN 1 HD": "DAZN 1", "Dazn 2": "DAZN 2", "DAZN 2 HD": "DAZN 2",
    "Hypermotion": "LaLiga TV Hypermotion HD", "LaLiga Hypermotion": "LaLiga TV Hypermotion HD",
    "LaLiga TV Hypermotion": "LaLiga TV Hypermotion HD", "LaLiga TV Hypermotion HD": "LaLiga TV Hypermotion HD",
    "Dazn F1": "DAZN F1", "DAZN F1": "DAZN F1", "DAZN F1 HD": "DAZN F1",
    "Eurosport1": "Eurosport 1", "Eurosport 1 HD": "Eurosport 1", "Eurosport2": "Eurosport 2",
    "Eurosport 2": "Eurosport 2",
    "Movistar Deportes": "M. Deportes", "M Deportes": "M. Deportes", "M+ Deportes HD": "M. Deportes",
    "Movistar Deportes 2": "M. Deportes 2", "M Deportes 2": "M. Deportes 2", "M+ Deportes 2 HD": "M. Deportes 2",
    "Movistar Liga de Campeones": "Liga de Campeones", "Liga Campeones": "Liga de Campeones", "M+ Liga de Campeones HD": "Liga de Campeones",
    "Movistar Liga de Campeones 2": "Liga de Campeones 2", "Liga Campeones 2": "Liga de Campeones 2", "M+ Liga de Campeones 2 HD": "Liga de Campeones 2",
    "Movistar Liga de Campeones 3": "Liga de Campeones 3", "Liga Campeones 3": "Liga de Campeones 3", "M+ Liga de Campeones 3 HD": "Liga de Campeones 3",
    "Movistar Liga de Campeones 4": "Liga de Campeones 4", "Liga Campeones 4": "Liga de Campeones 4", "M+ Liga de Campeones 4 HD": "Liga de Campeones 4"
}

URL_Guia = "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv_sincolor0.xml.gz"

def create_temp_epg_file(data, temp_file="epg_temp.xml"):
    """Create a temporary XML file with only the specified channels."""
    filtered_data = {
        'tv': {
            'channel': [],
            'programme': []
        }
    }
    
    # Filter channels
    if 'channel' in data['tv']:
        channels = data['tv']['channel']
        if isinstance(channels, dict):
            channels = [channels]
        filtered_data['tv']['channel'] = [
            ch for ch in channels
            if ALIAS_CANAL.get(ch.get('@id', ''), ch.get('@id', '')) in CHANNELS_OFICIALES
        ]
    
    # Filter programmes
    if 'programme' in data['tv']:
        programmes = data['tv']['programme']
        if isinstance(programmes, dict):
            programmes = [programmes]
        filtered_data['tv']['programme'] = [
            prog for prog in programmes
            if ALIAS_CANAL.get(prog.get('@channel', ''), prog.get('@channel', '')) in CHANNELS_OFICIALES
        ]
    
    # Write to temporary file
    xml_string = xmltodict.unparse(filtered_data, pretty=True)
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(xml_string)
    
    return filtered_data

def get_epg_data():
    cache_file = "epg_cache.xml"
    temp_file = "epg_temp.xml"
    today = datetime.now(pytz.utc).date()
    
    # Check if temp file exists and is from today
    if os.path.exists(temp_file):
        file_mtime = datetime.fromtimestamp(os.path.getmtime(temp_file), tz=pytz.utc).date()
        if file_mtime == today:
            with open(temp_file, "r", encoding="utf-8") as f:
                return xmltodict.parse(f.read())
    
    # Check if cache file exists and is from today
    if os.path.exists(cache_file):
        file_mtime = datetime.fromtimestamp(os.path.getmtime(cache_file), tz=pytz.utc).date()
        if file_mtime == today:
            with open(cache_file, "rb") as f:
                data = xmltodict.parse(f.read())
                return create_temp_epg_file(data, temp_file)
    
    # Download and save new XML
    try:
        respuesta = requests.get(URL_Guia, timeout=10)
        respuesta.raise_for_status()
        xml = gzip.decompress(respuesta.content)
        with open(cache_file, "wb") as f:
            f.write(xml)
        data = xmltodict.parse(xml)
        return create_temp_epg_file(data, temp_file)
    except Exception as e:
        raise Exception(f"Error al obtener la EPG: {e}")

def escape_js_string(s):
    """Escape special characters for JavaScript string literals."""
    if not s:
        return ""
    return s.replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n')

@app.route("/")
def mostrar_epg():
    canal_entrada = request.args.get("canal", "").strip()
    dia_entrada = request.args.get("dia", "hoy").strip()
    canal = ALIAS_CANAL.get(canal_entrada, canal_entrada)

    dias = ["hoy", "mañana", "fin de semana"]
    selector_dias = "".join(
        f'<option value="{d}" {"selected" if d == dia_entrada else ""}>{d.capitalize()}</option>'
        for d in dias
    )

    selector_canales = "".join(
        f'<option value="{nombre}" {"selected" if nombre == canal else ""}>{nombre}</option>'
        for nombre in CHANNELS_OFICIALES
    )

    if canal not in CHANNELS_OFICIALES or dia_entrada not in dias:
        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>EPG</title>
            <style>
                body {{ font-family: Arial, sans-serif; background: #111; color: #eee; padding: 10px; margin: 0; }}
                .contenedor {{ max-width: 800px; margin: auto; padding: 10px; }}
                .logo {{ display: block; margin: 0 auto; max-width: 200px; height: auto; }}
                h1 {{ font-size: 1.8em; text-align: center; margin: 20px 0; font-weight: bold; }}
                form {{ display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; align-items: center; }}
                select {{ font-size: 1.2em; padding: 12px; border-radius: 8px; background: #333; color: #eee; border: 1px solid #555; width: 100%; max-width: 350px; text-align: center; }}
                button {{ padding: 12px 24px; background: #4cf; color: #111; border: none; border-radius: 8px; cursor: pointer; font-size: 1.2em; }}
                button:hover {{ background: #3be; }}
                @media (max-width: 600px) {{ 
                    .logo {{ max-width: 150px; }}
                    h1 {{ font-size: 1.4em; }}
                    select {{ font-size: 1.1em; padding: 10px; max-width: 100%; }}
                    button {{ font-size: 1.1em; padding: 10px 20px; }}
                }}
            </style>
        </head>
        <body>
            <div class="contenedor">
                <img src="/static/img/logo.png" alt="Logo" class="logo">
                <h1>Guía de programación para los canales de EMBY TV</h1>
                <form method="get">
                    <select name="canal">{selector_canales}</select>
                    <select name="dia">{selector_dias}</select>
                    <button type="submit">Ver programación</button>
                </form>
            </div>
        </body>
        </html>
        """
        return html

    try:
        data = get_epg_data()
    except Exception as e:
        return f"<h3>Error al obtener la EPG: {e}</h3>"

    now = datetime.now(pytz.utc)
    hoy = now.date()
    mañana = hoy + timedelta(days=1)
    fin_semana = [hoy + timedelta(days=i) for i in range(5) if (hoy + timedelta(days=i)).weekday() >= 5][:2]

    if dia_entrada == "hoy":
        fecha_inicio = hoy
        fecha_fin = hoy
    elif dia_entrada == "mañana":
        fecha_inicio = mañana
        fecha_fin = mañana
    else:
        fecha_inicio = fin_semana[0] if fin_semana else hoy
        fecha_fin = fin_semana[-1] if fin_semana else hoy

    eventos = []
    seen_programs = set()

    for prog in data['tv']['programme']:
        canal_xml = ALIAS_CANAL.get(prog['@channel'], prog['@channel'])
        if canal_xml != canal:
            continue

        try:
            inicio = datetime.strptime(prog['@start'], "%Y%m%d%H%M%S %z")
            fin = datetime.strptime(prog['@stop'], "%Y%m%d%H%M%S %z")
        except Exception:
            continue

        if fecha_inicio <= inicio.date() <= fecha_fin:
            prog_key = (prog['@start'], prog['@stop'], prog.get("title", {}).get("#text", ""))
            if prog_key in seen_programs:
                continue
            seen_programs.add(prog_key)

            hora_inicio = inicio.astimezone(pytz.timezone("Europe/Madrid")).strftime("%H:%M")
            hora_fin = fin.astimezone(pytz.timezone("Europe/Madrid")).strftime("%H:%M")
            fecha = inicio.astimezone(pytz.timezone("Europe/Madrid")).strftime("%d/%m/%Y")
            titulo = prog.get("title", {}).get("#text", "Sin título")
            descripcion = prog.get("desc", {}).get("#text", "Sin descripción")
            categoria = prog.get("category", {}).get("#text", "Sin categoría")
            imagen = prog.get("icon", {}).get("@src", "")
            desc_parts = descripcion.split(". ") if ". " in descripcion else [descripcion]
            synopsis = desc_parts[0]
            details = ". ".join(desc_parts[1:]) if len(desc_parts) > 1 else "Sin detalles adicionales"
            eventos.append({
                "inicio": inicio,
                "fecha": fecha,
                "hora_inicio": hora_inicio,
                "hora_fin": hora_fin,
                "titulo": titulo,
                "synopsis": synopsis,
                "details": details,
                "categoria": categoria,
                "imagen": imagen
            })

    eventos.sort(key=lambda x: x["inicio"])
    lista_html = "".join(
        f'<div class="evento" onclick="openModal(\'{escape_js_string(e["titulo"])}\', \'{escape_js_string(e["fecha"])}\', \'{escape_js_string(e["hora_inicio"])}\', \'{escape_js_string(e["hora_fin"])}\', \'{escape_js_string(e["synopsis"])}\', \'{escape_js_string(e["details"])}\', \'{escape_js_string(e["categoria"])}\', \'{escape_js_string(e["imagen"])}\')">{e["fecha"]} {e["hora_inicio"]} - {e["titulo"]}</div>'
        for e in eventos
    ) if eventos else '<div class="no-programas">No hay programas en la guía.</div>'

    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EPG - {canal}</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #111; color: #eee; padding: 10px; margin: 0; }}
            .contenedor {{ max-width: 800px; margin: auto; padding: 10px; }}
            .logo {{ display: block; margin: 0 auto; max-width: 200px; height: auto; }}
            h1 {{ font-size: 1.8em; text-align: center; margin: 20px 0; font-weight: bold; }}
            form {{ display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; align-items: center; }}
            select {{ font-size: 1.2em; padding: 12px; border-radius: 8px; background: #333; color: #eee; border: 1px solid #555; width: 100%; max-width: 350px; text-align: center; }}
            button {{ padding: 12px 24px; background: #4cf; color: #111; border: none; border-radius: 8px; cursor: pointer; font-size: 1.2em; }}
            button:hover {{ background: #3be; }}
            .evento {{ background: #222; padding: 10px; margin: 5px 0; border-radius: 5px; border-left: 4px solid #4cf; cursor: pointer; font-size: 1.1em; }}
            .evento:hover {{ background: #333; }}
            .no-programas {{ text-align: center; color: #aaa; margin-top: 20px; font-size: 1.1em; }}
            .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; overflow-y: auto; }}
            .modal-content {{ background: #222; margin: 5% auto; padding: 20px; border-radius: 5px; width: 90%; max-width: 600px; color: #eee; }}
            .modal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }}
            .modal-title {{ font-size: 1.8em; font-weight: bold; }}
            .close {{ cursor: pointer; font-size: 1.5em; color: #4cf; }}
            .close:hover {{ color: #3be; }}
            .modal-body {{ display: flex; flex-direction: column; gap: 15px; }}
            .modal-image {{ width: 100%; max-width: 300px; margin: 0 auto; }}
            .modal-image img {{ width: 100%; max-height: 200px; object-fit: contain; border-radius: 5px; display: none; }}
            .modal-details {{ width: 100%; padding: 10px; }}
            .modal-details p {{ margin: 10px 0; line-height: 1.4; font-size: 1.1em; }}
            .modal-details strong {{ color: #4cf; }}
            .modal-section {{ margin-bottom: 15px; }}
            @media (max-width: 600px) {{ 
                .logo {{ max-width: 150px; }}
                h1 {{ font-size: 1.4em; }}
                select {{ font-size: 1.1em; padding: 10px; max-width: 100%; }}
                button {{ font-size: 1.1em; padding: 10px 20px; }}
                .evento {{ font-size: 1em; padding: 8px; }}
                .modal-content {{ width: 95%; padding: 15px; }}
                .modal-image {{ max-width: 100%; }}
                .modal-image img {{ max-height: 150px; }}
                .modal-details {{ padding: 5px; }}
                .modal-details p {{ font-size: 1em; }}
            }}
        </style>
    </head>
    <body>
        <div class="contenedor">
            <img src="/static/img/logo.png" alt="Logo" class="logo">
            <h1>Guía de programación para los canales de EMBY TV</h1>
            <form method="get">
                <select name="canal">{selector_canales}</select>
                <select name="dia">{selector_dias}</select>
                <button type="submit">Ver programación</button>
            </form>
            <div style="margin-top: 20px;">
                {lista_html}
            </div>
        </div>
        <div id="eventModal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h3 id="modalTitle" class="modal-title"></h3>
                    <span class="close" onclick="closeModal()">×</span>
                </div>
                <div class="modal-body">
                    <div class="modal-image">
                        <img id="modalImage" alt="Event Image">
                    </div>
                    <div class="modal-details">
                        <div class="modal-section">
                            <p><strong>Fecha y Hora:</strong> <span id="modalDateTime"></span></p>
                        </div>
                        <div class="modal-section">
                            <p><strong>Categoría:</strong> <span id="modalCategory"></span></p>
                        </div>
                        <div class="modal-section">
                            <p><strong>Sinopsis:</strong> <span id="modalSynopsis"></span></p>
                        </div>
                        <div class="modal-section">
                            <p><strong>Detalles:</strong> <span id="modalDetails"></span></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <script>
            function openModal(title, date, startTime, endTime, synopsis, details, category, image) {{
                document.getElementById('modalTitle').textContent = title;
                document.getElementById('modalDateTime').textContent = `${{date}} ${{startTime}} - ${{endTime}}`;
                document.getElementById('modalCategory').textContent = category;
                document.getElementById('modalSynopsis').textContent = synopsis;
                document.getElementById('modalDetails').textContent = details;
                const modalImage = document.getElementById('modalImage');
                if (image) {{
                    modalImage.src = image;
                    modalImage.style.display = 'block';
                }} else {{
                    modalImage.style.display = 'none';
                }}
                document.getElementById('eventModal').style.display = 'block';
            }}

            function closeModal() {{
                document.getElementById('eventModal').style.display = 'none';
            }}

            window.onclick = function(event) {{
                const modal = document.getElementById('eventModal');
                if (event.target == modal) {{
                    modal.style.display = 'none';
                }}
            }}
        </script>
    </body>
    </html>
    """
    return html

if __name__ == "__main__":
    print("🔵 Servidor EPG en: http://0.0.0.0:5053/")
    app.run(host="0.0.0.0", port=5053, debug=True)