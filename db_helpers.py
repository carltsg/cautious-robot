"""Database abstraction layer - supports both JSON and SQL"""
import json
import os
from models import DBSession, RLSMapping, ReportAccess

# Feature flag: Use SQL if available, otherwise fallback to JSON
USE_SQL = DBSession is not None

# ==================== RLS Configuration ====================

def load_rls_config():
    """Load RLS configuration from SQL or JSON"""
    if USE_SQL:
        return load_rls_config_sql()
    return load_rls_config_json()

def load_rls_config_sql():
    """Load from SQL database"""
    session = DBSession()
    try:
        mappings = session.query(RLSMapping).all()
        return [{
            'userEmail': m.user_email,
            'datasetId': m.dataset_id,
            'roles': m.roles,
            'createdAt': m.created_at.isoformat() if m.created_at else None,
            'createdBy': m.created_by
        } for m in mappings]
    finally:
        session.close()

def load_rls_config_json():
    """Load from JSON file (fallback)"""
    if not os.path.exists('rls-config.json'):
        return []
    with open('rls-config.json', 'r') as f:
        return json.load(f)

def save_rls_config(config):
    """Save RLS configuration to SQL or JSON"""
    if USE_SQL:
        save_rls_config_sql(config)
    else:
        save_rls_config_json(config)

def save_rls_config_sql(config):
    """Save to SQL database"""
    session = DBSession()
    try:
        for mapping in config:
            mapping_id = f"{mapping['userEmail']}_{mapping['datasetId']}"
            existing = session.query(RLSMapping).filter_by(id=mapping_id).first()

            if existing:
                existing.roles = mapping['roles']
                existing.created_by = mapping.get('createdBy', '')
            else:
                new_mapping = RLSMapping(
                    id=mapping_id,
                    user_email=mapping['userEmail'],
                    dataset_id=mapping['datasetId'],
                    roles=mapping['roles'],
                    created_by=mapping.get('createdBy', '')
                )
                session.add(new_mapping)

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def save_rls_config_json(config):
    """Save to JSON file (fallback)"""
    with open('rls-config.json', 'w') as f:
        json.dump(config, f, indent=2)

# ==================== Report Access Configuration ====================

def load_reports_access_config():
    """Load report access configuration from SQL or JSON"""
    if USE_SQL:
        return load_reports_access_config_sql()
    return load_reports_access_config_json()

def load_reports_access_config_sql():
    """Load from SQL database"""
    session = DBSession()
    try:
        mappings = session.query(ReportAccess).all()
        return [{
            'userEmail': m.user_email,
            'reportIds': m.report_ids,
            'createdAt': m.created_at.isoformat() if m.created_at else None,
            'createdBy': m.created_by
        } for m in mappings]
    finally:
        session.close()

def load_reports_access_config_json():
    """Load from JSON file (fallback)"""
    if not os.path.exists('reports-access.json'):
        return []
    with open('reports-access.json', 'r') as f:
        return json.load(f)

def save_reports_access_config(config):
    """Save report access configuration to SQL or JSON"""
    if USE_SQL:
        save_reports_access_config_sql(config)
    else:
        save_reports_access_config_json(config)

def save_reports_access_config_sql(config):
    """Save to SQL database"""
    session = DBSession()
    try:
        # Clear existing mappings for updated users
        for mapping in config:
            existing = session.query(ReportAccess).filter_by(
                user_email=mapping['userEmail']
            ).first()

            if existing:
                existing.report_ids = mapping['reportIds']
                existing.created_by = mapping.get('createdBy', '')
            else:
                new_mapping = ReportAccess(
                    user_email=mapping['userEmail'],
                    report_ids=mapping['reportIds'],
                    created_by=mapping.get('createdBy', '')
                )
                session.add(new_mapping)

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def save_reports_access_config_json(config):
    """Save to JSON file (fallback)"""
    with open('reports-access.json', 'w') as f:
        json.dump(config, f, indent=2)
