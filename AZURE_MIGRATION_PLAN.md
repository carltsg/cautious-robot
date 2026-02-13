# Azure App Service Migration & SQL Database Plan

## Overview
Migrate the Power BI Embedded Flask app to Azure App Service with Azure SQL Database, using a gradual approach to minimize risk. Deploy via GitHub Actions for automated CI/CD.

## User Requirements
- ✅ Azure subscription and resource group already available
- ✅ Gradual migration (SQL + JSON coexist, then cutover)
- ✅ GitHub Actions for automated deployment
- ✅ Production-ready hosting on Azure App Service

## Migration Strategy: 3-Phase Gradual Approach

**Phase 1: Add SQL Support (Dual Mode)**
- Add SQLAlchemy ORM and database models
- Create database abstraction layer
- Keep JSON files as fallback
- Test locally with Azure SQL

**Phase 2: Azure Infrastructure & Deployment**
- Create Azure resources (App Service, SQL Database, Key Vault)
- Set up GitHub Actions CI/CD
- Deploy with SQL enabled
- Migrate existing JSON data to SQL

**Phase 3: Cutover & Cleanup**
- Switch to SQL-only mode
- Remove JSON file dependencies
- Clean up old code

---

## PHASE 1: Add SQL Database Support (Local Development)

### 1.1 Update Dependencies

**File:** `requirements.txt`

Add these packages:
```
Flask==3.0.0
msal==1.26.0
requests==2.31.0
python-dotenv==1.0.0
SQLAlchemy==2.0.25
pyodbc==5.0.1
azure-identity==1.15.0
gunicorn==21.2.0
```

**What each does:**
- `SQLAlchemy`: ORM for database operations
- `pyodbc`: ODBC driver for Azure SQL
- `azure-identity`: For Azure Key Vault and managed identity auth
- `gunicorn`: Production WSGI server for Azure

---

### 1.2 Create Database Models

**File:** `models.py` (new file)

```python
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
```

---

### 1.3 Create Database Abstraction Layer

**File:** `db_helpers.py` (new file)

```python
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
```

---

### 1.4 Update app.py

**Changes to make:**

1. **Add imports** (top of file):
```python
from models import init_db, db_engine, DBSession
from db_helpers import (
    load_rls_config,
    save_rls_config,
    load_reports_access_config,
    save_reports_access_config
)
```

2. **Initialize database** (after app creation, around line 14):
```python
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize database connection
from models import init_db
db_engine, DBSession = init_db()
if DBSession:
    print("✓ Database connected (SQL mode)")
else:
    print("⚠ Database not configured - using JSON files")
```

3. **Remove old helper functions** (lines 40-77):
   - Delete: `load_rls_config()`, `save_rls_config()`
   - Delete: `load_reports_access_config()`, `save_reports_access_config()`
   - Keep: `get_user_roles()`, `get_user_reports()`, `is_admin()`

4. **Update REDIRECT_URI** (line 23):
```python
# Support both local and Azure environments
REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:5000/callback')
```

---

### 1.5 Add Environment Variables

**File:** `.env.example`

Add these new variables:
```
# Existing variables...
TENANT_ID=your-tenant-id-here
CLIENT_ID=your-client-id-here
CLIENT_SECRET=your-client-secret-here
WORKSPACE_ID=your-workspace-id-here
ADMIN_EMAILS=admin@yourdomain.com
SECRET_KEY=your-random-secret-key-here

# New for Azure deployment
REDIRECT_URI=http://localhost:5000/callback

# Database configuration (for Azure SQL)
DATABASE_URL=
# OR component-based for local dev:
DB_SERVER=localhost
DB_NAME=powerbi_embedded
DB_USERNAME=
DB_PASSWORD=
```

---

### 1.6 Local Testing with Azure SQL

**Test the gradual migration locally:**

1. Create a test Azure SQL database (or use SQL Server LocalDB)
2. Update `.env` with connection details
3. Run the app - it should connect to SQL
4. Test admin panel - save/delete mappings
5. Verify data persists in SQL tables
6. **Important:** JSON files should still work if SQL is unavailable

---

## PHASE 2: Azure Infrastructure Setup

### 2.1 Azure Resources Needed

Create these resources in your existing resource group:

#### A. Azure SQL Database
```bash
# Basic tier for POC (upgrade to Standard/Premium for production)
Name: powerbi-embedded-db
Pricing Tier: Basic (5 DTUs, ~$5/month) or S0 Standard (~$15/month)
Compute: Serverless (auto-pause to save costs)
```

**Important Settings:**
- Enable "Allow Azure services to access server": YES
- Firewall: Add your client IP for management
- Authentication: SQL authentication + Azure AD admin

#### B. Azure App Service
```bash
Name: powerbi-embedded-app (or your-app-name)
Runtime: Python 3.11
OS: Linux
Pricing Tier: B1 Basic (~$13/month) or P1V2 Premium (~$75/month for production)
```

