"""
Planificador de Horario Académico - SIIAU UDG
FastAPI Version 2.0

Migrated from Flask to FastAPI for better performance and modern async support
"""
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Body
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse, StreamingResponse, Response
from starlette.middleware.sessions import SessionMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List, Any, Union
import requests
from bs4 import BeautifulSoup
import re
import time
import os
from dotenv import load_dotenv
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors as reportlab_colors
from datetime import datetime
import json
from functools import lru_cache  # OPTIMIZACIÓN: Para caché en memoria

# Supabase imports
from supabase_client import (
    SUPABASE_URL,
    supabase_sign_in,
    supabase_sign_up,
    supabase_get_schedules,
    supabase_create_schedule,
    supabase_create_profile_service,
    supabase_get_user,
    supabase_get_profile,
    supabase_delete_schedule,
    supabase_update_schedule,
    supabase_get_schedule_items,
    supabase_delete_schedule_items,
    supabase_reset_password_email,
    supabase_update_user_password,
    supabase_get_professor_ratings,
    supabase_add_professor_rating,
    supabase_get_all_professor_averages,
)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Planificador de Horario Académico - SIIAU UDG",
    description="Aplicación para planificar horarios académicos de la UDG",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Setup Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Rate Limit Middleware (should be close to application layer)
app.add_middleware(SlowAPIMiddleware)

# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get('FLASK_SECRET', 'dev-secret-changeme'),
    max_age=86400,  # 24 hours
    https_only=False,
    same_site='lax'
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Add custom filter for flash messages
def get_flashed_messages(with_categories=False, category_filter=[]):
    """
    Get and clear flash messages from session (Flask-compatible).
    Note: This is injected into templates via context, not called directly.
    """
    # This function is replaced in templates by a context-aware version
    # This is just a placeholder
    return []

# Add to Jinja2 env
templates.env.globals['get_flashed_messages'] = get_flashed_messages

# Custom TemplateResponse that auto-injects url_for
class CustomTemplateResponse(HTMLResponse):
    """Template response with auto-injected url_for and get_flashed_messages"""
    def __init__(self, template_name: str, context: dict, *args, **kwargs):
        request = context.get('request')
        if request:
            # Create url_for wrapper for this request
            def url_for(name: str, **path_params):
                if name == 'static' and 'filename' in path_params:
                    path_params['path'] = path_params.pop('filename')
                return request.url_for(name, **path_params)
            
            # Create get_flashed_messages wrapper for this request
            def get_flashed_messages(with_categories=False, category_filter=[]):
                """Flask-compatible flash message getter"""
                messages = request.session.pop("flash_messages", [])
                if with_categories:
                    # Return as (category, message) tuples
                    return [(msg.get('category', 'info'), msg.get('message', '')) for msg in messages]
                else:
                    # Return just messages
                    return [msg.get('message', '') for msg in messages]
            
            context['url_for'] = url_for
            context['get_flashed_messages'] = get_flashed_messages
            if 'session_user' not in context:
                context['session_user'] = request.session.get('user')
        
        # Render the template
        content = templates.get_template(template_name).render(context)
        super().__init__(content=content, *args, **kwargs)

# Constants from original app
POST_URL = "https://siiauescolar.siiau.udg.mx/wal/sspseca.consulta_oferta"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "es-419,es;q=0.9",
    "Cache-Control": "max-age=0",
    "DNT": "1",
    "Origin": "https://siiauescolar.siiau.udg.mx",
    "Referer": "https://siiauescolar.siiau.udg.mx/wal/sspseca.forma_consulta",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded"
}

COOKIES = {
    "21082024SIIAUSESION": "1542435678",
    "21082024SIIAUUDG": "1692153",
    "07122024SIIAUSESION": "611522407",
    "07122024SIIAUUDG": "1692153",
    "06082025SIIAUSESION": "1015485614",
    "06082025SIIAUUDG": "1692153",
    "07082025SIIAUUDG": "1692153",
    "07082025SIIAUSESION": "588707643",
    "cookiesession1": "678B287E4E1A792C793C3634D5FF5F58",
    "03102025SIIAUSESION": "1280826723",
    "03102025SIIAUUDG": "1692153",
    "05102025SIIAUSESION": "1231724026",
    "05102025SIIAUUDG": "1692153"
}

CENTROS = {
    '3': 'CUTLAJO - de Tlajomulco',
    '4': 'CUGDL - de Guadalajara',
    '5': 'CUTlAQUEPAQUE - de Tlaquepaque',
    '6': 'CUCHAPALA - de Chapala',
    'A': 'CUAAD - Arte, Arquitectura y Diseño',
    'B': 'CUCBA - Ciencias Biológicas y Agropecuarias',
    'C': 'CUCEA - Ciencias Económico Administrativas',
    'D': 'CUCEI - Ciencias Exactas e Ingenierías',
    'E': 'CUCS - Ciencias de la Salud',
    'F': 'CUCSH - Ciencias Sociales y Humanidades',
    'G': 'CUALTOS - de los Altos',
    'H': 'CUCIENEGA - de la Ciénega',
    'I': 'CUCOSTA - de la Costa',
    'J': 'CUCSUR - de la Costa Sur',
    'K': 'CUSUR - del Sur',
    'M': 'CUVALLES - de los Valles',
    'N': 'CUNORTE - del Norte',
    'O': 'CUCEI SEDE VALLES',
    'P': 'CUCSUR SEDE VALLES',
    'Q': 'CUCEI SEDE NORTE',
    'R': 'CUALTOS SEDE NORTE',
    'S': 'CUCOSTA SEDE NORTE',
    'T': 'SEDE TLAJOMULCO',
    'U': 'CULAGOS - DE LOS LAGOS',
    'V': 'CICLO DE VERANO',
    'W': 'CUCEA SEDE VALLE',
    'X': 'SIST DE UNIVERSIDAD VIRTUAL',
    'Y': 'ESCUELAS INCORPORADAS',
    'Z': 'CUTONALA - de Tonalá',
}

