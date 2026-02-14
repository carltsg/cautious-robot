"""Database abstraction layer - supports both JSON and SQL"""
import json
import os
import logging
import models
from models import RLSMapping, ReportAccess, UserActivity, AdminUser

# Get logger
logger = logging.getLogger(__name__)

# ==================== RLS Configuration ====================

def load_rls_config():
    """Load RLS configuration from SQL or JSON"""
    if models.DBSession is not None:
        return load_rls_config_sql()
    return load_rls_config_json()

def load_rls_config_sql():
    """Load from SQL database with error handling"""
    session = models.DBSession()
    try:
        mappings = session.query(RLSMapping).all()
        return [{
            'userEmail': m.user_email,
            'datasetId': m.dataset_id,
            'roles': m.roles,
            'createdAt': m.created_at.isoformat() if m.created_at else None,
            'createdBy': m.created_by
        } for m in mappings]
    except Exception as e:
        logger.error(f"Database error loading RLS config, falling back to JSON: {e}")
        return load_rls_config_json()
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
    if models.DBSession is not None:
        save_rls_config_sql(config)
    else:
        save_rls_config_json(config)

def save_rls_config_sql(config):
    """Save to SQL database with error handling"""
    session = models.DBSession()
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
        logger.error(f"Database error saving RLS config, falling back to JSON: {e}")
        save_rls_config_json(config)
    finally:
        session.close()

def save_rls_config_json(config):
    """Save to JSON file (fallback)"""
    with open('rls-config.json', 'w') as f:
        json.dump(config, f, indent=2)

# ==================== Report Access Configuration ====================

def load_reports_access_config():
    """Load report access configuration from SQL or JSON"""
    if models.DBSession is not None:
        return load_reports_access_config_sql()
    return load_reports_access_config_json()

def load_reports_access_config_sql():
    """Load from SQL database with error handling"""
    session = models.DBSession()
    try:
        mappings = session.query(ReportAccess).all()
        return [{
            'userEmail': m.user_email,
            'reportIds': m.report_ids,
            'createdAt': m.created_at.isoformat() if m.created_at else None,
            'createdBy': m.created_by
        } for m in mappings]
    except Exception as e:
        logger.error(f"Database error loading report access, falling back to JSON: {e}")
        return load_reports_access_config_json()
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
    if models.DBSession is not None:
        save_reports_access_config_sql(config)
    else:
        save_reports_access_config_json(config)

def save_reports_access_config_sql(config):
    """Save to SQL database with error handling"""
    session = models.DBSession()
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
        logger.error(f"Database error saving report access, falling back to JSON: {e}")
        save_reports_access_config_json(config)
    finally:
        session.close()

def save_reports_access_config_json(config):
    """Save to JSON file (fallback)"""
    with open('reports-access.json', 'w') as f:
        json.dump(config, f, indent=2)

# ==================== User Activity Logging ====================

def log_user_activity(activity_type, user_email, user_name=None, report_id=None, report_name=None, request=None):
    """Log user activity to database

    Args:
        activity_type: 'login' or 'view_report'
        user_email: User's email
        user_name: User's display name (optional)
        report_id: Report ID (for view_report)
        report_name: Report name (for view_report)
        request: Flask request object (for IP/user agent)
    """
    if models.DBSession is None:
        return  # Skip if no database

    session = models.DBSession()
    try:
        import uuid
        activity = UserActivity(
            id=str(uuid.uuid4()),
            user_email=user_email,
            user_name=user_name,
            activity_type=activity_type,
            report_id=report_id,
            report_name=report_name,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent', '')[:500] if request else None
        )
        session.add(activity)
        session.commit()
    except Exception as e:
        logger.error(f"Failed to log user activity: {e}")
        session.rollback()
    finally:
        session.close()

