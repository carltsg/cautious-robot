# Power BI Embedded POC with Row-Level Security

A simple Python Flask web application demonstrating Power BI embedding with Entra ID authentication and row-level security (RLS) configuration.

## Features

- Entra ID (Azure AD) authentication for users (including external B2B guests)
- Power BI report embedding
- Row-level security (RLS) enforcement
- **Automatic customer filtering by email** (no manual config per user)
- Admin panel for special role assignments
- Simple JSON-based storage for POC
- Responsive Bootstrap UI

## Use Case: Sharing Reports with External Customers

This POC is **optimized for sharing Power BI reports with external customers** where each customer should only see their own data.

**How it works:**

1. **Invite external customers** as Azure AD B2B guest users (one-time setup per customer)
2. **Configure dynamic RLS** in Power BI using email-based filtering (one-time setup)
3. **Customers log in** with their own company email addresses
4. **Automatic filtering** - Each customer sees only their data based on their email
5. **No manual admin work** per customer - just maintain the customer mapping table in Power BI

**Scalability:** This approach works well for 20-100+ external customers without requiring manual configuration for each user.

See **"RLS Configuration → Pattern 1: Automatic Customer Filtering"** below for detailed setup instructions.

## Prerequisites

- Python 3.10 or higher
- Azure subscription with:
  - Power BI workspace (backed by Embedded capacity)
  - Entra ID (Azure AD) tenant
- Power BI reports with RLS roles defined

## Quick Start

### 1. Clone and Setup

```bash
# Navigate to project directory
cd pbiembedded

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Azure AD App Registration

Before running the app, you need to create an app registration in Entra ID:

1. **Go to Azure Portal** → Entra ID → App registrations → New registration

2. **Configure the registration:**
   - Name: `PowerBI-Embedded-POC`
   - Supported account types: Single tenant
   - Redirect URI: Web → `http://localhost:5000/callback`
   - Click **Register**

