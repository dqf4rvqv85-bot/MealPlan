from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# import models so SQLModel.metadata is populated before create_all
from app import models  # noqa: F401

_db_file = settings.resolve(settings.db_path)
engine = create_engine(
    f"sqlite:///{_db_file}",
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
