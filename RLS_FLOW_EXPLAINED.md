# Row-Level Security (RLS) Flow - Complete Guide

This document explains how Row-Level Security works in your Power BI Embedded app, from user login to data filtering in Power BI.

---

## Overview: The Complete RLS Journey

```
User Login → Get User Email → Lookup Roles → Generate Embed Token → Power BI Filters Data
```

---

## Step 1: User Authentication (Microsoft Login)

**File:** `app.py` - Routes: `/login`, `/auth/microsoft`, `/callback`

### What Happens:

1. **User visits the app** → redirected to `/login`
2. **User clicks "Sign in with Microsoft"** → calls `/auth/microsoft`
3. **Microsoft OAuth flow starts:**
   - App redirects to Microsoft login page
   - User enters Microsoft credentials
   - Microsoft redirects back to `/callback` with auth code
4. **App exchanges code for user info:**
   ```python
   user_info = requests.get('https://graph.microsoft.com/v1.0/me')
   session['user'] = {
       'name': user_info.get('displayName'),
       'email': user_info.get('userPrincipalName')  # ← THIS IS KEY!
   }
   ```

### Result:
**User's email is stored in session** (e.g., `john.smith@company.com`)

---

## Step 2: User Views a Report

**File:** `app.py` - Route: `/report/<report_id>`

### What Happens:

1. **User clicks on a report** (e.g., Sales Dashboard)
2. **App fetches report metadata** from Power BI API
3. **App identifies the dataset ID** for that report
4. **App checks if dataset has RLS roles:**
   ```python
   roles_response = requests.get(
       f'.../datasets/{dataset_id}/roles'
   )
   dataset_has_rls = len(dataset_roles) > 0
   ```

---

## Step 3: Determine User's Roles

**File:** `app.py` - Function: `get_user_roles(user_email, dataset_id)`

### What Happens:

The app checks the **RLS configuration** to find what roles this user should have:

**Source 1: Database (if configured)**
- Queries `rls_mappings` table in Azure SQL
- Looks for matching `user_email` + `dataset_id`

**Source 2: JSON file (fallback)**
- Reads `rls-config.json`
- Looks for matching user/dataset

**Example configuration:**
```json
{
  "userEmail": "john.smith@company.com",
  "datasetId": "abc-123-xyz",
  "roles": ["Customer"],
  "createdBy": "admin@company.com"
}
```

### Role Assignment Logic:

```python
def get_user_roles(user_email, dataset_id):
    # Check if user has explicit role mapping
    config = load_rls_config()
    for mapping in config:
        if mapping['userEmail'].lower() == user_email.lower():
            if mapping.get('datasetId') == dataset_id:
                return mapping['roles']  # ← Returns ["Customer"]

    # Default: assign "Customer" role for automatic RLS
    return ['Customer']
```

### Result:
**User's roles are determined** (e.g., `["Customer"]`)

---

## Step 4: Generate Power BI Embed Token (WITH IDENTITY)

**File:** `app.py` - Route: `/report/<report_id>` (lines 296-306)

### What Happens:

The app generates an **embed token** that tells Power BI:
- Which report to show
- Who is viewing it (identity)
- What roles to apply

```python
# Build the embed token payload
embed_payload = {
    'datasets': [{'id': dataset_id}],
    'reports': [{'id': report_id}]
}

# Only add identity if dataset has RLS
if dataset_has_rls:
    user_email = session['user']['email']  # ← From Step 1
    roles = get_user_roles(user_email, dataset_id)  # ← From Step 3

    embed_payload['identities'] = [{
        'username': user_email,      # ← "john.smith@company.com"
        'roles': roles,              # ← ["Customer"]
        'datasets': [dataset_id]     # ← Which dataset to apply it to
    }]

# Request embed token from Power BI
token_response = requests.post(
    'https://api.powerbi.com/v1.0/myorg/GenerateToken',
    headers={'Authorization': f'Bearer {service_principal_token}'},
    json=embed_payload
)
```

### Debug Output (from your app logs):
```
DEBUG RLS - Email: john.smith@company.com, Roles: ['Customer'], Dataset: abc-123-xyz
```

