#!/bin/bash
#
# Run RAG pipeline tests with coverage reporting
#
# This script:
# 1. Runs all RAG-related unit tests
# 2. Runs integration tests
# 3. Generates HTML coverage reports
# 4. Displays coverage summary
#
# Usage:
#   ./scripts/run_rag_tests_with_coverage.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}RAG Pipeline Test Coverage Report${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Set PYTHONPATH
export PYTHONPATH=.

# Create coverage directory
mkdir -p coverage/rag_pipeline

# Erase previous coverage data
echo -e "${YELLOW}Clearing previous coverage data...${NC}"
coverage erase

# Run unit tests for RAG tools
echo -e "${YELLOW}Running RAG unit tests...${NC}"
coverage run --source=summarizer_agent -m unittest discover tests/summarizer_tools -p "test_*rag*.py" -v

# Run integration tests
echo -e "${YELLOW}Running RAG integration tests...${NC}"
coverage run --append --source=summarizer_agent -m unittest discover tests/integration -p "test_rag*.py" -v

# Generate coverage reports
echo ""
echo -e "${YELLOW}Generating coverage reports...${NC}"

# Terminal report
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Coverage Summary${NC}"
echo -e "${GREEN}========================================${NC}"
coverage report --include="summarizer_agent/tools/*rag*.py,summarizer_agent/tools/*zep*.py,summarizer_agent/tools/*opensearch*.py,summarizer_agent/tools/*bigquery*.py,summarizer_agent/tools/*experiment*.py"

# HTML report
coverage html --include="summarizer_agent/tools/*rag*.py,summarizer_agent/tools/*zep*.py,summarizer_agent/tools/*opensearch*.py,summarizer_agent/tools/*bigquery*.py,summarizer_agent/tools/*experiment*.py" -d coverage/rag_pipeline

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}HTML Coverage Report Generated${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "View report: ${YELLOW}coverage/rag_pipeline/index.html${NC}"
echo ""

# Check coverage threshold
COVERAGE_PERCENTAGE=$(coverage report --include="summarizer_agent/tools/*rag*.py,summarizer_agent/tools/*zep*.py,summarizer_agent/tools/*opensearch*.py,summarizer_agent/tools/*bigquery*.py,summarizer_agent/tools/*experiment*.py" | grep TOTAL | awk '{print $4}' | sed 's/%//')

if [ -n "$COVERAGE_PERCENTAGE" ]; then
    if (( $(echo "$COVERAGE_PERCENTAGE >= 80" | bc -l) )); then
        echo -e "${GREEN}✅ Coverage threshold met: ${COVERAGE_PERCENTAGE}% >= 80%${NC}"
        exit 0
    else
        echo -e "${RED}❌ Coverage threshold not met: ${COVERAGE_PERCENTAGE}% < 80%${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  Could not determine coverage percentage${NC}"
    exit 0
fi
