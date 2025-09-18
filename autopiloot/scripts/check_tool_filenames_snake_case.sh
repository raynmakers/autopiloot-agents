#!/bin/bash

# Script to enforce snake_case filenames in */tools/ directories
# Fails CI when any tool filename is not snake_case

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Checking tool filenames for snake_case compliance..."

# Find all Python files in tools directories, excluding __init__.py and venv
# Handle both running from project root and from autopiloot directory
if [ -d "autopiloot" ]; then
    # Running from project root
    tools_files=$(find autopiloot -path "*/tools/*.py" -not -path "*/venv/*" -not -name "__init__.py" | sort)
else
    # Running from autopiloot directory
    tools_files=$(find . -path "*/tools/*.py" -not -path "*/venv/*" -not -name "__init__.py" | sort)
fi

if [ -z "$tools_files" ]; then
    echo -e "${YELLOW}⚠️  No tool files found to check${NC}"
    exit 0
fi

echo "📁 Found $(echo "$tools_files" | wc -l) tool files to check"

# Snake case pattern: lowercase letters, numbers, and underscores only
snake_case_pattern='^[a-z0-9_]+\.py$'
violations=0

for file in $tools_files; do
    filename=$(basename "$file")

    if [[ ! $filename =~ $snake_case_pattern ]]; then
        echo -e "${RED}❌ VIOLATION: $file${NC}"
        echo -e "   Filename '$filename' is not snake_case"
        echo -e "   Expected pattern: lowercase letters, numbers, and underscores only"
        violations=$((violations + 1))
    else
        echo -e "${GREEN}✅ $file${NC}"
    fi
done

echo ""
if [ $violations -eq 0 ]; then
    echo -e "${GREEN}🎉 All tool filenames are snake_case compliant!${NC}"
    exit 0
else
    echo -e "${RED}💥 Found $violations filename violation(s)${NC}"
    echo ""
    echo -e "${YELLOW}📋 Snake case requirements:${NC}"
    echo "   - Use only lowercase letters (a-z)"
    echo "   - Use only numbers (0-9)"
    echo "   - Use only underscores (_) as separators"
    echo "   - No hyphens, spaces, or uppercase letters"
    echo "   - Examples: my_tool.py, data_processor.py, api_client.py"
    echo ""
    echo -e "${RED}Fix the violations above and re-run this script.${NC}"
    exit 1
fi