# ===== Helper Functions =====

# OPTIMIZACIÓN: Caché para ratings de profesores (reduce DB queries)
_professor_ratings_cache = {'data': None, 'timestamp': 0}
CACHE_TTL = 3600  # 1 hora en segundos

def get_cached_professor_ratings():
    """Obtiene ratings de profesores con caché de 1 hora"""
    current_time = time.time()
    
    # Verificar si el caché es válido
    if (_professor_ratings_cache['data'] is not None and 
        (current_time - _professor_ratings_cache['timestamp']) < CACHE_TTL):
        return _professor_ratings_cache['data']
    
    # Si no hay caché válido, obtener de Supabase
    ratings_averages, _ = supabase_get_all_professor_averages()
    
    # Actualizar caché
    _professor_ratings_cache['data'] = ratings_averages
    _professor_ratings_cache['timestamp'] = current_time
    
    return ratings_averages

def flash(request: Request, message: str, category: str = "info"):
    """Add a flash message to the session"""
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append({"message": message, "category": category})

def extract_rows_from_table(soup):
    """Extrae las filas de la tabla principal, expandiendo los horarios."""
    tabla = soup.find('table')
    if not tabla:
        return []

    filas = tabla.find_all('tr', recursive=False)
    datos_finales = []
    for tr in filas:
        tds = tr.find_all('td', recursive=False)
        if not tds or not re.match(r'^\d{4,}', tds[0].get_text(strip=True)):
            continue

        def txt(cell):
            return cell.get_text(' ', strip=True)

        base_info = {
            'NRC': txt(tds[0]),
            'Clave': txt(tds[1]) if len(tds) > 1 else '',
            'Materia': txt(tds[2]) if len(tds) > 2 else '',
            'Sec': txt(tds[3]) if len(tds) > 3 else '',
            'CR': txt(tds[4]) if len(tds) > 4 else '',
            'CUP': txt(tds[5]) if len(tds) > 5 else '',
            'DIS': txt(tds[6]) if len(tds) > 6 else '',
        }

        profesor = ''
        if len(tds) > 8:
            inner_prof = tds[8].find('table')
            if inner_prof:
                prof_tr = inner_prof.find('tr')
                if prof_tr and len(prof_tr.find_all('td')) >= 2:
                    profesor = prof_tr.find_all('td')[1].get_text(' ', strip=True)
                elif prof_tr:
                    profesor = txt(prof_tr)
            else:
                profesor = txt(tds[8])
        base_info['Profesor'] = profesor

        horario_str = ''
        if len(tds) > 7:
            inner_table = tds[7].find('table')
            if inner_table:
                parts = []
                for ir in inner_table.find_all('tr'):
                    parts.append(' | '.join([c.get_text(' ', strip=True) for c in ir.find_all('td')]))
                horario_str = ' ; '.join(p for p in parts if p.strip())
            else:
                horario_str = txt(tds[7])

        if horario_str.strip():
            sesiones = horario_str.split(';')
            for sesion in sesiones:
                partes = [p.strip() for p in sesion.split('|')]
                fila_expandida = base_info.copy()
                fila_expandida.update({
                    'SesionNum': partes[0] if len(partes) > 0 else '',
                    'Horas': partes[1] if len(partes) > 1 else '',
                    'Dias': partes[2] if len(partes) > 2 else '',
                    'Edificio': partes[3] if len(partes) > 3 else '',
                    'Aula': partes[4] if len(partes) > 4 else '',
                    'Periodo': partes[5] if len(partes) > 5 else '',
                })
                datos_finales.append(fila_expandida)
        else:
            fila_vacia = base_info.copy()
            fila_vacia.update({
                'SesionNum': '', 'Horas': '', 'Dias': '', 'Edificio': '', 'Aula': '', 'Periodo': ''
            })
            datos_finales.append(fila_vacia)

    return datos_finales

def get_next_p_start(soup):
    """Busca el siguiente valor de p_start."""
    form = soup.find('form', attrs={'name': True})
    if not form:
        inp = soup.find('input', attrs={'name': 'p_start'})
    else:
        inp = form.find('input', attrs={'name': 'p_start'})
    if inp and inp.get('value'):
        try:
            return int(inp.get('value'))
        except ValueError:
            return None
    return None

