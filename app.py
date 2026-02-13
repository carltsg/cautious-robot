from flask import Flask, render_template, session, redirect, url_for, request, jsonify
from msal import ConfidentialClientApplication
import requests
import json
import os
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize database connection
from models import init_db
db_engine, DBSession = init_db()
if DBSession:
    print("✓ Database connected (SQL mode)")
    import models
    models.db_engine = db_engine
    models.DBSession = DBSession
else:
    print("⚠ Database not configured - using JSON files")

# Import database helpers
from db_helpers import (
    load_rls_config,
    save_rls_config,
    load_reports_access_config,
    save_reports_access_config
)

# Load configuration
TENANT_ID = os.getenv('TENANT_ID')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
WORKSPACE_ID = os.getenv('WORKSPACE_ID')
ADMIN_EMAILS = os.getenv('ADMIN_EMAILS', '').split(',')
AUTHORITY = f'https://login.microsoftonline.com/{TENANT_ID}'
# Support both local and Azure environments
REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:5000/callback')
SCOPE = ['https://analysis.windows.net/powerbi/api/.default']

# MSAL Client
msal_app = ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
)

# Helper functions
def get_powerbi_token():
    """Get Power BI access token using service principal"""
    result = msal_app.acquire_token_for_client(scopes=SCOPE)
    if 'access_token' in result:
        return result.get('access_token')
    else:
        raise Exception(f"Failed to acquire token: {result.get('error_description')}")

def get_user_reports(user_email):
    """Get list of report IDs assigned to a user

    Returns:
        list: Report IDs the user has access to, or empty list if no access
    """
    config = load_reports_access_config()
    for mapping in config:
        if mapping['userEmail'].lower() == user_email.lower():
            return mapping['reportIds']
    return []

def get_user_roles(user_email, dataset_id):
    """Get RLS roles for a user

    If user has explicit mapping in rls-config.json, return those roles.
    Otherwise, return 'Customer' role by default for dynamic RLS.
    This allows external customers to automatically see their data filtered
    by email without manual admin configuration.
    """
    config = load_rls_config()
    for mapping in config:
        if mapping['userEmail'].lower() == user_email.lower():
            if not dataset_id or mapping.get('datasetId') == dataset_id:
                return mapping['roles']

    # Default: assign 'Customer' role for automatic email-based RLS filtering
    return ['Customer']

def is_admin():
    """Check if current user is an admin"""
    if 'user' not in session:
        return False
    user_email = session['user']['email']
    admin_list = [email.strip().lower() for email in ADMIN_EMAILS]
    return user_email.lower() in admin_list

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        user_email = session['user']['email']
        # Clean up admin emails and compare (case-insensitive)
        admin_list = [email.strip().lower() for email in ADMIN_EMAILS]

        # Debug logging
        print(f"DEBUG - Admin check:")
        print(f"  Logged in as: '{user_email}' (lowercase: '{user_email.lower()}')")
        print(f"  Admin list: {admin_list}")
        print(f"  Match: {user_email.lower() in admin_list}")

        if user_email.lower() not in admin_list:
            return f'Unauthorized - Admin access required<br><br>Your email: <code>{user_email}</code><br>Admin emails: <code>{admin_list}</code><br><br>Update ADMIN_EMAILS in .env file and restart the app.', 403
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
@login_required
def index():
    return render_template('index.html', user=session['user'], is_admin=is_admin())

@app.route('/login')
def login():
    # If user is already authenticated, redirect to home
    if 'user' in session:
        return redirect(url_for('index'))

    # Otherwise, render the login page
    return render_template('login.html')

