from sqlalchemy import create_engine, Column, String, DateTime, JSON, Boolean
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

class UserActivity(Base):
    """Track user logins and report views"""
    __tablename__ = 'user_activity'

    id = Column(String(50), primary_key=True)  # UUID
    user_email = Column(String(255), nullable=False, index=True)
    user_name = Column(String(255), nullable=True)
    activity_type = Column(String(50), nullable=False)  # 'login', 'view_report'
    report_id = Column(String(255), nullable=True)  # For view_report events
    report_name = Column(String(500), nullable=True)  # For view_report events
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)

class AdminUser(Base):
    """Admin user management"""
    __tablename__ = 'admin_users'

    email = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255), nullable=False)
    is_super_admin = Column(Boolean, default=False)

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
    """Initialize database connection and create tables with connection pooling"""
    db_url = get_database_url()
    if not db_url:
        return None, None

    # Configure connection pool for Azure SQL
    engine = create_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,        # Test connection before using (fixes stale connections)
        pool_recycle=1800,         # Recycle connections after 30min (before Azure timeout)
        pool_size=5,               # Keep 5 connections in pool (small, cost-effective)
        max_overflow=10            # Allow 10 overflow connections
    )

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session

# Global session maker (initialized in app.py)
db_engine, DBSession = None, None
