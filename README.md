# Canvas Discussions Engagement Azure Function

This app runs the existing Canvas → Excel → Box pipeline as a weekly Azure Functions timer job.

## Structure

- `function_app.py`: Azure Functions entry point.
- `shared/`: reusable PEP 420 namespace package modules.
- `shared/pipeline.py`: downloads the course configuration workbook from Box using a fixed file ID before processing.

## Schedule

Set:

- `DISCUSSION_REPORT_SCHEDULE=0 0 17 * * 1`
- `WEBSITE_TIME_ZONE=Eastern Standard Time`

That runs the job every Monday at 5:00 PM Eastern, including daylight saving time handling on Azure App Service / Functions.

## Workbook-driven Mondays

Keep the Azure timer fixed to every Monday at 5:00 PM Eastern. Use a second Box-hosted workbook to decide which Mondays are active.

Recommended files in Box:

- `courses.xlsx`: course rows with `course_name`, `course_id`, and `box_folder_id`
- `schedule.xlsx`: a `run_date` column containing allowed run dates in `YYYY-MM-DD` format

Recommended `schedule.xlsx` layout:

```text
run_date
2026-05-18
2026-06-01
2026-06-29
```

Behavior:

- If `schedule.xlsx` is configured and today is not listed, the function exits without processing courses.
- If no schedule workbook is configured, the function keeps the old behavior and runs every Monday trigger.
- In either workbook, a named worksheet is optional. The loader prefers `courses` for course data and `schedule` for dates, but will fall back to the active sheet for backward compatibility.

## Local development

1. Create a virtualenv and install `requirements.txt`.
2. Copy `local.settings.json.example` to `local.settings.json`.
3. Update the placeholder Box file ID constants in `shared/pipeline.py`.
4. Run locally with Azure Functions Core Tools:

```powershell
func start
```

## Box workbook sources

The job downloads `courses.xlsx` and optionally `schedule.xlsx` from Box using fixed file IDs that are currently hardcoded in [shared/pipeline.py](C:/Users/Levester/Documents/New%20project/shared/pipeline.py).

```python
BOX_COURSE_CONFIG_FILE_ID = "123456789012" # Placeholder
BOX_SCHEDULE_FILE_ID = "234567890123" # Placeholder
```

Replace the placeholders with the real Box file IDs for the workbooks.

Course workbook resolution order:

1. Explicit `config_path` argument
2. `COURSE_CONFIG_PATH` environment variable
3. Box download to the function temp directory

Schedule workbook resolution order:

1. Explicit `schedule_path` argument
2. `SCHEDULE_CONFIG_PATH` environment variable
3. Box download to the function temp directory
4. disabled when `BOX_SCHEDULE_FILE_ID` is blank

This lets you keep both operational workbooks in Box and update them without redeploying code.

## Azure CLI deployment

```powershell
az login
az group create --name <rg> --location eastus
az storage account create --name <storage> --location eastus --resource-group <rg> --sku Standard_LRS
az functionapp create --resource-group <rg> --consumption-plan-location eastus --runtime python --runtime-version 3.12 --functions-version 4 --name <function-app-name> --os-type Linux --storage-account <storage>
az functionapp config appsettings set --name <function-app-name> --resource-group <rg> --settings WEBSITE_TIME_ZONE="Eastern Standard Time" DISCUSSION_REPORT_SCHEDULE="0 0 17 * * 1" CANVAS_API_CRED='<json>' KEY_VAULT_NAME='<vault-name>'
func azure functionapp publish <function-app-name>
```

## Box OAuth persistence

The app now prefers Azure Key Vault for Box OAuth token storage so the rotated refresh token survives across timer runs.

Create these secrets in Key Vault:

- `box-client-id`
- `box-client-secret`
- `box-refresh-token`
- `box-access-token`
- `box-expires-at`

Required app setting:

- `KEY_VAULT_NAME=<vault-name>`

Recommended permissions:

- Enable the Function App managed identity.
- Grant it permission to read and write secrets in the vault.
- With Azure RBAC, `Key Vault Secrets Officer` is the simplest role for this flow.

Local development fallback:

- If `KEY_VAULT_NAME` is not set, `shared/box_auth.py` falls back to `box_api_cred.json` when one is available.
