# AI Agent Platform - Backend

Stateless Python microservices for Google Cloud Functions (Gen2), split by domain.

## TODOS

- Create MCP server for the tooling and agent runtime to use (instead of local ADK)

## Current Structure

```text
project/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── scripts/
│   │   └── deploy_agent_engines.py
│   ├── shared/
│   │   ├── config.py
│   │   ├── firebase.py
│   │   ├── firestore.py
│   │   ├── auth.py
│   │   ├── http.py
│   │   └── logging.py
│   └── services/
│       ├── auth_service/
│       │   ├── main.py
│       │   ├── models.py
│       │   └── service.py
│       ├── agents_service/
│       │   ├── main.py
│       │   ├── chat/
│       │   │   ├── main.py
│       │   │   ├── service.py
│       │   │   ├── tools.py
│       │   │   └── tool_handlers/
│       │   │       ├── shared.py
│       │   │       ├── articles.py
│       │   │       ├── users.py
│       │   │       ├── fetch_url_content.py
│       │   │       ├── web_search/
│       │   │       │   ├── models.py
│       │   │       │   └── search.py
│       │   │       └── web_research/
│       │   │           ├── models.py
│       │   │           ├── planner.py
│       │   │           ├── executor.py
│       │   │           ├── info_extractor.py
│       │   │           └── research.py
│       │   └── admin/
│       │       ├── main.py
│       │       ├── models.py
│       │       ├── repository.py
│       │       ├── task_scheduler.py
│       │       ├── service.py
│       │       ├── agent_factory.py
│       │       └── agent_deployer.py
│       ├── articles_service/
│       │   ├── main.py
│       │   ├── models.py
│       │   ├── repository.py
│       │   └── service.py
│       └── users_service/
│           ├── main.py
│           ├── models.py
│           ├── repository.py
│           └── service.py
└── frontend/
    └── ...
```

## Services and Endpoints

- **Auth Service** (`auth_service`): FastAPI-based service with docs at `GET /docs` and schema at `GET /openapi.json`, plus `POST /login`, `POST /logout`
- **Agents Service** (`agents_service`): FastAPI-based service with docs at `GET /docs` and schema at `GET /openapi.json`, plus dynamic agent lifecycle endpoints `GET /agents`, `POST /agents`, `GET /agents/{id}`, `PUT /agents/{id}`, `POST /agents/{id}/deploy`, `DELETE /agents/{id}`; and chat/session endpoints `GET /agents/available`, `POST /agents/chat`, `GET /agents/chat/sessions`, `POST /agents/chat/sessions`, `GET /agents/chat/sessions/{id}`, `DELETE /agents/chat/sessions/{id}`
- **Articles Service** (`articles_service`): FastAPI-based service with docs at `GET /docs` and schema at `GET /openapi.json`, plus `GET /articles`, `GET /articles/{id}`, `POST /articles/{id}`, `PUT /articles/{id}`, `DELETE /articles/{id}`
- **Users Service** (`users_service`): FastAPI-based service with docs at `GET /docs` and schema at `GET /openapi.json`, plus `GET /me`, `PUT /me`, `POST /me/password`, `GET /users`, `POST /users`, `GET /users/{uid}`, `PUT /users/{uid}`, `DELETE /users/{uid}`

Protected endpoints require `Authorization: Bearer <JWT>` and are validated with Firebase Admin SDK.

## What the main dependencies are for

- **Firebase**: provides Authentication for login and JWT issuance/verification.
- **Firestore**: stores application data such as articles and user profiles.
- **Gemini/OpenAI APIs**: generate the response returned by the agents service chat.
- **functions-framework**: runs each Cloud Function locally and provides the HTTP entrypoint used by Google Cloud Functions.
- **FastAPI**: powers the annotated auth, users, and articles APIs and generates interactive API documentation.
- **firebase-admin**: initializes Firebase/Firestore access and verifies Firebase ID tokens on the backend.
- **email-validator**: validates email fields used by the login and user profile models.
- **python-dotenv**: loads values from `backend/.env` into the process environment when running locally.

## Environment Variables