def fetch_all_pages(session, post_url, payload_base):
    """Itera páginas y acumula resultados."""
    results = []
    p_start = 0
    seen_any = False
    page = 0
    
    # OPTIMIZACIÓN: Reducir de 100 a 10 páginas para reducir CPU usage
    MAX_PAGES = 10

    while page < MAX_PAGES:
        page += 1
        payload = dict(payload_base)
        payload['p_start'] = str(p_start)

        try:
            # OPTIMIZACIÓN: Aumentar timeout a 60s para evitar reintentos
            resp = session.post(post_url, data=payload, timeout=60)
            if resp.status_code != 200:
                break

            soup = BeautifulSoup(resp.text, 'html.parser')
            page_rows = extract_rows_from_table(soup)

            if page_rows:
                seen_any = True
                results.extend(page_rows)
            else:
                if seen_any or page == 1:
                    break

            mostrar_val = int(payload_base.get('mostrarp', '100'))
            next_button = soup.find('input', {'value': f'{mostrar_val} Próximos'}) or soup.find('input', {'value': '100 Próximos'})
            if next_button:
                p_start += mostrar_val
                continue

            next_p = get_next_p_start(soup)
            if next_p and next_p > p_start:
                p_start = next_p
                continue

            break

            time.sleep(1)

        except Exception as e:
            print(f"Error en página {page}: {str(e)}")
            break

    return results

def prepare_schedule_data(schedule, schedule_items):
    """Prepara los datos del horario para el PDF."""
    materias_map = {}
    colors_assigned = {}
    color_palette = [
        reportlab_colors.HexColor('#667eea'),
        reportlab_colors.HexColor('#4facfe'),
        reportlab_colors.HexColor('#fdcb6e'),
        reportlab_colors.HexColor('#43e97b'),
        reportlab_colors.HexColor('#fa709a'),
        reportlab_colors.HexColor('#30cfd0'),
        reportlab_colors.HexColor('#a8edea'),
        reportlab_colors.HexColor('#c471f5'),
        reportlab_colors.HexColor('#ff7675'),
        reportlab_colors.HexColor('#00b894'),
    ]
    
    for idx, item in enumerate(schedule_items):
        nrc = item.get('nrc', '')
        materia = item.get('materia', '')
        key = f"{nrc}_{materia}"
        
        if key not in materias_map:
            color_idx = len(materias_map) % len(color_palette)
            materias_map[key] = {
                'nrc': nrc,
                'clave': item.get('clave', ''),
                'materia': materia,
                'seccion': item.get('seccion', ''),
                'creditos': item.get('creditos', ''),
                'profesor': item.get('profesor', ''),
                'color': color_palette[color_idx],
                'horarios': []
            }
            
        dias = item.get('dias', '')
        horas = item.get('horas', '')
        edificio = item.get('edificio', '')
        aula = item.get('aula', '')
        
        if dias and horas:
            materias_map[key]['horarios'].append({
                'dias': dias,
                'horas': horas,
                'edificio': edificio,
                'aula': aula
            })
    
    return list(materias_map.values())

def parse_hours(hours_str):
    """Parsea string de horas tipo '08:00-10:00' o '0800-1000'."""
    if not hours_str:
        return None, None
    
    hours_str = hours_str.strip()
    
    if '-' in hours_str:
        parts = hours_str.split('-')
        if len(parts) == 2:
            start_str = parts[0].strip()
            end_str = parts[1].strip()
            
            if ':' in start_str:
                start_time = start_str
                end_time = end_str
            else:
                if len(start_str) == 4:
                    start_time = f"{start_str[:2]}:{start_str[2:]}"
                else:
                    start_time = start_str
                    
                if len(end_str) == 4:
                    end_time = f"{end_str[:2]}:{end_str[2:]}"
                else:
                    end_time = end_str
                    
            return start_time, end_time
            
    return None, None

def parse_days(days_val):
    """Parsea días a lista de números (1=Lun, 2=Mar, etc)."""
    if not days_val:
        return []
    
    days_val = str(days_val).strip().upper()
    days_list = []
    
    day_map = {
        'L': 1,
        'M': 2,
        'I': 3,  # Miércoles
        'MI': 3,
        'J': 4,
        'V': 5,
        'S': 6
    }
    
    parts = days_val.split()
    for part in parts:
        part = part.strip().replace('.', '')
        if part in day_map:
            days_list.append(day_map[part])
    
    return days_list

def parse_days_to_string(days_val):
    """Convierte días a string legible (L, M, Mi, J, V, S)."""
    days_list = parse_days(days_val)
    dias_map = {1: 'L', 2: 'M', 3: 'Mi', 4: 'J', 5: 'V', 6: 'S'}
    return ' '.join([dias_map.get(d, '') for d in days_list])

def create_schedule_table(schedule_data):
    """Crea la tabla del calendario de horario."""
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    
    # Headers
    headers = ['Hora', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']
    
    # Time slots
    hours = [
        '07:00', '08:00', '09:00', '10:00', '11:00', '12:00',
        '13:00', '14:00', '15:00', '16:00', '17:00', '18:00',
        '19:00', '20:00', '21:00'
    ]
    
    # Initialize grid
    grid = [[hour] + [''] * 6 for hour in hours]
    
    # Fill grid with classes
    for materia in schedule_data:
        for horario in materia['horarios']:
            start_time, end_time = parse_hours(horario['horas'])
            days_list = parse_days(horario['dias'])
            
            if not start_time or not days_list:
                continue
            
            try:
                start_hour = int(start_time.split(':')[0])
                if start_hour < 7 or start_hour > 21:
                    continue
                    
                row_idx = start_hour - 7
                
                cell_text = f"{materia['materia'][:20]}\n{horario['edificio']} {horario['aula']}\n{horario['horas']}"
                
                for day_num in days_list:
                    if 1 <= day_num <= 6:
                        col_idx = day_num
                        if row_idx < len(grid):
                            if grid[row_idx][col_idx]:
                                grid[row_idx][col_idx] += f"\n---\n{cell_text}"
                            else:
                                grid[row_idx][col_idx] = cell_text
            except (ValueError, IndexError):
                continue
    
    # Build table data
    table_data = [headers] + grid
    
    # Create table
    table = Table(table_data, colWidths=[0.7*inch] + [1.2*inch]*6)
    
    # Apply style
    style = TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), reportlab_colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), reportlab_colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Time column
        ('BACKGROUND', (0, 1), (0, -1), reportlab_colors.HexColor('#f0f0f0')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (0, -1), 8),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 1, reportlab_colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (1, 1), (-1, -1), 7),
        ('LEFTPADDING', (1, 1), (-1, -1), 4),
        ('RIGHTPADDING', (1, 1), (-1, -1), 4),
    ])
    
    table.setStyle(style)
    return table