@app.route('/auth/microsoft')
def auth_microsoft():
    """Initiate Microsoft OAuth authentication flow"""
    auth_url = msal_app.get_authorization_request_url(
        scopes=['User.Read'],
        redirect_uri=REDIRECT_URI
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    error = request.args.get('error')
    error_description = request.args.get('error_description')

    # Handle OAuth errors
    if error:
        session['login_error'] = error_description or 'Authentication failed. Please try again.'
        return redirect(url_for('login'))

    if not code:
        session['login_error'] = 'No authorization code received from Microsoft.'
        return redirect(url_for('login'))

    result = msal_app.acquire_token_by_authorization_code(
        code, scopes=['User.Read'], redirect_uri=REDIRECT_URI
    )

    if 'access_token' in result:
        # Get user info from Microsoft Graph
        headers = {'Authorization': f'Bearer {result["access_token"]}'}
        user_info_response = requests.get(
            'https://graph.microsoft.com/v1.0/me',
            headers=headers
        )

        if user_info_response.status_code == 200:
            user_info = user_info_response.json()
            session['user'] = {
                'name': user_info.get('displayName'),
                'email': user_info.get('userPrincipalName')
            }
            return redirect(url_for('index'))
        else:
            session['login_error'] = 'Failed to get user info from Microsoft Graph.'
            return redirect(url_for('login'))

    session['login_error'] = result.get('error_description', 'Unknown authentication error')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/reports')
@login_required
def reports():
    """List all Power BI reports"""
    try:
        token = get_powerbi_token()
        headers = {'Authorization': f'Bearer {token}'}

        response = requests.get(
            f'https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/reports',
            headers=headers
        )

        if response.status_code == 200:
            reports = response.json().get('value', [])
            return render_template('reports.html', reports=reports, user=session['user'], is_admin=is_admin())
        else:
            return f'Error fetching reports: {response.text}', 500
    except Exception as e:
        return f'Error: {str(e)}', 500

@app.route('/my-reports')
@login_required
def my_reports():
    """List Power BI reports assigned to current user"""
    try:
        # Get user's assigned report IDs
        user_email = session['user']['email']
        allowed_report_ids = get_user_reports(user_email)

        # Fetch all reports from Power BI API
        token = get_powerbi_token()
        headers = {'Authorization': f'Bearer {token}'}

        response = requests.get(
            f'https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/reports',
            headers=headers
        )

        if response.status_code != 200:
            return f'Error fetching reports: {response.text}', 500

        all_reports = response.json().get('value', [])

        # Filter reports based on user access
        user_reports = [
            report for report in all_reports
            if report['id'] in allowed_report_ids
        ]

        return render_template('my_reports.html',
                             reports=user_reports,
                             user=session['user'],
                             is_admin=is_admin())
    except Exception as e:
        return f'Error: {str(e)}', 500

@app.route('/report/<report_id>')
@login_required
def view_report(report_id):
    """View embedded report with RLS"""
    try:
        token = get_powerbi_token()
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

        # Get report details
        report_response = requests.get(
            f'https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/reports/{report_id}',
            headers=headers
        )

        if report_response.status_code != 200:
            return f'Error fetching report: {report_response.text}', 500

        report = report_response.json()
        dataset_id = report['datasetId']

        # Check if dataset has RLS roles defined
        roles_response = requests.get(
            f'https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{dataset_id}/roles',
            headers=headers
        )

        dataset_has_rls = False
        if roles_response.status_code == 200:
            dataset_roles = roles_response.json().get('value', [])
            dataset_has_rls = len(dataset_roles) > 0

        # Build embed token payload
        embed_payload = {
            'datasets': [{'id': dataset_id}],
            'reports': [{'id': report_id}]
        }

        # Only include identities if dataset has RLS roles defined
        if dataset_has_rls:
            user_email = session['user']['email']
            roles = get_user_roles(user_email, dataset_id)

            # DEBUG: Print what we're sending
            print(f"DEBUG RLS - Email: {user_email}, Roles: {roles}, Dataset: {dataset_id}")

            embed_payload['identities'] = [{
                'username': user_email,
                'roles': roles,
                'datasets': [dataset_id]
            }]

        token_response = requests.post(
            'https://api.powerbi.com/v1.0/myorg/GenerateToken',
            headers=headers,
            json=embed_payload
        )

        if token_response.status_code != 200:
            return f'Error generating embed token: {token_response.text}', 500

        embed_token = token_response.json()['token']

        return render_template('view_report.html',
                             report_id=report_id,
                             report_name=report['name'],
                             embed_url=report['embedUrl'],
                             embed_token=embed_token,
                             user=session['user'],
                             is_admin=is_admin(),
                             rls_enabled=dataset_has_rls)
    except Exception as e:
        return f'Error: {str(e)}', 500

@app.route('/admin')
@admin_required
def admin():
    """Admin panel for RLS configuration"""
    try:
        # Get all reports
        token = get_powerbi_token()
        headers = {'Authorization': f'Bearer {token}'}

        reports_response = requests.get(
            f'https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/reports',
            headers=headers
        )

        if reports_response.status_code != 200:
            return f'Error fetching reports: {reports_response.text}', 500

        reports = reports_response.json().get('value', [])

        # Get RLS roles for each dataset
        dataset_roles = {}
        for report in reports:
            dataset_id = report['datasetId']
            if dataset_id not in dataset_roles:
                roles_response = requests.get(
                    f'https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{dataset_id}/roles',
                    headers=headers
                )
                if roles_response.status_code == 200:
                    roles = roles_response.json().get('value', [])
                    dataset_roles[dataset_id] = [r['name'] for r in roles]
                else:
                    dataset_roles[dataset_id] = []

        # Load current mappings
        rls_mappings = load_rls_config()
        report_access_mappings = load_reports_access_config()

        return render_template('admin.html',
                             rls_mappings=rls_mappings,
                             report_access_mappings=report_access_mappings,
                             reports=reports,
                             dataset_roles=dataset_roles,
                             user=session['user'],
                             is_admin=is_admin())
    except Exception as e:
        return f'Error: {str(e)}', 500

@app.route('/admin/save_mapping', methods=['POST'])
@admin_required
def save_mapping():
    """Save user-to-role mapping"""
    try:
        data = request.json
        mappings = load_rls_config()

        # Remove existing mapping for this user and dataset
        mappings = [m for m in mappings if not (
            m['userEmail'].lower() == data['userEmail'].lower() and
            m.get('datasetId') == data['datasetId']
        )]

        # Add new mapping
        new_mapping = {
            'userEmail': data['userEmail'],
            'roles': data['roles'],
            'datasetId': data['datasetId'],
            'createdAt': datetime.utcnow().isoformat(),
            'createdBy': session['user']['email']
        }
        mappings.append(new_mapping)

        save_rls_config(mappings)
        return jsonify({'success': True, 'message': 'Mapping saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/delete_mapping', methods=['POST'])
@admin_required
def delete_mapping():
    """Delete user-to-role mapping"""
    try:
        user_email = request.json['userEmail']
        dataset_id = request.json.get('datasetId')
        mappings = load_rls_config()

        # Remove matching mappings
        if dataset_id:
            mappings = [m for m in mappings if not (
                m['userEmail'].lower() == user_email.lower() and
                m.get('datasetId') == dataset_id
            )]
        else:
            mappings = [m for m in mappings if m['userEmail'].lower() != user_email.lower()]

        save_rls_config(mappings)
        return jsonify({'success': True, 'message': 'Mapping deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/save_report_access', methods=['POST'])
@admin_required
def save_report_access():
    """Save user-to-reports access mapping"""
    try:
        data = request.json
        mappings = load_reports_access_config()

        # Remove existing mapping for this user
        mappings = [m for m in mappings if m['userEmail'].lower() != data['userEmail'].lower()]

        # Add new mapping
        new_mapping = {
            'userEmail': data['userEmail'],
            'reportIds': data['reportIds'],
            'createdAt': datetime.utcnow().isoformat(),
            'createdBy': session['user']['email']
        }
        mappings.append(new_mapping)

        save_reports_access_config(mappings)
        return jsonify({'success': True, 'message': 'Report access saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/delete_report_access', methods=['POST'])
@admin_required
def delete_report_access():
    """Delete user-to-reports access mapping"""
    try:
        user_email = request.json['userEmail']
        mappings = load_reports_access_config()

        # Remove matching mapping
        mappings = [m for m in mappings if m['userEmail'].lower() != user_email.lower()]

        save_reports_access_config(mappings)
        return jsonify({'success': True, 'message': 'Report access deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Check if required environment variables are set
    required_vars = ['TENANT_ID', 'CLIENT_ID', 'CLIENT_SECRET', 'WORKSPACE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please create a .env file based on .env.example and fill in the values.")
        exit(1)

    print("Starting Power BI Embedded POC...")
    print(f"Admin emails: {ADMIN_EMAILS}")
    print("Navigate to http://localhost:5000")
    app.run(debug=True, port=5000)
