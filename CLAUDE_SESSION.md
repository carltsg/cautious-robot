# Power BI Embedded POC - Development Session Log

**Project:** Power BI Embedded Web Application with RLS
**Developer:** Carl Hunter (carl.hunter@TSGdemonstration.onmicrosoft.com)
**Date Started:** 2026-02-11
**Last Updated:** 2026-03-05
**Repository:** https://github.com/carltsg/cautious-robot
**Production URL:** https://tsgpbiembed-eqbbewh4bebxh9hk.uksouth-01.azurewebsites.net

---

## Project Overview

Built a simple Python Flask web application that embeds Power BI reports with row-level security (RLS) for sharing reports with external customers. Each customer logs in and automatically sees only their data filtered by email.

### Key Features
- Entra ID (Azure AD) authentication with B2B guest support
- Power BI report embedding using service principal
- **Automatic customer filtering** - Users without explicit mappings get "Customer" role
- Admin panel for special role assignments (managers, power users)
- Responsive Bootstrap UI
- JSON-based configuration storage

### Use Case
Customer wants to share Power BI reports with their external customers (20-100 users), where each customer sees only their own data based on their email address.

---

## Technology Stack

- **Backend:** Python 3.11 with Flask
- **Authentication:** MSAL (Microsoft Authentication Library)
- **Power BI:** REST API + powerbi-client JavaScript SDK
- **Frontend:** Bootstrap 5 + vanilla JavaScript
- **Database:** Azure SQL Database with SQLAlchemy ORM (with JSON fallback)
- **Hosting:** Azure Web App (Linux, Basic B1 tier)

### Dependencies (requirements.txt)
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

---

## Project Structure

```
pbiembedded/
├── app.py                          # Main Flask application (~550 lines)
├── models.py                       # SQLAlchemy database models
├── db_helpers.py                   # Database abstraction layer with JSON fallback
├── requirements.txt                # Python dependencies
├── .env                           # Configuration (NOT in git)
├── .env.example                   # Configuration template
├── rls-config.json                # User-to-role mappings (fallback, auto-created)
├── reports-access.json            # Report access mappings (fallback, auto-created)
├── templates/
│   ├── layout.html                # Base template with navigation
│   ├── index.html                 # Home page
│   ├── login.html                 # Login page
│   ├── reports.html               # Report listing (admin)
│   ├── my_reports.html            # User's assigned reports
│   ├── view_report.html           # Embedded report viewer
│   └── admin.html                 # Full admin panel with user activity stats
├── static/
│   ├── powerbi.js                 # Power BI embed logic
│   └── style.css                  # Custom CSS
├── .github/workflows/
│   └── main_tsgpbiembed.yml       # GitHub Actions CI/CD pipeline
├── README.md                      # Complete setup guide
├── EXTERNAL_CUSTOMERS_GUIDE.md    # Step-by-step customer setup
├── AZURE_OPTIMIZATION.md          # Azure performance optimization guide
├── TECHNICAL_DOCUMENTATION.md     # Technical architecture docs
├── RLS_FLOW_EXPLAINED.md          # RLS implementation details
└── CLAUDE_SESSION.md              # This file - session log
```

---

## What We Built

### Phase 1: Initial Planning
**Decision:** Chose Python Flask over ASP.NET Core for simplicity
- **ASP.NET approach:** 30+ files, ~2000 lines, 6-8 hours
- **Python Flask approach:** 8 files, ~500 lines, 2-3 hours ✅

### Phase 2: Core Implementation
1. **Project setup** - Created folder structure, requirements.txt, .gitignore
2. **Flask app (app.py)** - All routes, authentication, Power BI integration
3. **Templates** - HTML pages for viewing reports and admin configuration
4. **Static files** - JavaScript for Power BI embedding, CSS styling
5. **Documentation** - README, external customer guide

### Phase 3: Testing & Fixes
Encountered and resolved several issues during testing.

---

## Issues Encountered & Resolved

