"""One-time migration script: JSON → SQL"""
import json
from models import init_db, DBSession, RLSMapping, ReportAccess
from datetime import datetime

def migrate_rls_config():
    """Migrate rls-config.json to SQL"""
    try:
        with open('rls-config.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("No rls-config.json found, skipping")
        return

    session = DBSession()
    try:
        for item in data:
            mapping_id = f"{item['userEmail']}_{item['datasetId']}"
            existing = session.query(RLSMapping).filter_by(id=mapping_id).first()

            if not existing:
                mapping = RLSMapping(
                    id=mapping_id,
                    user_email=item['userEmail'],
                    dataset_id=item['datasetId'],
                    roles=item['roles'],
                    created_by=item.get('createdBy', 'migration')
                )
                session.add(mapping)

        session.commit()
        print(f"✓ Migrated {len(data)} RLS mappings")
    except Exception as e:
        session.rollback()
        print(f"✗ Error migrating RLS: {e}")
    finally:
        session.close()

def migrate_report_access():
    """Migrate reports-access.json to SQL"""
    try:
        with open('reports-access.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("No reports-access.json found, skipping")
        return

    session = DBSession()
    try:
        for item in data:
            existing = session.query(ReportAccess).filter_by(
                user_email=item['userEmail']
            ).first()

            if not existing:
                mapping = ReportAccess(
                    user_email=item['userEmail'],
                    report_ids=item['reportIds'],
                    created_by=item.get('createdBy', 'migration')
                )
                session.add(mapping)

        session.commit()
        print(f"✓ Migrated {len(data)} report access mappings")
    except Exception as e:
        session.rollback()
        print(f"✗ Error migrating report access: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    print("Starting data migration...")
    db_engine, DBSession = init_db()

    if not DBSession:
        print("ERROR: Database connection not configured!")
        print("Please set DATABASE_URL or DB_* variables in .env file")
        exit(1)

    migrate_rls_config()
    migrate_report_access()
    print("Migration complete!")
