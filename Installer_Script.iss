; Script de Inno Setup para MiBotTrading
; Descarga Inno Setup desde: https://jrsoftware.org/isdl.php
; Para compilar: iscc Installer_Script.iss

#define MyAppName "MiBotTrading"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MiBotTrading"
#define MyAppURL "https://github.com/tuusuario/MiBotTrading"
#define MyAppExeName "MiBotTrading.exe"

[Setup]
AppId={{B8F7A3D2-1E5C-4A6B-9D8C-3F2E1A0B5C7D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=MiBotTrading_Installer_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "dist\MiBotTrading.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\.env"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "dist\config.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "dist\canales.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "dist\posiciones.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "dist\README_INSTALACION.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:ProgramOnTheWeb,{#MyAppName}}"; Filename: "{#MyAppURL}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c schtasks /delete /tn MiBotTrading_AutoStart /f"; Flags: runhidden

[Code]
function InitializeSetup: Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // No hacer nada especial post-instalación
  end;
end;