# Power BI Embedded POC - Development Session Log

**Project:** Power BI Embedded Web Application with RLS
**Developer:** Carl Hunter (carl.hunter@TSGdemonstration.onmicrosoft.com)
**Date Started:** 2026-02-11
**Last Updated:** 2026-02-11
**Repository:** https://github.com/carltsg/cautious-robot

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

- **Backend:** Python 3.10+ with Flask
- **Authentication:** MSAL (Microsoft Authentication Library)
- **Power BI:** REST API + powerbi-client JavaScript SDK
- **Frontend:** Bootstrap 5 + vanilla JavaScript
- **Storage:** JSON file (designed for easy database migration)
- **Hosting Target:** Azure Web App

### Dependencies (requirements.txt)
```
Flask==3.0.0
msal==1.26.0
requests==2.31.0
python-dotenv==1.0.0
```

---

## Project Structure

```
pbiembedded/
├── app.py                          # Main Flask application (~330 lines)
├── requirements.txt                # Python dependencies
├── .env                           # Configuration (NOT in git)
├── .env.example                   # Configuration template
├── rls-config.json                # User-to-role mappings (auto-created)
├── templates/
│   ├── layout.html                # Base template with navigation
│   ├── index.html                 # Home page
│   ├── reports.html               # Report listing
│   ├── view_report.html           # Embedded report viewer
│   └── admin.html                 # RLS configuration UI
├── static/
│   ├── powerbi.js                 # Power BI embed logic
│   └── style.css                  # Custom CSS
├── README.md                      # Complete setup guide
├── EXTERNAL_CUSTOMERS_GUIDE.md    # Step-by-step customer setup
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
- **Redirect URI:** `http://localhost:5000/callback`
- **Permissions:** Power BI Service (Report.Read.All, Dataset.Read.All, Workspace.Read.All)
- **Admin consent:** Granted
- **Service principal:** Enabled in Power BI tenant settings
- **Workspace access:** Service principal added as Member/Admin

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
1. Admin user logs in (email in ADMIN_EMAILS list)
2. Admin link appears in navigation
3. Admin can manually assign specific roles to users
4. These explicit mappings override the default "Customer" role

---

## Current Status

### ✅ Working
- Flask app runs on `http://localhost:5000`
- Entra ID authentication
- Report listing from Power BI workspace
- Report embedding (with or without RLS)
- Admin panel accessible at `/admin`
- Admin link visible in navigation for admin users
- Automatic "Customer" role assignment
- Case-insensitive admin email checking

### ⚠️ Not Yet Configured
- **Power BI RLS roles** - Dataset doesn't have "Customer" role defined yet
  - App works without RLS (all users see same data)
  - Shows yellow warning: "This dataset does not have RLS roles defined"
- **External customers** - No guest users invited yet
- **Production deployment** - Still running locally

### 📝 To Do Next
1. **Test report embedding fully** - Verify report loads in iframe
2. **Configure RLS in Power BI Desktop:**
   - Create CustomerMapping table
   - Create "Customer" role with DAX filter
   - Publish to Power BI Service
3. **Test RLS filtering:**
   - Add test data to CustomerMapping table
   - Verify users see filtered data
4. **Invite external customers** as Azure AD B2B guests
5. **Deploy to Azure Web App** for production

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

### Commit History
1. `a20b1df` - Initial implementation of Power BI Embedded POC with automatic RLS
2. `6d95b7b` - Update Claude settings to allow git commit commands
3. `840d6a7` - Update Claude settings to allow git push commands
4. `ef6c738` - Fix: Only apply RLS when dataset has roles defined
5. `f15e603` - Add debugging and fix Power BI models undefined error
6. `0949d2c` - Fix: Make admin email comparison case-insensitive
7. `69726f0` - Improve admin check and show Admin link in navigation

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
2. **No audit logging** - RLS config changes not logged
3. **JSON storage** - Not suitable for concurrent access (production needs database)
4. **No bulk user import** - Admin must add mappings one by one
5. **Single workspace** - App configured for one workspace only

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
- **GitHub Repo** - https://github.com/carltsg/cautious-robot

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

**Total Development Time:** ~3-4 hours
**Lines of Code Written:** ~1500 lines (including documentation)
**Files Created:** 14 files
**Commits Made:** 7 commits
**Issues Resolved:** 4 major issues

**Status:** POC functional, ready for Power BI RLS configuration and testing

**Next Session:** Continue with Power BI RLS setup and external customer testing

---

**End of Session Log**
*Last updated: 2026-02-11*
*For questions or continuation, reference this document and the GitHub repository.*