def create_courses_detail_table(schedule_data):
    """Crea tabla detallada de materias."""
    table_data = [['Materia', 'NRC', 'Profesor', 'Horarios']]
    
    for materia in schedule_data:
        horarios_text = []
        for h in materia['horarios']:
            dias_str = parse_days_to_string(h['dias'])
            horarios_text.append(f"{dias_str} {h['horas']} - {h['edificio']} {h['aula']}")
        
        horarios_combined = '\n'.join(horarios_text)
        
        table_data.append([
            materia['materia'],
            materia['nrc'],
            materia['profesor'],
            horarios_combined
        ])
    
    table = Table(table_data, colWidths=[2.5*inch, 0.8*inch, 1.5*inch, 2*inch])
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), reportlab_colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), reportlab_colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, reportlab_colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (1, 1), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ])
    
    table.setStyle(style)
    return table

# ===== PYDANTIC MODELS =====

class BuscarMateriasRequest(BaseModel):
    ciclo: str = ""
    centro: str = ""
    carrera: str = ""

class BuscarProfesoresRequest(BaseModel):
    ciclo: str = ""
    centro: str = ""
    carrera: str = ""

class RateProfessorRequest(BaseModel):
    professor_name: str
    rating: Union[int, Dict[str, int]]
    comment: Optional[str] = ""

# ===== DEPENDENCIES =====

