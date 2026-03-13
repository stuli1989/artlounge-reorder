@echo off
REM Lightweight launcher to avoid a lingering console window.
REM Delegates to the hidden VBScript launcher in the src folder.

start "" wscript.exe "C:\Users\Kshitij Shah\OneDrive\Documents\Art Lounge\ReOrderingProject\src\ArtLounge-Tray.vbs"
exit /b 0