### Issue 1: "shouldn't have effective identity" Error
**Problem:** Power BI rejected embed token because dataset didn't have RLS roles defined yet.

**Solution:** Modified `view_report()` to check if dataset has RLS roles before including identities:
```python
# Check if dataset has RLS roles defined
roles_response = requests.get(
    f'https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{dataset_id}/roles',
    headers=headers
)

dataset_has_rls = len(roles_response.json().get('value', [])) > 0

# Only include identities if dataset has RLS roles
if dataset_has_rls:
    embed_payload['identities'] = [{...}]
```

**Commit:** `ef6c738` - Fix: Only apply RLS when dataset has roles defined

---

### Issue 2: "models is not defined" JavaScript Error
**Problem:** Power BI JavaScript library's `models` object wasn't loading correctly.

**Solution:** Removed dependency on `models` object, used direct config values:
```javascript
// Before (broken):
permissions: models.Permissions.Read,
background: models.BackgroundType.Transparent

// After (working):
tokenType: 1, // Embed token
// Removed background setting
```

Added comprehensive debugging and error handling.

**Commit:** `f15e603` - Add debugging and fix Power BI models undefined error

---

### Issue 3: "Unauthorized - Admin access required"
**Problem:** Admin email comparison was case-sensitive. User's email was `carl.hunter@TSGdemonstration.onmicrosoft.com` but .env had `carl.hunter@tsgdemonstration.onmicrosoft.com`.

**Solution:** Made email comparison case-insensitive:
```python
def admin_required(f):
    user_email = session['user']['email']
    admin_list = [email.strip().lower() for email in ADMIN_EMAILS]
    if user_email.lower() not in admin_list:
        return 'Unauthorized', 403
```

**Commit:** `0949d2c` - Fix: Make admin email comparison case-insensitive

---

### Issue 4: Admin Link Not Showing in Navigation
**Problem:** Template check `{% if user.email in admin_emails %}` didn't work with case-insensitive logic.

**Solution:** Created centralized `is_admin()` function and passed flag to all templates:
```python
def is_admin():
    if 'user' not in session:
        return False
    user_email = session['user']['email']
    admin_list = [email.strip().lower() for email in ADMIN_EMAILS]
    return user_email.lower() in admin_list

# In routes:
return render_template('index.html', user=session['user'], is_admin=is_admin())
```

**Commit:** `69726f0` - Improve admin check and show Admin link in navigation

---

### Issue 5: Azure Deployment & Database Migration
**Problem:** Needed to migrate from local JSON storage to production-ready database and deploy to Azure.

**Solution:** Implemented database abstraction layer with automatic fallback:
1. Created SQLAlchemy models for all data (RLS mappings, report access, user activity, admin users)
2. Built `db_helpers.py` abstraction layer that tries SQL first, falls back to JSON
3. Added connection pooling with `pool_pre_ping` and `pool_recycle` for Azure SQL
4. Configured GitHub Actions CI/CD pipeline for automatic deployment
5. Set up Azure SQL Database (Basic tier) with secure connection string

**Key Features:**
- Graceful degradation: App works even if database connection fails
- User activity tracking: Login and report view logging
- Admin management: Database-driven admin user system
- Connection pooling: Handles Azure SQL idle timeouts

**Commits:**
- `b3065d3` - Add database connection error handling for graceful fallback
- `827c5c3` - Revert yml changes - workflow was fine, issue was timing
- `07e0a56` - Fix: Ensure Oryx build runs during deployment

---

### Issue 6: Cold Start Performance (60-90 seconds)
**Problem:** After deploying to Azure, the app experienced severe cold starts. Login page took minutes to load when app was idle.

**Root Cause Analysis:**
- Virtual environment extraction: ~42 seconds
- Database connection initialization: ~29 seconds
- Azure App Service sleeping after idle periods (default on Basic tier)

**Solution:**
1. Added lightweight `/health` endpoint for monitoring and warming
2. Created comprehensive optimization guide (AZURE_OPTIMIZATION.md)
3. Recommended enabling "Always On" in Azure App Service
4. Configured health check monitoring path