async def get_current_user(request: Request):
    """Dependency to get current authenticated user"""
    if not request.session.get('access_token'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return request.session.get('user')

# ===== PUBLIC ROUTES =====

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Página de inicio (Landing Page)"""
    user = request.session.get('user')
    profile = None
    if user and request.session.get('access_token'):
        profile = supabase_get_profile(request.session['access_token'], user['id'])
    return CustomTemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "profile": profile
        }
    )

@app.get("/feedback", response_class=HTMLResponse)
async def feedback_page(request: Request):
    """Página de sugerencias"""
    user = request.session.get('user')
    profile = None
    if user and request.session.get('access_token'):
        profile = supabase_get_profile(request.session['access_token'], user['id'])
    return CustomTemplateResponse(
        "feedback.html",
        {"request": request, "user": user, "profile": profile}
    )

@app.get("/planner", response_class=HTMLResponse)
async def planner_page(request: Request):
    """Página del planificador de horarios"""
    user = request.session.get('user')
    profile = None
    if user and request.session.get('access_token'):
        profile = supabase_get_profile(request.session['access_token'], user['id'])
    
    return CustomTemplateResponse(
        "planner.html",
        {
            "request": request,
            "centros": CENTROS,
            "user": user,
            "profile": profile
        }
    )

@app.get("/beneficios")
async def beneficios():
    """Redirige a la página externa de beneficios UDG"""
    return RedirectResponse(url="https://beneficios.diferente.page/", status_code=303)

@app.get("/professors", response_class=HTMLResponse)
async def professors_page(request: Request):
    """Página para calificar profesores"""
    user = request.session.get('user')
    
    return CustomTemplateResponse(
        "professors.html",
        {
            "request": request,
            "centros": CENTROS,
            "user": user
        }
    )

# ===== AUTH ROUTES =====

@app.get("/auth/google")
async def auth_google(request: Request):
    """Redirige a Supabase Google OAuth"""
    redirect_to = str(request.base_url) + "login"
    url = f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={redirect_to}"
    return RedirectResponse(url=url, status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_view(request: Request):
    """Página de login"""
    return CustomTemplateResponse("signin.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
async def signup_view(request: Request):
    """Página de registro"""
    return CustomTemplateResponse("signup.html", {"request": request})

@app.post("/auth/login")
@limiter.limit("10/minute")
async def auth_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    """Login de usuario"""
    if not email or not password:
        flash(request, 'Email y contraseña requeridos', 'error')
        return RedirectResponse(url="/login", status_code=303)
    
    res = supabase_sign_in(email, password)
    if not res or 'access_token' not in res:
        flash(request, 'Error al autenticar', 'error')
        return RedirectResponse(url="/login", status_code=303)
    
    request.session['access_token'] = res['access_token']
    u = res['user']
    request.session['user'] = {'id': u.get('id'), 'email': u.get('email'), 'user_metadata': {'full_name': u.get('user_metadata', {}).get('full_name'), 'avatar_url': u.get('user_metadata', {}).get('avatar_url')}}
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/auth/register")
async def auth_register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    full_name: str = Form(...)
):
    """Registro de nuevo usuario"""
    if not email or not password:
        flash(request, 'Email y contraseña requeridos', 'error')
        return RedirectResponse(url="/signup", status_code=303)
    
    if password != confirm_password:
        flash(request, 'Las contraseñas no coinciden', 'error')
        return RedirectResponse(url="/signup", status_code=303)
    
    res = supabase_sign_up(email, password, full_name)
    if not res:
        flash(request, 'Error de conexión con el servicio de autenticación', 'error')
        return RedirectResponse(url="/login", status_code=303)

    user = None
    if 'user' in res:
        user = res['user']
    elif 'id' in res and 'email' in res:
        user = res

    if not user:
        error_msg = res.get('msg') or res.get('error_description') or res.get('message') or res.get('error')
        if not error_msg:
            error_msg = f"Respuesta desconocida del servidor: {res}"
        
        error_str = str(error_msg)
        if "security purposes" in error_str and "seconds" in error_str:
            flash(request, 'Por seguridad, debes esperar unos segundos antes de intentar registrarte de nuevo.', 'error')
        elif "User already registered" in error_str:
            flash(request, 'Este correo ya está registrado. Intenta iniciar sesión.', 'error')
        else:
            flash(request, f'Error al registrar: {error_str}', 'error')
        
        return RedirectResponse(url="/login", status_code=303)

    user_id = user.get('id') if user else None
    if user_id:
        time.sleep(1)
        try:
            prof = supabase_create_profile_service(user_id, email, full_name)
            if not prof:
                time.sleep(2)
                supabase_create_profile_service(user_id, email, full_name)
        except Exception as e:
            print(f'Error al crear profile: {e}')

    flash(request, 'Registro exitoso. Por favor revise su correo (y la carpeta de no deseados) para confirmar su cuenta y poder iniciar sesión.', 'success')
    return RedirectResponse(url="/login", status_code=303)

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_get(request: Request):
    """Página de recuperación de contraseña"""
    return CustomTemplateResponse("forgot_password.html", {"request": request})

@app.post("/forgot-password")
async def forgot_password_post(
    request: Request,
    email: str = Form(...)
):
    """Enviar email de recuperación"""
    if not email:
        flash(request, 'Por favor ingresa tu correo', 'error')
        return RedirectResponse(url="/forgot-password", status_code=303)
    
    callback_url = str(request.url_for('auth_callback'))
    success = supabase_reset_password_email(email, redirect_url=callback_url)
    
    if success:
        flash(request, 'Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.', 'success')
    else:
        flash(request, 'Error al enviar el correo. Intenta más tarde.', 'error')
    
    return RedirectResponse(url="/login", status_code=303)

@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_get(request: Request):
    """Página para establecer nueva contraseña"""
    if not request.session.get('access_token'):
        flash(request, 'Enlace inválido o expirado. Por favor solicita uno nuevo.', 'error')
        return RedirectResponse(url="/forgot-password", status_code=303)
    
    return CustomTemplateResponse("reset_password.html", {"request": request})

@app.post("/reset-password")
async def reset_password_post(
    request: Request,
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    """Actualizar contraseña"""
    if not request.session.get('access_token'):
        flash(request, 'Enlace inválido o expirado. Por favor solicita uno nuevo.', 'error')
        return RedirectResponse(url="/forgot-password", status_code=303)
    
    if not password or len(password) < 6:
        flash(request, 'La contraseña debe tener al menos 6 caracteres', 'error')
        return RedirectResponse(url="/reset-password", status_code=303)
    
    if password != confirm_password:
        flash(request, 'Las contraseñas no coinciden', 'error')
        return RedirectResponse(url="/reset-password", status_code=303)
    
    user, error_msg = supabase_update_user_password(request.session['access_token'], password)
    
    if user:
        flash(request, 'Has restablecido la contraseña con éxito.', 'success')
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)
    else:
        flash(request, f'Error al actualizar la contraseña: {error_msg}', 'error')
        return RedirectResponse(url="/reset-password", status_code=303)

@app.get("/auth/callback")
async def auth_callback_get(request: Request):
    """Manejar confirmación de email desde Supabase (GET)"""
    access_token = request.query_params.get('access_token')
    refresh_token = request.query_params.get('refresh_token')
    token_type = request.query_params.get('token_type')
    expires_in = request.query_params.get('expires_in')
    error = request.query_params.get('error')
    error_description = request.query_params.get('error_description')
    type_ = request.query_params.get('type')

    if error:
        flash(request, f'Error en confirmación: {error_description}', 'error')
        return RedirectResponse(url="/login", status_code=303)

    if not access_token:
        flash(request, 'Token de acceso faltante', 'error')
        return RedirectResponse(url="/login", status_code=303)

    user = supabase_get_user(access_token)
    if not user:
        flash(request, 'Error al obtener información del usuario', 'error')
        return RedirectResponse(url="/login", status_code=303)

    request.session['access_token'] = access_token
    request.session['user'] = {'id': user.get('id'), 'email': user.get('email'), 'user_metadata': {'full_name': user.get('user_metadata', {}).get('full_name'), 'avatar_url': user.get('user_metadata', {}).get('avatar_url')}}
    if refresh_token:
        request.session['refresh_token'] = refresh_token

    if type_ == 'recovery':
        return RedirectResponse(url="/reset-password", status_code=303)

    return CustomTemplateResponse("confirmation.html", {"request": request})

@app.post("/auth/callback/form")
async def auth_callback_form(
    request: Request,
    access_token: str = Form(None),
    refresh_token: str = Form(None),
    type: str = Form(None),
    error: str = Form(None),
    error_description: str = Form(None),
):
    """Manejar callback OAuth via form submit (cookie-safe)"""
    if error:
        flash(request, f'Error: {error_description}', 'error')
        return RedirectResponse(url="/login", status_code=303)
    if not access_token:
        flash(request, 'Token de acceso faltante', 'error')
        return RedirectResponse(url="/login", status_code=303)
    user = supabase_get_user(access_token)
    if not user:
        flash(request, 'Error al obtener información del usuario', 'error')
        return RedirectResponse(url="/login", status_code=303)
    request.session['access_token'] = access_token
    request.session['user'] = {
        'id': user.get('id'),
        'email': user.get('email'),
        'user_metadata': {
            'full_name': user.get('user_metadata', {}).get('full_name'),
            'avatar_url': user.get('user_metadata', {}).get('avatar_url'),
        }
    }
    if refresh_token:
        request.session['refresh_token'] = refresh_token
    dest = "/reset-password" if type == "recovery" else "/dashboard"
    from fastapi.responses import HTMLResponse as _HR
    return _HR(content=f'<meta http-equiv="refresh" content="0;url={dest}">', status_code=200)

@app.post("/auth/callback")
async def auth_callback_post(request: Request, data: Dict[str, Any] = Body(...)):
    """Manejar confirmación de email desde Supabase (POST)"""
    access_token = data.get('access_token')
    refresh_token = data.get('refresh_token')
    error = data.get('error')
    error_description = data.get('error_description')
    type_ = data.get('type')

    if error:
        return JSONResponse({'error': f'Error en confirmación: {error_description}'}, status_code=400)

    if not access_token:
        return JSONResponse({'error': 'Token de acceso faltante'}, status_code=400)

    user = supabase_get_user(access_token)
    if not user:
        return JSONResponse({'error': 'Error al obtener información del usuario'}, status_code=400)

    request.session['access_token'] = access_token
    request.session['user'] = {'id': user.get('id'), 'email': user.get('email'), 'user_metadata': {'full_name': user.get('user_metadata', {}).get('full_name'), 'avatar_url': user.get('user_metadata', {}).get('avatar_url')}}
    if refresh_token:
        request.session['refresh_token'] = refresh_token

    if type_ == 'recovery':
        return JSONResponse({'redirect': '/reset-password'})

    return JSONResponse({'redirect': '/dashboard'})

@app.get("/logout")
async def logout(request: Request):
    """Cerrar sesión"""
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)

# ===== DASHBOARD & SCHEDULES =====

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard de usuario"""
    if not request.session.get('access_token'):
        return RedirectResponse(url="/login", status_code=303)
    
    access_token = request.session['access_token']
    user = request.session.get('user')
    user_id = user.get('id')
    
    profile = supabase_get_profile(access_token, user_id)
    
    schedules = supabase_get_schedules(access_token, user_id)
    
    # Handle case where schedules might be None
    if schedules is None:
        schedules = []
    
    max_schedules = 3
    can_create_more = len(schedules) < max_schedules
    
    return CustomTemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "schedules": schedules,
            "user": user,
            "profile": profile,
            "can_create_more": can_create_more,
            "schedule_count": len(schedules),
            "max_schedules": max_schedules,
            "centros": CENTROS
        }
    )

