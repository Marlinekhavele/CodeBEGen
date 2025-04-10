""" The database module
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from config import settings

DB_HOST = settings.DB_HOST
DB_PORT = settings.DB_PORT
DB_USER = settings.DB_USER
DB_PASSWORD = settings.DB_PASSWORD
DB_NAME = settings.DB_NAME

# Create the PostgreSQL connection URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Initialize the database engine
engine = create_engine(DATABASE_URL)

# Create session classes
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionLocal)

# Create declarative base for models
Base = declarative_base()

def create_database():
    """Create all tables defined in models"""
    return Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency to get a database session"""
    db = db_session()
    try:
        yield db
    finally:
        db.close()