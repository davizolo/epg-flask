from flask import Flask, request, Response
import requests
import xmltodict
from datetime import datetime, timedelta
import pytz
import gzip
import logging
import re
import os
import urllib.parse
import unicodedata # Import for accent handling

# Configuración de logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', static_url_path='/static')

# Lista de canales oficiales que se mostrarán en la guía
CHANNELS_OFICIALES = [
    "La 1 HD", "La 2", "Antena 3 HD", "Cuatro HD", "Telecinco HD", "La Sexta HD", "TVG Europa HD", "Teledeporte",
    "M. LaLiga", "DAZN LaLiga", "#Vamos por M+", "Movistar Plus+", "DAZN 1", "DAZN 2", "LaLiga TV Hypermotion HD",
    "DAZN F1", "Eurosport 1", "Eurosport 2", "M. Deportes", "M. Deportes 2", "Liga de Campeones",
    "Liga de Campeones 2", "Liga de Campeones 3", "Liga de Campeones 4"
]

# Diccionario de alias para mapear nombres de canales de la EPG a nombres oficiales
ALIAS_CANAL = {
    "La 1": "La 1 HD", "La 2": "La 2", "Antena 3": "Antena 3 HD", "Cuatro": "Cuatro HD", "Telecinco": "Telecinco HD",
    "La Sexta": "La Sexta HD", "Tvga": "TVG Europa HD", "tdp": "Teledeporte", "Movistar LaLiga": "M. LaLiga",
    "Movistar La Liga": "M. LaLiga", "M LaLiga": "M. LaLiga", "M+ LaLiga TV HD": "M. LaLiga",
    "Dazn Laliga": "DAZN LaLiga", "DAZN LaLiga HD": "DAZN LaLiga", "vamos": "#Vamos por M+", "#vamos": "#Vamos por M+",
    "M+ Vamos HD": "#Vamos por M+", "Vamos BAR": "#Vamos por M+", "Movistar Vamos": "#Vamos por M+",
    "M+ Vamos": "#Vamos por M+", "M+ Vamos.TV": "#Vamos por M+", "M+ Vamos SD": "#Vamos por M+",
    "M+ Vamos FHD": "#Vamos por M+", "M+ Vamos UHD": "#Vamos por M+", "M+ Vamos 720": "#Vamos por M+",
    "M+ Vamos 1080": "#Vamos por M+", "Movistar Plus": "Movistar Plus+", "Movistar+": "Movistar Plus+",
    "Movistar Plus+ HD": "Movistar Plus+", "Dazn 1": "DAZN 1", "DAZN 1 HD": "DAZN 1", "Dazn 2": "DAZN 2",
    "DAZN 2 HD": "DAZN 2", "Hypermotion": "LaLiga TV Hypermotion HD", "LaLiga Hypermotion": "LaLiga TV Hypermotion HD",
    "LaLiga TV Hypermotion": "LaLiga TV Hypermotion HD",
    "Dazn F1": "DAZN F1", "DAZN F1 HD": "DAZN F1", "Eurosport1": "Eurosport 1",
    "Eurosport 1 HD": "Eurosport 1", "Eurosport2": "Eurosport 2", "Eurosport 2 HD": "Eurosport 2",
    "Movistar Deportes": "M. Deportes", "M Deportes": "M. Deportes", "M+ Deportes HD": "M. Deportes",
    "Movistar Deportes 2": "M. Deportes 2", "M Deportes 2": "M. Deportes 2", "M+ Deportes 2 HD": "M. Deportes 2",
    "Movistar Liga de Campeones": "Liga de Campeones", "LigaCampeones": "Liga de Campeones",
    "M+ Liga de Campeones HD": "Liga de Campeones", "Movistar Liga de Campeones 2": "Liga de Campeones 2",
    "LigaCampeones2": "Liga de Campeones 2", "M+ Liga de Campeones 2 HD": "Liga de Campeones 2",
    "Movistar Liga de Campeones 3": "Liga de Campeones 3", "LigaCampeones3": "Liga de Campeones 3",
    "M+ Liga de Campeones 3 HD": "Liga de Campeones 3", "Movistar Liga de Campeones 4": "Liga de Campeones 4",
    "LigaCampeones4": "Liga de Campeones 4", "M+ Liga de Campeones 4 HD": "Liga de Campeones 4"
}

# Mapeo de canales a nombres de archivo PNG para los logos
CANAL_TO_PNG = {
    "M. LaLiga": "mlaliga.png",
    "DAZN LaLiga": "daznlaliga.png",
    "#Vamos por M+": "vamos.png",
    "Movistar Plus+": "mplus.png",
    "DAZN 1": "dazn1.png",
    "DAZN 2": "dazn2.png",
    "LaLiga TV Hypermotion HD": "hypermotion.png",
    "DAZN F1": "f1.png",
    "Eurosport 1": "eurosport.png",
    "Eurosport 2": "eurosport2.png",
    "M. Deportes": "mdeportes.png",
    "M. Deportes 2": "mdeportes2.png",
    "Liga de Campeones": "ligadecampeones.png",
    "Liga de Campeones 2": "ligadecampeones2.png",
    "Liga de Campeones 3": "ligadecampeones3.png",
    "Liga de Campeones 4": "ligadecampeones4.png",
    "La 1 HD": "la1hd.png",
    "La 2": "la2.png",
    "Antena 3 HD": "antena3hd.png",
    "Cuatro HD": "cuatrohd.png",
    "Telecinco HD": "telecincohd.png",
    "La Sexta HD": "lasextahd.png",
    "TVG Europa HD": "tvgeuropahd.png",
    "Teledeporte": "teledeporte.png"
}

# URL de la guía EPG
URL_Guia = "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv_sincolor0.xml.gz"

