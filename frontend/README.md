# Frontend

React + Vite frontend for the AI Agent Platform.

## Prerequisites

- Node.js 18+ (recommended)
- npm

## Setup

1. Install dependencies:

```bash
npm install
```

2. Create your environment file:

```bash
cp .env.example .env
```

3. Confirm API URLs in `.env`:

```bash
VITE_AUTH_API_BASE_URL=http://localhost:8081
VITE_ARTICLES_API_BASE_URL=http://localhost:8082
VITE_USERS_API_BASE_URL=http://localhost:8083
VITE_AGENTS_API_BASE_URL=http://localhost:8084
VITE_LOG_LEVEL=info
```

Set `VITE_LOG_LEVEL=debug` to see debug-only logs in the browser console.

## Run locally

```bash
npm run dev
```

Vite will print the local URL (usually `http://localhost:5173`).

## Build for production

```bash
npm run build
```

## Preview production build

```bash
npm run preview
```

## Deploy to Google Cloud Run

### Prerequisites

- `gcloud` CLI installed and authenticated
- Docker installed locally
- GCP project set up (e.g., `personalized-ai-agents-572b3`)

### Steps

1. **Set environment variables:**

```bash
export PROJECT_ID=<replace this by the real project id>
export REGION=<replace this by the real region name>
export SERVICE_NAME=personalized-ai-agents-frontend
```

2. **Create Google Secret Manager secrets:**

```bash
echo "https://${REGION}-${PROJECT_ID}.cloudfunctions.net/auth-service" | \
  gcloud secrets create VITE_AUTH_API_BASE_URL --data-file=-

echo "https://${REGION}-${PROJECT_ID}.cloudfunctions.net/articles-service" | \
  gcloud secrets create VITE_ARTICLES_API_BASE_URL --data-file=-

echo "https://${REGION}-${PROJECT_ID}.cloudfunctions.net/users-service" | \
  gcloud secrets create VITE_USERS_API_BASE_URL --data-file=-

echo "https://${REGION}-${PROJECT_ID}.cloudfunctions.net/agents-service" | \
  gcloud secrets create VITE_AGENTS_API_BASE_URL --data-file=-
```

3. **Grant Cloud Run service account access to secrets:**

```bash
# Get the Cloud Run service account (typically the default compute service account)
export PID_SA_EMAIL="${PROJECT_ID}@appspot.gserviceaccount.com"
export PNUM_SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant Secret Reader role for each secret
for SECRET in VITE_AUTH_API_BASE_URL VITE_ARTICLES_API_BASE_URL VITE_USERS_API_BASE_URL VITE_AGENTS_API_BASE_URL; do
  gcloud secrets add-iam-policy-binding ${SECRET} \
    --member="serviceAccount:${PID_SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"

  gcloud secrets add-iam-policy-binding ${SECRET} \
    --member="serviceAccount:${PNUM_SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"
done

echo "✓ Permissions granted to: ${PID_SA_EMAIL} and ${PNUM_SA_EMAIL}"
gcloud secrets get-iam-policy VITE_AUTH_API_BASE_URL
```

4. **Create Artifact Registry repository (one-time setup):**

```bash
gcloud artifacts repositories create cloud-run-repo \
    --repository-format=docker \
    --location=${REGION} \
    --description="Docker images for Cloud Run"
```

5. **Build and push the Docker image to Artifact Registry:**

```bash
# Configure Docker to push to Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build the image (secrets are fetched at runtime, not build time)
docker build \
  -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-repo/${SERVICE_NAME}:latest .

# Push to Artifact Registry
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-repo/${SERVICE_NAME}:latest
```

6. **Deploy to Cloud Run:**

```bash
gcloud run deploy ${SERVICE_NAME} \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-repo/${SERVICE_NAME}:latest \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated
```

The command will output the public URL for your deployed frontend (e.g., `https://personalized-ai-agents-frontend-1054556563606.europe-west1.run.app`).

7. **Update backend API CORS origins:**

After deployment, update the `FRONTEND_ORIGIN` environment variable on all backend services to your deployed frontend URL:

```bash
# For each backend service (auth-service, articles-service, users-service, agents-service)
gcloud functions deploy <SERVICE_NAME> \
  --region ${REGION} \
  --update-env-vars FRONTEND_ORIGIN=https://personalized-ai-agents-frontend-1054556563606.europe-west1.run.app
```

### Updating Secrets

To update API endpoints without rebuilding the container:

```bash
echo "https://new-url" | gcloud secrets versions add VITE_AUTH_API_BASE_URL --data-file=-
```

Restart the Cloud Run service to fetch the updated secret:

```bash
gcloud run deploy ${SERVICE_NAME} --region ${REGION} --no-gen2 # restart only
```
# For each backend service (auth-service, articles-service, users-service)
gcloud functions deploy <SERVICE_NAME> \
  --region ${REGION} \
  --update-env-vars FRONTEND_ORIGIN=https://personalized-ai-agents-frontend-1054556563606.europe-west1.run.app
```