- `PROJECT_ID`
- `FIREBASE_CREDENTIALS` (JSON string or file path)
- `GOOGLE_APPLICATION_CREDENTIALS` (optional when `FIREBASE_CREDENTIALS` is set)
- `SECRET_KEY`
- `FIREBASE_WEB_API_KEY` (required by `auth_service`)
- `OPENAI_API_KEY` (required when using GPT models)
- `OPENAI_BASE_URL` (optional, defaults to `https://api.openai.com/v1`)
- `ARTICLES_SERVICE_URL` (URL of the articles microservice; defaults to `http://localhost:8092`)
- `USERS_SERVICE_URL` (URL of the users microservice; defaults to `http://localhost:8093`)
- `ARTICLES_AGENT_ENGINE` (optional deployed Agent Engine resource name for `article_agent`)
- `USERS_AGENT_ENGINE` (optional deployed Agent Engine resource name for `users_expert_agent`)
- `GOOGLE_CLOUD_LOCATION` (default deployment location for dynamic agents; defaults to `REGION` or `us-central1`)
- `AGENT_STAGING_BUCKET` (GCS staging bucket used by dynamic deployment, format `gs://...`)
- `AGENT_IDENTITY_TYPE` (`AGENT_IDENTITY` or `SERVICE_ACCOUNT`)
- `AGENT_RUNTIME_SERVICE_ACCOUNT` (required when `AGENT_IDENTITY_TYPE=SERVICE_ACCOUNT`)
- `AGENT_TASKS_QUEUE` (Cloud Tasks queue name for async deploy/undeploy)
- `AGENT_TASKS_LOCATION` (Cloud Tasks queue location)
- `AGENT_TASKS_TARGET_URL` (HTTP target to `/internal/agents/tasks/process`)
- `AGENT_TASKS_SERVICE_ACCOUNT` (optional OIDC service account for Cloud Tasks HTTP requests)
- `AGENT_TASKS_SECRET` (shared secret header used by internal task endpoint)
- `FRONTEND_ORIGIN` (example: `http://localhost:5173`)
- `LOG_LEVEL` (use `DEBUG` to show debug logs)

Gemini is called through Vertex AI in `agents_service`, so this backend setup uses `PROJECT_ID` + `GOOGLE_CLOUD_LOCATION` instead of Gemini API keys.

All Firebase values must point to the **same Firebase project** (for example `personalized-ai-agents-572b3`): project ID, Web API key, and service-account key file.

`web_search` in `agents_service` uses Gemini Google Search grounding (generic web scope) and does not require a Programmable Search Engine `cx`. The platform also includes a reusable `fetch_url_content` tool for HTML/text extraction from public URLs.

## First User Bootstrap (Required)

The platform does **not** auto-create the very first user/admin.  
Before people can log in and use in-app user management, create an initial user in **Firebase Authentication** (Console or Admin SDK/script).

Why:
- `users_service` endpoints like `POST /users`, `GET /users`, `PUT /users/{uid}`, `DELETE /users/{uid}` are protected and require a valid authenticated user token.
- Without at least one existing Firebase Auth user, nobody can authenticate to call those protected endpoints.

Recommended bootstrap flow:
1. Create the first user in Firebase Authentication.
2. Sign in through the app (`auth_service` / login UI).
3. (Optional) Create/update profile fields (`display_name`, `role`, `preferences`) through `users_service` (`PUT /me`) or the Users UI.

Notes:
- Firestore profile documents are managed by `users_service`; they are not required to exist before first login.
- The first user bootstrap is a one-time setup per Firebase project/environment.

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip show functions-framework

# terminal 1
set -a; 
source .env
set +a; 
python -m functions_framework --target auth_service --source main.py --port 8091

# terminal 2
set -a; 
source .env
set +a; 
python -m functions_framework --target articles_service --source main.py --port 8092

# terminal 3
set -a; 
source .env
set +a; 
python -m functions_framework --target users_service --source main.py --port 8093