**Health Endpoint:**
```python
@app.route('/health')
def health():
    """Lightweight health check endpoint for warming up the app"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'database': 'connected' if DBSession else 'json_mode'
    }), 200
```

**Expected Performance After Configuration:**
- Before: 60-90 second first load
- After: Consistently <5 seconds with "Always On" enabled

**Commit:** `602cd92` - Add health check endpoint and cold start optimization guide

---

## Current Configuration

### Environment Variables (.env)
```
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
WORKSPACE_ID=your-workspace-id
ADMIN_EMAILS=carl.hunter@tsgdemonstration.onmicrosoft.com
SECRET_KEY=your-flask-secret-key
```

### Azure AD App Registration
- **Name:** PowerBI-Embedded-POC (or similar)
- **Redirect URIs:**
  - `http://localhost:5000/callback` (local dev)
  - `https://tsgpbiembed-eqbbewh4bebxh9hk.uksouth-01.azurewebsites.net/callback` (production)
- **Permissions:** Power BI Service (Report.Read.All, Dataset.Read.All, Workspace.Read.All)
- **Admin consent:** Granted
- **Service principal:** Enabled in Power BI tenant settings
- **Workspace access:** Service principal added as Member/Admin

### Azure Resources
- **App Service:** tsgpbiembed (Linux, Python 3.11, Basic B1 tier)
- **App Service Plan:** ASP-tsgpbiembed-8c4b (UK South)
- **Database:** Azure SQL Database (Basic tier, 2GB)
- **Resource Group:** tsgpbiembed_group
- **Deployment:** GitHub Actions CI/CD (automatic on push to main)
- **Application Settings:** Environment variables configured in Azure Portal

---

## How It Works

### Authentication Flow
1. User navigates to app → Redirected to Entra ID login
2. User authenticates with their company email
3. Entra ID redirects back to `/callback` with auth code
4. App exchanges code for access token
5. App gets user info from Microsoft Graph API
6. User email stored in Flask session
7. User can access reports

### RLS Flow (Automatic Customer Filtering)
1. User clicks on a report
2. App checks if dataset has RLS roles defined
3. If yes:
   - App calls `get_user_roles(user_email, dataset_id)`
   - No explicit mapping found → Returns `["Customer"]` (default)
   - App generates Power BI embed token with:
     - `username`: user's email
     - `roles`: ["Customer"]
     - `datasets`: [dataset_id]
4. Power BI applies DAX filter: `[CustomerEmail] = USERPRINCIPALNAME()`
5. User sees only their data!

### Admin Panel Flow
1. Admin user logs in (email in ADMIN_EMAILS list or admin_users table)
2. Admin link appears in navigation
3. Admin can manually assign specific roles to users
4. These explicit mappings override the default "Customer" role
5. Admin can view user activity statistics (logins, report views)
6. Admin can manage other admin users

### Database Schema (Azure SQL)
**Tables:**
- `rls_mappings` - User email to RLS roles mappings
  - id (PK), user_email, dataset_id, roles (JSON), created_at, created_by
- `report_access` - User email to report IDs mappings
  - user_email (PK), report_ids (JSON), created_at, created_by
- `user_activity` - Login and report view tracking
  - id (PK), user_email, user_name, activity_type, report_id, report_name, timestamp, ip_address, user_agent
- `admin_users` - Admin user management
  - email (PK), name, created_at, created_by, is_super_admin

**Connection Pooling:**
- pool_pre_ping: Tests connections before use
- pool_recycle: 1800s (recycles before Azure timeout)
- pool_size: 5 connections
- max_overflow: 10 connections
- timeout: 10 seconds

---

## Current Status

### ✅ Working
- **Production deployment:** https://tsgpbiembed-eqbbewh4bebxh9hk.uksouth-01.azurewebsites.net
- Flask app runs locally on `http://localhost:5000` and in Azure
- Entra ID authentication with Microsoft login
- Azure SQL Database with graceful JSON fallback
- Report listing from Power BI workspace
- Report embedding with smart RLS fallback (works with or without RLS)
- User activity tracking (logins and report views)
- Admin panel at `/admin` with:
  - User-to-report access management
  - Recent users list (from activity logs)
  - Activity statistics (logins, views, top reports)
  - Admin user management
