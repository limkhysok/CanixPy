from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

# Import every domain's models module so its table registers on SQLModel.metadata.
from app.assets import models as _assets_models  # noqa: F401
from app.designs import models as _designs_models  # noqa: F401
from app.pages import models as _pages_models  # noqa: F401
from app.projects import models as _projects_models  # noqa: F401
from app.users import models as _users_models  # noqa: F401

DATABASE_URL = "sqlite:///./canixpy.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
