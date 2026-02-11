/**
 * Embed a Power BI report with RLS applied
 * @param {string} reportId - The Power BI report ID
 * @param {string} embedUrl - The embed URL for the report
 * @param {string} accessToken - The embed token with RLS
 */
function embedReport(reportId, embedUrl, accessToken) {
    console.log('Starting Power BI embed...');
    console.log('Report ID:', reportId);
    console.log('Embed URL:', embedUrl);
    console.log('Token length:', accessToken ? accessToken.length : 0);

    const embedContainer = document.getElementById('embedContainer');

    if (!embedContainer) {
        console.error('Embed container not found');
        showError('Embed container not found on page');
        return;
    }

    // Check if Power BI library loaded
    if (typeof powerbi === 'undefined') {
        console.error('Power BI JavaScript library not loaded');
        showError('Power BI library failed to load. Check your internet connection.');
        return;
    }

    console.log('Power BI library loaded successfully');
    console.log('Available on powerbi object:', Object.keys(powerbi));

    // Power BI embed configuration - simplified without models
    const config = {
        type: 'report',
        id: reportId,
        embedUrl: embedUrl,
        accessToken: accessToken,
        tokenType: 1, // Embed token
        settings: {
            filterPaneEnabled: true,
            navContentPaneEnabled: true,
            panes: {
                filters: {
                    expanded: false,
                    visible: true
                },
                pageNavigation: {
                    visible: true
                }
            }
        }
    };

    console.log('Embed config:', config);

    // Show loading indicator
    embedContainer.innerHTML = '<div style="padding: 40px; text-align: center;"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-3">Loading report...</p></div>';

    try {
        // Embed the report
        const report = powerbi.embed(embedContainer, config);
        console.log('Embed initiated successfully');

    // Event handlers
    report.on('loaded', function() {
        console.log('Report loaded successfully');
        embedContainer.style.opacity = '1';
    });

    report.on('rendered', function() {
        console.log('Report rendered successfully');
    });

    report.on('error', function(event) {
        console.error('Report error:', event.detail);
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger mt-3';
        errorDiv.innerHTML = `
            <h4 class="alert-heading">Error Loading Report</h4>
            <p>${event.detail.message || 'An error occurred while loading the report.'}</p>
        `;
        embedContainer.parentNode.insertBefore(errorDiv, embedContainer);
    });

    report.on('pageChanged', function(event) {
        console.log('Page changed:', event.detail.newPage.displayName);
    });
    } catch (error) {
        console.error('Exception during embed:', error);
        showError('Failed to embed report: ' + error.message);
    }
}

/**
 * Show error message on page
 */
function showError(message) {
    const embedContainer = document.getElementById('embedContainer');
    if (embedContainer) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger';
        errorDiv.innerHTML = `
            <h4 class="alert-heading">Error Loading Report</h4>
            <p>${message}</p>
            <hr>
            <p class="mb-0">Check the browser console (F12) for more details.</p>
        `;
        embedContainer.innerHTML = '';
        embedContainer.appendChild(errorDiv);
    }
}
