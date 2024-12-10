#!/bin/bash

PROJECT_ID="YOUR_PROJECT_ID"
REGION="YOUR_PREFERRED_REGION"
ARTIFACT_REGISTRY="YOUR_REGISTRY_NAME"
IMAGE_NAME="news-scraper"
SERVICE_NAME="news-scraper-service"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "Starting deployment process..."

echo -e "${GREEN}Building Docker image...${NC}"
docker build -t ${IMAGE_NAME} .
if [ $? -ne 0 ]; then
    echo -e "${RED}Docker build failed${NC}"
    exit 1
fi

echo -e "${GREEN}Tagging image...${NC}"
docker tag ${IMAGE_NAME} ${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY}/${IMAGE_NAME}

echo -e "${GREEN}Pushing to Artifact Registry...${NC}"
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY}/${IMAGE_NAME}
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to push image to Artifact Registry${NC}"
    exit 1
fi

echo -e "${GREEN}Deploying to Cloud Run...${NC}"
gcloud run deploy ${SERVICE_NAME} \
    --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY}/${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID}" \
    --set-env-vars "BQ_DATASET_ID=news_data" \
    --set-env-vars "BQ_TABLE_ID=articles" \
    --service-account="news-scraper@${PROJECT_ID}.iam.gserviceaccount.com"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Deployment completed successfully!${NC}"
else
    echo -e "${RED}Deployment failed${NC}"
    exit 1
fi