## News Scraper and BigQuery Integration Challenge

A Python-based web scraper that collects news articles from Yogonet, processes them, and stores them in Google BigQuery. The application is containerized with Docker and can be deployed to Google Cloud Run.

### Prerequisites

- Docker installed ([Docker Installation Guide](https://docs.docker.com/get-started/))
- Google Cloud CLI installed ([gcloud Installation Guide](https://cloud.google.com/sdk/docs/install))
- A Google Cloud Project with enabled:
  - BigQuery API
  - Cloud Run API
  - Artifact Registry API

### Environment Variables

The application requires the following environment variables:

| Variable                     | Description                                 |
|------------------------------|---------------------------------------------|
| `GCP_PROJECT_ID`             | Your Google Cloud Project ID               |
| `BQ_DATASET_ID`              | BigQuery dataset name (default: `news_data`) |
| `BQ_TABLE_ID`                | BigQuery table name (default: `articles`)  |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account credentials   |

### Setup

1. **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2. **Configure Google Cloud:**
    ```bash
    # Login to Google Cloud
    gcloud auth login

    # Set your project ID
    gcloud config set project YOUR_PROJECT_ID

    # Create a service account
    gcloud iam service-accounts create news-scraper \
        --display-name="News Scraper Service Account"

    # Grant necessary permissions
    gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
        --member="serviceAccount:news-scraper@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/bigquery.admin"

    # Download service account key (saved as `credentials.json`)
    gcloud iam service-accounts keys create credentials.json \
        --iam-account=news-scraper@YOUR_PROJECT_ID.iam.gserviceaccount.com
    ```

3. **Create BigQuery Dataset:**
    ```bash
    bq mk --dataset YOUR_PROJECT_ID:news_data
    ```

### Configuration

Update the following variables in `deploy.sh`:
```bash
PROJECT_ID="YOUR_PROJECT_ID"
REGION="YOUR_PREFERRED_REGION"
ARTIFACT_REGISTRY="YOUR_REGISTRY_NAME"
```

### Local Development

1. **Build the Docker image:**
```bash
docker build -t news-scraper .
```

2. **Run locally:**
```bash
docker run --rm \
  -e GCP_PROJECT_ID=YOUR_PROJECT_ID \
  -e BQ_DATASET_ID=news_data \
  -e BQ_TABLE_ID=articles \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -v "$(pwd)/credentials.json:/app/credentials.json:ro" \
  -v "$(pwd)/output:/app/output" \
  news-scraper
```

### Deployment

1. **Create Artifact Registry repository:**
```bash
gcloud artifacts repositories create YOUR_REGISTRY_NAME \
    --repository-format=docker \
    --location=YOUR_PREFERRED_REGION
```

2. **Deploy to Cloud Run:**
```bash
chmod +x deploy.sh
./deploy.sh
```

### Testing
To run the unit tests, execute the following command in the project directory:

```bash
pytest tests/ -v
```

### Project Structure
```bash
├── scraper.py          # Main scraping logic
├── Dockerfile          # Container configuration
├── deploy.sh           # Deployment script
├── requirements.txt    # Python dependencies
├── tests/
│   └── test_scraper.py # Unit tests
└── README.md          # Documentation
```

### Requirements

See `requirements.txt` for Python dependencies:
```
google-cloud-bigquery==3.17.2
mock==5.0.1 
pandas==2.2.0
pyarrow==15.0.0
pytest==7.3.1
requests==2.31.0
selenium==4.17.2
```

### Common Issues

1. **Credentials not found**: Ensure your credentials.json is in the correct location and mounted properly in Docker.
2. **Permission denied**: Verify your service account has the correct IAM roles.
3. **Docker mount issues on Windows**: Use Windows path format: `C:\path\to\credentials.json:/app/credentials.json:ro`

### BigQuery Schema

The scraper creates a table with the following schema:

| Field | Type | Description |
|-------|------|-------------|
| title | STRING | Article title |
| kicker | STRING | Text above headline |
| link | STRING | Article URL |
| image | STRING | Image URL |
| title_word_count | INTEGER | Word count |
| title_char_count | INTEGER | Character count |
| capital_words | ARRAY<STRING> | Words starting with capital letter |
| scrape_date | TIMESTAMP | Scraping timestamp |

### License

This project is licensed under the MIT License. See [LICENSE.md](LICENSE.md) for details.
