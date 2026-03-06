@echo off
echo Telegram Kino Botini ishga tushirish...

set PYTHON_PATH="C:\Users\admin\AppData\Local\Programs\Python\Python311\python.exe"
%PYTHON_PATH% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Xatolik: Python topilmadi! 
    echo Iltimos, Pythonni o'rnating.
    pause
    exit /b
)

echo Kutubxonalarni tekshirish...
%PYTHON_PATH% -m pip install -r requirements.txt

echo Bot ishga tushmoqda...
%PYTHON_PATH% bot.py
pause
