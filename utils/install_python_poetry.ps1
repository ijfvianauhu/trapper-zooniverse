# PowerShell script to install Python, add it to the user PATH, and enable script execution
# Run as a normal user (admin rights are not required for modifying PATH and CurrentUser ExecutionPolicy)

# Require:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# ------------------------------
# Configuration
# ------------------------------
$pythonUrl = "https://www.python.org/ftp/python/3.12.6/python-3.12.6-amd64.exe"   # Adjust if you want another version
$installer = "$env:TEMP\python-installer.exe"

# ------------------------------
# Download and Install Python installer
# ------------------------------
Write-Host "Downloading Python installer..."
Invoke-WebRequest -Uri $pythonUrl -OutFile $installer

Write-Host "Installing Python..."
Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=0 PrependPath=0 Include_test=0" -Wait -NoNewWindow

# Path where Python is usually installed for current user
$pythonPath = "$env:LocalAppData\Programs\Python\Python312"
$pipPath = "$pythonPath\Scripts"

# ------------------------------
# Adding Python to the user PATH
# ------------------------------
Write-Host "Adding Python to the user PATH..."

$oldPath = [Environment]::GetEnvironmentVariable("PATH", "User")

if ($oldPath -notlike "*$pythonPath*" -or $oldPath -notlike "*$pipPath*") {
    $newPath = "$pythonPath;$pipPath;$oldPath"
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    $env:PATH = $newPath
    Write-Host "Python paths added to user PATH."
} else {
    Write-Host "Python paths already exist in user PATH."
}

# ------------------------------
# Enable PowerShell script execution for the current user
# ------------------------------
# Write-Host "Enabling script execution for the current user..."
# Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force

# ------------------------------
# Install Poetry for the current user
# ------------------------------
Write-Host "Downloading Poetry..."
$poetryInstaller = "$env:TEMP\install-poetry.py"
Invoke-WebRequest -Uri "https://install.python-poetry.org" -OutFile $poetryInstaller

Write-Host "Installing Poetry..."
$pythonExe = "$pythonPath\python.exe"
& $pythonExe $poetryInstaller -y

Write-Host "Adding Poetry to the user PATH..."

$poetryBin = "$env:APPDATA\Python\Scripts"

# Get current user PATH
$oldPath = [Environment]::GetEnvironmentVariable("PATH", "User")

# Check if Poetry path is already present
if (-not ($oldPath.Split(";") -contains $poetryBin)) {
    # Build new PATH
    $newPath = $poetryBin + ";" + $oldPath

    # Set PATH for current session and user
    $env:PATH = $newPath
    [Environment]::SetEnvironmentVariable("PATH", $newPath, 'User')

    Write-Host "Poetry paths added to user PATH."
} else {
    Write-Host "Poetry paths already exist in user PATH."
}


# Check that poetry.exe exists
$poetryExe = "$poetryBin\poetry.exe"
if (Test-Path $poetryExe) {
    Write-Host "Poetry installed and paths added to user PATH."
    Write-Host "Installing Poetry 'shell' plugin..."
    & $poetryExe self update
    & $poetryExe self add poetry-plugin-shell
    Write-Host "Poetry 'shell' plugin installed."
} else {
    Write-Host "Poetry.exe not found in $poetryBin" -ForegroundColor Red
}

Write-Host "Please enable script execution for the current user by running: Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force"
Write-Host "Close and reopen your terminal for the PATH changes to take effect."
