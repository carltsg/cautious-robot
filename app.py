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

# Load configuration
TENANT_ID = os.getenv('TENANT_ID')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
WORKSPACE_ID = os.getenv('WORKSPACE_ID')
ADMIN_EMAILS = os.getenv('ADMIN_EMAILS', '').split(',')
AUTHORITY = f'https://login.microsoftonline.com/{TENANT_ID}'
REDIRECT_URI = 'http://localhost:5000/callback'
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

def load_rls_config():
    """Load RLS configuration from JSON file"""
    if not os.path.exists('rls-config.json'):
        return []
    with open('rls-config.json', 'r') as f:
        return json.load(f)

def save_rls_config(config):
    """Save RLS configuration to JSON file"""
    with open('rls-config.json', 'w') as f:
        json.dump(config, f, indent=2)

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
        # Clean up admin emails and compare
        admin_list = [email.strip() for email in ADMIN_EMAILS]
        if user_email not in admin_list:
            return 'Unauthorized - Admin access required', 403
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
@login_required
def index():
    return render_template('index.html', user=session['user'], admin_emails=ADMIN_EMAILS)

@app.route('/login')
def login():
    auth_url = msal_app.get_authorization_request_url(
        scopes=['User.Read'],
        redirect_uri=REDIRECT_URI
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return 'No authorization code received', 400

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
            return f'Failed to get user info: {user_info_response.text}', 400

    return f'Login failed: {result.get("error_description", "Unknown error")}', 400

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
            return render_template('reports.html', reports=reports, user=session['user'], admin_emails=ADMIN_EMAILS)
        else:
            return f'Error fetching reports: {response.text}', 500
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

        # Get user's RLS roles
        user_email = session['user']['email']
        roles = get_user_roles(user_email, report['datasetId'])

        # Generate embed token with RLS
        embed_payload = {
            'datasets': [{'id': report['datasetId']}],
            'reports': [{'id': report_id}],
            'identities': [{
                'username': user_email,
                'roles': roles,
                'datasets': [report['datasetId']]
            }]
        }

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
                             admin_emails=ADMIN_EMAILS)
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
        mappings = load_rls_config()

        return render_template('admin.html',
                             mappings=mappings,
                             reports=reports,
                             dataset_roles=dataset_roles,
                             user=session['user'],
                             admin_emails=ADMIN_EMAILS)
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