@app.post("/schedules/create")
async def create_schedule(
    request: Request,
    name: str = Form(...),
    data: str = Form(...)
):
    """Crear nuevo horario"""
    if not request.session.get('access_token'):
        flash(request, 'Debes iniciar sesión para guardar horarios', 'error')
        return RedirectResponse(url="/login", status_code=303)
    
    access_token = request.session['access_token']
    user_id = request.session['user']['id']
    
    profile = supabase_get_profile(access_token, user_id)
    
    if not profile:
        user_data = request.session.get('user', {})
        email = user_data.get('email')
        full_name = user_data.get('user_metadata', {}).get('full_name')
        if email:
            profile = supabase_create_profile_service(user_id, email, full_name)

    schedules = supabase_get_schedules(access_token, user_id)
    
    # Handle case where schedules might be None
    if schedules is None:
        schedules = []
    
    if len(schedules) >= 3:
        flash(request, 'Límite alcanzado. Máximo 3 horarios permitidos', 'error')
        return RedirectResponse(url="/dashboard", status_code=303)
    
    name = name or 'Mi horario'
    
    try:
        data_parsed = json.loads(data)
    except Exception as e:
        data_parsed = {}
    
    s = supabase_create_schedule(access_token, user_id, name, data=data_parsed)
    if s:
        flash(request, f'¡Horario "{name}" guardado exitosamente!', 'success')
        schedule_id = s[0]['id'] if isinstance(s, list) and len(s) > 0 else s.get('id') if isinstance(s, dict) else None
        if schedule_id:
            return RedirectResponse(url=f"/schedules/{schedule_id}", status_code=303)
        return RedirectResponse(url="/dashboard", status_code=303)
    else:
        flash(request, 'Error al guardar horario. Por favor intenta de nuevo.', 'error')
        return RedirectResponse(url="/", status_code=303)

