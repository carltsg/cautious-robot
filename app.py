from flask import Flask, render_template, session, redirect, url_for, request, jsonify
from msal import ConfidentialClientApplication
import requests
import json
import os
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
import logging
import sys

# Configure logging to stdout for Azure
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize database connection
from models import init_db
db_engine, DBSession = init_db()
if DBSession:
    logger.info("✓ Database connected (SQL mode)")
    import models
    models.db_engine = db_engine
    models.DBSession = DBSession

    # Bootstrap admin users from environment variable
    try:
        from db_helpers import add_admin_user
        admin_emails_env = os.getenv('ADMIN_EMAILS', '')
        if admin_emails_env:
            for email in admin_emails_env.split(','):
                email = email.strip()
                if email:
                    try:
                        result = add_admin_user(
                            email=email,
                            created_by='system_bootstrap',
                            is_super_admin=True  # First admins are super admins
                        )
                        if result:
                            logger.info(f"✓ Bootstrapped admin user: {email}")
                    except Exception as e:
                        logger.warning(f"⚠ Failed to bootstrap admin {email}: {e}")
    except Exception as e:
        logger.error(f"⚠ Admin bootstrap failed (non-fatal): {e}")
else:
    logger.info("⚠ Database not configured - using JSON files")

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
    """Check if current user is an admin (uses database)"""
    if 'user' not in session:
        return False
    user_email = session['user']['email']
    from db_helpers import is_user_admin
    return is_user_admin(user_email)

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
        logger.debug(f"Admin check: user='{user_email.lower()}', admins={admin_list}, match={user_email.lower() in admin_list}")

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

            # Log login activity
            from db_helpers import log_user_activity
            log_user_activity(
                activity_type='login',
                user_email=session['user']['email'],
                user_name=session['user']['name'],
                request=request
            )

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
    """View embedded report with RLS using smart fallback strategy"""
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
        user_email = session['user']['email']

        # Log report view activity
        from db_helpers import log_user_activity
        log_user_activity(
            activity_type='view_report',
            user_email=user_email,
            user_name=session['user'].get('name'),
            report_id=report_id,
            report_name=report.get('name'),
            request=request
        )

        logger.info(f"RLS Fallback - Generating embed token for dataset {dataset_id}, user {user_email}")

        # Build embed token payload WITHOUT identity (try this first)
        embed_payload = {
            'datasets': [{'id': dataset_id}],
            'reports': [{'id': report_id}]
        }

        logger.info(f"RLS Fallback - Attempt 1: Trying WITHOUT identity")
        token_response = requests.post(
            'https://api.powerbi.com/v1.0/myorg/GenerateToken',
            headers=headers,
            json=embed_payload
        )

        # Check if it failed due to RLS requirement
        rls_enabled = False
        if token_response.status_code != 200:
            error_text = token_response.text.lower()
            requires_identity = 'requires effective identity' in error_text

            if requires_identity:
                # Dataset has RLS - retry WITH identity
                logger.info(f"RLS Fallback - Attempt 1 failed: Power BI requires identity (RLS detected)")
                roles = get_user_roles(user_email, dataset_id)

                logger.info(f"RLS Fallback - Attempt 2: Retrying WITH identity - Email={user_email}, Roles={roles}")

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

                rls_enabled = True

                if token_response.status_code != 200:
                    logger.error(f"RLS Fallback - Attempt 2 FAILED: {token_response.text}")
                    return f'Error generating embed token with RLS: {token_response.text}', 500
                else:
                    logger.info(f"RLS Fallback - Attempt 2 SUCCESS: Token generated with identity")
            else:
                # Failed for a different reason
                logger.error(f"RLS Fallback - Attempt 1 failed for non-RLS reason: {token_response.text}")
                return f'Error generating embed token: {token_response.text}', 500
        else:
            # Success without identity - no RLS on this dataset
            logger.info(f"RLS Fallback - Attempt 1 SUCCESS: Token generated without identity (no RLS)")

        embed_token = token_response.json()['token']

        return render_template('view_report.html',
                             report_id=report_id,
                             report_name=report['name'],
                             embed_url=report['embedUrl'],
                             embed_token=embed_token,
                             user=session['user'],
                             is_admin=is_admin(),
                             rls_enabled=rls_enabled)
    except Exception as e:
        logger.error(f"Exception in view_report: {str(e)}")
        return f'Error: {str(e)}', 500

@app.route('/admin')
@admin_required
def admin():
    """Admin panel for report access configuration"""
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

        # Load report access mappings
        report_access_mappings = load_reports_access_config()

        # Get recent users for dropdown
        from db_helpers import get_recent_users, get_user_activity_stats, get_total_logins, get_all_admins
        recent_users = get_recent_users(limit=50)

        # Get activity statistics (last 30 days)
        top_reports = get_user_activity_stats(days=30)
        total_logins = get_total_logins(days=30)

        # Calculate total views from top_reports
        total_views = sum(stat['view_count'] for stat in top_reports) if top_reports else 0

        activity_stats = {
            'active_users': len(recent_users),
            'total_logins': total_logins,
            'total_views': total_views,
            'top_reports': top_reports
        }

        # Get admin users
        admin_users = get_all_admins()

        return render_template('admin.html',
                             reports=reports,
                             report_access_mappings=report_access_mappings,
                             recent_users=recent_users,
                             activity_stats=activity_stats,
                             admin_users=admin_users,
                             user=session['user'],
                             is_admin=is_admin())
    except Exception as e:
        return f'Error: {str(e)}', 500

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

@app.route('/admin/add_admin', methods=['POST'])
@admin_required
def add_admin():
    """Add a new admin user"""
    try:
        data = request.json
        from db_helpers import add_admin_user

        success = add_admin_user(
            email=data['email'],
            name=data.get('name'),
            created_by=session['user']['email'],
            is_super_admin=False
        )

        if success:
            logger.info(f"Admin user added: {data['email']} by {session['user']['email']}")
            return jsonify({'success': True, 'message': 'Admin added successfully'})
        else:
            return jsonify({'success': False, 'error': 'Admin already exists'}), 400
    except Exception as e:
        logger.error(f"Failed to add admin: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/remove_admin', methods=['POST'])
@admin_required
def remove_admin():
    """Remove an admin user"""
    try:
        data = request.json
        user_email = session['user']['email']

        # Prevent removing yourself
        if data['email'].lower() == user_email.lower():
            return jsonify({'success': False, 'error': 'Cannot remove yourself'}), 400

        from db_helpers import remove_admin_user
        success = remove_admin_user(data['email'])

        if success:
            logger.info(f"Admin user removed: {data['email']} by {user_email}")
            return jsonify({'success': True, 'message': 'Admin removed successfully'})
        else:
            return jsonify({'success': False, 'error': 'Admin not found'}), 404
    except Exception as e:
        logger.error(f"Failed to remove admin: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Check if required environment variables are set
    required_vars = ['TENANT_ID', 'CLIENT_ID', 'CLIENT_SECRET', 'WORKSPACE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please create a .env file based on .env.example and fill in the values.")
        exit(1)

    logger.info("Starting Power BI Embedded POC...")
    logger.info(f"Admin emails: {ADMIN_EMAILS}")
    logger.info("Navigate to http://localhost:5000")
    app.run(debug=True, port=5000)
