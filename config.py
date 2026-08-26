import os

database_url: str = os.getenv(
    DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@smartpromarco-postgres:5432/smartpromarco_db"
)