def create_temp_epg_file(data, temp_file="epg_temp.xml"):
    """
    Filtra los datos de la EPG para incluir solo los canales oficiales y crea un archivo XML temporal.
    """
    filtered_data = {
        'tv': {
            'channel': [],
            'programme': []
        }
    }
    
    # Filtrar canales
    if 'channel' in data['tv']:
        channels = data['tv']['channel']
        if isinstance(channels, dict):
            channels = [channels] # Asegura que sea una lista
        filtered_channels = []
        for ch in channels:
            channel_id = ch.get('@id', '')
            mapped_channel = ALIAS_CANAL.get(channel_id, channel_id)
            if mapped_channel in CHANNELS_OFICIALES:
                filtered_channels.append(ch)
        filtered_data['tv']['channel'] = filtered_channels

    # Filtrar programas
    if 'programme' in data['tv']:
        programmes = data['tv']['programme']
        if isinstance(programmes, dict):
            programmes = [programmes] # Asegura que sea una lista
        filtered_programmes = []
        for prog in programmes:
            channel_id = prog.get('@channel', '')
            mapped_channel = ALIAS_CANAL.get(channel_id, channel_id)
            # Manejo especial para "#Vamos por M+" debido a variaciones en el XML
            if mapped_channel == "#Vamos por M+" and not re.search(r'vamos|m\+ vamos|#vamos', channel_id, re.IGNORECASE):
                continue # Si es #Vamos pero el ID original no coincide con los patrones, lo saltamos
            
            if mapped_channel in CHANNELS_OFICIALES:
                filtered_programmes.append(prog)
        filtered_data['tv']['programme'] = filtered_programmes

    xml_string = xmltodict.unparse(filtered_data, pretty=True)
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(xml_string)
        logger.debug(f"Archivo temporal EPG creado en: {temp_file}, tamaño: {os.path.getsize(temp_file)} bytes")
    except Exception as e:
        logger.error(f"Error al crear archivo temporal EPG: {e}")
    return filtered_data

def get_epg_data():
    """
    Obtiene los datos de la EPG, utilizando caché local si está disponible y actualizada.
    Descarga y descomprime si es necesario.
    """
    cache_file = "epg_cache.xml"
    temp_file = "epg_temp.xml"
    madrid_tz = pytz.timezone("Europe/Madrid")
    today = datetime.now(madrid_tz).date()
    
    # 1. Intentar usar el archivo temporal (ya filtrado) si es de hoy
    if os.path.exists(temp_file):
        file_mtime = datetime.fromtimestamp(os.path.getmtime(temp_file), tz=madrid_tz).date()
        if file_mtime == today:
            try:
                with open(temp_file, "r", encoding="utf-8") as f:
                    logger.debug("Usando archivo temporal EPG existente (filtrado y actualizado)")
                    return xmltodict.parse(f.read())
            except Exception as e:
                logger.error(f"Error al leer el archivo temporal EPG: {e}. Reintentando con caché.")
                os.remove(temp_file) # Eliminar archivo corrupto

    # 2. Intentar usar el archivo de caché (sin filtrar) si es de hoy
    if os.path.exists(cache_file):
        file_mtime = datetime.fromtimestamp(os.path.getmtime(cache_file), tz=madrid_tz).date()
        if file_mtime == today:
            try:
                with open(cache_file, "rb") as f:
                    data = xmltodict.parse(f.read())
                    logger.debug("Usando archivo caché EPG existente (sin filtrar)")
                    return create_temp_epg_file(data, temp_file) # Filtrar y guardar en temp
            except Exception as e:
                logger.error(f"Error al leer el archivo caché EPG: {e}. Reintentando descargar.")
                os.remove(cache_file) # Eliminar archivo corrupto
    
    # 3. Descargar, descomprimir y cachear la EPG
    try:
        logger.info(f"Descargando EPG desde: {URL_Guia}")
        respuesta = requests.get(URL_Guia, timeout=15) # Aumentar timeout
        respuesta.raise_for_status() # Lanza excepción para códigos de estado HTTP erróneos
        xml = gzip.decompress(respuesta.content)
        with open(cache_file, "wb") as f:
            f.write(xml)
        data = xmltodict.parse(xml)
        logger.debug("Datos EPG descargados y cacheados")
        return create_temp_epg_file(data, temp_file)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error de red al obtener la EPG: {e}")
        raise # Propagar la excepción para que la ruta principal la maneje
    except Exception as e:
        logger.error(f"Error inesperado al obtener o procesar la EPG: {e}")
        raise # Propagar la excepción

def escape_js_string(s):
    """Escapa caracteres especiales para usar una cadena Python en JavaScript."""
    if not s:
        return ""
    # Escapa comillas simples, comillas dobles y saltos de línea
    return s.replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '')

def normalize_text(text):
    """Normaliza el texto quitando acentos y convirtiendo a minúsculas."""
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    return text.lower()

