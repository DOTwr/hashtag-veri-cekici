@echo off
setlocal
cd /d "%~dp0"
set "PY="

rem 1) Anaconda / Miniconda (Store kisayolundan once denenir)
for %%P in (
  "%USERPROFILE%\anaconda3\python.exe"
  "%USERPROFILE%\miniconda3\python.exe"
  "%LOCALAPPDATA%\anaconda3\python.exe"
  "%LOCALAPPDATA%\miniconda3\python.exe"
  "%ProgramData%\anaconda3\python.exe"
  "%ProgramData%\miniconda3\python.exe"
  "C:\anaconda3\python.exe"
  "C:\miniconda3\python.exe"
) do (
  if not defined PY if exist %%P set "PY=%%~P"
)

rem 2) py baslaticisi
if not defined PY (
  py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
)

rem 3) python (gercekten calisiyorsa; Store kisayolu bu testi gecemez)
if not defined PY (
  python -c "import sys" >nul 2>nul && set "PY=python"
)

if not defined PY (
  echo.
  echo HATA: Calisan bir Python bulunamadi.
  echo python.org adresinden Python kurun ve kurulumda "Add Python to PATH" kutusunu isaretleyin.
  echo.
  pause
  exit /b 1
)

echo Kullanilan Python: %PY%
%PY% --version
echo.
echo Gerekli paketler kuruluyor (ilk seferde birkac dakika surebilir)...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo HATA: Paket kurulumu basarisiz oldu. Bu pencerenin ekran goruntusunu Claude'a gonderin.
  pause
  exit /b 1
)
echo.
echo Uygulama aciliyor... Tarayicida http://localhost:8501 adresi acilacak.
echo Kapatmak icin bu pencereyi kapatin.
%PY% -m streamlit run app.py
pause
