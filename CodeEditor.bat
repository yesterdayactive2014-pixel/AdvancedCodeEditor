@echo off
title CodeEditor
cd /d "%~dp0"
"C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\python.exe" code_editor.py 2>error.log
pause
