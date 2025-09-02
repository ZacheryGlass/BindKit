; Inno Setup script for BindKit

#define MyAppName "BindKit"
#define MyAppExeName "BindKit.exe"
; Allow CI to pass /DMyAppVersion=1.2.3, with a local default
#ifndef MyAppVersion
#define MyAppVersion "0.0.0"
#endif
#define MyPublisher "BindKit"

[Setup]
AppId={{B0DE5D8F-DAE9-4F28-9C22-4F996B0EDE16}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
; Paths are relative to this .iss file's directory
OutputDir=output
OutputBaseFilename=BindKit-{#MyAppVersion}-Setup
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest

[Files]
; Install the entire PyInstaller onedir output
; Point to the PyInstaller onedir output located one directory up
Source: "..\dist\BindKit\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
; Create a Startup shortcut to launch minimized (user-level, uninstall cleans it up)
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--minimized"; Tasks: startwithwindows

[Tasks]
Name: "startwithwindows"; Description: "Start {#MyAppName} at login"; Flags: checkedonce

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