### Result:
**Embed token is generated** containing the user's identity and roles

---

## Step 5: Power BI Receives the Identity

**Where:** Power BI Service (cloud)

### What Happens:

When the report loads in the browser:

1. **Browser requests report** from Power BI using the embed token
2. **Power BI extracts the identity** from the token:
   ```
   username: john.smith@company.com
   roles: ["Customer"]
   ```
3. **Power BI checks the dataset's RLS configuration:**
   - Does this dataset have a role called "Customer"?
   - What filter is defined for the "Customer" role?

---

## Step 6: Power BI Applies RLS Filters

**Where:** Power BI Desktop → Modeling → Manage roles

### How RLS Filters Work:

In Power BI Desktop, you define roles with **DAX filter expressions**:

**Example Role: "Customer"**
```dax
[Email] = USERPRINCIPALNAME()
```

### What This Means:

- `[Email]` = A column in your data table containing email addresses
- `USERPRINCIPALNAME()` = Returns the email from the embed token identity
- `=` = Filter to only show rows where they match

### At Runtime:

When `john.smith@company.com` views the report:

```
USERPRINCIPALNAME() → Returns "john.smith@company.com"
Filter becomes: [Email] = "john.smith@company.com"
Result: User only sees rows where Email column = "john.smith@company.com"
```

---

## Step 7: User Sees Filtered Data

**Result:** John Smith only sees HIS data, not everyone's data!

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER LOGIN (Microsoft OAuth)                                 │
│    ↓                                                             │
│    User email captured: john.smith@company.com                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. USER CLICKS REPORT                                           │
│    ↓                                                             │
│    App identifies: Dataset ID = abc-123-xyz                     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. LOOKUP USER ROLES                                            │
│    ↓                                                             │
│    Query: rls_mappings table (or rls-config.json)              │
│    Match: john.smith@company.com + abc-123-xyz                 │
│    Result: Roles = ["Customer"]                                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. GENERATE EMBED TOKEN                                         │
│    ↓                                                             │
│    POST to Power BI API:                                        │
│    {                                                             │
│      "identities": [{                                           │
│        "username": "john.smith@company.com",                    │
│        "roles": ["Customer"],                                   │
│        "datasets": ["abc-123-xyz"]                              │
│      }]                                                          │
│    }                                                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. POWER BI RECEIVES IDENTITY                                   │
│    ↓                                                             │
│    Power BI extracts from token:                                │
│    - Username: john.smith@company.com                           │
│    - Role: Customer                                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. POWER BI APPLIES RLS FILTER                                  │
│    ↓                                                             │
│    Role "Customer" has filter:                                  │
│    [Email] = USERPRINCIPALNAME()                                │
│    ↓                                                             │
│    Evaluates to:                                                │
│    [Email] = "john.smith@company.com"                           │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. USER SEES FILTERED DATA                                      │
│    ✓ Only rows where Email = "john.smith@company.com"          │
│    ✗ All other rows are hidden                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## How to Configure RLS in Power BI Desktop

### Step 1: Create the Role

1. Open your Power BI report in **Power BI Desktop**
2. Click **Modeling** tab → **Manage roles**
3. Click **Create**
4. Name: `Customer`

### Step 2: Add the Filter

1. **Select your data table** (e.g., "Sales", "Orders", "Customers")
2. In the **"Table filter DAX expression"** box, enter:
   ```dax
   [YourEmailColumn] = USERPRINCIPALNAME()
   ```

   **Replace `YourEmailColumn` with your actual column name**, such as:
   - `[Email]`
   - `[UserEmail]`
   - `[CustomerEmail]`
   - `[SalesRep]`

3. Click **Save**

### Step 3: Test Locally

1. Click **Modeling** → **View as**
2. Check **"Customer"** role
3. Check **"Other user"**
4. Type a test email: `john.smith@company.com`
5. Click **OK**

**Expected result:** You should only see data for john.smith@company.com

### Step 4: Publish

1. Click **Publish**
2. Select your workspace
3. Click **Publish**

### Step 5: Verify in Power BI Service

1. Go to **Power BI Service** (app.powerbi.com)
2. Navigate to your workspace
3. Click on the **dataset** (not the report)
4. Click **Security** (or **More options** → **Security**)
5. Verify the "Customer" role appears