@app.post("/schedules/{schedule_id}/delete")
async def delete_schedule_route(request: Request, schedule_id: str):
    """Eliminar horario"""
    if not request.session.get('access_token'):
        return JSONResponse({'error': 'not authenticated'}, status_code=401)
    
    access_token = request.session['access_token']
    success = supabase_delete_schedule(access_token, schedule_id)
    
    if success:
        flash(request, 'Horario eliminado', 'success')
    else:
        flash(request, 'Error al eliminar horario', 'error')
    
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/schedules/{schedule_id}/edit")
async def edit_schedule_route(
    request: Request,
    schedule_id: str,
    name: str = Form(None),
    color: str = Form(None),
    notes: str = Form(None),
    deleted_items: str = Form(None),
    metadata_materias: str = Form(None)
):
    """Editar horario"""
    if not request.session.get('access_token'):
        return JSONResponse({'error': 'not authenticated'}, status_code=401)
    
    access_token = request.session['access_token']
    
    if deleted_items:
        try:
            item_ids = [id.strip() for id in deleted_items.split(',') if id.strip()]
            if item_ids:
                supabase_delete_schedule_items(access_token, item_ids)
        except Exception as e:
            print(f"Error deleting items: {e}")

    new_metadata = None
    try:
        schedules = supabase_get_schedules(access_token, request.session['user']['id'])
        current_schedule = next((s for s in schedules if str(s.get('id')) == str(schedule_id)), None)
        
        if current_schedule:
            new_metadata = current_schedule.get('metadata', {}) or {}
            
            if metadata_materias:
                new_metadata['materias'] = json.loads(metadata_materias)
            
            if name:
                new_metadata['nombre'] = name
            
            if color:
                new_metadata['color'] = color
            if notes:
                new_metadata['notes'] = notes
    except Exception as e:
        print(f"Error preparing metadata update: {e}")
    
    success = supabase_update_schedule(access_token, schedule_id, name=name, color=color, notes=notes, metadata=new_metadata)
    
    if success:
        if deleted_items:
            flash(request, 'Horario actualizado y materias eliminadas correctamente', 'success')
        else:
            flash(request, 'Horario actualizado correctamente', 'success')
        return RedirectResponse(url=f"/schedules/{schedule_id}", status_code=303)
    else:
        flash(request, 'Error al actualizar horario', 'error')
        return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/schedules/{schedule_id}", response_class=HTMLResponse)
async def view_schedule(request: Request, schedule_id: str):
    """Ver detalles de un horario"""
    if not request.session.get('access_token'):
        return RedirectResponse(url="/login", status_code=303)
    
    access_token = request.session['access_token']
    user_id = request.session['user']['id']
    
    schedules = supabase_get_schedules(access_token, user_id)
    schedule = next((s for s in schedules if str(s.get('id')) == str(schedule_id)), None)
    
    if not schedule:
        flash(request, 'Horario no encontrado', 'error')
        return RedirectResponse(url="/dashboard", status_code=303)
    
    schedule_items = supabase_get_schedule_items(access_token, schedule_id)
    
    metadata = schedule.get('metadata', {}) or {}
    materias = metadata.get('materias', [])
    
    profile = supabase_get_profile(access_token, user_id)
    
    return CustomTemplateResponse(
        "schedule_detail.html",
        {
            "request": request,
            "schedule": schedule,
            "schedule_items": schedule_items,
            "materias": materias,
            "user": request.session.get('user'),
            "profile": profile,
            "centros": CENTROS
        }
    )

@app.get("/schedules/{schedule_id}/download")
async def download_schedule_pdf(request: Request, schedule_id: str):
    """Descargar horario como PDF"""
    if not request.session.get('access_token'):
        return RedirectResponse(url="/login", status_code=303)
    
    access_token = request.session['access_token']
    user_id = request.session['user']['id']
    
    schedules = supabase_get_schedules(access_token, user_id)
    schedule = next((s for s in schedules if str(s.get('id')) == str(schedule_id)), None)
    
    if not schedule:
        flash(request, 'Horario no encontrado', 'error')
        return RedirectResponse(url="/dashboard", status_code=303)
    
    schedule_items = supabase_get_schedule_items(access_token, schedule_id)
    
    buffer = BytesIO()
    
    from reportlab.lib.pagesizes import landscape, letter
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=reportlab_colors.HexColor('#667eea'),
        spaceAfter=20,
        alignment=1
    )
    
    title = Paragraph(f"Horario: {schedule.get('name', 'Sin nombre')}", title_style)
    story.append(title)
    story.append(Spacer(1, 0.3*inch))
    
    schedule_data = prepare_schedule_data(schedule, schedule_items)
    
    if schedule_data:
        calendar_table = create_schedule_table(schedule_data)
        story.append(calendar_table)
        story.append(PageBreak())
        
        subtitle = Paragraph("Detalle de Materias", styles['Heading2'])
        story.append(subtitle)
        story.append(Spacer(1, 0.2*inch))
        
        detail_table = create_courses_detail_table(schedule_data)
        story.append(detail_table)
    else:
        no_data = Paragraph("No hay materias en este horario", styles['Normal'])
        story.append(no_data)
    
    doc.build(story)
    buffer.seek(0)
    
    filename = f"horario_{schedule.get('name', 'sin_nombre').replace(' ', '_')}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ===== API ROUTES =====

