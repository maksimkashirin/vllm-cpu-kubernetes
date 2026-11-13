param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$project = $PSScriptRoot
$k8s = Join-Path $project "k8s"
$image = "kaspersky-vllm:0.28.0-rootless"
$namespace = "kaspersky-ml"

function Check-ExitCode($step) {
    if ($LASTEXITCODE -ne 0) {
        throw "FAILED: $step"
    }
}

Write-Host "=== STARTING MINIKUBE ==="

minikube start
Check-ExitCode "Minikube startup"

if (-not $SkipBuild) {
    Write-Host "=== BUILDING DOCKER IMAGE ==="

    docker build -t $image $project
    Check-ExitCode "Docker build"

    Write-Host "=== LOADING IMAGE INTO MINIKUBE ==="

    minikube image load $image
    Check-ExitCode "Minikube image load"
}
else {
    Write-Host "=== USING EXISTING IMAGE ==="

    $images = minikube image ls
    Check-ExitCode "Image list"

    if (-not ($images | Select-String -SimpleMatch $image)) {
        throw "Image not found. Run without -SkipBuild."
    }
}

Write-Host "=== CREATING NAMESPACE ==="

minikube kubectl -- apply -f "$k8s\00-namespace.json"
Check-ExitCode "Namespace"

Write-Host "=== PREPARING API KEY ==="

$privateDir = Join-Path (Split-Path $project -Parent) "private"
$keyFile = Join-Path $privateDir "vllm-api-key.txt"

New-Item -ItemType Directory -Force -Path $privateDir |
    Out-Null

if (-not (Test-Path $keyFile)) {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()

    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }

    [System.IO.File]::WriteAllText(
        $keyFile,
        [Convert]::ToBase64String($bytes)
    )
}

Write-Host "=== APPLYING KUBERNETES SECRET ==="

$secretArgs = @(
    "kubectl", "--", "create", "secret", "generic",
    "kaspersky-vllm-auth",
    "-n", $namespace,
    "--from-file=VLLM_API_KEY=$keyFile"
)

$hfTokenFile = Join-Path $privateDir "hf-token.txt"

if (Test-Path $hfTokenFile) {
    $secretArgs += "--from-file=HF_TOKEN=$hfTokenFile"
}

$secretArgs += @("--dry-run=client", "-o", "json")

$secretJson = & minikube @secretArgs
Check-ExitCode "Secret preparation"

$secretJson | minikube kubectl -- apply -f -
Check-ExitCode "Secret application"

Write-Host "=== APPLYING KUSTOMIZE ==="

minikube kubectl -- apply -k $k8s
Check-ExitCode "Kustomize deployment"

Write-Host "=== CHECKING DEPLOYMENT ==="

minikube kubectl -- rollout status `
    deployment/kaspersky-vllm `
    -n $namespace `
    --timeout=600s

Check-ExitCode "Deployment readiness"

Write-Host "=== CURRENT RESOURCES ==="

minikube kubectl -- get pods,pvc,svc -n $namespace
Check-ExitCode "Resource verification"

Write-Host "=== DEPLOYMENT SUCCESSFUL ==="
