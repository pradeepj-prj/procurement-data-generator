#!/bin/bash
set -euo pipefail

echo "=== Build UI ==="
(cd ui && npm ci && npm run build)

echo "=== Deploy to CF ==="
cf push procurement-graphrag

echo ""
echo "=== First deploy? Set secrets: ==="
echo "  cf set-env procurement-graphrag HANA_HOST <value>"
echo "  cf set-env procurement-graphrag HANA_USER <value>  # default: DBADMIN (set in manifest)"
echo "  cf set-env procurement-graphrag HANA_PASSWORD <value>"
echo "  cf set-env procurement-graphrag AICORE_AUTH_URL <value>"
echo "  cf set-env procurement-graphrag AICORE_CLIENT_ID <value>"
echo "  cf set-env procurement-graphrag AICORE_CLIENT_SECRET <value>"
echo "  cf set-env procurement-graphrag AICORE_BASE_URL <value>"
echo "  cf set-env procurement-graphrag GENAI_MODEL_NAME anthropic--claude-4.6-opus"
echo "  cf restage procurement-graphrag"