**App Settings to configure:**
- `SCM_DO_BUILD_DURING_DEPLOYMENT`: true
- `WEBSITE_HTTPLOGGING_RETENTION_DAYS`: 7
- Python version: 3.11

#### C. Azure Key Vault (Recommended)
```bash
Name: powerbi-kv-<unique-suffix>
Pricing: Standard (~$0.03/month + per-operation costs)
```

**Secrets to store:**
- `CLIENT-SECRET`: Azure AD app secret
- `SECRET-KEY`: Flask session key
- `DATABASE-URL`: SQL connection string

---

### 2.2 Azure Portal Setup Steps

**Step 1: Create Azure SQL Database**

1. Go to Azure Portal → Create a resource → Azure SQL
2. Select "SQL Database" → Create
3. Fill in:
   - Resource group: [your existing RG]
   - Database name: `powerbi-embedded-db`
   - Server: Create new server
     - Server name: `powerbi-sql-server-<unique>`
     - Location: Same as App Service
     - Authentication: SQL + Azure AD
     - Admin login: `sqladmin`
     - Password: [strong password]
   - Compute + storage: Basic (5 DTUs) or Serverless
4. Networking:
   - Allow Azure services: YES
   - Add current client IP: YES
5. Review + Create

**Step 2: Get Connection String**

1. Go to SQL Database → Connection strings
2. Copy the ADO.NET connection string
3. Convert to SQLAlchemy format:
   ```
   mssql+pyodbc://sqladmin:PASSWORD@powerbi-sql-server.database.windows.net/powerbi-embedded-db?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
   ```

**Step 3: Create App Service**

1. Create a resource → Web App
2. Fill in:
   - Name: `powerbi-embedded-app`
   - Runtime: Python 3.11
   - OS: Linux
   - Region: Same as SQL
   - Pricing: B1 Basic (can scale up later)
3. Review + Create

**Step 4: Create Key Vault**

1. Create a resource → Key Vault
2. Fill in:
   - Name: `powerbi-kv-<random>`
   - Region: Same region
   - Pricing: Standard
3. Access policies:
   - Add yourself as admin
   - Later: Add App Service managed identity

**Step 5: Store Secrets in Key Vault**

1. Go to Key Vault → Secrets → Generate/Import
2. Add these secrets:
   - `CLIENT-SECRET`: [from Azure AD app]
   - `SECRET-KEY`: [generate: `python -c "import secrets; print(secrets.token_hex(32))"`]
   - `DATABASE-URL`: [SQL connection string from Step 2]

---

### 2.3 Configure App Service

**App Service → Configuration → Application settings:**

Add these:
```
TENANT_ID=[your tenant ID]
CLIENT_ID=[your Azure AD app ID]
CLIENT_SECRET=@Microsoft.KeyVault(SecretUri=https://powerbi-kv-xxx.vault.azure.net/secrets/CLIENT-SECRET/)
WORKSPACE_ID=[your Power BI workspace ID]
ADMIN_EMAILS=[comma-separated emails]
SECRET_KEY=@Microsoft.KeyVault(SecretUri=https://powerbi-kv-xxx.vault.azure.net/secrets/SECRET-KEY/)
DATABASE_URL=@Microsoft.KeyVault(SecretUri=https://powerbi-kv-xxx.vault.azure.net/secrets/DATABASE-URL/)
REDIRECT_URI=https://powerbi-embedded-app.azurewebsites.net/callback
SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

**Enable Managed Identity:**
1. App Service → Identity → System assigned → ON
2. Copy the Object (principal) ID
3. Go to Key Vault → Access policies → Add
4. Principal: [paste App Service object ID]
5. Secret permissions: Get, List

---

## PHASE 3: GitHub Actions CI/CD

### 3.1 Create Deployment Files

**File:** `.github/workflows/azure-deploy.yml` (new file)

```yaml
name: Deploy to Azure App Service

on:
  push:
    branches:
      - main
  workflow_dispatch:

env:
  AZURE_WEBAPP_NAME: powerbi-embedded-app
  PYTHON_VERSION: '3.11'

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ env.PYTHON_VERSION }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt

    - name: Zip artifact for deployment
      run: |
        zip -r release.zip . -x "*.git*" "*.env" "*.json" "__pycache__/*" "*.pyc"

    - name: Deploy to Azure Web App
      uses: azure/webapps-deploy@v2
      with:
        app-name: ${{ env.AZURE_WEBAPP_NAME }}
        publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
        package: release.zip