3. **Note these values** (you'll need them for .env):
   - **Application (client) ID**
   - **Directory (tenant) ID**

4. **Create a client secret:**
   - Go to Certificates & secrets → New client secret
   - Description: `POC Secret`
   - Expires: 24 months
   - Click **Add**
   - **COPY THE SECRET VALUE IMMEDIATELY** (you won't see it again)

5. **Add API permissions:**
   - Go to API permissions → Add a permission
   - Select **Power BI Service**
   - Select **Delegated permissions**
   - Add: `Report.Read.All`, `Dataset.Read.All`, `Workspace.Read.All`
   - Click **Add permissions**
   - Click **Grant admin consent** (requires admin)

6. **Add optional claims** (for better user experience):
   - Go to Token configuration → Add optional claim
   - Token type: **ID**
   - Select: `email`, `preferred_username`
   - Click **Add**

### 3. Enable Service Principal in Power BI

1. **Go to Power BI Admin Portal** (https://app.powerbi.com/admin-portal)

2. **Tenant settings** → Developer settings

3. **Enable "Service principals can use Power BI APIs"**
   - Select "Specific security groups" (recommended)
   - Create a security group in Entra ID: `PowerBI-ServicePrincipal-Access`
   - Add your app registration to this group
   - Add the group to the Power BI setting
   - Click **Apply**

### 4. Grant Workspace Access

1. **Go to Power BI Service** (https://app.powerbi.com)

2. Navigate to your workspace

3. Click **Access** → **Add people or groups**

4. Search for your app registration name (`PowerBI-Embedded-POC`)

5. Assign role: **Member** or **Admin**

6. Click **Add**

### 5. Configure Environment Variables

1. **Copy the example file:**
   ```bash
   copy .env.example .env
   ```

2. **Edit .env** and fill in your values:
   ```
   TENANT_ID=your-tenant-id-from-step-2
   CLIENT_ID=your-client-id-from-step-2
   CLIENT_SECRET=your-client-secret-from-step-2
   WORKSPACE_ID=your-power-bi-workspace-id
   ADMIN_EMAILS=youremail@domain.com
   SECRET_KEY=your-random-secret-key-here
   ```

3. **To get your WORKSPACE_ID:**
   - Go to your Power BI workspace
   - Look at the URL: `https://app.powerbi.com/groups/{WORKSPACE_ID}/...`
   - Copy the GUID

4. **Generate a SECRET_KEY:**
   ```python
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

### 6. Run the Application

```bash
python app.py
```

Navigate to: **http://localhost:5000**

### 7. Invite External Customers (For Sharing with External Users)

If you're sharing reports with external customers, they need to be invited as **Azure AD B2B Guest Users**.

#### Option A: Invite Individual Users (Manual)

1. **Azure Portal** → Entra ID → Users → Invite external user
2. Enter their email: `customer@theircompany.com`
3. Customize invitation message (optional)
4. Click **Invite**
5. Customer receives email invitation
6. They click "Accept invitation" and authenticate with their own credentials
7. They can now log into your POC app

#### Option B: Bulk Invite (For Multiple Customers)

1. **Azure Portal** → Entra ID → Users → Bulk operations → Bulk invite
2. Download CSV template
3. Fill in customer emails:
   ```csv
   Name,Email address to invite,Redirection url,Send invitation message
   John Smith,john@acme.com,http://localhost:5000,TRUE
   Jane Doe,jane@widgetco.com,http://localhost:5000,TRUE
   ```
4. Upload CSV and submit
5. All customers receive invitation emails

#### Option C: Programmatic Invite (via Microsoft Graph API)

For automation, you can use the Microsoft Graph API to invite users programmatically.

**Note:** Guest users appear in your Azure AD as `customer_theircompany.com#EXT#@yourtenant.onmicrosoft.com` but log in with their original email.

## Usage

### For End Users (Including External Customers)

1. **Login** - Click login and authenticate with your Entra ID account
   - Internal users: Use your company credentials
   - External customers: Use your company email (must be invited as guest first)
2. **View Reports** - Browse available Power BI reports
3. **Open Report** - Click on a report to view it with RLS applied
4. **Data Filtering** - You automatically see only your data
   - If using automatic RLS (recommended): You see data filtered by your email
   - If admin assigned specific roles: You see data based on those roles

### For Administrators

**Note:** With automatic "Customer" role, you typically DON'T need to manually configure each external customer. They automatically get filtered by email. Only use admin panel for special cases.

**When to use the Admin Panel:**

1. **Login as Admin** - Your email must be in the `ADMIN_EMAILS` list
2. **Go to Admin Panel** - Click "Admin" in the navigation
3. **Configure Special Access:**
   - **Power users** who need access to multiple customers' data
   - **Managers** who need broader access (e.g., "Manager" role)
   - **Internal analysts** who need specific role combinations
   - **Override cases** where automatic filtering isn't appropriate
4. **How to configure:**
   - Enter user email
   - Select report/dataset
   - Choose RLS roles (defined in your Power BI report)
   - Click "Save Mapping"
5. **Manage Mappings** - View and delete existing mappings

**Important:** External customers invited as guests do NOT need to be added to admin panel if you're using the automatic "Customer" role pattern (see RLS Configuration below).

## RLS Configuration

### Two RLS Patterns Supported

#### Pattern 1: Automatic Customer Filtering (Recommended for External Customers)

**Best for:** Sharing reports with external customers who should only see their own data

**Setup in Power BI Desktop:**

1. **Create a Customer mapping table** in your dataset:
   ```
   CustomerMapping:
   CustomerEmail          | CustomerID | CustomerName
   john@acme.com         | ACME001    | Acme Corporation
   jane@widgetco.com     | WIDGET001  | Widget Company
   ```

2. **Model view** → Manage roles → Create role **"Customer"**

3. **Add DAX filter** on your main data table (e.g., Sales table):
   ```dax
   [CustomerID] = LOOKUPVALUE(
       CustomerMapping[CustomerID],
       CustomerMapping[CustomerEmail],
       USERPRINCIPALNAME()
   )
   ```

   Or if you have CustomerEmail directly in your fact table:
   ```dax
   [CustomerEmail] = USERPRINCIPALNAME()
   ```

4. **Publish to Power BI Service**

**How it works:**
- ANY user who logs in automatically gets the "Customer" role
- Power BI's DAX filter shows them only data where their email matches
- **No manual admin configuration needed** for each customer
- Just maintain the CustomerMapping table in Power BI

**Example:**
- john@acme.com logs in → Automatically assigned "Customer" role
- DAX filter applies: Show only data where CustomerEmail = john@acme.com
- John sees only Acme Corporation's data

#### Pattern 2: Manual Role Assignment (For Power Users/Admins)

**Best for:** Internal users, managers, or users who need access to multiple customers

**Setup in Power BI Desktop:**

1. **Model view** → Manage roles
2. **Create specific roles** (e.g., "Sales", "Manager", "WestRegion")
3. **Define DAX filters** for each role
4. **Publish to Power BI Service**

**In the Web App:**

1. Admin goes to admin panel (`/admin`)
2. Manually assigns user emails to specific roles
3. These explicit assignments override the default "Customer" role

**Example:**
- manager@company.com → Assigned ["Manager", "AllRegions"] in admin panel
- When they view a report, they get Manager + AllRegions roles
- They see broader data based on those role filters

### How RLS Works in This App

1. User logs in via Entra ID → Email stored in session
2. User views a report → App calls `get_user_roles(user_email, dataset_id)`
3. Role assignment logic:
   - **If user has explicit mapping** in admin panel → Use those roles
   - **If no explicit mapping** → Automatically assign ["Customer"] role
4. App generates Power BI embed token with assigned roles
5. Power BI enforces RLS server-side (cannot be bypassed)

## Project Structure

```
pbiembedded/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── .env                    # Configuration (DO NOT commit)
├── .env.example           # Configuration template
├── rls-config.json        # User-to-role mappings (auto-created)
├── templates/             # HTML templates
│   ├── layout.html       # Base layout
│   ├── index.html        # Home page
│   ├── reports.html      # Report list
│   ├── view_report.html  # Embedded report viewer
│   └── admin.html        # RLS configuration UI
├── static/               # Static files
│   ├── powerbi.js       # Power BI embed logic
│   └── style.css        # Custom CSS
└── README.md            # This file
```

## Security Considerations

- **Never commit .env file** - It contains secrets
- **Use HTTPS in production** - Azure Web App provides this
- **RLS is enforced server-side** - Cannot be bypassed in the browser
- **Tokens expire after 60 minutes** - Users will need to refresh
- **Admin access is email-based** - Consider database storage for production

## Troubleshooting

### "Missing required environment variables"
- Check that your .env file exists and has all required values

### "Failed to acquire token"
- Verify your TENANT_ID, CLIENT_ID, and CLIENT_SECRET
- Check that the app registration client secret hasn't expired

### "Error fetching reports"
- Verify WORKSPACE_ID is correct
- Check that service principal is enabled in Power BI admin portal
- Verify app registration has been added to the workspace

### "No RLS roles defined for this dataset"
- RLS roles must be created in Power BI Desktop first
- Publish the report to Power BI Service
- Refresh the admin page

### "User sees all data (RLS not working)"
- Check that the user has a mapping in the admin panel
- Verify the roles match exactly (case-sensitive)
- Check that RLS is defined in the Power BI dataset

## Deployment to Azure Web App

### 1. Create Azure Web App

```bash
az webapp up --name your-app-name --runtime "PYTHON:3.10" --sku B1
```

### 2. Configure App Settings

In Azure Portal → Web App → Configuration → Application settings:

- `TENANT_ID` = your-tenant-id
- `CLIENT_ID` = your-client-id
- `CLIENT_SECRET` = your-client-secret (use Key Vault in production)
- `WORKSPACE_ID` = your-workspace-id
- `ADMIN_EMAILS` = admin@domain.com
- `SECRET_KEY` = random-secret-key

### 3. Update Redirect URI

In your app registration:
- Add redirect URI: `https://your-app-name.azurewebsites.net/callback`
- Update `REDIRECT_URI` in app.py to match

### 4. Deploy

```bash
# Using Azure CLI
az webapp up --name your-app-name

# Or using Git
git push azure main
```

## Future Enhancements

- Database storage (instead of JSON)
- Audit logging for RLS changes
- Role-based admin access
- Bulk user import (CSV)
- Token refresh mechanism
- Multi-language support

## License

This is a proof of concept for demonstration purposes.

## Support

For issues or questions, refer to:
- [Power BI Embedded Documentation](https://learn.microsoft.com/en-us/power-bi/developer/embedded/)
- [MSAL Python Documentation](https://learn.microsoft.com/en-us/azure/active-directory/develop/msal-overview)
- [Flask Documentation](https://flask.palletsprojects.com/)
