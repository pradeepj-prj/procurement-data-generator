#!/usr/bin/env bash
# Deploy procurement data to EC2 Postgres instance.
#
# Usage:
#   bash scripts/deploy_to_ec2.sh [--dry-run]
#
# Prerequisites:
#   - SSH key at ~/.ssh/kp-2.pem
#   - Generated Postgres SQL in output/postgres/
#   - EC2 instance reachable at the configured IP

set -euo pipefail

# --- Load .env if present ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    # shellcheck disable=SC1091
    set -a; source "$PROJECT_ROOT/.env"; set +a
fi

# --- Configuration (override via .env or environment) ---
: "${EC2_IP:?'EC2_IP not set. Copy .env.example to .env and fill in values.'}"
: "${SSH_KEY:?'SSH_KEY not set.'}"
SSH_USER="${SSH_USER:-ubuntu}"
DB_NAME="${DB_NAME:-procurement_demo}"
DB_USER="${DB_USER:-procurement_user}"
DB_SCHEMA="${DB_SCHEMA:-procurement}"
LOCAL_SQL_DIR="${LOCAL_SQL_DIR:-output/postgres}"
REMOTE_DIR="/tmp/procurement_load"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[DRY RUN] Commands will be printed but not executed."
    echo ""
fi

run_cmd() {
    if $DRY_RUN; then
        echo "  [CMD] $*"
    else
        "$@"
    fi
}

# --- Validate local files ---
if [[ ! -d "$LOCAL_SQL_DIR" ]]; then
    echo "ERROR: $LOCAL_SQL_DIR not found. Run 'python -m procurement_generator --scale 1' first."
    exit 1
fi

if [[ ! -f "$LOCAL_SQL_DIR/_load_all.sql" ]]; then
    echo "ERROR: $LOCAL_SQL_DIR/_load_all.sql not found."
    exit 1
fi

if [[ ! -f "$SSH_KEY" ]]; then
    echo "ERROR: SSH key not found at $SSH_KEY"
    exit 1
fi

echo "=== Procurement Data Deployment ==="
echo "  EC2:        $SSH_USER@$EC2_IP"
echo "  Key:        $SSH_KEY"
echo "  Database:   $DB_NAME"
echo "  Schema:     $DB_SCHEMA"
echo "  User:       $DB_USER"
echo "  Local SQL:  $LOCAL_SQL_DIR"
echo ""

# --- Step 1: Upload SQL files ---
echo "--- Step 1: Uploading SQL files to $REMOTE_DIR ---"
run_cmd ssh -i "$SSH_KEY" "$SSH_USER@$EC2_IP" "mkdir -p $REMOTE_DIR"
run_cmd scp -i "$SSH_KEY" -r "$LOCAL_SQL_DIR/"* "$SSH_USER@$EC2_IP:$REMOTE_DIR/"

# --- Step 2: Create DB user and database (idempotent) ---
echo ""
echo "--- Step 2: Creating user and database (if needed) ---"
if $DRY_RUN; then
    echo "  [CMD] ssh ... \"sudo -u postgres psql\" (create role $DB_USER if not exists)"
    echo "  [CMD] ssh ... \"sudo -u postgres createdb $DB_NAME -O $DB_USER\" (if not exists)"
    echo "  [CMD] ssh ... \"sudo -u postgres psql -d $DB_NAME\" (grant privileges)"
else
    # Create role if not exists
    ssh -i "$SSH_KEY" "$SSH_USER@$EC2_IP" \
        "sudo -u postgres psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'\" | grep -q 1 || sudo -u postgres psql -c \"CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_USER';\""

    # Create database if not exists
    ssh -i "$SSH_KEY" "$SSH_USER@$EC2_IP" \
        "sudo -u postgres psql -tAc \"SELECT 1 FROM pg_database WHERE datname='$DB_NAME'\" | grep -q 1 || sudo -u postgres createdb $DB_NAME -O $DB_USER"

    # Grant privileges
    ssh -i "$SSH_KEY" "$SSH_USER@$EC2_IP" \
        "sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;\""
fi

# --- Step 3: Load data ---
echo ""
echo "--- Step 3: Loading data into $DB_NAME.$DB_SCHEMA ---"
run_cmd ssh -i "$SSH_KEY" "$SSH_USER@$EC2_IP" \
    "cd $REMOTE_DIR && sudo -u postgres psql -d $DB_NAME -f _load_all.sql"

# --- Step 4: Verify ---
echo ""
echo "--- Step 4: Verification ---"
run_cmd ssh -i "$SSH_KEY" "$SSH_USER@$EC2_IP" \
    "sudo -u postgres psql -d $DB_NAME -c \"SELECT table_name, (xpath('/row/cnt/text()', xml_count))[1]::text::int AS row_count FROM (SELECT table_name, query_to_xml('SELECT count(*) AS cnt FROM $DB_SCHEMA.' || table_name, false, true, '') AS xml_count FROM information_schema.tables WHERE table_schema = '$DB_SCHEMA') t ORDER BY table_name;\""

# --- Cleanup ---
echo ""
echo "--- Cleanup: Removing temp files ---"
run_cmd ssh -i "$SSH_KEY" "$SSH_USER@$EC2_IP" "rm -rf $REMOTE_DIR"

echo ""
echo "=== Deployment complete ==="
echo "Connect: psql -h $EC2_IP -U $DB_USER -d $DB_NAME"
