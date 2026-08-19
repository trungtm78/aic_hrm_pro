@echo off
REM Start the AIConnect HRM Pro demo servers.
REM
REM Two of them, on purpose. 8074 carries the customer's own DLSP plan;
REM 8079 carries the fictional Acme dataset that ships with the app and
REM is the one screenshots are published from. Both configs pin dbfilter
REM and hide the database list, so neither can reach the working
REM database by a wrong click during a demo.

setlocal
cd /d "%~dp0"

echo Starting customer demo  ... http://127.0.0.1:8074
start "AIC HRM demo 8074 (DLSP)" cmd /c "set PYTHONUTF8=1&& python odoo-bin -c odoo.customer.conf"

echo Starting international demo http://127.0.0.1:8079
start "AIC HRM demo 8079 (Acme)" cmd /c "set PYTHONUTF8=1&& python odoo-bin -c odoo.demo.conf"

echo.
echo Give them about 40 seconds, then open:
echo    http://127.0.0.1:8074   admin / admin   - DLSP 2026, Vietnamese
echo    http://127.0.0.1:8079   admin / admin   - Acme FY 2026, English
echo.
echo Close the two server windows to stop them.
pause
