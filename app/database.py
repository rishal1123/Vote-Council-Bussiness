from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={
        "check_same_thread": False,  # SQLite specific
        "timeout": 30,  # Wait up to 30s for locked database
    },
    pool_size=20,  # Support 20 concurrent connections
    max_overflow=10,  # Allow 10 extra connections under load
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=300,  # Recycle connections every 5 minutes
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Optimize SQLite for concurrent access."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrent reads
    cursor.execute("PRAGMA busy_timeout=30000")  # 30s busy timeout
    cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe with WAL
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    from app.models import user, voter, focal, candidate, box
    Base.metadata.create_all(bind=engine)
