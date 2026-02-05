#!/bin/bash
# Setup script for PostgreSQL database
# Uses "super graph" server configuration

set -e

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

DB_NAME="super_graph_db"
DB_USER="${POSTGRES_USER:-manideepbangaru}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

echo "=== LangGraph PostgreSQL Database Setup ==="
echo "Database: $DB_NAME"
echo "Host: $DB_HOST:$DB_PORT"
echo "User: $DB_USER"
echo ""

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "Error: psql command not found. Please install PostgreSQL client."
    exit 1
fi

# Build psql connection arguments
# Use socket connection if host is localhost (default on macOS)
if [ "$DB_HOST" = "localhost" ] || [ -z "$DB_HOST" ]; then
    PSQL_ARGS="-U $DB_USER"
else
    PSQL_ARGS="-h $DB_HOST -p $DB_PORT -U $DB_USER"
fi

# Check if database exists
if psql $PSQL_ARGS -d postgres -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo "Database '$DB_NAME' already exists."
else
    echo "Creating database '$DB_NAME'..."
    psql $PSQL_ARGS -d postgres -c "CREATE DATABASE $DB_NAME;" || {
        echo "Error: Failed to create database. Trying with template0..."
        psql $PSQL_ARGS -d postgres -c "CREATE DATABASE $DB_NAME WITH TEMPLATE template0;"
    }
    echo "Database created successfully!"
fi

echo ""
echo "=== Verifying connection ==="
psql $PSQL_ARGS -d "$DB_NAME" -c "SELECT 'Connection successful!' as status;"

echo ""
echo "=== Setup Complete ==="
echo "Database '$DB_NAME' is ready to use."
echo ""
echo "Connection string (already in .env):"
echo "POSTGRES_URI=postgresql://$DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
