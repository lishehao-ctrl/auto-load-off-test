# Environment setup notes
# cd C:\Users\15038\Desktop\HardWare\mm_report 
# python -m venv venv
# .\venv\Scripts\Activate.ps1
# python issues.py
# pip install requests PyGithub pyinstaller
# pyinstaller --onefile --name test_load_off.exe main.py

from ui import UI

ui_mm_control = UI()
ui_mm_control.mainloop()
