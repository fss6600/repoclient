rm -v -r .\dist
rm -v -r .\build

rem c:\python34\Scripts\pyinstaller --clean eiisclient.spec
C:\Users\mb.petrov.66\workspace\.virtualenv\py34_eiisclient\Scripts\pyinstaller --clean eiisclient.spec

rem cd nsis

rem make_full.cmd
