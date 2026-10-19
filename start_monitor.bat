@echo off

cd /d D:\bandwidth-monitor

call venv\Scripts\activate.bat

python -m monitor.health_monitor