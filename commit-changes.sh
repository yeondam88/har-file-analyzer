#!/bin/bash

# Script to commit our database permission fixes

echo "Adding modified files to git..."
git add Dockerfile src/db/session.py src/db/init_db.py coolify.sh commit-changes.sh

echo "Committing changes..."
git commit -m "Fix: Enhanced SQLite database handling for Coolify environment

- Added SQLite diagnostics script (coolify.sh)
- Updated Dockerfile to support Coolify environment better
- Enhanced database session with connection retries and better error handling
- Improved init_db.py with diagnostics and permission fixes
- Added fallback to in-memory database as last resort"

echo "Completed commit of database fixes" 