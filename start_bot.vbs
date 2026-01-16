Set WshShell = CreateObject("WScript.Shell")

' Проверяем, не запущен ли уже батник
Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")
Set colProcesses = objWMIService.ExecQuery("Select * from Win32_Process Where Name = 'wscript.exe' AND CommandLine LIKE '%run_bot.vbs%'")

' Если уже есть запущенный скрипт, не запускаем новый
If colProcesses.Count > 1 Then
    WScript.Quit
End If

WshShell.Run chr(34) & "C:\InventoryBot\run_bot.bat" & Chr(34), 0
Set WshShell = Nothing