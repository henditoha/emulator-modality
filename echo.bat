@echo off
TITLE Menjalankan Aplikasi Python

echo ===================================================
echo Memulai proses eksekusi aplikasi...
echo ===================================================

REM 3. Validasi keberadaan file aplikasi
IF NOT EXIST "app.py" (
    echo [ERROR] File 'app.py' tidak ditemukan di direktori ini!
    echo [INFO] Menonaktifkan virtual environment...
    call deactivate
    pause
    exit /b 1
)

REM 4. Menjalankan aplikasi
echo [INFO] Menjalankan echo...
echo ---------------------------------------------------
python app.py echo
echo ---------------------------------------------------


echo ===================================================
echo Eksekusi selesai dengan aman.
echo ===================================================
pause