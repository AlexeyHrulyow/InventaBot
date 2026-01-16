@echo off
echo [%date% %time%] Останавливаем все процессы инвентаризационного бота...
taskkill /F /IM python.exe 2>NUL
taskkill /F /IM wscript.exe 2>NUL
del bot.lock 2>NUL
echo [%date% %time%] Все процессы остановлены.
pause