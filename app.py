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

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', static_url_path='/static')

CHANNELS_OFICIALES = [
    "La 1 HD", "La 2", "Antena 3 HD", "Cuatro HD", "Telecinco HD", "La Sexta HD", "TVG Europa HD", "Teledeporte",
    "M. LaLiga", "DAZN LaLiga", "#Vamos por M+", "Movistar Plus+", "DAZN 1", "DAZN 2", "LaLiga TV Hypermotion HD",
    "DAZN F1", "Eurosport 1", "Eurosport 2", "M. Deportes", "M. Deportes 2", "Liga de Campeones",
    "Liga de Campeones 2", "Liga de Campeones 3", "Liga de Campeones 4"
]

ALIAS_CANAL = {
    "La 1": "La 1 HD", "La 2": "La 2", "Antena 3": "Antena 3 HD", "Cuatro HD": "Cuatro HD", "Telecinco HD": "Telecinco HD",
    "La Sexta HD": "La Sexta HD", "Tvga": "TVG Europa HD", "tdp": "Teledeporte", "Movistar LaLiga": "M. LaLiga",
    "Movistar La Liga": "M. LaLiga", "M LaLiga": "M. LaLiga", "M+ LaLiga TV HD": "M. LaLiga", "DAZN LaLiga": "DAZN LaLiga",
    "Dazn Laliga": "DAZN LaLiga", "DAZN LaLiga HD": "DAZN LaLiga", "vamos": "#Vamos por M+", "#vamos": "#Vamos por M+",
    "M+ Vamos HD": "#Vamos por M+", "Vamos BAR": "#Vamos por M+", "Movistar Vamos": "#Vamos por M+",
    "M+ Vamos": "#Vamos por M+", "M+ Vamos.TV": "#Vamos por M+", "M+ Vamos SD": "#Vamos por M+",
    "M+ Vamos FHD": "#Vamos por M+", "M+ Vamos UHD": "#Vamos por M+", "M+ Vamos 720": "#Vamos por M+",
    "M+ Vamos 1080": "#Vamos por M+", "Movistar Plus": "Movistar Plus+", "Movistar+": "Movistar Plus+",
    "Movistar Plus+ HD": "Movistar Plus+", "Dazn 1": "DAZN 1", "DAZN 1 HD": "DAZN 1", "Dazn 2": "DAZN 2",
    "DAZN 2 HD": "DAZN 2", "Hypermotion": "LaLiga TV Hypermotion HD", "LaLiga Hypermotion": "LaLiga TV Hypermotion HD",
    "LaLiga TV Hypermotion": "LaLiga TV Hypermotion HD", "LaLiga TV Hypermotion HD": "LaLiga TV Hypermotion HD",
    "Dazn F1": "DAZN F1", "DAZN F1": "DAZN F1", "DAZN F1 HD": "DAZN F1", "Eurosport1": "Eurosport 1",
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

URL_Guia = "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv_sincolor0.xml.gz"

def create_temp_epg_file(data, temp_file="epg_temp.xml"):
    filtered_data = {
        'tv': {
            'channel': [],
            'programme': []
        }
    }
    if 'channel' in data['tv']:
        channels = data['tv']['channel']
        if isinstance(channels, dict):
            channels = [channels]
        filtered_channels = []
        for ch in channels:
            channel_id = ch.get('@id', '')
            mapped_channel = ALIAS_CANAL.get(channel_id, channel_id)
            logger.debug(f"Channel ID in EPG: {channel_id}, Mapped to: {mapped_channel}")
            if mapped_channel in CHANNELS_OFICIALES:
                filtered_channels.append(ch)
        filtered_data['tv']['channel'] = filtered_channels

    if 'programme' in data['tv']:
        programmes = data['tv']['programme']
        if isinstance(programmes, dict):
            programmes = [programmes]
        filtered_programmes = []
        for prog in programmes:
            channel_id = prog.get('@channel', '')
            mapped_channel = ALIAS_CANAL.get(channel_id, channel_id)
            if mapped_channel == "#Vamos por M+":
                logger.debug(f"Programa encontrado para canal_xml: {channel_id}, mapeado a: {mapped_channel}")
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
    cache_file = "epg_cache.xml"
    temp_file = "epg_temp.xml"
    today = datetime.now(pytz.timezone("Europe/Madrid")).date()
    
    if os.path.exists(temp_file):
        file_mtime = datetime.fromtimestamp(os.path.getmtime(temp_file), tz=pytz.timezone("Europe/Madrid")).date()
        if file_mtime == today:
            with open(temp_file, "r", encoding="utf-8") as f:
                logger.debug("Usando archivo temporal EPG existente")
                return xmltodict.parse(f.read())
    
    if os.path.exists(cache_file):
        file_mtime = datetime.fromtimestamp(os.path.getmtime(cache_file), tz=pytz.timezone("Europe/Madrid")).date()
        if file_mtime == today:
            with open(cache_file, "rb") as f:
                data = xmltodict.parse(f.read())
                logger.debug("Usando archivo cache EPG existente")
                return create_temp_epg_file(data, temp_file)
    
    try:
        respuesta = requests.get(URL_Guia, timeout=10)
        respuesta.raise_for_status()
        xml = gzip.decompress(respuesta.content)
        with open(cache_file, "wb") as f:
            f.write(xml)
        data = xmltodict.parse(xml)
        logger.debug("Datos EPG descargados y cacheados")
        return create_temp_epg_file(data, temp_file)
    except Exception as e:
        logger.error(f"Error al obtener la EPG: {e}")
        raise Exception(f"Error al obtener la EPG: {e}")

def escape_js_string(s):
    if not s:
        return ""
    return s.replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n')

def extract_categories(category_text):
    """Extrae todas las categorías y subcategorías del texto de categoría"""
    if not category_text:
        return []
    
    # Lista de categorías principales conocidas
    main_categories = ["Fútbol", "Baloncesto", "Tenis", "Motor", "Motociclismo", "Rugby", "Padel", "Ciclismo"]
    
    # Primero buscamos categorías principales
    found_categories = []
    for cat in main_categories:
        if re.search(r'\b' + re.escape(cat) + r'\b', category_text, re.IGNORECASE):
            found_categories.append(cat)
    
    # Si no encontramos categorías principales, usamos el texto completo como categoría
    if not found_categories:
        found_categories = [category_text.strip()]
    
    return found_categories

@app.route("/")
def mostrar_epg():
    canal_entrada = request.args.get("canal", "").strip()
    dia_entrada = request.args.get("dia", "hoy").strip()
    categoria_entrada = request.args.get("categoria", "Todos").strip()
    canal = ALIAS_CANAL.get(canal_entrada, canal_entrada)
    logger.debug(f"Canal de entrada: {canal_entrada}, Mapeado a: {canal}, Categoría: {categoria_entrada}, Día: {dia_entrada}")

    # Generar opciones del selector con fecha para "hoy"
    now = datetime.now(pytz.timezone("Europe/Madrid"))
    hoy = now.strftime("%d de %B").lower()
    dias = [
        f"hoy - {hoy}",
        "mañana",
        "fin de semana"
    ]
    selector_dias = "".join(
        f'<option value="{d.split(" - ")[0]}" {"selected" if d.split(" - ")[0] == dia_entrada else ""}>{d.capitalize()}</option>'
        for d in dias
    )

    # Generar channel_grid con solo logos, bien alineados, usando URL encoding
    channel_grid = "".join(
        f'<div class="w-full p-2">'
        f'<a href="/?canal={urllib.parse.quote(nombre)}&dia={dia_entrada}" class="block w-full h-16 flex items-center justify-center bg-gray-200 rounded-lg hover:bg-gray-300 transition duration-200">'
        f'<img src="/static/img/{CANAL_TO_PNG.get(nombre, "default.png")}" alt="{nombre}" class="max-h-12 object-contain" onerror="this.style.display=\'none\';">'
        f'</a>'
        f'</div>'
        for nombre in CHANNELS_OFICIALES
    )

    try:
        data = get_epg_data()
    except Exception as e:
        html = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error - Guía EMBY TV</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: linear-gradient(to bottom, #f3f4f6, #e5e7eb); }
    </style>
</head>
<body class="min-h-screen flex flex-col items-center p-4">
    <div class="w-full max-w-md">
        <img src="/static/img/logo.png" alt="Logo" class="w-28 mx-auto mb-4">
        <h1 class="text-2xl font-bold text-center mb-6 text-cyan-600">Guía de Programación EMBY TV</h1>
        <p class="text-center text-red-500 text-lg">Error al obtener la EPG: """ + str(e) + """</p>
    </div>
</body>
</html>"""
        return Response(html, mimetype="text/html")

    # Definir categorías fijas para el selector
    categorias_ordenadas = ["Fútbol", "Baloncesto", "Tenis", "Motor", "Motociclismo", "Rugby", "Padel", "Ciclismo"]
    logger.debug(f"Categorías ordenadas para el selector: {categorias_ordenadas}")
    
    selector_categorias = (
        f'<option value="Todos" {"selected" if categoria_entrada == "Todos" else ""}>Todos</option>' +
        "".join(
            f'<option value="{cat}" {"selected" if categoria_entrada == cat else ""}>{cat}</option>'
            for cat in categorias_ordenadas
        )
    )

    now = datetime.now(pytz.timezone("Europe/Madrid"))
    hoy = now.date()
    mañana = hoy + timedelta(days=1)
    
    # Calcular fin de semana (July 27, 2025, is Sunday, so use July 26-27)
    if now.weekday() >= 5:  # Si es sábado (5) o domingo (6), usar fin de semana actual
        sabado = hoy if now.weekday() == 5 else hoy - timedelta(days=1)
        domingo = sabado + timedelta(days=1)
    else:  # Si es de lunes a viernes, usar próximo fin de semana
        dias_hasta_sabado = (5 - now.weekday()) % 7
        sabado = hoy + timedelta(days=dias_hasta_sabado)
        domingo = sabado + timedelta(days=1)
    fin_semana = [sabado, domingo]

    if dia_entrada == "hoy":
        fecha_inicio = hoy
        fecha_fin = hoy
    elif dia_entrada == "mañana":
        fecha_inicio = mañana
        fecha_fin = mañana
    else:
        fecha_inicio = fin_semana[0]
        fecha_fin = fin_semana[1]

    eventos = []
    seen_programs = set()

    # Procesar todos los programas
    for prog in data['tv']['programme']:
        canal_xml = prog.get('@channel', '')
        canal_mapped = ALIAS_CANAL.get(canal_xml, canal_xml)
        if canal in CHANNELS_OFICIALES and canal_mapped != canal:
            # Fallback para coincidencias parciales con "Vamos"
            if canal == "#Vamos por M+" and re.search(r'vamos|m\+ vamos|#vamos', canal_xml, re.IGNORECASE):
                canal_mapped = "#Vamos por M+"
                logger.debug(f"Fallback aplicado: {canal_xml} mapeado a #Vamos por M+")
            else:
                continue
        elif canal not in CHANNELS_OFICIALES:
            # Para modo categoría o general, incluir todos los canales oficiales
            if canal_mapped not in CHANNELS_OFICIALES:
                continue

        try:
            inicio = datetime.strptime(prog['@start'], "%Y%m%d%H%M%S %z")
            fin = datetime.strptime(prog['@stop'], "%Y%m%d%H%M%S %z")
        except Exception:
            continue

        if fecha_inicio <= inicio.date() <= fecha_fin:
            categoria = prog.get("category", {}).get("#text", "Sin categoría")
            # Extraer todas las categorías del programa
            categorias_programa = extract_categories(categoria)
            
            # Si hay categoría de entrada, comprobar si coincide con alguna de las categorías del programa
            if categoria_entrada != "Todos" and not any(
                re.search(r'\b' + re.escape(categoria_entrada) + r'\b', cat, re.IGNORECASE)
                for cat in categorias_programa
            ):
                continue
                
            logger.debug(f"Programa incluido: {prog.get('title', {}).get('#text', 'Sin título')} con categorías '{categorias_programa}' para filtro '{categoria_entrada}'")

            prog_key = (prog['@start'], prog['@stop'], prog.get("title", {}).get("#text", ""), canal_mapped)
            if prog_key in seen_programs:
                continue
            seen_programs.add(prog_key)

            hora_inicio = inicio.astimezone(pytz.timezone("Europe/Madrid")).strftime("%H:%M")
            hora_fin = fin.astimezone(pytz.timezone("Europe/Madrid")).strftime("%H:%M")
            fecha = inicio.astimezone(pytz.timezone("Europe/Madrid")).strftime("%d/%m/%Y")
            titulo = prog.get("title", {}).get("#text", "Sin título")
            descripcion = prog.get("desc", {}).get("#text", "Sin descripción")
            imagen = prog.get("icon", {}).get("@src", "")
            desc_parts = descripcion.split(". ") if ". " in descripcion else [descripcion]
            synopsis = desc_parts[0][:100] + "..." if len(desc_parts[0]) > 100 else desc_parts[0]
            details = ". ".join(desc_parts[1:])[:200] + "..." if len(". ".join(desc_parts[1:])) > 200 else ". ".join(desc_parts[1:])
            
            eventos.append({
                "inicio": inicio,
                "fecha": fecha,
                "hora_inicio": hora_inicio,
                "hora_fin": hora_fin,
                "titulo": titulo,
                "synopsis": synopsis,
                "details": details,
                "categorias": categorias_programa,
                "imagen": imagen,
                "canal": canal_mapped
            })

    eventos.sort(key=lambda x: x["inicio"])

    # Determinar el modo de visualización
    if canal in CHANNELS_OFICIALES:
        # Modo canal específico
        eventos = [e for e in eventos if e["canal"] == canal]
        if not eventos:
            logger.warning(f"No se encontraron eventos para {canal} en el rango {fecha_inicio} a {fecha_fin}")
            lista_html = f'<p class="text-center text-red-500 text-lg font-semibold">No hay programas disponibles para {canal}. Verifique la fuente de datos EPG.</p>'
        else:
            lista_html = "".join(
                f'<div class="event-item relative bg-gradient-to-r from-gray-200 to-gray-300 p-4 rounded-lg cursor-pointer hover:scale-105 transition-transform duration-200 shadow-lg mb-4" onclick="openModal(\'{escape_js_string(evento["titulo"])}\', \'{escape_js_string(evento["fecha"])}\', \'{escape_js_string(evento["hora_inicio"])}\', \'{escape_js_string(evento["hora_fin"])}\', \'{escape_js_string(evento["synopsis"])}\', \'{escape_js_string(evento["details"])}\', \'{escape_js_string(",".join(evento["categorias"]))}\', \'{escape_js_string(evento["imagen"])}\')">'
                f'<div class="absolute left-0 top-0 h-full w-2 bg-cyan-500 rounded-l-lg"></div>'
                f'<div class="ml-4">'
                f'<p class="event-title font-bold text-gray-800 text-lg leading-tight mb-2 break-words">{evento["titulo"]}</p>'
                f'<p class="event-time font-mono text-gray-600 text-sm mb-2">{evento["fecha"]} {evento["hora_inicio"]} - {evento["hora_fin"]}</p>'
                f'<div class="flex flex-wrap gap-1">' +
                "".join(
                    f'<a href="/?categoria={urllib.parse.quote(cat)}&dia={dia_entrada}" class="event-category inline-block px-2 py-1 text-xs font-semibold rounded-full category-{cat.replace(" ", "_")}">{cat}</a>'
                    for cat in evento["categorias"]
                ) +
                f'</div>'
                f'</div>'
                f'</div>'
                for evento in eventos
            )
        channel_logo_html = (
            f'<div class="flex justify-center mb-6">'
            f'<img src="/static/img/{CANAL_TO_PNG.get(canal, "default.png")}" alt="{canal}" class="max-h-16 object-contain" onerror="this.style.display=\'none\';">'
            f'</div>'
        )
        page_title = canal
        show_back_link = True
    else:
        # Modo categoría o general
        if not eventos:
            logger.warning(f"No se encontraron eventos para categoría {categoria_entrada} en el rango {fecha_inicio} a {fecha_fin}")
            lista_html = f'<p class="text-center text-red-500 text-lg font-semibold">No hay programas disponibles para la categoría {categoria_entrada}. Verifique la fuente de datos EPG.</p>'
        else:
            lista_html = "".join(
                f'<div class="event-item relative bg-gradient-to-r from-gray-200 to-gray-300 p-4 rounded-lg cursor-pointer hover:scale-105 transition-transform duration-200 shadow-lg mb-4" onclick="openModal(\'{escape_js_string(evento["titulo"])}\', \'{escape_js_string(evento["fecha"])}\', \'{escape_js_string(evento["hora_inicio"])}\', \'{escape_js_string(evento["hora_fin"])}\', \'{escape_js_string(evento["synopsis"])}\', \'{escape_js_string(evento["details"])}\', \'{escape_js_string(",".join(evento["categorias"]))}\', \'{escape_js_string(evento["imagen"])}\')">'
                f'<div class="absolute left-0 top-0 h-full w-2 bg-cyan-500 rounded-l-lg"></div>'
                f'<div class="ml-4 flex items-start space-x-4">'
                f'<img src="/static/img/{CANAL_TO_PNG.get(evento["canal"], "default.png")}" alt="{evento["canal"]}" class="max-h-12 object-contain" onerror="this.style.display=\'none\';">'
                f'<div>'
                f'<p class="event-title font-bold text-gray-800 text-lg leading-tight mb-2 break-words">{evento["titulo"]}</p>'
                f'<p class="event-time font-mono text-gray-600 text-sm mb-2">{evento["fecha"]} {evento["hora_inicio"]} - {evento["hora_fin"]} | {evento["canal"]}</p>'
                f'<div class="flex flex-wrap gap-1">' +
                "".join(
                    f'<a href="/?categoria={urllib.parse.quote(cat)}&dia={dia_entrada}" class="event-category inline-block px-2 py-1 text-xs font-semibold rounded-full category-{cat.replace(" ", "_")}">{cat}</a>'
                    for cat in evento["categorias"]
                ) +
                f'</div>'
                f'</div>'
                f'</div>'
                f'</div>'
                for evento in eventos
            )
        channel_logo_html = ""
        page_title = f"Categoría: {categoria_entrada}"
        show_back_link = categoria_entrada != "Todos"
        # Para el modo general, incluir el channel_grid
        if categoria_entrada == "Todos":
            lista_html = f'<div class="channel-grid mb-6">{channel_grid}</div>' + lista_html
            page_title = "Guía de Programación EMBY TV"
            show_back_link = False

    html = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>""" + page_title + """</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .category-Fútbol { background-color: #22c55e; box-shadow: 0 0 8px #22c55e; color: white; }
        .category-Baloncesto { background-color: #3b82f6; box-shadow: 0 0 8px #3b82f6; color: white; }
        .category-Tenis { background-color: #d946ef; box-shadow: 0 0 8px #d946ef; color: white; }
        .category-Motor { background-color: #f43f5e; box-shadow: 0 0 8px #f43f5e; color: white; }
        .category-Motociclismo { background-color: #f97316; box-shadow: 0 0 8px #f97316; color: white; }
        .category-Rugby { background-color: #059669; box-shadow: 0 0 8px #059669; color: white; }
        .category-Padel { background-color: #f59e0b; box-shadow: 0 0 8px #f59e0b; color: white; }
        .category-Ciclismo { background-color: #10b981; box-shadow: 0 0 8px #10b981; color: white; }
        .category-Sin_categoría { background-color: #6b7280; box-shadow: 0 0 8px #6b7280; color: white; }
        body { background: linear-gradient(to bottom, #f3f4f6, #e5e7eb); }
        .event-item { position: relative; overflow: hidden; }
        .event-title { word-break: break-word; }
        .event-time { word-break: break-word; }
        .event-category { white-space: nowrap; cursor: pointer; }
        .event-category:hover { opacity: 0.8; }
        .channel-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px; }
    </style>
</head>
<body class="min-h-screen flex flex-col">
    <header class="sticky top-0 bg-gray-100 shadow-lg z-10 p-4">
        <div class="max-w-7xl mx-auto flex items-center justify-between">
            <div class="flex items-center space-x-4">
                <img src="/static/img/logo.png" alt="Logo" class="w-20">
                <h1 class="text-xl font-bold text-cyan-600">Guía EMBY TV - """ + page_title + """</h1>
            </div>
            """ + ('<a href="/" class="text-cyan-500 hover:text-cyan-400 text-sm font-semibold">Volver a Canales</a>' if show_back_link else '') + """
        </div>
    </header>
    <main class="flex-1 w-full max-w-7xl mx-auto p-4">
        <form id="filterForm" method="get" class="flex flex-col gap-4 mb-6">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <select name="dia" onchange="document.getElementById('filterForm').submit();" class="w-full max-w-xs p-2 bg-gray-200 border border-gray-400 rounded-lg text-gray-800 text-center focus:outline-none focus:ring-2 focus:ring-cyan-500">
                    """ + selector_dias + """
                </select>
                <select name="categoria" onchange="document.getElementById('filterForm').submit();" class="w-full max-w-xs p-2 bg-gray-200 border border-gray-400 rounded-lg text-gray-800 text-center focus:outline-none focus:ring-2 focus:ring-cyan-500">
                    """ + selector_categorias + """
                </select>
            </div>
        </form>
        <div class="w-full">
            """ + channel_logo_html + lista_html + """
        </div>
    </main>
    <div id="eventModal" class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center p-4 hidden z-20">
        <div class="bg-gray-200 rounded-xl p-6 w-full max-w-md shadow-2xl" onclick="event.stopPropagation()">
            <div class="flex justify-between items-center mb-4">
                <h2 id="modalTitle" class="text-xl font-bold text-cyan-600 break-words"></h2>
                <button onclick="closeModal()" class="text-cyan-500 text-2xl hover:text-cyan-400">&times;</button>
            </div>
            <div class="space-y-4">
                <img id="modalImage" alt="Event" class="w-full max-h-64 object-contain rounded-lg cursor-pointer hidden" onclick="openFullScreenImage(this.src)">
                <div class="grid grid-cols-1 gap-3">
                    <p class="text-sm"><strong class="text-cyan-600">Fecha y Hora:</strong> <span id="modalDateTime" class="text-gray-800 ml-2 break-words"></span></p>
                    <p class="text-sm"><strong class="text-cyan-600">Categoría:</strong> <span id="modalCategory" class="ml-2 break-words"></span></p>
                    <p class="text-sm"><strong class="text-cyan-600">Sinopsis:</strong> <span id="modalSynopsis" class="text-gray-800 ml-2 break-words"></span></p>
                    <p class="text-sm"><strong class="text-cyan-600">Detalles:</strong> <span id="modalDetails" class="text-gray-800 ml-2 break-words"></span></p>
                </div>
            </div>
        </div>
    </div>
    <div id="fullScreenImageModal" class="fixed inset-0 bg-black flex items-center justify-center hidden z-30">
        <img id="fullScreenImage" alt="Full Screen Event" class="max-w-full max-h-full object-contain">
        <button onclick="closeFullScreenImage()" class="absolute top-4 right-4 text-white text-3xl bg-gray-800 rounded-full w-10 h-10 flex items-center justify-center hover:bg-gray-700">&times;</button>
    </div>
    <script>
        function openModal(title, date, startTime, endTime, synopsis, details, categories, image) {
            document.getElementById('modalTitle').textContent = title;
            document.getElementById('modalDateTime').textContent = `${date} ${startTime} - ${endTime}`;
            
            // Mostrar todas las categorías con sus colores
            const modalCategory = document.getElementById('modalCategory');
            modalCategory.innerHTML = categories.split(',').map(cat => 
                `<span class="px-2 py-1 text-xs font-semibold rounded-full category-${cat.replace(' ', '_')}">${cat}</span>`
            ).join(' ');
            
            document.getElementById('modalSynopsis').textContent = synopsis;
            document.getElementById('modalDetails').textContent = details;
            const modalImage = document.getElementById('modalImage');
            if (image) {
                modalImage.src = image;
                modalImage.classList.remove('hidden');
            } else {
                modalImage.classList.add('hidden');
            }
            document.getElementById('eventModal').classList.remove('hidden');
        }

        function closeModal() {
            document.getElementById('eventModal').classList.add('hidden');
        }

        function openFullScreenImage(src) {
            const fullScreenImage = document.getElementById('fullScreenImage');
            fullScreenImage.src = src;
            document.getElementById('fullScreenImageModal').classList.remove('hidden');
        }

        function closeFullScreenImage() {
            document.getElementById('fullScreenImageModal').classList.add('hidden');
        }

        window.onclick = function(event) {
            const eventModal = document.getElementById('eventModal');
            const fullScreenModal = document.getElementById('fullScreenImageModal');
            if (event.target === eventModal) {
                eventModal.classList.add('hidden');
            }
            if (event.target === fullScreenModal) {
                fullScreenModal.classList.add('hidden');
            }
        }
    </script>
</body>
</html>"""
    return Response(html, mimetype="text/html")

if __name__ == "__main__":
    print("🔵 Servidor EPG en: http://0.0.0.0:5053/")
    app.run(host="0.0.0.0", port=5053, debug=True)