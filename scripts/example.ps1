# Example PowerShell Script for BindKit
# This script demonstrates PowerShell script support

param(
    [Parameter(Mandatory=$false)]
    [string]$Message = "Hello from PowerShell!",

    [Parameter(Mandatory=$false)]
    [string]$Title = "BindKit PowerShell Example"
)

# Display a message box (Windows only)
Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show($Message, $Title, 'OK', 'Information')

# Output to console
Write-Host "PowerShell script executed successfully"
Write-Host "Message: $Message"
Write-Host "Title: $Title"

# Exit with success code
exit 0