@app.post("/api/buscar_materias")
@limiter.limit("5/minute")
async def buscar_materias(request: Request, data: BuscarMateriasRequest):
    """API para buscar materias"""
    try:
        payload = {
            "ciclop": data.ciclo,
            "cup": data.centro,
            "majrp": data.carrera,
            "crsep": "",
            "materiap": "",
            "horaip": "",
            "horafp": "",
            "edifp": "",
            "aulap": "",
            "ordenp": "0",
            "mostrarp": "100",  # OPTIMIZACIÓN: Reducir de 500 a 100 para reducir parsing HTML
            "dispp": "1",
        }

        with requests.Session() as s:
            s.headers.update(HEADERS)
            s.cookies.update(COOKIES)
            materias = fetch_all_pages(s, POST_URL, payload)

        # Get professor ratings (con caché de 1 hora)
        ratings_averages = get_cached_professor_ratings()
        
        # Add ratings to each materia
        for materia in materias:
            prof_name = materia.get('Profesor', '').strip()
            if prof_name and prof_name != '.' and prof_name != 'POR ASIGNAR':
                rating_data = ratings_averages.get(prof_name, {'average': 0, 'count': 0})
                materia['ProfesorRating'] = rating_data['average']
                materia['ProfesorRatingCount'] = rating_data['count']
            else:
                materia['ProfesorRating'] = 0
                materia['ProfesorRatingCount'] = 0

        return {
            'success': True,
            'materias': materias,
            'total': len(materias)
        }

    except Exception as e:
        return JSONResponse(
            {'success': False, 'error': str(e)},
            status_code=500
        )

@app.post("/api/buscar_profesores")
async def buscar_profesores(data: BuscarProfesoresRequest):
    """API para buscar profesores únicos"""
    try:
        payload = {
            "ciclop": data.ciclo,
            "cup": data.centro,
            "majrp": data.carrera,
            "crsep": "",
            "materiap": "",
            "horaip": "",
            "horafp": "",
            "edifp": "",
            "aulap": "",
            "ordenp": "0",
            "mostrarp": "100",  # OPTIMIZACIÓN: Reducir de 500 a 100 para reducir parsing HTML
            "dispp": "1",
        }

        with requests.Session() as s:
            s.headers.update(HEADERS)
            s.cookies.update(COOKIES)
            materias = fetch_all_pages(s, POST_URL, payload)

        profesores_dict = {}
        for m in materias:
            prof = m.get('Profesor', '').strip()
            materia_nombre = m.get('Materia', '').strip()
            if prof and prof != '.' and prof != 'POR ASIGNAR':
                if prof not in profesores_dict:
                    profesores_dict[prof] = set()
                if materia_nombre:
                    profesores_dict[prof].add(materia_nombre)
        
        ratings_averages = get_cached_professor_ratings()

        profesores_lista = []
        for name in sorted(profesores_dict.keys()):
            rating_data = ratings_averages.get(name, {'average': 0, 'count': 0})
            profesores_lista.append({
                'nombre': name,
                'materias': sorted(list(profesores_dict[name])),
                'rating_average': rating_data['average'],
                'rating_count': rating_data['count']
            })

        return {
            'success': True,
            'profesores': profesores_lista,
            'total': len(profesores_lista)
        }

    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@app.post("/api/rate_professor")
@limiter.limit("10/minute")
async def rate_professor(
    request: Request,  
    data: RateProfessorRequest,
    user: dict = Depends(get_current_user)
):
    """API para calificar a un profesor"""
    try:
        prof_name = data.professor_name
        rating = data.rating
        comment = data.comment or ''
        
        if not prof_name:
            return JSONResponse({'success': False, 'error': 'Datos incompletos'}, status_code=400)
        
        # User is already validated by Depends(get_current_user)
        access_token = request.session.get('access_token')
        user_id = user.get('id')

        # Convert rating dict to int (assuming it's a single rating value)
        rating_value = 0
        if isinstance(rating, dict):
            rating_value = rating.get('overall', 0)
        else:
            rating_value = int(rating)

        res, error_msg = supabase_add_professor_rating(
            access_token,
            user_id,
            prof_name,
            rating_value,
            comment
        )
        
        if res:
            return {'success': True, 'data': res}
        else:
            error_str = str(error_msg)
            if "JWT expired" in error_str:
                return JSONResponse(
                    {'success': False, 'error': 'Tu sesión ha expirado. Por favor, inicia sesión de nuevo.', 'auth_error': True},
                    status_code=401
                )
            
            if "relation" in error_str and "does not exist" in error_str:
                error_msg = "La tabla 'professor_ratings' no existe en Supabase. Por favor ejecuta el SQL proporcionado."
            
            return JSONResponse({'success': False, 'error': error_msg}, status_code=500)
            
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@app.get("/api/professor_ratings/{name}")
async def get_professor_ratings_route(name: str):
    """API para obtener calificaciones de un profesor"""
    try:
        ratings, error = supabase_get_professor_ratings(name)
        if ratings is not None:
            return {'success': True, 'ratings': ratings}
        else:
            return JSONResponse(
                {'success': False, 'error': error or 'Error al obtener calificaciones'},
                status_code=500
            )
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)

@app.get("/api/get_centros")
async def get_centros():
    """API para obtener lista de centros"""
    return CENTROS

@app.get("/favicon.ico")
async def favicon():
    """Servir favicon"""
    return Response(status_code=204)

# ===== STARTUP =====

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="127.0.0.1",  # Changed from 0.0.0.0 for Windows
        port=5000,
        reload=True
    )