```

**File:** `startup.txt` (new file - tells Azure how to start the app)

```bash
gunicorn --bind=0.0.0.0 --timeout 600 app:app
```

---

### 3.2 Configure GitHub Secrets

1. Go to your GitHub repo → Settings → Secrets and variables → Actions
2. Add new repository secret:
   - Name: `AZURE_WEBAPP_PUBLISH_PROFILE`
   - Value: [get from Azure Portal]

**To get publish profile:**
1. Azure Portal → App Service → Overview
2. Click "Get publish profile" (download button)
3. Open the `.PublishSettings` XML file
4. Copy entire contents
5. Paste into GitHub secret

---

### 3.3 Update .gitignore

Make sure these are excluded:
```
.env
*.json
__pycache__/
*.pyc
*.pyo
*.db
*.sqlite
.vscode/
.idea/
venv/
```

---

### 3.4 First Deployment

**Steps:**

1. Commit all changes to git
2. Push to GitHub `main` branch
3. GitHub Actions will automatically:
   - Build the app
   - Install dependencies
   - Deploy to Azure App Service
4. Monitor deployment:
   - GitHub → Actions tab → Watch workflow
   - Azure Portal → App Service → Deployment Center → Logs

**After first deployment:**
1. Go to App Service URL: `https://powerbi-embedded-app.azurewebsites.net`
2. Test login flow (make sure REDIRECT_URI is updated in Azure AD app registration!)
3. Check logs: App Service → Log stream

---

## PHASE 4: Data Migration & Cutover

### 4.1 Migrate Existing JSON Data to SQL

**File:** `migrate_data.py` (new script)

```python
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
    init_db()
    migrate_rls_config()
    migrate_report_access()
    print("Migration complete!")
```

**Run locally before deployment:**
```bash
python migrate_data.py
```

---

### 4.2 Update Azure AD App Registration

**Critical: Update Redirect URI**

1. Azure Portal → Azure Active Directory → App registrations
2. Find your app (CLIENT_ID)
3. Authentication → Redirect URIs
4. Add: `https://powerbi-embedded-app.azurewebsites.net/callback`
5. Keep localhost for local testing: `http://localhost:5000/callback`
6. Save

---

### 4.3 Testing Checklist

- [ ] Local: App runs with SQL database
- [ ] Local: Can save/delete RLS mappings
- [ ] Local: Can save/delete report access
- [ ] Local: Data persists across restarts
- [ ] Azure: App deploys successfully
- [ ] Azure: Database connection works
- [ ] Azure: Key Vault secrets are accessible
- [ ] Azure: Login redirects correctly
- [ ] Azure: Can view reports
- [ ] Azure: Admin panel works
- [ ] Azure: Data migration successful

---

### 4.4 Optional: Remove JSON Fallback

Once confident SQL is working in production:

1. **Update `db_helpers.py`**: Remove `_json()` functions
2. **Update `models.py`**: Remove `USE_SQL` flag
3. **Remove files**: Delete `rls-config.json`, `reports-access.json`
4. **Deploy**: Push to GitHub

---

## Cost Estimate (Azure - UK South)

| Resource | Tier | Monthly Cost (approx) |
|----------|------|----------------------|
| App Service | B1 Basic | £10 |
| SQL Database | Basic (5 DTU) | £4 |
| Key Vault | Standard | £0.03 + usage |
| **Total** | | **~£15/month** |

**Scaling for production:**
- App Service P1V2: ~£60/month
- SQL S1 Standard: ~£12/month
- **Production Total: ~£75/month**

---

## Rollback Strategy

If issues occur in production:

1. **Quick rollback**: GitHub Actions → Re-run old deployment
2. **Database rollback**: Keep JSON files temporarily as backup
3. **App Service slots**: Use staging slot for testing before swap

---

## Security Checklist

- [ ] All secrets in Key Vault (not in code or env vars)
- [ ] Managed Identity enabled for App Service
- [ ] SQL firewall configured (no public access)
- [ ] HTTPS enforced on App Service
- [ ] Admin emails properly configured
- [ ] SECRET_KEY is strong and unique
- [ ] .gitignore excludes secrets and data files

---

## File Summary

**New Files:**
- `models.py` - SQLAlchemy database models
- `db_helpers.py` - Abstraction layer (SQL + JSON)
- `migrate_data.py` - One-time migration script
- `startup.txt` - Azure startup command
- `.github/workflows/azure-deploy.yml` - CI/CD pipeline

**Modified Files:**
- `app.py` - Import db_helpers, initialize database, update REDIRECT_URI
- `requirements.txt` - Add SQL and Azure dependencies
- `.env.example` - Add database and Azure variables
- `.gitignore` - Ensure JSON files excluded

**Azure Resources:**
- Azure SQL Database
- Azure App Service (Linux, Python 3.11)
- Azure Key Vault

---

## Next Steps After Plan Approval

1. Implement Phase 1 (SQL support) locally
2. Test with Azure SQL or local SQL Server
3. Create Azure resources
4. Configure GitHub Actions
5. Deploy to Azure
6. Migrate data
7. Test in production
8. Remove JSON fallback (optional)