@app.route("/")
def mostrar_epg():
    """
    Ruta principal para mostrar la guía de programación.
    Permite filtrar por canal, día y categoría.
    """
    canal_entrada = request.args.get("canal", "").strip()
    dia_entrada = request.args.get("dia", "hoy").strip()
    categoria_entrada = request.args.get("categoria", "Todos").strip()
    search_query = request.args.get("search_query", "").strip()
    
    # Mapear el canal de entrada a su nombre oficial si existe un alias
    canal = ALIAS_CANAL.get(canal_entrada, canal_entrada)
    logger.debug(f"Canal de entrada: '{canal_entrada}', Mapeado a: '{canal}', Categoría: '{categoria_entrada}', Día: '{dia_entrada}', Búsqueda: '{search_query}'")

    # Generar opciones del selector de días
    now = datetime.now(pytz.timezone("Europe/Madrid"))
    meses_es = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
        7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    hoy_str = f"{now.day} de {meses_es[now.month]}"
    
    # Determinar las fechas para los filtros
    hoy_date = now.date()
    mañana_date = hoy_date + timedelta(days=1)
    
    # Calcular fin de semana (próximo sábado y domingo)
    if now.weekday() >= 5:  # Si es sábado (5) o domingo (6), usar fin de semana actual
        sabado_date = hoy_date if now.weekday() == 5 else hoy_date - timedelta(days=1)
        domingo_date = sabado_date + timedelta(days=1)
    else:  # Si es de lunes a viernes, usar próximo fin de semana
        dias_hasta_sabado = (5 - now.weekday()) % 7
        sabado_date = hoy_date + timedelta(days=dias_hasta_sabado)
        domingo_date = sabado_date + timedelta(days=1)

    dias_opciones = [
        {"value": "hoy", "text": f"Hoy - {hoy_str}", "date_start": hoy_date, "date_end": hoy_date},
        {"value": "mañana", "text": f"Mañana - {mañana_date.day} de {meses_es[mañana_date.month]}", "date_start": mañana_date, "date_end": mañana_date},
        {"value": "fin de semana", "text": f"Fin de Semana - {sabado_date.day} de {meses_es[sabado_date.month]} y {domingo_date.day} de {meses_es[domingo_date.month]}", "date_start": sabado_date, "date_end": domingo_date}
    ]
    
    selector_dias = "".join(
        f'<option value="{d["value"]}" {"selected" if d["value"] == dia_entrada else ""}>{d["text"]}</option>'
        for d in dias_opciones
    )

    # Generar el grid de canales con logos
    channel_grid = "".join(
        f'<div class="logo-tile-wrapper">'
        f'<a href="/?canal={urllib.parse.quote(nombre)}&dia={dia_entrada}" class="block w-full h-20 flex items-center justify-center">'
        f'<img src="/static/img/{CANAL_TO_PNG.get(nombre, "default.png")}" alt="{nombre}" class="max-h-32 object-contain" onerror="this.src=\'/static/img/default.png\'; this.onerror=null;">'
        f'</a>'
        f'</div>'
        for nombre in CHANNELS_OFICIALES
    )

    try:
        data = get_epg_data()
    except Exception as e:
        # HTML de error en caso de fallo al obtener la EPG
        error_html_content = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error - Guía de Programación</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        :root {{
            --bg-dark: #121212;
            --bg-darker: #0a0a0a;
            --text-primary: #e0e0e0;
            --text-secondary: #b0b0b0;
            --accent-color: #3b82f6;
            --card-bg: rgba(30, 30, 30, 0.8);
            --card-border: rgba(255, 255, 255, 0.1);
            --bg-light: #ffffff;
            --text-dark: #111827;
            --text-dark-secondary: #4b5563;
        }}
        body {{
            background: var(--bg-dark);
            color: var(--text-primary);
            font-family: 'Inter', sans-serif;
            min-height: 100vh;
            transition: background 0.3s ease, color 0.3s ease;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 1rem;
        }}
        body.light-mode {{
            background: var(--bg-light);
            color: var(--text-dark);
        }}
        .card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
            padding: 1.5rem;
            text-align: center;
            width: 100%;
            max-width: 42rem;
        }}
        .light-mode .card {{
            background: rgba(255, 255, 255, 0.9) !important; /* Asegura fondo blanco */
            border: 1px solid rgba(0, 0, 0, 0.1);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
        }}
        .error-icon {{
            width: 6rem;
            height: 6rem;
            margin: 0 auto 1.5rem;
            color: #ef4444; /* red-500 */
        }}
        .light-mode .error-icon {{
            color: #dc2626; /* red-600 */
        }}
        .theme-toggle {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            cursor: pointer;
            padding: 8px 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }}
        .light-mode .theme-toggle {{
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(0, 0, 0, 0.1);
        }}
        .theme-toggle:hover {{
            background: var(--bg-darker);
            transform: translateY(-2px);
        }}
        .light-mode .theme-toggle:hover {{
            background: rgba(229, 231, 235, 0.5);
        }}
        .theme-toggle svg {{
            width: 24px;
            height: 24px;
            fill: var(--text-primary);
            stroke: var(--text-primary);
        }}
        .light-mode .theme-toggle svg {{
            fill: var(--text-dark);
            stroke: var(--text-dark);
        }}
        .theme-toggle span {{
            color: var(--text-primary);
            font-size: 0.875rem;
            font-weight: 600;
        }}
        .light-mode .theme-toggle span {{
            color: var(--text-dark);
        }}
    </style>
</head>
<body class="min-h-screen flex flex-col items-center justify-center p-4">
    <div class="fixed top-4 right-4 flex space-x-2 z-50">
        <button class="theme-toggle" onclick="toggleTheme()">
            <svg id="theme-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
            </svg>
            <span id="theme-text">Noche</span>
        </button>
    </div>
    <div class="card">
        <svg class="error-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <h1 class="text-2xl font-bold mb-2 text-red-400 light-mode:text-red-600">¡Oops! Algo salió mal.</h1>
        <p class="text-lg text-text-primary light-mode:text-text-dark mb-4">No se pudo cargar la guía de programación.</p>
        <p class="text-sm text-text-secondary light-mode:text-text-dark-secondary">Detalles del error: {str(e)}</p>
        <p class="text-sm text-text-secondary light-mode:text-text-dark-secondary mt-2">Por favor, inténtalo de nuevo más tarde.</p>
    </div>
    <script>
        function toggleTheme() {{
            const body = document.body;
            const themeIcon = document.getElementById('theme-icon');
            const themeText = document.getElementById('theme-text');
            body.classList.toggle('light-mode');
            if (body.classList.contains('light-mode')) {{
                themeIcon.innerHTML = '<path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>';
                themeText.textContent = 'Día';
                localStorage.setItem('theme', 'light');
            }} else {{
                themeIcon.innerHTML = '<path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>';
                themeText.textContent = 'Noche';
                localStorage.setItem('theme', 'dark');
            }}
        }}
        document.addEventListener('DOMContentLoaded', () => {{
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'light') {{
                document.body.classList.add('light-mode');
                document.getElementById('theme-icon').innerHTML = '<path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>';
                document.getElementById('theme-text').textContent = 'Día';
            }}
        }});
    </script>
