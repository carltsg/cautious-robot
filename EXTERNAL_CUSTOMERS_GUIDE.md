# Quick Start Guide: Sharing Reports with External Customers

This guide walks you through setting up the POC to share Power BI reports with external customers where each customer sees only their own data.

## Overview

Your external customers will:
- Log in with their own company email addresses
- Automatically see only their data (filtered by email)
- No manual admin configuration needed for each customer

## Step-by-Step Setup

### Step 1: Prepare Your Power BI Report (One-Time Setup)

#### 1.1 Create Customer Mapping Table

In Power BI Desktop, create a table that maps customer emails to their data:

**Option A: Create in Power Query**
1. Home → Enter Data
2. Create table with these columns:

| CustomerEmail | CustomerID | CustomerName |
|---------------|------------|--------------|
| john@acme.com | ACME001 | Acme Corporation |
| jane@widgetco.com | WIDGET001 | Widget Company |
| bob@techcorp.com | TECH001 | Tech Corp |

3. Name the table: `CustomerMapping`
4. Close & Apply

**Option B: Connect to Existing Data**
If you already have this data in a database/Excel:
1. Get Data → Connect to your source
2. Load the customer mapping table
3. Ensure it has: CustomerEmail, CustomerID columns

#### 1.2 Link to Your Fact Tables

Make sure your main data tables have a CustomerID column that matches the CustomerMapping table.

**Relationships:**
- CustomerMapping[CustomerID] → Sales[CustomerID]
- CustomerMapping[CustomerID] → Orders[CustomerID]
- etc.

#### 1.3 Create Dynamic RLS Role

1. **Model view** → **Manage roles** → **Create**
2. Name: `Customer`
3. Select your main table (e.g., Sales)
4. Add this DAX filter:

**If you linked via CustomerID:**
```dax
[CustomerID] = LOOKUPVALUE(
    CustomerMapping[CustomerID],
    CustomerMapping[CustomerEmail],
    USERPRINCIPALNAME()
)
```

**If CustomerEmail is directly in your fact table:**
```dax
[CustomerEmail] = USERPRINCIPALNAME()
```

5. **Save**

#### 1.4 Test RLS (Important!)

1. **Model view** → **View as** → Select "Customer" role
2. Enter a test email: `john@acme.com`
3. **OK**
4. Verify you see only Acme Corporation's data
5. Exit **View as** mode

#### 1.5 Publish Report

1. **File** → **Publish** → Publish to Power BI Service
2. Select your workspace (must be backed by Embedded capacity)
3. **Publish**

### Step 2: Set Up the Web Application

Follow the main README.md to:
1. Configure Azure AD app registration
2. Enable service principal in Power BI
3. Grant workspace access
4. Create .env file with credentials
5. Run the application

### Step 3: Invite External Customers

For each external customer you want to give access to:

#### Azure Portal Method:
1. Go to **Azure Portal** → **Entra ID** → **Users**
2. Click **Invite external user**
3. Fill in:
   - **Email address:** `john@acme.com`
   - **Display name:** `John Smith (Acme Corp)` (helpful for tracking)
   - **Personal message:** Customize the invitation (optional)
   - **Groups:** (optional - can add to security groups)
4. Click **Invite**
5. Customer receives email invitation
6. They click "Accept invitation"
7. Done! They can now access your POC

#### Bulk Invite Method (For Multiple Customers):
1. **Azure Portal** → **Entra ID** → **Users** → **Bulk operations** → **Bulk invite**
2. Download CSV template
3. Fill in customer details:
```csv
Name,Email address to invite,Redirection url,Send invitation message
John Smith,john@acme.com,http://localhost:5000,TRUE
Jane Doe,jane@widgetco.com,http://localhost:5000,TRUE
Bob Johnson,bob@techcorp.com,http://localhost:5000,TRUE
```
4. Upload and submit
5. All receive invitations automatically

### Step 4: Customer Experience

Once invited, your customers:

1. Receive invitation email from Microsoft
2. Click "Accept invitation"
3. Navigate to your POC app URL
4. Click "Login"
5. Authenticate with THEIR company credentials (e.g., john@acme.com)
6. See the reports list
7. Click on a report
8. **Automatically see only their data** - no manual config needed!

## How the Automatic Filtering Works

```
1. john@acme.com logs in
   ↓
2. Entra ID authenticates user
   ↓
3. User clicks on a Power BI report
   ↓
4. App generates embed token:
   - Username: john@acme.com
   - Role: "Customer" (automatically assigned)
   ↓
5. Power BI receives request:
   - Applies "Customer" role RLS
   - DAX filter: Show only records where CustomerEmail = john@acme.com
   ↓
6. John sees only Acme Corporation's data!
```

## Maintaining Customer Access

### Adding New Customers