- `/health` endpoint for monitoring and warming
- Admin link visible in navigation for admin users
- Automatic "Customer" role assignment for RLS
- Case-insensitive admin email checking
- GitHub Actions CI/CD pipeline for automatic deployment

### ⏱️ Performance Optimization Needed
- **Cold starts:** 60-90 seconds when app is idle
  - **Fix:** Enable "Always On" in Azure App Service settings
  - **Fix:** Configure Health Check monitoring with path `/health`
  - See AZURE_OPTIMIZATION.md for detailed instructions

### ⚠️ Not Yet Configured
- **Power BI RLS roles** - Dataset doesn't have "Customer" role defined yet
  - App works without RLS (all users see same data)
  - Smart fallback detects when RLS is needed
- **External customers** - No guest users invited yet
- **Always On setting** - Needs to be enabled in Azure to prevent cold starts

### 📝 To Do Next
1. **Enable Always On** in Azure App Service (fixes cold start issue)
2. **Configure Health Check** monitoring in Azure
3. **Configure RLS in Power BI Desktop:**
   - Create CustomerMapping table
   - Create "Customer" role with DAX filter
   - Publish to Power BI Service
4. **Test RLS filtering:**
   - Add test data to CustomerMapping table
   - Verify users see filtered data
5. **Invite external customers** as Azure AD B2B guests

---

## Testing Checklist

### Local Testing
- [x] App starts without errors
- [x] Can login with Entra ID
- [x] Can see reports list
- [x] Can view report page
- [ ] Report actually loads in iframe (in progress)
- [x] Admin link appears for admin users
- [x] Admin panel accessible
- [ ] Can add user-to-role mappings in admin panel
- [ ] RLS filtering works (needs Power BI setup first)

### Power BI Setup (Not Done Yet)
- [ ] Create CustomerMapping table in Power BI Desktop
- [ ] Create "Customer" RLS role
- [ ] Add DAX filter: `[CustomerEmail] = USERPRINCIPALNAME()`
- [ ] Test with "View as" in Power BI Desktop
- [ ] Publish to Power BI Service

### Azure AD Setup
- [x] App registration created
- [x] Client secret generated
- [x] Power BI API permissions added
- [x] Admin consent granted
- [x] Service principal enabled in Power BI admin
- [x] Service principal added to workspace
- [ ] External customers invited as guests

---

## Git Repository

**GitHub:** https://github.com/carltsg/cautious-robot

### Recent Commit History
1. `602cd92` - Add health check endpoint and cold start optimization guide
2. `6e21829` - Delete tsgpbiembed.database.windows.net.txt
3. `b3065d3` - Add database connection error handling for graceful fallback
4. `827c5c3` - Revert yml changes - workflow was fine, issue was timing
5. `07e0a56` - Fix: Ensure Oryx build runs during deployment
6. `3d75978` - Trigger Azure Oryx build
7. `030e12c` - Fix: Resolve import timing issue causing app startup failure
8. ... (earlier commits)
9. `69726f0` - Improve admin check and show Admin link in navigation
10. `0949d2c` - Fix: Make admin email comparison case-insensitive
11. `ef6c738` - Fix: Only apply RLS when dataset has roles defined
12. `a20b1df` - Initial implementation of Power BI Embedded POC with automatic RLS

---

## Running the Application

### Prerequisites
- Python 3.10+ installed
- Virtual environment created and activated
- Dependencies installed from requirements.txt
- .env file configured with Azure AD and Power BI credentials

### Start the App
```bash
# Navigate to project directory
cd "C:\Users\carl.hunter\OneDrive - Technology Services Group Ltd\Claude\pbiembedded"

# Activate virtual environment (if using one)
venv\Scripts\activate

# Run the app
python app.py
```

