Set shell = CreateObject("WScript.Shell")

' Ensure the working directory is the src folder
shell.CurrentDirectory = "C:\Users\Kshitij Shah\OneDrive\Documents\Art Lounge\ReOrderingProject\src"

' Run the tray app using pythonw.exe so no console window is shown.
' 0 = hidden window, False = do not wait for completion.
shell.Run """venv\Scripts\pythonw.exe"" ""artlounge_tray.py""", 0, False

