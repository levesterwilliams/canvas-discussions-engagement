# Canvas Discussions Engagement Azure Function

This app runs the existing Canvas → Excel → Box pipeline as a weekly Azure Functions timer job.

## Structure

- `function_app.py`: Azure Functions entry point.
- `shared/`: reusable PEP 420 namespace package modules.
- `courses.xlsx`: optional local course configuration workbook, or supply `COURSE_CONFIG_PATH`.

## Schedule

Set:

- `DISCUSSION_REPORT_SCHEDULE=0 0 17 * * 1`
- `WEBSITE_TIME_ZONE=Eastern Standard Time`

That runs the job every Monday at 5:00 PM Eastern, including daylight saving time handling on Azure App Service / Functions.

## Local development

1. Create a virtualenv and install `requirements.txt`.
2. Copy `local.settings.json.example` to `local.settings.json`.
3. Add `courses.xlsx` to the app root, or point `COURSE_CONFIG_PATH` at it.
4. Run locally with Azure Functions Core Tools:

```powershell
func start
```

## Azure CLI deployment

```powershell
az login
az group create --name <rg> --location eastus
az storage account create --name <storage> --location eastus --resource-group <rg> --sku Standard_LRS
az functionapp create --resource-group <rg> --consumption-plan-location eastus --runtime python --runtime-version 3.12 --functions-version 4 --name <function-app-name> --os-type Linux --storage-account <storage>
az functionapp config appsettings set --name <function-app-name> --resource-group <rg> --settings WEBSITE_TIME_ZONE="Eastern Standard Time" DISCUSSION_REPORT_SCHEDULE="0 0 17 * * 1" COURSE_CONFIG_PATH="courses.xlsx" CANVAS_API_CRED='<json>' BOX_CLIENT_ID='<id>' BOX_CLIENT_SECRET='<secret>' BOX_REFRESH_TOKEN='<refresh-token>'
func azure functionapp publish <function-app-name>
```

## Important Box note

The current Box OAuth refresh-token flow rotates refresh tokens. For production, persist the refreshed token outside the function filesystem, such as Key Vault or another durable store, or switch to a non-rotating server-to-server Box auth pattern.