---

## How to Assign Roles in Your App

### Via Admin Panel

1. Go to: `https://tsgpbiembed-eqbbewh4bebxh9hk.uksouth-01.azurewebsites.net/admin`
2. Login as admin
3. Under **"Assign RLS Role"**:
   - User Email: `john.smith@company.com`
   - Dataset: Select your dataset
   - Roles: Select "Customer"
   - Click **"Save Mapping"**

### What Gets Stored:

**In Azure SQL Database** (or JSON file):
```json
{
  "userEmail": "john.smith@company.com",
  "datasetId": "abc-123-xyz",
  "roles": ["Customer"],
  "createdAt": "2026-02-13T16:45:00Z",
  "createdBy": "admin@company.com"
}
```

---

## Common DAX Functions for RLS

### USERPRINCIPALNAME()
Returns the email passed in the embed token.

**Use case:** Filter by user email
```dax
[Email] = USERPRINCIPALNAME()
```

### USERNAME()
Alternative to USERPRINCIPALNAME() (returns same value in this app)

```dax
[Email] = USERNAME()
```

### Multiple Users in One Column
If your data has multiple emails in one column (comma-separated):

```dax
SEARCH(USERPRINCIPALNAME(), [EmailList], 1, 0) > 0
```

---

## Troubleshooting

### Problem: User sees ALL data (no filtering)

**Possible causes:**
1. ❌ Dataset has no RLS role defined
2. ❌ Role name mismatch (app sends "Customer", Power BI has "User")
3. ❌ DAX filter syntax error
4. ❌ Column name wrong in DAX filter
5. ❌ User has no email in the data

**Check:**
- App logs show: `DEBUG RLS - Email: ..., Roles: ['Customer']`
- Power BI Desktop has role named exactly "Customer"
- DAX filter uses correct column name

### Problem: User sees NO data (empty report)

**Possible causes:**
1. ❌ Email in identity doesn't match ANY email in data
2. ❌ Case sensitivity issue (`John.Smith@company.com` vs `john.smith@company.com`)
3. ❌ DAX filter too restrictive

**Fix:**
- Make data emails lowercase: `LOWER([Email]) = LOWER(USERPRINCIPALNAME())`
- Verify test email exists in your data

### Problem: Getting GUID instead of email

**Cause:** You created a MEASURE instead of a ROLE FILTER

**Fix:**
- Delete the measure
- Create role filter instead (Modeling → Manage roles)

---

## Testing Checklist

- [ ] Role created in Power BI Desktop
- [ ] DAX filter uses correct column name
- [ ] DAX filter syntax validated
- [ ] Report published to workspace
- [ ] Role visible in Power BI Service → Dataset → Security
- [ ] User assigned role in app admin panel
- [ ] User can login to app
- [ ] User can view report
- [ ] App logs show correct email and roles
- [ ] User sees only THEIR data (not all data)
- [ ] Different users see different data

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `app.py` | Main application logic, RLS flow |
| `models.py` | Database models for RLS mappings |
| `db_helpers.py` | Load/save RLS config from DB or JSON |
| `rls-config.json` | Local RLS mappings (fallback) |
| `reports-access.json` | Report access control |

---

## Security Notes

✅ **What's secure:**
- User email from Microsoft OAuth (trusted source)
- Embed token signed by Power BI
- RLS enforced server-side by Power BI

❌ **What's NOT secure:**
- Don't trust client-side data
- Don't put sensitive data in report names/titles
- Always use RLS for multi-tenant data

---

## Next Steps

1. ✅ Read this document
2. ✅ Identify your email column name in Power BI
3. ✅ Create RLS role with DAX filter
4. ✅ Test in Power BI Desktop
5. ✅ Publish to workspace
6. ✅ Assign roles in app admin panel
7. ✅ Test with real users
8. ✅ Check app logs to verify identity is passed correctly
9. ✅ Verify data filtering works

---

**Questions?** Check the app logs first:
```
Azure Portal → App Service → Log stream
Look for: DEBUG RLS - Email: ..., Roles: ...
```
