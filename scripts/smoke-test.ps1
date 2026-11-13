param(
    [int]$Port = 8002
)

$ErrorActionPreference = "Stop"
$baseUrl = "http://127.0.0.1:$Port"

Write-Host "=== TEST 1: UNAUTHORIZED ACCESS ==="

$status = 0

try {
    $response = Invoke-WebRequest `
        -Uri "$baseUrl/v1/models" `
        -UseBasicParsing

    $status = [int]$response.StatusCode
}
catch [System.Net.WebException] {
    if ($null -eq $_.Exception.Response) {
        throw "Cannot connect to API. Check port-forward."
    }

    $status = [int]$_.Exception.Response.StatusCode
}

if ($status -ne 401) {
    throw "FAIL: Expected HTTP 401, got $status"
}

Write-Host "PASS: HTTP 401"

Write-Host "=== TEST 2: AUTHORIZED ACCESS ==="

$encoded = minikube kubectl -- get secret kaspersky-vllm-auth `
    -n kaspersky-ml `
    -o jsonpath='{.data.VLLM_API_KEY}'

if ($LASTEXITCODE -ne 0 -or -not $encoded) {
    throw "Cannot read Kubernetes Secret"
}

$apiKey = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String($encoded)
)

$headers = @{ Authorization = "Bearer $apiKey" }

$models = Invoke-RestMethod `
    -Uri "$baseUrl/v1/models" `
    -Headers $headers

$modelId = $models.data[0].id

if (-not $modelId) {
    throw "FAIL: Model not found"
}

Write-Host "PASS: $modelId"

Write-Host "=== TEST 3: TEXT GENERATION ==="

$body = @{
    model = $modelId
    messages = @(
        @{
            role = "user"
            content = "Назови столицу Франции одним предложением."
        }
    )
    temperature = 0
    max_tokens = 80
    chat_template_kwargs = @{
        enable_thinking = $false
    }
} | ConvertTo-Json -Depth 10

$response = Invoke-WebRequest `
    -Uri "$baseUrl/v1/chat/completions" `
    -Method POST `
    -Headers $headers `
    -ContentType "application/json; charset=utf-8" `
    -Body ([Text.Encoding]::UTF8.GetBytes($body)) `
    -UseBasicParsing

$result = [Text.Encoding]::UTF8.GetString(
    $response.RawContentStream.ToArray()
) | ConvertFrom-Json

$answer = $result.choices[0].message.content

if ($response.StatusCode -ne 200 -or
    [string]::IsNullOrWhiteSpace($answer)) {
    throw "FAIL: Text generation"
}

Write-Host "PASS: HTTP 200"
Write-Host "MODEL ANSWER: $answer"

Write-Host "=== ALL SMOKE TESTS PASSED ==="
