[CmdletBinding(DefaultParameterSetName = 'Render')]
param(
    [Parameter(Mandatory = $true)][string]$SourceDocx,
    [Parameter(Mandatory = $true, ParameterSetName = 'Render')][string]$OutputPdf,
    [Parameter(Mandatory = $true, ParameterSetName = 'Inspect')][switch]$MetricsOnly
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$source = (Resolve-Path -LiteralPath $SourceDocx).Path
if ([IO.Path]::GetExtension($source) -ne '.docx') { throw 'Expected native DOCX source.' }
if (-not $MetricsOnly) {
    $target = [IO.Path]::GetFullPath($OutputPdf)
    if ([IO.Path]::GetExtension($target) -ne '.pdf') { throw 'Expected native PDF output.' }
    if (Test-Path -LiteralPath $target) { throw 'PDF target already exists.' }
}
# The isolated research engine deliberately redirects these folders. Word's
# automation server needs the actual Windows profile to resolve its Office
# templates; with the redirected profile Documents.Open can return null.
# Restore only native profile paths in this renderer process, never ambient
# credentials or environment variables in the research engine itself.
$nativeProfile = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
if ([string]::IsNullOrWhiteSpace($nativeProfile) -or -not [IO.Directory]::Exists($nativeProfile)) { throw 'Native Word rendering requires an accessible Windows user profile.' }
$env:USERPROFILE = $nativeProfile
$env:HOME = $nativeProfile
$nativeFolders = Get-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
$nativeRoaming = [Environment]::ExpandEnvironmentVariables([string]$nativeFolders.AppData)
$nativeLocal = [Environment]::ExpandEnvironmentVariables([string]$nativeFolders.'Local AppData')
if ([string]::IsNullOrWhiteSpace($nativeRoaming) -or [string]::IsNullOrWhiteSpace($nativeLocal) -or -not [IO.Directory]::Exists($nativeRoaming) -or -not [IO.Directory]::Exists($nativeLocal)) { throw 'Native Word rendering could not resolve the actual Windows application-data folders.' }
$env:APPDATA = $nativeRoaming
$env:LOCALAPPDATA = $nativeLocal
$word = $null
$document = $null
$ownsWord = $false
try {
    $word = New-Object -ComObject Word.Application
    if ($word.Documents.Count -ne 0 -or $word.Visible) { throw 'Word automation must own an empty hidden instance.' }
    $ownsWord = $true
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($source, $false, $true, $false, '', '', $false, '', '', 0, 0, $false)
    if ($null -eq $document) { throw 'Microsoft Word returned no document while opening the exact read-only native manuscript.' }
    $document.Repaginate()
    $details = @{ version = $word.Version; pages = $document.ComputeStatistics(2); read_only = $document.ReadOnly }
    if ($MetricsOnly) {
        $includeNotes = $true
        $details.whole_words = $document.ComputeStatistics(0, [ref]$includeNotes)
        $referenceStart = [int]$document.Content.End
        $bodyEnd = $referenceStart
        $details.abstract_words = 0
        $details.reference_count = 0
        $details.reference_heading_found = $false
        foreach ($paragraph in $document.Paragraphs) {
            $style = [string]$paragraph.Range.Style.NameLocal
            if ($style -eq 'ReferenceHead' -and -not $details.reference_heading_found) {
                $referenceStart = [int]$paragraph.Range.Start
                $bodyEnd = [Math]::Min($bodyEnd, $referenceStart)
                $details.reference_heading_found = $true
            }
            if ($style -eq 'AuthorBioHead') { $bodyEnd = [Math]::Min($bodyEnd, [int]$paragraph.Range.Start) }
            if ($style -eq 'Bib_entry' -and ([string]$paragraph.Range.Text).Trim()) { $details.reference_count += 1 }
            if ($style -eq 'Abstract') {
                $range = $paragraph.Range.Duplicate
                if (([string]$range.Text).StartsWith('Abstract' + [char]0x2014, [StringComparison]::Ordinal)) { $range.Start = [int]$range.Start + 9 }
                $details.abstract_words += $range.ComputeStatistics(0)
            }
        }
        $details.body_words = $document.Range(0, $bodyEnd).ComputeStatistics(0)
        $details.body_table_words = 0
        $details.body_tables = 0
        foreach ($table in $document.Tables) {
            if ([int]$table.Range.End -le $bodyEnd) {
                $details.body_tables += 1
                $details.body_table_words += $table.Range.ComputeStatistics(0)
            }
        }
        $details.tables = $document.Tables.Count
        $details.figures = $document.InlineShapes.Count + $document.Shapes.Count
        $details.body_figures = 0
        foreach ($shape in $document.InlineShapes) {
            if ([int]$shape.Range.StoryType -eq 1 -and [int]$shape.Range.End -le $bodyEnd) { $details.body_figures += 1 }
        }
        foreach ($shape in $document.Shapes) {
            if ([int]$shape.Anchor.StoryType -eq 1 -and [int]$shape.Anchor.End -le $bodyEnd) { $details.body_figures += 1 }
        }
    }
    Add-Type -AssemblyName System.Drawing
    $fonts = New-Object System.Drawing.Text.InstalledFontCollection
    try {
        $installed = @($fonts.Families | ForEach-Object { $_.Name })
        $details.missing_template_fonts = @('Helvetica-Light', 'Cheltenham-Book' | Where-Object { $_ -notin $installed })
    } finally { $fonts.Dispose() }
    if (-not $MetricsOnly) { $document.ExportAsFixedFormat($target, 17, $false, 0, 0, 1, 1, 0, $false, $true, 0, $true, $true, $false) }
    $details | ConvertTo-Json -Compress
} finally {
    $noSave = 0
    if ($null -ne $document) { $document.Close([ref]$noSave); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) }
    if ($null -ne $word) {
        if ($ownsWord) { $word.Quit([ref]$noSave) }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
