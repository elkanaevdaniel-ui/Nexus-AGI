"""Database setup for Lead Gen service — isolated SQLite DB."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.lead_gen_db_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _connection_record: object) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables."""
    from src.models.lead import Lead, Campaign, OutreachMessage, CRMDeal  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency for DB sessions."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