# terminal 4
set -a;
source .env
set +a;
python -m functions_framework --target agents_service --source main.py --port 8094
```

## ADK Web UI (run from backend root)

Start ADK from `backend/` so `services/*`, `shared/*`, and relative credential paths resolve correctly:

```bash
set -a
source .env
set +a

adk web services --port 8000
```

Then open `http://127.0.0.1:8000` and select `agents_service`.

## Deploy ADK agents to Google Agent Runtime

Use the deployment script in `backend/scripts/deploy_agent_engines.py` to publish both:
- `articles_agent`
- `users_expert_agent`

### Prerequisites

1. A GCS bucket for staging (`STAGING_BUCKET`, format `gs://your-bucket-name`)
2. Vertex AI API enabled in your project
3. Choose runtime identity mode:
   - `AGENT_IDENTITY` (default): do **not** pass `--service-account`
   - `SERVICE_ACCOUNT`: pass `--service-account <service-account-email>`
4. Python 3.11+ recommended (Python 3.10 still works but emits Google SDK deprecation warnings)

### Run

From `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

set -a
source .env
set +a

python scripts/deploy_agent_engines.py \
  --project-id <PROJECT_ID> \
  --location <REGION> \
  --staging-bucket gs://YOUR_BUCKET_NAME \
  --identity-type SERVICE_ACCOUNT \
  --service-account <service-account-email> \
  --articles-service-url https://<articles-service-url> \
  --users-service-url https://<users-service-url> \
  --articles-display-name articles-agent-runtime \
  --users-display-name users-expert-agent-runtime
```

The script prints the deployed Agent Engine resource names for both agents.

Important for tool calls:

1. `ARTICLES_SERVICE_URL` and `USERS_SERVICE_URL` must be reachable from Agent Runtime (do not use `localhost`).
2. The bearer token from `/agents/chat` is propagated into ADK session state for each request and used by tools.
3. After changing dynamic-agent factory/tool behavior (for example `services/agents_service/admin/agent_factory.py` or chat tool handlers), redeploy agent engines.

To make `agents_service` use the deployed agents, set these env vars before starting/deploying `agents_service`:

```bash
ARTICLES_AGENT_ENGINE=projects/<PROJECT_NUMBER>/locations/<REGION>/reasoningEngines/<ARTICLES_ENGINE_ID>
USERS_AGENT_ENGINE=projects/<PROJECT_NUMBER>/locations/<REGION>/reasoningEngines/<USERS_ENGINE_ID>
```

If these are unset, `agents_service` falls back to local in-process ADK execution.

The script flow remains supported. In addition, `agents_service` can now deploy user-defined agents programmatically through `POST /agents/{id}/deploy`, with async execution via Cloud Tasks (or local background thread fallback when Cloud Tasks settings are absent).

## Deploy (Google Cloud Functions Gen2)

```bash
export PROJECT_ID=<replace this by the real project id>

# create tasks queue for async agent deployment
gcloud tasks queues create agent-deploy-queue --project ${PROJECT_ID} --location <REGION>

# Create FIREBASE_WEB_API_KEY secret
echo "<replace this by the real key>" | \
  gcloud secrets create FIREBASE_WEB_API_KEY --data-file=-

# Create SECRET_KEY secret
echo "<replace this by the real key>" | \
  gcloud secrets create SECRET_KEY --data-file=-

# Create OPENAI_API_KEY secret
echo "<replace this by the real key>" | \
  gcloud secrets create OPENAI_API_KEY --data-file=-

# Get the Cloud Run service account (typically the default compute service account)
export SA_EMAIL="${PROJECT_ID}@appspot.gserviceaccount.com"
export SERVICE_ACCOUNT_ID="<replace this by your google developer service account>"

# Grant Secret Reader role for each secret
for SECRET in FIREBASE_WEB_API_KEY SECRET_KEY OPENAI_API_KEY; do
  gcloud secrets add-iam-policy-binding ${SECRET} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"

  gcloud secrets add-iam-policy-binding ${SECRET} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet
  
  gcloud secrets add-iam-policy-binding ${SECRET} \
  --member=serviceAccount:${SERVICE_ACCOUNT_ID}@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
done

echo "✓ Permissions granted to: ${SA_EMAIL} and ${SERVICE_ACCOUNT_ID}"
gcloud secrets get-iam-policy FIREBASE_WEB_API_KEY

# grant permission to create tasks
gcloud tasks queues add-iam-policy-binding <AGENT_TASKS_QUEUE> \
  --location <REGION> \
  --project $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/cloudtasks.enqueuer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/cloudtasks.enqueuer"

gcloud functions deploy auth-service \
  --gen2 \
  --runtime python312 \
  --region <REGION> \
  --source . \
  --entry-point auth_service \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=<PROJECT_ID>,FRONTEND_ORIGIN=<FRONTEND_ORIGIN> \
  --set-secrets FIREBASE_WEB_API_KEY=FIREBASE_WEB_API_KEY:latest,SECRET_KEY=SECRET_KEY:latest

gcloud functions deploy articles-service \
  --gen2 \
  --runtime python312 \
  --region <REGION> \
  --source . \
  --entry-point articles_service \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=<PROJECT_ID>,FRONTEND_ORIGIN=<FRONTEND_ORIGIN> \
  --set-secrets FIREBASE_WEB_API_KEY=FIREBASE_WEB_API_KEY:latest,SECRET_KEY=SECRET_KEY:latest

gcloud functions deploy users-service \
  --gen2 \
  --runtime python312 \
  --region <REGION> \
  --source . \
  --entry-point users_service \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=<PROJECT_ID>,FRONTEND_ORIGIN=<FRONTEND_ORIGIN> \
  --set-secrets FIREBASE_WEB_API_KEY=FIREBASE_WEB_API_KEY:latest,SECRET_KEY=SECRET_KEY:latest

gcloud functions deploy agents-service \
  --gen2 \
  --runtime python312 \
  --region <REGION> \
  --source . \
  --entry-point agents_service \
  --trigger-http \
  --allow-unauthenticated \
  --timeout=1800s \
  --set-env-vars LOG_LEVEL=DEBUG,PROJECT_ID=<PROJECT_ID>,FRONTEND_ORIGIN=<FRONTEND_ORIGIN>,ARTICLES_AGENT_ENGINE=<ARTICLES_AGENT_ENGINE>,USERS_AGENT_ENGINE=<USERS_AGENT_ENGINE>,GOOGLE_CLOUD_LOCATION=europe-west1,AGENT_STAGING_BUCKET=<gs://your-agent-staging-bucket>,AGENT_IDENTITY_TYPE=SERVICE_ACCOUNT,AGENT_RUNTIME_SERVICE_ACCOUNT=<AGENT_RUNTIME_SERVICE_ACCOUNT>,AGENT_TASKS_QUEUE=<AGENT_TASKS_QUEUE>,AGENT_TASKS_LOCATION=europe-west1,AGENT_TASKS_TARGET_URL=<AGENT_TASKS_TARGET_URL>,AGENT_TASKS_SERVICE_ACCOUNT=<AGENT_TASKS_SERVICE_ACCOUNT>,AGENT_TASKS_SECRET=<AGENT_TASKS_SECRET> \
  --set-secrets FIREBASE_WEB_API_KEY=FIREBASE_WEB_API_KEY:latest,SECRET_KEY=SECRET_KEY:latest,ARTICLES_SERVICE_URL=VITE_ARTICLES_API_BASE_URL:latest,USERS_SERVICE_URL=VITE_USERS_API_BASE_URL:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest
```

## Google Cloud Functions Results

**auth_service** 
- Logs are available at: https://console.cloud.google.com/cloud-build/builds;region=europe-west1/be1b33ce-5baa-4df5-a3e2-395284fa88bc?project=10545
  56563606
- You can view your function in the Cloud Console here: https://console.cloud.google.com/functions/details/europe-west1/auth-service?project=personalized-ai-agents-572b3
- build: projects/1054556563606/locations/europe-west1/builds/be1b33ce-5baa-4df5-a3e2-395284fa88bc
- dockerRepository: projects/personalized-ai-agents-572b3/locations/europe-west1/repositories/gcf-artifacts
- serviceAccount: projects/personalized-ai-agents-572b3/serviceAccounts/1054556563606-compute@developer.gserviceaccount.com
- name: projects/personalized-ai-agents-572b3/locations/europe-west1/functions/auth-service
- uri: https://auth-service-yqro3fzdwq-ew.a.run.app
- public url: https://europe-west1-personalized-ai-agents-572b3.cloudfunctions.net/auth-service
- curl cmd: curl -i -X POST 'https://europe-west1-personalized-ai-agents-572b3.cloudfunctions.net/auth-service/login' \
  -H 'Content-Type: application/json' \
  --data '{"email":"test@test.com","password":"test"}'

**articles_service**
- Logs are available at: https://console.cloud.google.com/cloud-build/builds;region=europe-west1/257179dd-3325-464e-a7c9-fcee4ff69bcf?project=10545
  56563606
- You can view your function in the Cloud Console here: https://console.cloud.google.com/functions/details/europe-west1/articles-service?project=personalized-ai-agents-572b3
- build: projects/1054556563606/locations/europe-west1/builds/257179dd-3325-464e-a7c9-fcee4ff69bcf
- dockerRepository: projects/personalized-ai-agents-572b3/locations/europe-west1/repositories/gcf-artifacts
- serviceAccount: projects/personalized-ai-agents-572b3/serviceAccounts/1054556563606-compute@developer.gserviceaccount.com
- name: projects/personalized-ai-agents-572b3/locations/europe-west1/functions/articles-service 
- uri: https://articles-service-yqro3fzdwq-ew.a.run.app
- public url: https://europe-west1-personalized-ai-agents-572b3.cloudfunctions.net/articles-service 

**users_service**
- Logs are available at: https://console.cloud.google.com/cloud-build/builds;region=europe-west1/7c7e2df8-251a-46ed-a9ba-2da394e319c1?project=10545
  56563606
- You can view your function in the Cloud Console here: https://console.cloud.google.com/functions/details/europe-west1/users-service?project=personalized-ai-agents-572b3
- build: projects/1054556563606/locations/europe-west1/builds/7c7e2df8-251a-46ed-a9ba-2da394e319c1
- dockerRepository: projects/personalized-ai-agents-572b3/locations/europe-west1/repositories/gcf-artifacts
- serviceAccount: projects/personalized-ai-agents-572b3/serviceAccounts/1054556563606-compute@developer.gserviceaccount.com
- name: projects/personalized-ai-agents-572b3/locations/europe-west1/functions/users-service
- uri: https://users-service-yqro3fzdwq-ew.a.run.app
- public url: https://europe-west1-personalized-ai-agents-572b3.cloudfunctions.net/users-service

**agents_service**
- Logs are available at: https://console.cloud.google.com/cloud-build/builds;region=europe-west1/a334af64-0a1f-48c3-b49e-8cd0ccaa024d?project=
  1054556563606
- You can view your function in the Cloud Console here: https://console.cloud.google.com/functions/details/europe-west1/agents-service?project=personalized-ai-agents-572b3
- build: projects/1054556563606/locations/europe-west1/builds/a334af64-0a1f-48c3-b49e-8cd0ccaa024d
- dockerRepository: projects/personalized-ai-agents-572b3/locations/europe-west1/repositories/gcf-artifacts
- serviceAccount: projects/personalized-ai-agents-572b3/serviceAccounts/1054556563606-compute@developer.gserviceaccount.com
- name: projects/personalized-ai-agents-572b3/locations/europe-west1/functions/agents-service
- uri: https://agents-service-yqro3fzdwq-ew.a.run.app
- public url: https://europe-west1-personalized-ai-agents-572b3.cloudfunctions.net/agents-service

**agents deployed**
- ARTICLES_AGENT_ENGINE=projects/1054556563606/locations/europe-west1/reasoningEngines/3269393427145424896
- USERS_AGENT_ENGINE=projects/1054556563606/locations/europe-west1/reasoningEngines/6325085774316306432

## Frontend Integration

In `frontend/.env`:

```bash
VITE_AUTH_API_BASE_URL=http://localhost:8091
VITE_ARTICLES_API_BASE_URL=http://localhost:8092
VITE_USERS_API_BASE_URL=http://localhost:8093
VITE_AGENTS_API_BASE_URL=http://localhost:8094
```

## Python test scripts

Run these from `backend/` after exporting your env vars:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

set -a
source .env
set +a

pytest -q tests
```
