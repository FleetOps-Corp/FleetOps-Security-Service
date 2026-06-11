# FleetOps — Security Cell (API Gateway + Auth Service + Role Service)

Célula de seguridad del sistema FleetOps. Provee el único punto de acceso al sistema distribuido mediante un **API Gateway** con validación JWT, aplicación de RBAC, CORS y Rate Limiting, respaldado por un **Auth Service** (registro/login/JWT) y un **Role Service** (gestión y validación de roles).

**Curso:** Desarrollo de Software III (750027C) — Semestre 2026-1
**SAD Reference:** Software Architecture Document v1.0 — Security Team

---

## Arquitectura

```
Cliente (HTTPS)
     │
     ▼
┌─────────────────────────────────┐  ← Security Layer (SAD §6)
│         API Gateway :8000       │  JWT · CORS · Rate Limit · Routing
└──────────┬──────────────────────┘
           │ HTTP interno
     ┌─────┴──────┐
     ▼            ▼
┌─────────┐  ┌─────────────┐        ← Logic Layer (SAD §6)
│  Auth   │  │   Role      │
│ Service │  │  Service    │
│  :8001  │  │   :8002     │
└────┬────┘  └──────┬──────┘
     │               │
     └───────┬───────┘
             ▼
    ┌─────────────────┐              ← Infrastructure Layer (SAD §6)
    │   PostgreSQL    │  Redis
    │  users/roles/   │  (caché)
    │  user_roles     │
    └─────────────────┘
```

**Flujo de autenticación (SAD pág. 9):**
1. Cliente → `POST /auth/login` → API Gateway
2. Gateway reenvía a AuthService → valida credenciales en Redis/PostgreSQL
3. AuthService genera JWT (1 hora, sin renovación automática)
4. Token devuelto al cliente

**Flujo de validación y redirección (SAD pág. 10):**
1. Cliente → request con `Authorization: Bearer <token>` → API Gateway
2. Gateway valida JWT y extrae identidad
3. RoleService verifica rol del usuario (Redis → PostgreSQL)
4. Si autorizado: Gateway redirige al microservicio correspondiente

**Roles del sistema (SAD §1):**

| Rol | Acceso |
|-----|--------|
| `EMPLEADO` | Propias asignaciones (ruta + vehículo) |
| `EMPLEADO_MANTENIMIENTO` | Info de vehículos para mantenimiento |
| `EMPLEADO_INCIDENTES` | Info de vehículo y conductor para incidentes |
| `ADMINISTRADOR` | Vehículos, incidentes, mantenimiento, reportes |

---

## Prerrequisitos

- **Docker** >= 26.0
- **Docker Compose** >= 2.24 (plugin integrado)
- **Python** >= 3.12 (solo para tests locales sin Docker)
- **Git**

---

## Quick Start

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd fleetops-security

# 2. Copiar y configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores (mínimo: cambiar JWT_SECRET_KEY y POSTGRES_PASSWORD)

# 3. Levantar todos los servicios
docker compose up --build

# 4. Verificar que todo esté saludable
docker compose ps
```

**El Gateway estará disponible en:** `http://localhost:8000`

**Documentación Swagger (solo en desarrollo):**
- Gateway:      `http://localhost:8000/docs`
- Auth Service: `http://localhost:8001/docs` *(solo si expones el puerto)*
- Role Service: `http://localhost:8002/docs` *(solo si expones el puerto)*

---

## Endpoints disponibles

### Públicos (sin autenticación)
```
POST /auth/register    → Registrar nuevo usuario
POST /auth/login       → Login → obtiene JWT
GET  /health           → Liveness probe
```

### Protegidos (requieren JWT en header: `Authorization: Bearer <token>`)
```
GET|POST|PUT|DELETE /vehiculos/**       → EMPLEADO_MANTENIMIENTO, EMPLEADO_INCIDENTES, ADMINISTRADOR
GET|POST|PUT|DELETE /asignaciones/**    → EMPLEADO, ADMINISTRADOR
GET|POST|PUT|DELETE /incidentes/**      → EMPLEADO_INCIDENTES, ADMINISTRADOR
GET|POST|PUT|DELETE /mantenimiento/**   → EMPLEADO_MANTENIMIENTO, ADMINISTRADOR
GET|POST|PUT|DELETE /reportes/**        → ADMINISTRADOR
```

---

## Ejecutar tests localmente (sin Docker)

### API Gateway
```bash
cd api_gateway
python -m venv env
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Ejecutar tests con cobertura
pytest

# Ver reporte de cobertura HTML
open htmlcov/index.html            # macOS
xdg-open htmlcov/index.html        # Linux
```

### Auth Service
```bash
cd auth_service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
open htmlcov/index.html
```

### Role Service
```bash
cd role_service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
open htmlcov/index.html
```

---

## Generar y ver el reporte de cobertura

El reporte HTML se genera automáticamente al ejecutar `pytest` (configurado en `pytest.ini`).

```bash
# Dentro de cualquier servicio:
pytest --cov=app --cov-report=html:htmlcov --cov-report=term-missing

# Abrir reporte visual:
open htmlcov/index.html
```

La cobertura mínima configurada es **80%** en dominio + aplicación. La meta del equipo es **100% en las capas Domain y Application**.

---

## Estructura del proyecto

