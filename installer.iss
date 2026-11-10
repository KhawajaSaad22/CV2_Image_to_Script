[Setup]
AppId=CV2ImageToScriptWorkbench
AppName=CV2 Pipeline Workbench
AppVersion=0.2.1
DefaultDirName={localappdata}\Programs\CV2Workbench
DefaultGroupName=CV2 Pipeline Workbench
PrivilegesRequired=lowest
OutputDir=installer-output
OutputBaseFilename=CV2Workbench-Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\CV2Workbench.exe

[Files]
Source: "dist\CV2Workbench\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "examples\*"; DestDir: "{app}\examples"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\CV2 Pipeline Workbench"; Filename: "{app}\CV2Workbench.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\CV2 Pipeline Workbench"; Filename: "{app}\CV2Workbench.exe"; WorkingDir: "{app}"
