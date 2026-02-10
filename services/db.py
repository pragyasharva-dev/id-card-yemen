"""
PostgreSQL Database Configuration using SQLAlchemy and asyncpg.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from utils.config import DATABASE_URL

# Create Async Engine
# echo=True will log all SQL statements, good for debugging (set to False in production)
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    # Pool settings can be adjusted based on load
    pool_size=20,
    max_overflow=10
)

# Create Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Base class for SQLAlchemy models to inherit from
class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for obtaining an async database session.
    
    Usage in FastAPI:
        @app.get("/items/")
        async def read_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """
    Initialize database tables. 
    Useful for creating tables in development if Alembic is not used.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
