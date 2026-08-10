@echo off
REM Stop hook: chan Claude Code dung lai cho den khi PROGRESS.md co sentinel.
REM
REM LUU Y VE DAU MU: pattern phai la "^STATUS" voi MOT dau mu, khong phai "^^".
REM Trong regex cua findstr, dau mu dau tien la neo dau dong; dau mu thu hai bi
REM hieu la KY TU mu theo nghia den, nen "^^STATUS" doi mot dong bat dau bang
REM ky tu ^ roi moi den STATUS - dieu khong bao gio xay ra. Hook vi the block
REM vinh vien du file hoan toan dung. Da do bang probe:
REM     doubled_caret_errorlevel=1   (khong khop)
REM     single_caret_errorlevel=0    (khop)
REM
REM PROGRESS.md phai la ASCII thuan: findstr va cac cong cu doc file khac tren
REM Windows dung cp1252 mac dinh, khong giai ma duoc tieng Viet UTF-8.
REM Nhat ky tieng Viet day du nam o Docs\progress-log-vi.md.
set "PF=%~dp0..\..\PROGRESS.md"
findstr /R /C:"^STATUS: *ALL_MILESTONES_DONE" /C:"^STATUS: *BLOCKED" "%PF%" >nul 2>&1
if %ERRORLEVEL% EQU 0 exit /b 0
echo {"decision":"block","reason":"PROGRESS.md has no STATUS: ALL_MILESTONES_DONE or STATUS: BLOCKED yet. Read PROGRESS.md, identify the next task and execute it immediately. Do NOT ask the user whether to continue."}
exit /b 0
