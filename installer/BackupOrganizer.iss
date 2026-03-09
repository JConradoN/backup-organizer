; Inno Setup script for Backup Organizer
#define MyAppName "Backup Organizer"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Backup Organizer"
#define MyAppExeName "BackupOrganizer.exe"

[Setup]
AppId={{D6A3D5A8-4F64-4D1A-A24A-4DA265CD53A1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Backup Organizer
DefaultGroupName=Backup Organizer
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=BackupOrganizer_Setup
SetupIconFile=

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "..\dist\BackupOrganizer\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\docs\HELPME_UI.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\Backup Organizer"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar Backup Organizer"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Backup Organizer"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar Backup Organizer agora"; Flags: nowait postinstall skipifsilent
