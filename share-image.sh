#!/bin/bash
# Quick script to share Docker image via Docker Hub

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Docker Image Sharing Script${NC}"
echo "================================"
echo ""

# Check if image exists
if ! docker images | grep -q "myntra-scraper"; then
    echo -e "${RED}Error: Image 'myntra-scraper:latest' not found${NC}"
    echo "Build it first with: docker build -t myntra-scraper:latest ."
    exit 1
fi

# Get Docker Hub username
read -p "Enter your Docker Hub username: " DOCKERHUB_USERNAME

if [ -z "$DOCKERHUB_USERNAME" ]; then
    echo -e "${RED}Error: Docker Hub username is required${NC}"
    exit 1
fi

# Get version tag (optional)
read -p "Enter version tag (default: latest): " VERSION_TAG
VERSION_TAG=${VERSION_TAG:-latest}

# Tag the image
echo -e "${YELLOW}Tagging image...${NC}"
docker tag myntra-scraper:latest ${DOCKERHUB_USERNAME}/myntra-scraper:${VERSION_TAG}
docker tag myntra-scraper:latest ${DOCKERHUB_USERNAME}/myntra-scraper:latest

echo -e "${GREEN}Image tagged successfully!${NC}"
echo ""

# Login to Docker Hub
echo -e "${YELLOW}Logging in to Docker Hub...${NC}"
docker login

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Docker Hub login failed${NC}"
    exit 1
fi

# Push the image
echo -e "${YELLOW}Pushing image to Docker Hub...${NC}"
echo "This may take a while depending on your internet speed..."
docker push ${DOCKERHUB_USERNAME}/myntra-scraper:${VERSION_TAG}
docker push ${DOCKERHUB_USERNAME}/myntra-scraper:latest

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}Success! Image pushed to Docker Hub${NC}"
    echo ""
    echo "To pull on another device, run:"
    echo -e "${GREEN}docker pull ${DOCKERHUB_USERNAME}/myntra-scraper:latest${NC}"
    echo ""
    echo "Then run with:"
    echo -e "${GREEN}docker run -d -p 8501:8501 --shm-size=2gb -e MONGO_DB_URL='your_url' ${DOCKERHUB_USERNAME}/myntra-scraper:latest${NC}"
else
    echo -e "${RED}Error: Failed to push image${NC}"
    exit 1
fi