</body>
</html>
        """
        return Response(error_html_content, mimetype="text/html")

    # Definir categorías fijas y ordenadas para el selector
    categorias_ordenadas = ["Fútbol", "Baloncesto", "Tenis", "Motor", "Motociclismo", "Rugby", "Padel", "Ciclismo"]
    logger.debug(f"Categorías ordenadas para el selector: {categorias_ordenadas}")
    
    selector_categorias = (
        f'<option value="Todos" {"selected" if categoria_entrada == "Todos" else ""}>Todos</option>' +
        "".join(
            f'<option value="{cat}" {"selected" if categoria_entrada == cat else ""}>{cat}</option>'
            for cat in categorias_ordenadas
        )
    )

    # Determinar el rango de fechas para filtrar eventos
    fecha_inicio = None
    fecha_fin = None
    for d in dias_opciones:
        if d["value"] == dia_entrada:
            fecha_inicio = d["date_start"]
            fecha_fin = d["date_end"]
            break

    eventos = []
    seen_programs = set()

    # Procesar todos los programas de la EPG
    for prog in data['tv']['programme']:
        canal_xml = prog.get('@channel', '')
        canal_mapped = ALIAS_CANAL.get(canal_xml, canal_xml)
        
        # Si se ha seleccionado un canal específico, filtrar por él
        if canal_entrada and canal_entrada != "Todos" and canal_mapped != canal:
             continue # Si el canal no coincide con el filtro, saltar

        # Si no se ha seleccionado un canal específico, asegurar que sea un canal oficial
        if not canal_entrada and canal_mapped not in CHANNELS_OFICIALES:
            continue
        
        # Si se ha seleccionado un canal específico y es oficial, pero el mapeo no es exacto
        # (ej. "Vamos" variantes), asegurar que el canal mapeado sea el que se espera.
        if canal_entrada and canal_entrada != "Todos" and canal_mapped == canal and canal not in CHANNELS_OFICIALES:
            # Esto maneja el caso donde el usuario busca un alias que no está en CHANNELS_OFICIALES
            # pero sí en ALIAS_CANAL y el mapeo es correcto.
            pass
        elif canal_mapped not in CHANNELS_OFICIALES:
            continue # Si no es un canal oficial y no se está buscando un alias específico, saltar

        try:
            inicio = datetime.strptime(prog['@start'], "%Y%m%d%H%M%S %z")
            fin = datetime.strptime(prog['@stop'], "%Y%m%d%H%M%S %z")
        except Exception:
            logger.warning(f"Error al parsear fecha/hora para un programa: {prog.get('title', 'N/A')}")
            continue

        # Filtrar por rango de fechas solo si no hay una búsqueda activa
        if not search_query and not (fecha_inicio <= inicio.date() <= fecha_fin):
            continue

        categoria = prog.get("category", {}).get("#text", "Sin categoría")
        # Filtrar por categoría con límites de palabra para evitar coincidencias parciales no deseadas
        if categoria_entrada != "Todos" and not re.search(r'\b' + re.escape(categoria_entrada) + r'\b', categoria, re.IGNORECASE):
            continue
        
        titulo = prog.get("title", {}).get("#text", "Sin título")
        descripcion = prog.get("desc", {}).get("#text", "Sin descripción")

        # Filtrar por búsqueda si hay una query
        if search_query:
            normalized_search_query = normalize_text(search_query)
            normalized_title = normalize_text(titulo)
            normalized_description = normalize_text(descripcion)
            if normalized_search_query not in normalized_title and \
               normalized_search_query not in normalized_description:
                continue

        prog_key = (prog['@start'], prog['@stop'], titulo, canal_mapped)
        if prog_key in seen_programs:
            continue # Evitar programas duplicados
        seen_programs.add(prog_key)

        hora_inicio = inicio.astimezone(pytz.timezone("Europe/Madrid")).strftime("%H:%M")
        hora_fin = fin.astimezone(pytz.timezone("Europe/Madrid")).strftime("%H:%M")
        fecha = inicio.astimezone(pytz.timezone("Europe/Madrid")).strftime("%d/%m/%Y")
        
        # Mapear categoría a las predefinidas si coincide, sino usar la categoría del EPG
        categoria_display = next((cat for cat in categorias_ordenadas if re.search(r'\b' + re.escape(cat) + r'\b', categoria, re.IGNORECASE)), categoria)
        categoria_display_class = re.sub(r'\s+', '_', categoria_display.strip()) if categoria_display else "Sin_categoría"
        categoria_display_text = categoria_display.replace("_", " ") if categoria_display else "Sin categoría"
        
        imagen = prog.get("icon", {}).get("@src", "")
        
        # Generar sinopsis y detalles para el modal
        desc_parts = descripcion.split(". ") if ". " in descripcion else [descripcion]
        synopsis = desc_parts[0][:200] + "..." if len(desc_parts[0]) > 200 else desc_parts[0]
        details = ". ".join(desc_parts[1:])[:400] + "..." if len(". ".join(desc_parts[1:])) > 400 else ". ".join(desc_parts[1:])

        eventos.append({
            "inicio": inicio,
            "fecha": fecha,
            "hora_inicio": hora_inicio,
            "hora_fin": hora_fin,
            "titulo": titulo,
            "synopsis": synopsis,
            "details": details,
            "categoria": categoria_display_class, # Para la clase CSS
            "categoria_text": categoria_display_text, # Para el texto visible
            "imagen": imagen,
            "canal": canal_mapped
        })

    eventos.sort(key=lambda x: x["inicio"])

    lista_html = ""
    channel_logo_html = ""
    page_title = "Guía de Programación"
    show_back_link = False

    if search_query:
        eventos_filtrados_search = eventos # eventos ya está filtrado por la búsqueda
        if not eventos_filtrados_search:
            lista_html = f'<p class="text-center text-red-700 light-mode:text-red-800 text-lg font-semibold card p-4">No se encontraron resultados para "{search_query}".</p>'
        else:
            lista_html = "".join(
                f'<div class="event-item card p-4 cursor-pointer transition-all duration-300 mb-4 hover:bg-gray-800 light-mode:hover:bg-gray-200" onclick="openModal(\'{escape_js_string(evento["titulo"])}\', \'{escape_js_string(evento["fecha"])}\', \'{escape_js_string(evento["hora_inicio"])}\', \'{escape_js_string(evento["hora_fin"])}\', \'{escape_js_string(evento["synopsis"])}\', \'{escape_js_string(evento["details"])}\', \'{escape_js_string(evento["categoria"])}\', \'{escape_js_string(evento["categoria_text"])}\', \'{escape_js_string(evento["imagen"])}\')">'
                f'<div class="absolute left-0 top-0 h-full w-2 bg-gradient-to-b from-blue-500 to-blue-700 rounded-l"></div>'
                f'<div class="ml-4 flex items-start space-x-4">'
                f'<div class="logo-tile p-2 bg-white">' # Baldosa blanca explícita
                f'<a href="/?canal={urllib.parse.quote(evento["canal"])}&dia={dia_entrada}" class="block">'
                f'<img src="/static/img/{CANAL_TO_PNG.get(evento["canal"], "default.png")}" alt="{evento["canal"]}" class="max-h-24 object-contain" onerror="this.src=\'/static/img/default.png\'; this.onerror=null;">'
                f'</a>'
                f'</div>'
                f'<div>'
                f'<p class="event-title font-bold text-lg leading-tight mb-2 break-words text-white light-mode:text-gray-900">{evento["titulo"]}</p>'
                f'<p class="event-time font-mono text-gray-300 light-mode:text-gray-800 text-base mb-2">{evento["fecha"]} {evento["hora_inicio"]} - {evento["hora_fin"]} | {evento["canal"]}</p>'
                f'<a href="/?categoria={urllib.parse.quote(evento["categoria_text"])}&dia={dia_entrada}" class="event-category inline-block px-3 py-1 text-sm font-semibold rounded-full category-{evento["categoria"]}">{evento["categoria_text"]}</a>'
                f'</div>'
                f'</div>'
                f'</div>'
                for evento in eventos_filtrados_search
            )
        page_title = f"Resultados para \"{search_query}\""
        show_back_link = True
    elif canal_entrada and canal_entrada != "Todos":
        # Modo canal específico
        eventos_filtrados_canal = [e for e in eventos if e["canal"] == canal]
        if not eventos_filtrados_canal:
            logger.warning(f"No se encontraron eventos para {canal} en el rango {fecha_inicio} a {fecha_fin}")
            lista_html = f'<p class="text-center text-red-700 light-mode:text-red-800 text-lg font-semibold card p-4">No hay programas disponibles para {canal} en las fechas seleccionadas.</p>'
        else:
            lista_html = "".join(
                f'<div class="event-item card p-4 cursor-pointer transition-all duration-300 mb-4 hover:bg-gray-800 light-mode:hover:bg-gray-200" onclick="openModal(\'{escape_js_string(evento["titulo"])}\', \'{escape_js_string(evento["fecha"])}\', \'{escape_js_string(evento["hora_inicio"])}\', \'{escape_js_string(evento["hora_fin"])}\', \'{escape_js_string(evento["synopsis"])}\', \'{escape_js_string(evento["details"])}\', \'{escape_js_string(evento["categoria"])}\', \'{escape_js_string(evento["categoria_text"])}\', \'{escape_js_string(evento["imagen"])}\')">'
                f'<div class="absolute left-0 top-0 h-full w-2 bg-gradient-to-b from-blue-500 to-blue-700 rounded-l"></div>'
                f'<div class="ml-4">'
                f'<p class="event-title font-bold text-lg leading-tight mb-2 break-words text-white light-mode:text-gray-900">{evento["titulo"]}</p>'
                f'<p class="event-time font-mono text-gray-300 light-mode:text-gray-800 text-base mb-2">{evento["fecha"]} {evento["hora_inicio"]} - {evento["hora_fin"]}</p>'
                f'<a href="/?categoria={urllib.parse.quote(evento["categoria_text"])}&dia={dia_entrada}" class="event-category inline-block px-3 py-1 text-sm font-semibold rounded-full category-{evento["categoria"]}">{evento["categoria_text"]}</a>'
                f'</div>'
                f'</div>'
                for evento in eventos_filtrados_canal
            )
        channel_logo_html = (
            f'<div class="flex justify-center mb-6">'
            f'<div class="logo-tile p-2">'
            f'<img src="/static/img/{CANAL_TO_PNG.get(canal, "default.png")}" alt="{canal}" class="max-h-20 object-contain" onerror="this.src=\'/static/img/default.png\'; this.onerror=null;">'
            f'</div>'
            f'</div>'
        )
        page_title = canal
        show_back_link = True
    else:
        # Modo categoría o general
        if categoria_entrada != "Todos":
            eventos_filtrados_categoria = [e for e in eventos if e["categoria_text"] == categoria_entrada]
            if not eventos_filtrados_categoria:
                logger.warning(f"No se encontraron eventos para categoría {categoria_entrada} en el rango {fecha_inicio} a {fecha_fin}")
                lista_html = f'<p class="text-center text-red-700 light-mode:text-red-800 text-lg font-semibold card p-4">No hay programas disponibles para la categoría {categoria_entrada} en las fechas seleccionadas.</p>'
            else:
                lista_html = "".join(
                    f'<div class="event-item card p-4 cursor-pointer transition-all duration-300 mb-4 hover:bg-gray-800 light-mode:hover:bg-gray-200" onclick="openModal(\'{escape_js_string(evento["titulo"])}\', \'{escape_js_string(evento["fecha"])}\', \'{escape_js_string(evento["hora_inicio"])}\', \'{escape_js_string(evento["hora_fin"])}\', \'{escape_js_string(evento["synopsis"])}\', \'{escape_js_string(evento["details"])}\', \'{escape_js_string(evento["categoria"])}\', \'{escape_js_string(evento["categoria_text"])}\', \'{escape_js_string(evento["imagen"])}\')">'
                    f'<div class="absolute left-0 top-0 h-full w-2 bg-gradient-to-b from-blue-500 to-blue-700 rounded-l"></div>'
                    f'<div class="ml-4 flex items-start space-x-4">'
                    f'<div class="logo-tile p-2 bg-white">' # Baldosa blanca explícita
                    f'<a href="/?canal={urllib.parse.quote(evento["canal"])}&dia={dia_entrada}" class="block">'
                    f'<img src="/static/img/{CANAL_TO_PNG.get(evento["canal"], "default.png")}" alt="{evento["canal"]}" class="max-h-24 object-contain" onerror="this.src=\'/static/img/default.png\'; this.onerror=null;">'
                    f'</a>'
                    f'</div>'
                    f'<div>'
                    f'<p class="event-title font-bold text-lg leading-tight mb-2 break-words text-white light-mode:text-gray-900">{evento["titulo"]}</p>'
                    f'<p class="event-time font-mono text-gray-300 light-mode:text-gray-800 text-base mb-2">{evento["fecha"]} {evento["hora_inicio"]} - {evento["hora_fin"]} | {evento["canal"]}</p>'
                    f'<span class="event-category inline-block px-3 py-1 text-sm font-semibold rounded-full category-{evento["categoria"]}">{evento["categoria_text"]}</span>'
                    f'</div>'
                    f'</div>'
                    f'</div>'
                    for evento in eventos_filtrados_categoria
                )
            page_title = f"Categoría: {categoria_entrada}"
            show_back_link = True
        else:
            # Modo general (mostrar grid de canales y luego eventos de todos)
            lista_html = f'<div class="channel-grid grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-4 mb-6">{channel_grid}</div>' + "".join(
                f'<div class="event-item card p-4 cursor-pointer transition-all duration-300 mb-4 hover:bg-gray-800 light-mode:hover:bg-gray-200" onclick="openModal(\'{escape_js_string(evento["titulo"])}\', \'{escape_js_string(evento["fecha"])}\', \'{escape_js_string(evento["hora_inicio"])}\', \'{escape_js_string(evento["hora_fin"])}\', \'{escape_js_string(evento["synopsis"])}\', \'{escape_js_string(evento["details"])}\', \'{escape_js_string(evento["categoria"])}\', \'{escape_js_string(evento["categoria_text"])}\', \'{escape_js_string(evento["imagen"])}\')">'
                f'<div class="absolute left-0 top-0 h-full w-2 bg-gradient-to-b from-blue-500 to-blue-700 rounded-l"></div>'
                f'<div class="ml-4 flex items-start space-x-4">'
                f'<div class="logo-tile p-2 bg-white">' # Baldosa blanca explícita
                f'<a href="/?canal={urllib.parse.quote(evento["canal"])}&dia={dia_entrada}" class="block">'
                    f'<img src="/static/img/{CANAL_TO_PNG.get(evento["canal"], "default.png")}" alt="{evento["canal"]}" class="max-h-24 object-contain" onerror="this.src=\'/static/img/default.png\'; this.onerror=null;">'
                f'</a>'
                f'</div>'
                f'<div>'
                f'<p class="event-title font-bold text-lg leading-tight mb-2 break-words text-white light-mode:text-gray-900">{evento["titulo"]}</p>'
                f'<p class="event-time font-mono text-gray-300 light-mode:text-gray-800 text-base mb-2">{evento["fecha"]} {evento["hora_inicio"]} - {evento["hora_fin"]} | {evento["canal"]}</p>'
                f'<a href="/?categoria={urllib.parse.quote(evento["categoria_text"])}&dia={dia_entrada}" class="event-category inline-block px-3 py-1 text-sm font-semibold rounded-full category-{evento["categoria"]}">{evento["categoria_text"]}</a>'
                f'</div>'
                f'</div>'
                f'</div>'
                for evento in eventos
            )
            page_title = "Guía de Programación"
            show_back_link = False

    # HTML principal de la aplicación
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        :root {{
            --bg-dark: #121212;
            --bg-darker: #0a0a0a;
            --text-primary: #e0e0e0;
            --text-secondary: #b0b0b0;
            --accent-color: #3b82f6;
            --card-bg: rgba(30, 30, 30, 0.8);
            --card-border: rgba(255, 255, 255, 0.1);
            --bg-light: #ffffff;
            --text-dark: #111827;
            --text-dark-secondary: #4b5563;
        }}

        body {{
            background: var(--bg-dark);
            color: var(--text-primary);
            font-family: 'Inter', sans-serif;
            min-height: 100vh;
            transition: background 0.3s ease, color 0.3s ease;
        }}

        body.light-mode {{
            background: var(--bg-light);
            color: var(--text-dark);
        }}

        .card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
        }}

        .light-mode .card {{
            background: rgba(255, 255, 255, 0.9) !important; /* Asegura fondo blanco para las tarjetas en modo día */
            border: 1px solid rgba(0, 0, 0, 0.1);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
        }}

        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
        }}

        .light-mode .card:hover {{
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.2);
        }}

        .logo-tile-wrapper {{
            background: white; /* Siempre blanco para la baldosa del logo */
            border-radius: 8px;
            padding: 8px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .logo-tile-wrapper:hover {{
            transform: translateY(-3px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.3);
        }}
        
        /* Estilo específico para la baldosa del logo en los eventos individuales */
        .logo-tile {{
            border-radius: 8px;
            padding: 8px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            background: white; /* Asegura que la baldosa sea blanca en modo día y noche */
        }}


        /* Estilos para las categorías */
        .category-Fútbol {{ 
            background: linear-gradient(45deg, #166534, #22c55e); 
            box-shadow: 0 0 12px rgba(34, 197, 94, 0.5); 
            color: white; 
        }}
        .category-Baloncesto {{ 
            background: linear-gradient(45deg, #1e40af, #3b82f6); 
            box-shadow: 0 0 12px rgba(59, 130, 246, 0.5); 
            color: white; 
        }}
        .category-Tenis {{ 
            background: linear-gradient(45deg, #86198f, #d946ef); 
            box-shadow: 0 0 12px rgba(217, 70, 239, 0.5); 
            color: white; 
        }}
        .category-Motor {{ 
            background: linear-gradient(45deg, #9f1239, #f43f5e); 
            box-shadow: 0 0 12px rgba(244, 63, 94, 0.5); 
            color: white; 
        }}
        .category-Motociclismo {{ 
            background: linear-gradient(45deg, #9a3412, #f97316); 
            box-shadow: 0 0 12px rgba(249, 115, 22, 0.5); 
            color: white; 
        }}
        .category-Rugby {{ 
            background: linear-gradient(45deg, #065f46, #10b981); 
            box-shadow: 0 0 12px rgba(16, 185, 129, 0.5); 
            color: white; 
        }}
        .category-Padel {{ 
            background: linear-gradient(45deg, #92400e, #f59e0b); 
            box-shadow: 0 0 12px rgba(245, 158, 11, 0.5); 
            color: white; 
        }}
        .category-Ciclismo {{ 
            background: linear-gradient(45deg, #065f46, #10b981); 
            box-shadow: 0 0 12px rgba(16, 185, 129, 0.5); 
            color: white; 
        }}
        .category-Sin_categoría {{ 
            background: linear-gradient(45deg, #374151, #6b7280); 
            box-shadow: 0 0 12px rgba(107, 114, 128, 0.5); 
            color: white; 
        }}

        .event-item {{
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }}

        .light-mode .event-item:hover {{
            background: rgba(229, 231, 235, 0.5);
        }}

        /* Asegurar que el texto sea oscuro en modo día */
        body.light-mode .event-title {{
            color: var(--text-dark) !important;
        }}
        body.light-mode .event-time {{
            color: var(--text-dark-secondary) !important;
        }}
        /* Modal text color in light mode - now white */
        .light-mode #modalTitle,
        .light-mode #modalDateTime,
        .light-mode #modalSynopsis,
        .light-mode #modalDetails {{
            color: white !important; /* Changed to white */
        }}
        .light-mode strong {{
            color: white !important; /* Changed to white */
        }}
        /* Estilo para el texto de los selectores en modo día */
        .light-mode select {{
            color: var(--text-dark) !important;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%23000000'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/%3E%3C/svg%3E"); /* Asegura que la flecha sea oscura */
        }}
        /* Estilo para el texto del input de búsqueda en modo día */
        .light-mode .search-input {{
            color: var(--text-dark) !important;
        }}


        header, select, .event-item {{
            -webkit-tap-highlight-color: transparent;
        }}

        /* Estilos para el tema */
        .theme-toggle, .search-toggle, .back-button, .search-button-header {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            cursor: pointer;
            padding: 8px 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }}

        .light-mode .theme-toggle, .light-mode .search-toggle, .light-mode .back-button, .light-mode .search-button-header {{
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(0, 0, 0, 0.1);
        }}

        .theme-toggle:hover, .search-toggle:hover, .back-button:hover, .search-button-header:hover {{
            background: var(--bg-darker);
            transform: translateY(-2px);
        }}

        .light-mode .theme-toggle:hover, .light-mode .search-toggle:hover, .light-mode .back-button:hover, .light-mode .search-button-header:hover {{
            background: rgba(229, 231, 235, 0.5);
        }}

        .theme-toggle svg, .search-toggle svg, .search-button-header svg {{
            width: 24px;
            height: 24px;
            fill: var(--text-primary);
            stroke: var(--text-primary); /* Para iconos stroke */
        }}

        .light-mode .theme-toggle svg, .light-mode .search-toggle svg, .light-mode .search-button-header svg {{
            fill: var(--text-dark);
            stroke: var(--text-dark); /* Para iconos stroke */
        }}

        .theme-toggle span, .search-toggle span, .back-button span, .search-button-header span {{
            color: var(--text-primary);
            font-size: 0.875rem;
            font-weight: 600;
        }}

        .light-mode .theme-toggle span, .light-mode .search-toggle span, .light-mode .back-button span, .light-mode .search-button-header span {{
            color: var(--text-dark);
        }}
        .search-input {{
            color: white; /* Default text color for search input in dark mode */
        }}

        /* Specific styles for search section buttons in light mode */
        .light-mode .search-section-button-blue {{
            background-color: #2563eb !important; /* blue-600 */
            color: white !important;
        }}
        .light-mode .search-section-button-blue:hover {{
            background-color: #1d4ed8 !important; /* blue-700 */
        }}
        .light-mode .search-section-button-gray {{
            background-color: #4b5563 !important; /* gray-700 */
            color: white !important;
        }}
        .light-mode .search-section-button-gray:hover {{
            background-color: #374151 !important; /* gray-600 */
        }}


        /* Media queries para responsividad */
        @media (max-width: 640px) {{
            .channel-grid {{
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 8px;
                padding: 8px;
            }}
            .event-item {{
                padding: 12px;
            }}
            .event-title {{
                font-size: 1.125rem;
            }}
            .event-time {{
                font-size: 0.875rem;
            }}
            .event-category {{
                font-size: 0.75rem;
                padding: 2px 6px;
            }}
            .card {{
                border-radius: 8px;
            }}
            header .max-w-7xl {{
                padding: 0 8px;
            }}
            header img {{
                width: 112px;
                height: 112px;
            }}
        }}
    </style>
</head>
<body class="min-h-screen flex flex-col">
    <div class="w-full text-center py-0"> <img src="/static/img/logo.png" alt="Logo" class="max-w-xs h-auto mx-auto object-contain"> </div>

    <div class="flex flex-col items-center gap-2 mb-2">
        <div class="flex justify-center items-center gap-4">
            {'<a href="/" class="text-white hover:text-gray-300 light-mode:text-gray-900 light-mode:hover:text-gray-600 text-sm font-semibold bg-gray-800 light-mode:bg-gray-200 px-3 py-1 rounded-lg transition-colors">Canales</a>' if show_back_link else ''}
            <button class="theme-toggle" onclick="toggleTheme()">
                <svg id="theme-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
                </svg>
                <span id="theme-text">Noche</span>
            </button>
             <button class="search-button-header" onclick="toggleSearchMode()">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                </svg>
                <span>Buscar</span>
            </button>
        </div>
    </div>

    <main class="flex-1 w-full max-w-7xl mx-auto p-4">
        <div id="mainContent" class="{'hidden' if search_query else ''}">
            <form id="filterForm" method="get" class="flex flex-col gap-4 mb-2">
                <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <select name="dia" onchange="document.getElementById('filterForm').submit();" class="card w-full max-w-xs p-3 text-white light-mode:text-black bg-gray-800 light-mode:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-lg">
                        {selector_dias}
                    </select>
                    <select name="categoria" onchange="document.getElementById('filterForm').submit();" class="card w-full max-w-xs p-3 text-white light-mode:text-black bg-gray-800 light-mode:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-lg">
                        {selector_categorias}
                    </select>
                </div>
            </form>
            <div class="w-full">
                {channel_logo_html}
                <div class="event-list space-y-4">
                    {lista_html}
                </div>
            </div>
        </div>

        <div id="searchSection" class="{'block' if search_query else 'hidden'}">
            <div class="flex gap-2 mb-4">
                <input type="text" id="searchInput" class="search-input card flex-1 p-3 rounded-lg bg-gray-800 light-mode:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Buscar programas..." value="{search_query}">
                <button onclick="performSearch()" class="card px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors search-section-button-blue">Buscar</button>
                <button onclick="exitSearchMode()" class="back-button card px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white font-semibold transition-colors search-section-button-gray">Volver</button>
            </div>
            <div id="searchResults" class="event-list space-y-4">
                {lista_html if search_query else ''}
            </div>
        </div>
    </main>
    
    <div id="eventModal" class="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center p-4 hidden z-20">
        <div class="bg-gray-800 light-mode:bg-white rounded-xl p-6 w-full max-w-md border border-gray-700 light-mode:border-gray-200 shadow-lg" onclick="event.stopPropagation()">
            <div class="flex justify-between items-center mb-4">
                <h2 id="modalTitle" class="text-xl font-bold text-blue-400 light-mode:text-white break-words pr-4"></h2> <button onclick="closeModal()" class="text-white light-mode:text-gray-900 text-2xl hover:text-gray-300 light-mode:hover:text-gray-600 transition-colors">&times;</button>
            </div>
            <div class="space-y-4">
                <img id="modalImage" alt="Event" class="w-full max-h-64 object-contain rounded-lg cursor-pointer hidden border border-gray-700 light-mode:border-gray-200" onclick="openFullScreenImage(this.src)">
                <div class="grid grid-cols-1 gap-3 text-sm">
                    <p><strong class="text-blue-400 light-mode:text-white font-bold">Fecha y Hora:</strong> <span id="modalDateTime" class="text-white light-mode:text-white ml-2 break-words"></span></p> <p><strong class="text-blue-400 light-mode:text-white font-bold">Categoría:</strong> <span id="modalCategory" class="ml-2 break-words"></span></p> <p><strong class="text-blue-400 light-mode:text-white font-bold">Sinopsis:</strong> <span id="modalSynopsis" class="text-white light-mode:text-white ml-2 break-words"></span></p> <p><strong class="text-blue-400 light-mode:text-white font-bold">Detalles:</strong> <span id="modalDetails" class="text-white light-mode:text-white ml-2 break-words"></span></p> </div>
            </div>
        </div>
    </div>

    <div id="fullScreenImageModal" class="fixed inset-0 bg-black light-mode:bg-white flex items-center justify-center hidden z-30 p-4">
        <img id="fullScreenImage" alt="Full Screen Event" class="max-w-full max-h-full object-contain rounded-lg shadow-xl">
        <button onclick="closeFullScreenImage()" class="absolute top-4 right-4 text-white light-mode:text-gray-900 text-3xl bg-gray-900 light-mode:bg-gray-200 rounded-full w-10 h-10 flex items-center justify-center hover:bg-gray-800 light-mode:hover:bg-gray-300 transition-colors">&times;</button>
    </div>

    <script>
        // Función para abrir el modal de detalles del evento
        function openModal(title, date, startTime, endTime, synopsis, details, category, categoryText, image) {{
            try {{
                document.getElementById('modalTitle').textContent = title || 'Sin título';
                document.getElementById('modalDateTime').textContent = `${{date}} ${{startTime}} - ${{endTime}}` || 'Sin horario';
                // Usar innerHTML para aplicar la clase de categoría
                document.getElementById('modalCategory').innerHTML = `<span class="px-3 py-1 text-xs font-semibold rounded-full category-${{category}}">${{categoryText}}</span>`;
                document.getElementById('modalSynopsis').textContent = synopsis || 'Sin sinopsis';
                document.getElementById('modalDetails').textContent = details || 'Sin detalles';
                
                const modalImage = document.getElementById('modalImage');
                if (image) {{
                    modalImage.src = image;
                    modalImage.classList.remove('hidden');
                }} else {{
                    modalImage.classList.add('hidden');
                }}
                document.getElementById('eventModal').classList.remove('hidden');
            }} catch (error) {{
                console.error('Error al abrir el modal:', error);
            }}
        }}

        // Función para cerrar el modal de detalles del evento
        function closeModal() {{
            document.getElementById('eventModal').classList.add('hidden');
        }}

        // Función para abrir la imagen a pantalla completa
        function openFullScreenImage(src) {{
            const fullScreenImage = document.getElementById('fullScreenImage');
            fullScreenImage.src = src;
            document.getElementById('fullScreenImageModal').classList.remove('hidden');
        }}

        // Función para cerrar la imagen a pantalla completa
        function closeFullScreenImage() {{
            document.getElementById('fullScreenImageModal').classList.add('hidden');
        }}

        // Función para alternar el tema (claro/oscuro)
        function toggleTheme() {{
            const body = document.body;
            const themeIcon = document.getElementById('theme-icon');
            const themeText = document.getElementById('theme-text');
            body.classList.toggle('light-mode'); // Alternar la clase en el body

            // Actualizar el icono y texto del botón
            if (body.classList.contains('light-mode')) {{
                themeIcon.innerHTML = '<path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>';
                themeText.textContent = 'Día';
                localStorage.setItem('theme', 'light'); // Guardar preferencia
            }} else {{
                themeIcon.innerHTML = '<path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>';
                themeText.textContent = 'Noche';
                localStorage.setItem('theme', 'dark'); // Guardar preferencia
            }}
        }}

        // Aplicar el tema guardado al cargar la página
        document.addEventListener('DOMContentLoaded', () => {{
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'light') {{
                document.body.classList.add('light-mode');
                // Asegurarse de que el icono y texto del botón se actualicen al cargar
                document.getElementById('theme-icon').innerHTML = '<path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>';
                document.getElementById('theme-text').textContent = 'Día';
            }}
            // If there's a search query in the URL, show the search section
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('search_query')) {{
                document.getElementById('mainContent').classList.add('hidden');
                document.getElementById('searchSection').classList.remove('hidden');
                document.getElementById('searchInput').value = urlParams.get('search_query');
            }}
        }});

        // Cerrar modales al hacer clic fuera de ellos
        window.onclick = function(event) {{
            const eventModal = document.getElementById('eventModal');
            const fullScreenModal = document.getElementById('fullScreenImageModal');
            if (event.target === eventModal) {{
                eventModal.classList.add('hidden');
            }}
            if (event.target === fullScreenModal) {{
                fullScreenModal.classList.add('hidden');
            }}
        }};

        // Funciones para el modo de búsqueda
        function toggleSearchMode() {{
            document.getElementById('mainContent').classList.toggle('hidden');
            document.getElementById('searchSection').classList.toggle('hidden');
            if (!document.getElementById('searchSection').classList.contains('hidden')) {{
                document.getElementById('searchInput').focus();
            }}
        }}

        function performSearch() {{
            const query = document.getElementById('searchInput').value;
            window.location.href = `/?search_query=${{encodeURIComponent(query)}}`;
        }}

        function exitSearchMode() {{
            window.location.href = '/'; // Go back to the main page without any filters
        }}
    </script>
</body>
</html>


"""
    return Response(html_content, mimetype="text/html")

if __name__ == "__main__":
    print("🔵 Servidor EPG en: http://0.0.0.0:5053/")
    app.run(host="0.0.0.0", port=5053, debug=True)