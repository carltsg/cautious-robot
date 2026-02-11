/**
 * Embed a Power BI report with RLS applied
 * @param {string} reportId - The Power BI report ID
 * @param {string} embedUrl - The embed URL for the report
 * @param {string} accessToken - The embed token with RLS
 */
function embedReport(reportId, embedUrl, accessToken) {
    const embedContainer = document.getElementById('embedContainer');

    if (!embedContainer) {
        console.error('Embed container not found');
        return;
    }

    // Power BI embed configuration
    const config = {
        type: 'report',
        id: reportId,
        embedUrl: embedUrl,
        accessToken: accessToken,
        permissions: models.Permissions.Read,
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
            },
            background: models.BackgroundType.Transparent
        }
    };

    // Embed the report
    const report = powerbi.embed(embedContainer, config);

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
}
