import asyncio
from app.config import settings
from app.domain.user import UserRole
from app.domain.auth_service import AuthDomainService
from app.infrastructure.user_repository import UserRepository
import redis.asyncio as aioredis
from app.api.routes import _hasher, _jwt_handler 

# IMPORTA AQUÍ TU FÁBRICA REAL DESDE TU ARCHIVO DATABASE
from app.infrastructure.database import AsyncSessionFactory  

async def main():
    # 1. Inicializar conexión a Redis
    redis_client = aioredis.from_url(
        f"redis://{settings.redis_host}:{settings.redis_port}",
        password=settings.redis_password or None,
        encoding="utf-8",
        decode_responses=True,
    )
    
    # 2. Abrir la sesión asíncrona usando tu AsyncSessionFactory real
    async with AsyncSessionFactory() as session:
        # 3. Instanciar el repositorio y el servicio de dominio
        repo = UserRepository(session=session, redis_client=redis_client)
        auth_svc = AuthDomainService(
            user_repository=repo,
            password_hasher=_hasher,
            jwt_handler=_jwt_handler,
        )
        
        # 4. Datos del administrador a crear
        email = "admin@fleetops.com"
        password_plana = "AdminSecure2026!"
        
        print(f"Intentando registrar al administrador: {email}...")
        
        try:
            # Usamos el parámetro explícito 'role' para forzar ADMINISTRADOR
            user = await auth_svc.register(
                email=email,
                plain_password=password_plana,
                role=UserRole.ADMINISTRADOR
            )
            # Guardamos los cambios de forma explícita
            await session.commit()
            print(f"¡Éxito! Administrador creado con ID: {user.id} y Rol: {user.role.value}")
            
        except Exception as e:
            await session.rollback()
            print(f"Error al crear el administrador: {e}")
            
    # Cerrar cliente de Redis
    await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())