param(
  [string]$Pptx = "$PSScriptRoot\lekker-pay-submission.pptx",
  [string]$Pdf  = "$PSScriptRoot\lekker-pay-submission.pdf",
  [string]$JpgDir = "$PSScriptRoot\slides_jpg"
)
$ErrorActionPreference = "Stop"

# Resolve absolute paths (PowerPoint COM wants absolute)
$Pptx = (Resolve-Path $Pptx).Path
$Pdf  = [System.IO.Path]::GetFullPath($Pdf)
$JpgDir = [System.IO.Path]::GetFullPath($JpgDir)
if (Test-Path $JpgDir) { Remove-Item -Recurse -Force $JpgDir }
New-Item -ItemType Directory -Path $JpgDir | Out-Null

Write-Host "Source: $Pptx"
Write-Host "PDF:    $Pdf"
Write-Host "JPGs:   $JpgDir"

$ppt = $null
$pres = $null
try {
  $ppt = New-Object -ComObject PowerPoint.Application
  # Some Office installs require WindowState set; opening invisible:
  $pres = $ppt.Presentations.Open($Pptx, $true, $false, $false)

  # PpSaveAsFileType enum:
  #   ppSaveAsPDF = 32
  #   ppSaveAsJPG = 17
  $pres.SaveAs($Pdf,    32)  # PDF
  $pres.SaveAs($JpgDir, 17)  # JPG folder

  $pres.Close()
  Write-Host "Exported $($pres.Slides.Count) slides"
}
finally {
  if ($pres) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($pres) }
  if ($ppt)  { $ppt.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) }
  [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}

# List JPGs
Get-ChildItem $JpgDir -Filter *.JPG | Sort-Object Name | ForEach-Object {
  Write-Host ("  " + $_.Name + "  " + [math]::Round($_.Length / 1024) + " KB")
}
Write-Host "DONE"