def get_recent_users(limit=50):
    """Get list of recent users for admin dropdown"""
    if models.DBSession is None:
        return []

    session = models.DBSession()
    try:
        # Get distinct users ordered by most recent activity
        from sqlalchemy import func, desc
        users = session.query(
            UserActivity.user_email,
            UserActivity.user_name,
            func.max(UserActivity.timestamp).label('last_active')
        ).group_by(
            UserActivity.user_email,
            UserActivity.user_name
        ).order_by(
            desc('last_active')
        ).limit(limit).all()

        return [{
            'email': u.user_email,
            'name': u.user_name or u.user_email.split('@')[0],
            'last_active': u.last_active.isoformat() if u.last_active else None
        } for u in users]
    except Exception as e:
        logger.error(f"Failed to get recent users: {e}")
        return []
    finally:
        session.close()

def get_user_activity_stats(user_email=None, days=30):
    """Get activity statistics for user or all users"""
    if models.DBSession is None:
        return []

    session = models.DBSession()
    try:
        from sqlalchemy import func
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)
        query = session.query(
            UserActivity.report_id,
            UserActivity.report_name,
            func.count(UserActivity.id).label('view_count')
        ).filter(
            UserActivity.activity_type == 'view_report',
            UserActivity.timestamp >= cutoff
        )

        if user_email:
            query = query.filter(UserActivity.user_email == user_email)

        report_stats = query.group_by(
            UserActivity.report_id,
            UserActivity.report_name
        ).order_by(
            func.count(UserActivity.id).desc()
        ).all()

        return [{
            'report_id': r.report_id,
            'report_name': r.report_name,
            'view_count': r.view_count
        } for r in report_stats]
    except Exception as e:
        logger.error(f"Failed to get activity stats: {e}")
        return []
    finally:
        session.close()

def get_total_logins(days=30):
    """Get total login count for the last N days"""
    if models.DBSession is None:
        return 0

    session = models.DBSession()
    try:
        from sqlalchemy import func
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)
        count = session.query(func.count(UserActivity.id)).filter(
            UserActivity.activity_type == 'login',
            UserActivity.timestamp >= cutoff
        ).scalar()

        return count or 0
    except Exception as e:
        logger.error(f"Failed to get total logins: {e}")
        return 0
    finally:
        session.close()

# ==================== Admin User Management ====================

def is_user_admin(user_email):
    """Check if user is an admin (database + fallback to env var)"""
    # Check database first
    if models.DBSession is not None:
        session = models.DBSession()
        try:
            admin = session.query(AdminUser).filter_by(email=user_email.lower()).first()
            if admin:
                return True
        except Exception as e:
            logger.error(f"Failed to check admin status: {e}")
        finally:
            session.close()

    # Fallback to environment variable (for bootstrap/emergency access)
    admin_emails_env = os.getenv('ADMIN_EMAILS', '')
    admin_list = [email.strip().lower() for email in admin_emails_env.split(',') if email.strip()]
    return user_email.lower() in admin_list

def get_all_admins():
    """Get list of all admin users"""
    if models.DBSession is None:
        return []

    session = models.DBSession()
    try:
        admins = session.query(AdminUser).order_by(AdminUser.email).all()
        return [{
            'email': a.email,
            'name': a.name,
            'created_at': a.created_at.isoformat() if a.created_at else None,
            'created_by': a.created_by,
            'is_super_admin': a.is_super_admin
        } for a in admins]
    except Exception as e:
        logger.error(f"Failed to get admin users: {e}")
        return []
    finally:
        session.close()

def add_admin_user(email, name=None, created_by='system', is_super_admin=False):
    """Add a new admin user"""
    if models.DBSession is None:
        return False

    session = models.DBSession()
    try:
        existing = session.query(AdminUser).filter_by(email=email.lower()).first()
        if existing:
            return False  # Already exists

        new_admin = AdminUser(
            email=email.lower(),
            name=name,
            created_by=created_by,
            is_super_admin=is_super_admin
        )
        session.add(new_admin)
        session.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to add admin user: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def remove_admin_user(email):
    """Remove an admin user"""
    if models.DBSession is None:
        return False

    session = models.DBSession()
    try:
        admin = session.query(AdminUser).filter_by(email=email.lower()).first()
        if not admin:
            return False  # Doesn't exist

        session.delete(admin)
        session.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to remove admin user: {e}")
        session.rollback()
        return False
    finally:
        session.close()