### Access
- **Main app:** http://localhost:5000
- **Reports:** http://localhost:5000/reports
- **Admin panel:** http://localhost:5000/admin
- **Debug mode:** Enabled (auto-reloads on code changes)

### Stop the App
- Press `Ctrl + C` in the terminal

---

## Key Decisions Made

### 1. Automatic vs Manual RLS Assignment
**Decision:** Automatic "Customer" role by default, manual admin panel for exceptions

**Rationale:**
- Scales to 100+ external customers without manual config per user
- Admin panel still available for power users, managers, special cases
- Customer only needs to be added to CustomerMapping table in Power BI

### 2. Python Flask vs ASP.NET Core
**Decision:** Python Flask for POC

**Rationale:**
- 3x faster to implement (2-3 hours vs 6-8 hours)
- 75% less code (~500 lines vs ~2000 lines)
- Easier to understand for POC demonstration
- Can migrate to ASP.NET Core later if needed

### 3. JSON vs Database Storage
**Decision:** JSON file for POC, with abstraction layer for future migration

**Rationale:**
- Simpler for POC (no database setup required)
- Easy to inspect and debug (just open the JSON file)
- IStorageService interface designed for easy swap to database
- Customer requested "for now JSON is okay, longer term need persistent storage"

### 4. Service Principal vs Delegated Permissions
**Decision:** Service principal (app registration) for Power BI API access

**Rationale:**
- Standard pattern for Power BI Embedded
- Backend can access Power BI on behalf of all users
- Enables RLS with EffectiveIdentity
- Required for multi-tenant scenarios

---

## Known Limitations

### Current Limitations
1. **No token refresh** - Embed tokens expire after 60 minutes, user must refresh page
2. **Cold start performance** - 60-90 seconds when idle (fix: enable Always On in Azure)
3. **No bulk user import** - Admin must add user-to-report mappings one by one
4. **Single workspace** - App configured for one workspace only
5. **Basic audit logging** - Activity tracked but no detailed change audit trail

### Security Considerations
- `.env` file contains secrets (never commit to git)
- `rls-config.json` may contain user emails (gitignored)
- RLS enforced server-side by Power BI (cannot be bypassed client-side)
- Admin access controlled by email whitelist (consider role-based auth for production)
- Embed tokens are short-lived (60 minutes)

---

## Next Steps

### Immediate (Complete POC)
1. **Verify report embedding** - Troubleshoot if report not loading in iframe
2. **Configure RLS in Power BI** - Create roles and DAX filters
3. **Test RLS filtering** - Verify automatic filtering works
4. **Document customer onboarding** - Process for inviting guests

### Short Term (Production Ready)
1. **Add token refresh** - Auto-refresh embed tokens before expiry
2. **Migrate to database** - Replace JSON with SQL/SQLite
3. **Add audit logging** - Track who changes RLS mappings
4. **Deploy to Azure** - Move from localhost to Azure Web App
5. **Configure Key Vault** - Store secrets securely

### Long Term (Enterprise Features)
1. **Multi-workspace support** - Allow selection of different workspaces
2. **Bulk user import** - CSV upload for user-to-role mappings
3. **Role-based admin** - Azure AD groups for admin access
4. **Report scheduling** - Email reports to customers
5. **Usage analytics** - Track who views what reports

---

## Troubleshooting Guide

### App Won't Start
- Check Python version: `python --version` (need 3.10+)
- Check virtual environment is activated (see `(venv)` in prompt)
- Check all dependencies installed: `pip list`
- Check .env file exists and has all required variables

### Can't Login
- Check TENANT_ID, CLIENT_ID, CLIENT_SECRET in .env
- Check redirect URI matches in app registration: `http://localhost:5000/callback`
- Check app registration has Power BI API permissions granted

### Report Not Loading
- Open browser console (F12) and check for errors
- Verify WORKSPACE_ID is correct
- Check service principal has access to workspace
- Check report actually exists in the workspace

