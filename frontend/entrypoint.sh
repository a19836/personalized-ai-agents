#!/bin/sh
set -e

# Fetch secrets from Google Secret Manager
# Cloud Run automatically provides credentials via Workload Identity
echo "Fetching secrets from Google Secret Manager..."

VITE_AUTH_API_BASE_URL=$(gcloud secrets versions access latest --secret="VITE_AUTH_API_BASE_URL" 2>&1 || echo "ERROR")
VITE_ARTICLES_API_BASE_URL=$(gcloud secrets versions access latest --secret="VITE_ARTICLES_API_BASE_URL" 2>&1 || echo "ERROR")
VITE_USERS_API_BASE_URL=$(gcloud secrets versions access latest --secret="VITE_USERS_API_BASE_URL" 2>&1 || echo "ERROR")
VITE_AGENTS_API_BASE_URL=$(gcloud secrets versions access latest --secret="VITE_AGENTS_API_BASE_URL" 2>&1 || echo "ERROR")

# Check if secrets were fetched successfully
if [ "$VITE_AUTH_API_BASE_URL" = "ERROR" ] || [ -z "$VITE_AUTH_API_BASE_URL" ]; then
  echo "ERROR: Could not fetch VITE_AUTH_API_BASE_URL"
  echo "Make sure:"
  echo "  1. Secret 'VITE_AUTH_API_BASE_URL' exists in Secret Manager"
  echo "  2. Service account has 'Secret Accessor' role"
  echo "  3. Run: gcloud secrets describe VITE_AUTH_API_BASE_URL"
fi

if [ "$VITE_ARTICLES_API_BASE_URL" = "ERROR" ] || [ -z "$VITE_ARTICLES_API_BASE_URL" ]; then
  echo "ERROR: Could not fetch VITE_ARTICLES_API_BASE_URL"
fi

if [ "$VITE_USERS_API_BASE_URL" = "ERROR" ] || [ -z "$VITE_USERS_API_BASE_URL" ]; then
  echo "ERROR: Could not fetch VITE_USERS_API_BASE_URL"
fi

if [ "$VITE_AGENTS_API_BASE_URL" = "ERROR" ] || [ -z "$VITE_AGENTS_API_BASE_URL" ]; then
  echo "ERROR: Could not fetch VITE_AGENTS_API_BASE_URL"
fi

# Create a JavaScript config file with the secrets
cat > /usr/share/nginx/html/config.js << EOF
window.APP_CONFIG = {
  VITE_AUTH_API_BASE_URL: '${VITE_AUTH_API_BASE_URL}',
  VITE_ARTICLES_API_BASE_URL: '${VITE_ARTICLES_API_BASE_URL}',
  VITE_USERS_API_BASE_URL: '${VITE_USERS_API_BASE_URL}',
  VITE_AGENTS_API_BASE_URL: '${VITE_AGENTS_API_BASE_URL}'
};
EOF

echo "✓ Config loaded"
echo "  Auth API: ${VITE_AUTH_API_BASE_URL}"
echo "  Articles API: ${VITE_ARTICLES_API_BASE_URL}"
echo "  Users API: ${VITE_USERS_API_BASE_URL}"
echo "  Agents API: ${VITE_AGENTS_API_BASE_URL}"

# Start nginx
exec nginx -g "daemon off;"
