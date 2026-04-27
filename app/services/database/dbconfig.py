from os import environ
from typing import Annotated, Any, Generator

# from dotenv import load_dotenv
# from fastapi import Depends
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine
from queries import create_order_totals_trigger

# load_dotenv("../../.env")
# check if the database file exists
# If not, it will be created when the first table is created
DATABASE_ENGINE = environ.get("DATABASE_ENGINE", "duckdb")
DATABASE_NAME = environ.get("DATABASE_NAME", "tremenda-test")

if DATABASE_ENGINE == "duckdb":
    DATABASE_URL = "duckdb:///./data/dummy.db"
elif DATABASE_ENGINE == "postgresql":
    POSTGRES_USER = environ.get("POSTGRES_USER", "admin")
    POSTGRES_PASSWORD = environ.get("POSTGRES_PASSWORD", "password")
    POSTGRES_HOST = environ.get("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = environ.get("POSTGRES_PORT", 5432)
    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{DATABASE_NAME}"
else:
    raise ValueError(f"Unsupported DATABASE_ENGINE: {DATABASE_ENGINE}")

print(f"Connecting to database at {DATABASE_URL}")

engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    if DATABASE_ENGINE == "postgresql":
        with engine.connect() as conn:
            conn.execute(create_order_totals_trigger)
            conn.commit()


def get_session() -> Generator[Session, Any, None]:
    with Session(engine) as session:
        yield session


# SessionType = Annotated[Session, Depends(get_session)]