**Option 1: Just Update Power BI** (If using CustomerMapping table)
1. Open Power BI Desktop
2. Add new row to CustomerMapping table:
   - CustomerEmail: newcustomer@company.com
   - CustomerID: COMPANY001
   - CustomerName: Company Name
3. Publish to Power BI Service
4. Invite customer as Azure AD guest
5. Done! They can log in and see their data

**Option 2: If CustomerEmail is in your source data**
1. Ensure new customer's data includes their email in the CustomerEmail field
2. Refresh dataset in Power BI Service
3. Invite customer as Azure AD guest
4. Done!

### Removing Customer Access

**Option 1: Remove from Azure AD**
1. Azure Portal → Entra ID → Users
2. Find the guest user
3. Delete → Confirm
4. They can no longer log in

**Option 2: Remove from CustomerMapping**
1. Power BI Desktop → Remove row from CustomerMapping table
2. Publish to Power BI Service
3. They can log in but see no data (secure default)

### Modifying Customer Data Access

Just update the CustomerMapping table or your source data:
- Change CustomerID → They see different data
- Update relationships → Affects what they can see
- Publish changes → Takes effect immediately

## Special Cases

### Customer Needs Access to Multiple Datasets

If a customer should see data from multiple companies:

**Option 1: Update CustomerMapping**
- Add multiple rows for their email with different CustomerIDs

**Option 2: Use Admin Panel**
1. Log in as admin
2. Go to Admin panel
3. Assign custom roles to that customer's email
4. This overrides the automatic "Customer" role

### Internal User Needs Broad Access

For managers, analysts, or support staff:

1. Log in to POC as admin
2. Go to Admin panel
3. Add mapping:
   - Email: manager@yourcompany.com
   - Roles: ["Manager", "AllRegions"] (or whatever roles you defined)
4. Save
5. This user now sees data based on Manager role, not their email

### Testing with Your Own Email

1. Add your email to CustomerMapping table with a test CustomerID
2. Publish to Power BI
3. Log in to POC with your email
4. View report - you'll see data for that test CustomerID
5. Verify filtering is working correctly

## Troubleshooting

### Customer sees no data
- ✅ Check that their email exists in CustomerMapping table (exact match, case-insensitive)
- ✅ Verify CustomerID in mapping matches actual data
- ✅ Verify RLS DAX filter is applied correctly
- ✅ Test in Power BI Desktop using "View as" with their email

### Customer sees ALL data
- ❌ RLS role might not be applied - check `get_user_roles()` in app.py returns ["Customer"]
- ❌ DAX filter might be incorrect - test in Power BI Desktop
- ❌ CustomerMapping table might not be linked properly

### Guest invitation not received
- ✅ Check spam folder
- ✅ Verify email address is correct
- ✅ Try resending invitation from Azure Portal
- ✅ Check Azure AD audit logs for errors

### Guest can't log in
- ✅ Ensure they clicked "Accept invitation" first
- ✅ Verify they're using the correct email address
- ✅ Check that guest user appears in Azure AD → Users → All users (external)
- ✅ Verify redirect URI in app registration includes localhost:5000/callback

## Security Checklist

- ✅ RLS role "Customer" is defined in Power BI
- ✅ DAX filter uses USERPRINCIPALNAME() function
- ✅ Tested RLS with "View as" in Power BI Desktop
- ✅ .env file contains CLIENT_SECRET (not committed to git)
- ✅ Admin emails list only includes trusted administrators
- ✅ External customers are invited as guests (not full members)
- ✅ Power BI workspace uses Embedded capacity
- ✅ Service principal is enabled and has workspace access

## Production Deployment

When moving to production:

1. **Update redirect URI**
   - App registration: Add `https://your-app.azurewebsites.net/callback`
   - app.py: Update `REDIRECT_URI` variable

2. **Use Azure Key Vault**
   - Store CLIENT_SECRET in Key Vault
   - Reference in App Settings using Key Vault reference

3. **Update environment variables**
   - Azure Web App → Configuration → Application settings
   - Add all variables from .env

4. **Update invitation URLs**
   - When inviting guests, use production URL instead of localhost

5. **Test thoroughly**
   - Invite a test customer
   - Verify they can log in
   - Verify RLS filtering works
   - Check different browsers/devices

## Support

For issues:
- Check the main README.md troubleshooting section
- Review Power BI RLS documentation
- Check Azure AD B2B guest user documentation
- Verify all prerequisites are met

## Summary

**The key insight:** With automatic "Customer" role assignment and email-based RLS filtering, you can onboard 100+ external customers without touching the admin panel. Just:

1. Set up RLS once in Power BI ✅
2. Invite customers as guests ✅
3. Maintain CustomerMapping table ✅
4. Done! ✅

No manual configuration per user needed!
