#!/bin/bash
# Git commands to commit today's work to GitHub

# Stage all changes
git add diagrams/09_dual_pipeline_architecture.png
git add diagrams/09_dual_pipeline_architecture.puml
git add diagrams/README_PNG_GENERATION.md
git add apiApp/tests/test_admin_portal_regression.py
git add webApp/templates/webApp/dashboard.html
git add README.md
git add replit.md

# Commit with descriptive message
git commit -m "feat: Add dual-pipeline architecture diagram and admin portal regression tests

- Add dual-pipeline architecture diagram (PNG + PlantUML) with cyberpunk theme
- Create comprehensive admin portal regression test suite (18 test cases)
- Fix dashboard Pipeline Mode text wrapping for long values
- Consolidate documentation from 27 to 9 files for better organization
- Update README with clear documentation structure
- Apply migrations 0001-0006 for schema consistency"

# Push to GitHub
git push origin main

echo "✅ Changes pushed to GitHub successfully!"
