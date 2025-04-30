from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path
import os

current_file = Path(__file__).resolve()

PROJECT_DIR = current_file.parent.parent.parent

storage_dir = PROJECT_DIR / "storage"


def find_project_root():
    """Find project root by looking for specific directory structure."""
    check_dir = current_file.parent
    for _ in range(5):
        if not check_dir.parent or check_dir == check_dir.parent:
            break
        check_dir = check_dir.parent
        if (check_dir / "alembic").exists() and (check_dir / "storage").exists():
            return check_dir
    return None

project_root = find_project_root()

if project_root:
    BASE_DIR = project_root
else:
    cwd = Path(os.getcwd())
    repos_path = None
    
    for part in cwd.parts:
        if part == "repos":
            idx = cwd.parts.index(part)
            repos_path = Path(*cwd.parts[:idx+1])
            break
    
    if repos_path:
        project_candidates = [d for d in repos_path.iterdir() if d.is_dir()]

        for proj in project_candidates:
            if (proj / "alembic" / "core").exists() and (proj / "storage").exists():
                BASE_DIR = proj
                print(f"Found project at: {BASE_DIR}")
                break
        else:
            BASE_DIR = current_file.parent.parent.parent
    else:
        BASE_DIR = current_file.parent.parent.parent

DB_DIR = BASE_DIR / "storage" / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_DIR}/db.sqlite"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()