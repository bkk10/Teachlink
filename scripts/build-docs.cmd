@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0build-docs.ps1" %*
