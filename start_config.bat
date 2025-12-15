@echo off
echo Starting prisma config...
echo.
python -m prisma generate
@REM python -m prisma db push
echo.