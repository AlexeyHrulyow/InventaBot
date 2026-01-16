@echo off
cd /d "C:\InventoryBot"

:: Проверяем, не запущен ли уже бот
tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq InventaBot*" 2>NUL | find /I "python.exe" >NUL
if %ERRORLEVEL%==0 (
    echo [%date% %time%] Бот уже запущен. Завершаемся.
    exit /b
)

:: Убиваем все старые процессы python с этим скриптом (на всякий случай)
taskkill /F /IM python.exe 2>NUL
timeout /t 2 /nobreak >NUL

:start
echo [%date% %time%] Запуск инвентаризационного бота...
call venv\Scripts\activate.bat
python InventaBot.py

if %ERRORLEVEL%==0 (
    echo [%date% %time%] Бот завершил работу без ошибок.
    exit /b
)

echo [%date% %time%] Бот упал с ошибкой %ERRORLEVEL%. Перезапуск через 30 секунд...
timeout /t 30 /nobreak >NUL
goto start