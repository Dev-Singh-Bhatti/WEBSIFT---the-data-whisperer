#!/bin/bash
# Quick script to export Docker image as tar file

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Docker Image Export Script${NC}"
echo "=============================="
echo ""

# Check if image exists
if ! docker images | grep -q "myntra-scraper"; then
    echo -e "${RED}Error: Image 'myntra-scraper:latest' not found${NC}"
    echo "Build it first with: docker build -t myntra-scraper:latest ."
    exit 1
fi

# Get output filename
read -p "Enter output filename (default: myntra-scraper.tar.gz): " OUTPUT_FILE
OUTPUT_FILE=${OUTPUT_FILE:-myntra-scraper.tar.gz}

# Ask about compression
read -p "Compress with gzip? (y/n, default: y): " COMPRESS
COMPRESS=${COMPRESS:-y}

echo ""
echo -e "${YELLOW}Exporting image...${NC}"
echo "This may take a while..."

if [ "$COMPRESS" = "y" ] || [ "$COMPRESS" = "Y" ]; then
    # Export and compress
    docker save myntra-scraper:latest | gzip > ${OUTPUT_FILE}
    echo -e "${GREEN}Image exported and compressed: ${OUTPUT_FILE}${NC}"
else
    # Export without compression
    docker save myntra-scraper:latest -o ${OUTPUT_FILE}
    echo -e "${GREEN}Image exported: ${OUTPUT_FILE}${NC}"
fi

# Show file size
FILE_SIZE=$(du -h ${OUTPUT_FILE} | cut -f1)
echo -e "${GREEN}File size: ${FILE_SIZE}${NC}"
echo ""

echo "To import on another device:"
if [ "$COMPRESS" = "y" ] || [ "$COMPRESS" = "Y" ]; then
    echo -e "${GREEN}gunzip -c ${OUTPUT_FILE} | docker load${NC}"
else
    echo -e "${GREEN}docker load -i ${OUTPUT_FILE}${NC}"
fi

echo ""
echo "Then run with:"
echo -e "${GREEN}docker run -d -p 8501:8501 --shm-size=2gb -e MONGO_DB_URL='your_url' myntra-scraper:latest${NC}"

