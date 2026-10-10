# Ideation Scoring

A minimal app where signed-in users submit an ideation project with 5–1 scores
on basic parameters (Innovation, Feasibility, Impact) plus comments. Admins see
all results on a dashboard.

## Roles
- **User**: signs in with Google (Gmail), submits a project + scores, views own submissions at `/my`.
- **Admin**: any email in `ADMIN_EMAILS`; opens `/admin` to see every submission and average ratings.

## Run locally
```bash
pip install -r requirements.txt
export SECRET_KEY=devsecret GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... ADMIN_EMAILS=you@gmail.com
python app.py   # http://localhost:8000
```

## Deploy (Azure Container Apps)
Infra lives in `infra/` (Terraform, state in `stclasspulsetf/tfstate`, RG `IIT-smartclassroom`).

```bash
az acr build -r classpulseacrbxev55 -t ideation-scoring:v1 .
cd infra
terraform init
terraform apply \
  -var google_client_id=... -var google_client_secret=... \
  -var secret_key=$(openssl rand -hex 32) -var admin_emails=you@gmail.com \
  -var image_tag=v1
```

Google OAuth setup: create a Web OAuth client in Google Cloud Console with
authorized redirect URI `https://<app fqdn>/callback` (shown as `app_url` output).
