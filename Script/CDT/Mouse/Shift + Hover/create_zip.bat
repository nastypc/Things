@echo off
echo Creating zip file...
powershell -Command "Compress-Archive -Path 'shift_hover_converter.exe' -DestinationPath 'shift_hover_converter.zip' -Force"
echo Zip file created successfully!
pause