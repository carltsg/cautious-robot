from sqlalchemy import create_engine, Column, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class RLSMapping(Base):
    """RLS role mappings for users"""
    __tablename__ = 'rls_mappings'

    id = Column(String(50), primary_key=True)  # userEmail_datasetId
    user_email = Column(String(255), nullable=False, index=True)
    dataset_id = Column(String(255), nullable=False)
    roles = Column(JSON, nullable=False)  # Array of role names
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255), nullable=False)

class ReportAccess(Base):
    """Report access mappings for users"""
    __tablename__ = 'report_access'

    user_email = Column(String(255), primary_key=True)
    report_ids = Column(JSON, nullable=False)  # Array of report IDs
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255), nullable=False)

# Database connection setup
def get_database_url():
    """Get database connection string from environment"""
    # Check for Azure SQL connection string first
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url

    # Fallback to component-based connection for local dev
    server = os.getenv('DB_SERVER', 'localhost')
    database = os.getenv('DB_NAME', 'powerbi_embedded')
    username = os.getenv('DB_USERNAME')
    password = os.getenv('DB_PASSWORD')
    driver = '{ODBC Driver 18 for SQL Server}'

    if username and password:
        return f'mssql+pyodbc://{username}:{password}@{server}/{database}?driver={driver}'

    return None

def init_db():
    """Initialize database connection and create tables"""
    db_url = get_database_url()
    if not db_url:
        return None, None

    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session

# Global session maker (initialized in app.py)
db_engine, DBSession = None, None