```
fleetops-security/
│
├── docker-compose.yml          # Orquestación: postgres, redis, auth_svc, role_svc, gateway
├── .env.example                # Plantilla de variables de entorno (copiar a .env)
├── .gitignore
├── README.md
│
├── api_gateway/                # Security Layer (SAD pág. 5/6)
│   ├── Dockerfile              # Multi-stage build, usuario no-root
│   ├── app/
│   │   ├── main.py             # Entry point: CORS, Rate Limit, routers
│   │   ├── config.py           # Pydantic Settings
│   │   ├── domain/
│   │   │   ├── route_registry.py  # Diccionario de rutas + roles permitidos (SAD §3)
│   │   │   └── rbac_policy.py     # Decisión RBAC (SAD §4/7)
│   │   ├── middleware/
│   │   │   ├── jwt_middleware.py  # Extracción y validación de JWT
│   │   │   └── rate_limit.py      # Rate Limiting con slowapi
│   │   ├── routes/
│   │   │   ├── auth_routes.py     # Proxy público a AuthService
│   │   │   └── proxy_routes.py    # Proxy protegido a microservicios
│   │   ├── services/
│   │   │   └── role_validation_client.py  # Cliente HTTP a RoleService
│   │   └── schemas/
│   │       └── gateway_schemas.py # DTOs del Gateway
│   └── tests/                  # Cobertura de capas Domain y Middleware
│
├── auth_service/               # Logic Layer — Autenticación (SAD pág. 5)
│   ├── Dockerfile
│   ├── entrypoint.sh           # Corre migraciones Alembic antes de uvicorn
│   ├── alembic/                # Migraciones: tabla users
│   ├── app/
│   │   ├── domain/
│   │   │   ├── user.py         # Entidad User + UserRole enum
│   │   │   ├── jwt_handler.py  # Creación/verificación de JWT
│   │   │   └── auth_service.py # Servicio de dominio: register/login
│   │   ├── api/
│   │   │   ├── routes.py       # POST /register, POST /login
│   │   │   └── schemas.py      # DTOs: RegisterRequest, LoginRequest, TokenResponse
│   │   └── infrastructure/
│   │       ├── database.py     # Engine async SQLAlchemy
│   │       ├── models.py       # ORM: UserModel
│   │       └── user_repository.py  # Repository + cache-aside Redis (pág. 9)
│   └── tests/                  # 100% cobertura de capas Domain e Infrastructure
│
└── role_service/               # Logic Layer — Roles (SAD pág. 5)
    ├── Dockerfile
    ├── entrypoint.sh
    ├── alembic/                # Migraciones: tablas roles, user_roles (seeded)
    ├── app/
    │   ├── domain/
    │   │   ├── role.py         # Entidades Role y UserRoleAssignment
    │   │   └── role_service.py # Servicio RBAC: asignar, validar, inhabilitar
    │   ├── api/
    │   │   ├── routes.py       # POST /roles/validate, POST /roles/assign, etc.
    │   │   └── schemas.py      # DTOs de roles
    │   └── infrastructure/
    │       ├── database.py
    │       ├── models.py       # ORM: RoleModel, UserRoleModel
    │       ├── redis_client.py # Cliente Redis async
    │       └── role_repository.py  # Repository + cache-aside Redis (pág. 10)
    └── tests/                  # 100% cobertura de capas Domain e Infrastructure
```

---

## Decisiones arquitectónicas clave (resumen del SAD)

| Decisión | Justificación |
|---|---|
| API Gateway como único punto de entrada | Oculta topología interna, centraliza CORS/Rate Limit/JWT (SAD §3) |
| RBAC con 4 roles fijos | Roles asignados por administrador, no por auto-servicio (SAD §1/3) |
| JWT con expiración 1 hora sin refresh | Reduce ventana de ataque; re-login requerido (SAD §7) |
| PostgreSQL compartido (auth + role service) | Misma instancia, esquema compartido; apropiado para el alcance (SAD §5) |
| Redis cache-aside para roles y sesiones | Reduce carga en PostgreSQL en el hot-path de validación (SAD pág. 9/10) |
| Clean Architecture lite dentro de cada servicio | Capas API → Domain → Infrastructure; testabilidad y separación de responsabilidades (SAD diagrama pág. 5) |
| Alembic para migraciones | Versionamiento de esquema; ejecutado al arranque del contenedor (SAD pág. 5) |
| Docker Compose para orquestación local | Portabilidad; target final es AWS EC2 (SAD §8) |

---

## Limitaciones conocidas y próximos pasos

1. **Sin refresh tokens:** El SAD especifica expiración de 1 hora sin renovación. Para producción se recomienda implementar un endpoint `POST /auth/refresh` con refresh tokens de larga duración almacenados en Redis.

2. **Sin blacklist de tokens:** Si un usuario es desactivado, su JWT existente permanece válido hasta expirar. Para producción: agregar lista negra de tokens en Redis.

3. **CORS abierto en desarrollo:** `allow_origins=["*"]` en modo desarrollo. En producción, restringir a dominios específicos via variable de entorno.

4. **Sin TLS interno:** Los servicios internos se comunican por HTTP. En producción sobre EC2, configurar TLS mutuo o usar un service mesh.

5. **Rate limiting solo por IP:** Para mayor granularidad, implementar límites por `user_id` (disponible en el JWT una vez autenticado).

6. **Invalidación de caché al desactivar usuario:** Si un admin desactiva un usuario, el caché Redis puede devolver datos obsoletos hasta que expire el TTL. Solución: llamar a `redis.delete()` explícitamente en el endpoint de desactivación.

7. **URLs de microservicios downstream son placeholders:** Reemplazar `VEHICLES_SERVICE_URL`, `ASSIGNMENTS_SERVICE_URL`, etc. en `.env` con las URLs reales cuando los otros equipos expongan sus servicios.
