#!/bin/bash
# Coolify Diagnostic Script

echo "=== HAR File Analyzer Coolify Diagnostic Tool ==="
echo "Running diagnostics at $(date)"
echo

echo "=== Environment Variables ==="
env | grep -E 'COOLIFY|DATABASE|SECRET|JWT|DEBUG|APP_NAME' | sort
echo

echo "=== Directory Structure ==="
ls -la /app
echo
ls -la /app/data
echo

echo "=== User & Permissions ==="
id
echo

echo "=== Database Path Check ==="
DB_PATH=$(grep DATABASE_URL .env | cut -d= -f2 | sed 's/sqlite:\/\/\///' | sed 's/^\///')
echo "Database path from .env: $DB_PATH"

if [ -f "$DB_PATH" ]; then
    echo "Database file exists"
    ls -la "$DB_PATH"
else
    echo "Database file does not exist"
    echo "Attempting to create it..."
    touch "$DB_PATH" 2>&1 || echo "Failed to create database file: $?"
    chmod 666 "$DB_PATH" 2>&1 || echo "Failed to set permissions: $?"
fi
echo

echo "=== SQLite Test ==="
python3 -c "
import sqlite3
try:
    db_path = '$DB_PATH'
    print(f'Testing SQLite connection to {db_path}')
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE IF NOT EXISTS coolify_test (id INTEGER PRIMARY KEY)')
    conn.execute('INSERT INTO coolify_test VALUES (1)')
    conn.commit()
    print('SQLite test successful')
    conn.close()
except Exception as e:
    print(f'SQLite test failed: {str(e)}')
"
echo

echo "=== In-Memory SQLite Test ==="
python3 -c "
import sqlite3
try:
    print('Testing in-memory SQLite connection')
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE coolify_test (id INTEGER PRIMARY KEY)')
    conn.execute('INSERT INTO coolify_test VALUES (1)')
    result = conn.execute('SELECT * FROM coolify_test').fetchone()
    print(f'SQLite in-memory test successful, retrieved: {result}')
    conn.close()
except Exception as e:
    print(f'SQLite in-memory test failed: {str(e)}')
"
echo

echo "=== Python Import Test ==="
python3 -c "
try:
    import fastapi
    import sqlalchemy
    import uvicorn
    import pydantic
    print('All required packages are installed')
except ImportError as e:
    print(f'Missing package: {str(e)}')
"
echo

echo "=== End of Diagnostics ===" 