### Admin Panel Not Accessible
- Check your email is in ADMIN_EMAILS in .env
- Remember: comparison is case-insensitive now
- Restart app after changing .env file
- Logout and login again to refresh session

### RLS Not Working
- Check dataset has RLS roles defined in Power BI Desktop
- Verify roles are published to Power BI Service
- Check user has mapping in admin panel (or relying on automatic "Customer" role)
- Test RLS in Power BI Desktop using "View as" feature first

---

## Useful Commands

### Git
```bash
git status                    # Check what changed
git add .                     # Stage all changes
git commit -m "message"       # Commit changes
git push                      # Push to GitHub
git log --oneline            # View commit history
```

### Python/Flask
```bash
python app.py                # Start the app
pip list                     # List installed packages
pip install -r requirements.txt  # Install dependencies
python -m venv venv          # Create virtual environment
```

### Debugging
```bash
# In browser:
F12                          # Open developer tools
Console tab                  # View JavaScript logs

# In terminal where app is running:
# Watch for print() output and Flask logs
```

---

## Resources

### Documentation
- **README.md** - Complete setup and deployment guide
- **EXTERNAL_CUSTOMERS_GUIDE.md** - Step-by-step for external customer scenarios
- **AZURE_OPTIMIZATION.md** - Azure performance optimization and cold start fixes
- **TECHNICAL_DOCUMENTATION.md** - Technical architecture documentation
- **RLS_FLOW_EXPLAINED.md** - RLS implementation details
- **GitHub Repo** - https://github.com/carltsg/cautious-robot
- **Production URL** - https://tsgpbiembed-eqbbewh4bebxh9hk.uksouth-01.azurewebsites.net

### Microsoft Documentation
- [Power BI Embedded](https://learn.microsoft.com/en-us/power-bi/developer/embedded/)
- [Power BI RLS](https://learn.microsoft.com/en-us/power-bi/enterprise/service-admin-rls)
- [Azure AD B2B](https://learn.microsoft.com/en-us/entra/external-id/what-is-b2b)
- [MSAL Python](https://learn.microsoft.com/en-us/azure/active-directory/develop/msal-overview)

### Libraries
- [Flask](https://flask.palletsprojects.com/)
- [Power BI JavaScript Client](https://github.com/Microsoft/PowerBI-JavaScript)
- [python-dotenv](https://pypi.org/project/python-dotenv/)

---

## Session Summary

### Initial Development (2026-02-11)
**Development Time:** ~3-4 hours
**Lines of Code Written:** ~1500 lines (including documentation)
**Files Created:** 14 files
**Commits Made:** 7 commits
**Issues Resolved:** 4 major issues
**Status:** POC functional locally

### Production Deployment (2026-02-24 to 2026-03-05)
**Development Time:** ~4-5 hours
**Additional Code:** ~800 lines (database layer, models, deployment config)
**Additional Files:** 3 new files (models.py, db_helpers.py, AZURE_OPTIMIZATION.md)
**Commits Made:** 8+ commits
**Issues Resolved:** 2 major issues (Azure deployment, cold start performance)
**Status:** Deployed to Azure production, database migrated, performance optimization guide created

### Overall Project
**Total Development Time:** ~7-9 hours
**Total Lines of Code:** ~2300 lines (application code + documentation)
**Total Files:** 17+ files
**Total Commits:** 15+ commits
**Issues Resolved:** 6 major issues

**Current Status:**
- ✅ Production deployed to Azure
- ✅ Database migrated to Azure SQL
- ✅ User activity tracking implemented
- ✅ Health endpoint for monitoring
- ⏱️ Performance optimization needed (Always On configuration)
- ⚠️ Ready for Power BI RLS configuration and testing

**Next Steps:** Enable Always On, configure health check, set up Power BI RLS, test with external customers

---

**End of Session Log**
*Last updated: 2026-03-05*
*Production URL: https://tsgpbiembed-eqbbewh4bebxh9hk.uksouth-01.azurewebsites.net*
*For questions or continuation, reference this document and the GitHub repository.*
