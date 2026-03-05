# Azure App Service Cold Start Optimization

## Current Issue
The app experiences slow cold starts (60-90 seconds) due to:
1. Virtual environment extraction (~42 seconds)
2. Database connection initialization (~29 seconds)
3. App Service instance sleeping after idle period

## Immediate Solutions

### 1. Enable "Always On" (Recommended)
**Cost:** Available on Basic tier and above (already on Basic)
**Effect:** Keeps your app loaded even during idle periods

```bash
# Enable via Azure CLI
az webapp config set --name tsgpbiembed --resource-group tsgpbiembed_group --always-on true

# OR via Azure Portal:
# 1. Go to your App Service
# 2. Settings > Configuration > General settings
# 3. Set "Always On" to "On"
# 4. Click "Save"
```

### 2. Configure Health Check Endpoint
**Cost:** Free
**Effect:** Azure pings the endpoint regularly to keep app warm

```bash
# Configure via Azure CLI
az webapp config set --name tsgpbiembed --resource-group tsgpbiembed_group --health-check-path "/health"

# OR via Azure Portal:
# 1. Go to your App Service
# 2. Monitoring > Health check
# 3. Enable health check
# 4. Set path to: /health
# 5. Click "Save"
```

### 3. Add Application Initialization (web.config)
**Cost:** Free
**Effect:** Warms up specific routes during startup

Create or update `web.config` in your project root:

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <applicationInitialization>
      <add initializationPage="/health" />
    </applicationInitialization>
  </system.webServer>
</configuration>
```

## Medium-term Solutions

### 4. Optimize Database Connection Pool
Already implemented in `models.py`:
- pool_pre_ping: Tests connections before use
- pool_recycle: 1800s (recycles before Azure timeout)
- pool_size: 5 connections
- timeout: 10 seconds

Consider if database tier can be upgraded or if connection can be lazy-loaded.

### 5. Use Application Insights
Monitor cold start times and identify bottlenecks:

```bash
# Enable Application Insights
az monitor app-insights component create --app tsgpbiembed-insights --location uksouth --resource-group tsgpbiembed_group --application-type web

# Connect to App Service
az webapp config appsettings set --name tsgpbiembed --resource-group tsgpbiembed_group --settings APPLICATIONINSIGHTS_CONNECTION_STRING="<connection-string>"
```

### 6. Azure Monitor Ping
Set up external monitoring to ping your health endpoint every 5 minutes:
- Azure Monitor Availability Tests
- Or use external service like UptimeRobot (free)

## Long-term Solutions

### 7. Consider Premium Tier
- Premium tier provides:
  - Pre-warmed instances
  - Faster scaling
  - Better performance
- Cost: ~$75-150/month

### 8. Optimize Virtual Environment Size
Current approach uses Oryx build with compressed tarball.
- Review dependencies in requirements.txt
- Remove unused packages
- Consider Docker container for faster startup

## Expected Results

| Optimization | Expected Improvement |
|-------------|---------------------|
| Always On | Eliminates most cold starts |
| Health Check | Reduces cold start frequency |
| Combined | First load: 60s → 5s, Subsequent: <2s |

## Implementation Priority

1. **High Priority (Do Now):**
   - Enable "Always On"
   - Configure Health Check endpoint

2. **Medium Priority (This Week):**
   - Set up external monitoring/ping
   - Add Application Insights

3. **Low Priority (Future):**
   - Consider tier upgrade if budget allows
   - Optimize dependencies

## Monitoring

After implementing, monitor these metrics:
- Average response time for `/health` endpoint
- Number of cold starts per day
- Time to first byte (TTFB) for `/login` page

Use Azure App Service Logs and Application Insights for detailed analysis.
