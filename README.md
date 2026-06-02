# Planificador de Horario Académico — SIIAU UDG

> Aplicación web para planificar horarios académicos, consultar materias disponibles y evaluar profesores de la Universidad de Guadalajara.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Supabase-Auth%20%2B%20DB-3ECF8E.svg" alt="Supabase">
  <img src="https://img.shields.io/badge/UDG-SIIAU-red.svg" alt="UDG">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

---

## Características

### Planificador de Horarios
- Búsqueda de materias por ciclo, centro universitario y carrera — datos en tiempo real del SIIAU
- Secciones expandibles por materia: NRC, profesor con calificación, horario y salón
- Calendario semanal interactivo (7am–9pm)
- Detección automática de conflictos de horario
- Exportación a PDF con calendario visual
- Hasta 3 horarios guardados por cuenta

### Cuentas de Usuario
- Registro con email o Google OAuth
- Dashboard para gestionar horarios guardados
- Preferencia de centro universitario (guardada localmente)
- Recuperación de contraseña por email

### Evaluación de Profesores
- Búsqueda por centro, carrera y ciclo
- Grid de tarjetas con promedio de estrellas y conteo de opiniones
- Calificación anónima con comentario opcional
- Las calificaciones aparecen junto al nombre del profesor en el planificador

---

## Inicio Rápido

```bash
git clone https://github.com/moisesibanez17/Planificador-de-Horario.git
cd Planificador-de-Horario

python3 -m venv venv
source venv/bin/activate      # Linux/macOS
# venv\Scripts\activate       # Windows

pip install -r requirements.txt
cp .env.example .env          # editar con tus credenciales
python app.py
```

Abre **http://localhost:5000**

---

## Variables de Entorno

Crea `.env` en la raíz:

```env
SUPABASE_URL=https://<proyecto>.supabase.co
SUPABASE_ANON_KEY=tu_anon_key
SUPABASE_SERVICE_KEY=tu_service_role_key
FLASK_SECRET=clave_secreta_larga_y_aleatoria
```

> `SUPABASE_SERVICE_KEY` solo se usa en el servidor para crear perfiles al registrarse. Nunca la expongas en el frontend.

---

## Google OAuth (opcional)

1. Crea credenciales OAuth 2.0 en [Google Cloud Console](https://console.cloud.google.com) → tipo **Aplicación web**
2. Agrega como URI de redireccionamiento autorizado:
   ```
   https://<proyecto>.supabase.co/auth/v1/callback
   ```
3. En **Supabase Dashboard → Authentication → Providers → Google**, pega el Client ID y Client Secret
4. Para desarrollo local agrega también `http://localhost:5000` en orígenes autorizados de JavaScript

---

## Base de Datos (Supabase)

```sql
-- Perfiles de usuario
CREATE TABLE profiles (
  id UUID REFERENCES auth.users(id) PRIMARY KEY,
  full_name TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Horarios
CREATE TABLE schedules (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Items de horario
CREATE TABLE schedule_items (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  schedule_id UUID REFERENCES schedules(id) ON DELETE CASCADE,
  nrc TEXT, materia TEXT, clave TEXT, seccion TEXT,
  creditos TEXT, cupo TEXT, disponible TEXT,
  profesor TEXT, edificio TEXT, aula TEXT,
  dias TEXT, horas TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Calificaciones de profesores
CREATE TABLE professor_ratings (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  professor_name TEXT NOT NULL,
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  rating INTEGER CHECK (rating BETWEEN 1 AND 5),
  comment TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON schedules(user_id);
CREATE INDEX ON schedule_items(schedule_id);
CREATE INDEX ON professor_ratings(professor_name);
```

---

## Estructura del Proyecto

```
Planificador-de-Horario/
├── app.py                  # Aplicación FastAPI principal
├── supabase_client.py      # Funciones de Supabase (auth, DB)
├── requirements.txt
├── .env                    # Variables de entorno (no versionado)
│
├── templates/
│   ├── _navbar.html        # Navbar compartido (include)
│   ├── index.html
│   ├── planner.html        # Planificador de horarios
│   ├── professors.html     # Evaluación de profesores
│   ├── dashboard.html
│   ├── schedule_detail.html
│   ├── signin.html
│   ├── signup.html
│   ├── forgot_password.html
│   ├── reset_password.html
│   ├── confirmation.html
│   ├── feedback.html
│   └── pricing.html
│
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   └── assets/
│
└── docs/
    └── superpowers/        # Specs y planes de implementación
```

---

## Tech Stack

| Capa | Tecnología |
|---|---|
| Backend | FastAPI + Uvicorn |
| Auth + DB | Supabase (PostgreSQL) |
| Scraping | requests + BeautifulSoup4 |
| PDF | ReportLab |
| Frontend | HTML5 + CSS3 + Vanilla JS |
| Rate limiting | SlowAPI |

---

## Notas

- Las **cookies del SIIAU** en `app.py` expiran periódicamente. Si las búsquedas fallan, actualízalas desde las herramientas de desarrollador de tu navegador haciendo una búsqueda en el sistema SIIAU original.
- La app consulta directamente el SIIAU — úsala con moderación.
- Para producción configura `https_only=True` en el SessionMiddleware y asegura HTTPS.

---

## Ciclos disponibles

| Código | Ciclo |
|---|---|
| 202620 | 2026-B |
| 202610 | 2026-A |
| 202520 | 2025-B |
| 202510 | 2025-A |

---

## Contribuir

1. Fork del repositorio
2. `git checkout -b feature/mi-feature`
3. Commit + Push
4. Abre un Pull Request

Reporta bugs en [Issues](https://github.com/moisesibanez17/Planificador-de-Horario/issues) o usa el formulario de feedback dentro de la app.

---

## Licencia

MIT — ver [LICENSE](LICENSE)

---

**Autor:** [Moises Ibañez](https://github.com/moisesibanez17)
