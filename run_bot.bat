@echo off
cd /d "C:\InventoryBot"
:start
echo [%date% %time%] Запуск инвентаризационного бота...
call venv\Scripts\activate.bat
python InventaBot.py

echo [%date% %time%] Бот остановлен. Перезапуск через 10 секунд...
timeout /t 10 /nobreak > nul
goto start