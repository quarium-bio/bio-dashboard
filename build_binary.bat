@echo off
echo Building Quarium Dashboard binary...
pyinstaller --noconfirm --windowed --onefile --name "QuariumDashboard" QuariumDashboard.py
echo Build complete! Your new binary is located in the 'dist' folder.
pause