# -*- mode: python -*-

block_cipher = None


a = Analysis(['eiisclient\\cli.py'],
             pathex=['C:\\Users\\pmike\\workspace\\python\\eiisclient',
                     'C:\\Users\\pmike\\workspace\\python\\eiisclient\\eiisclient'],
             binaries=[],
             datas=[(r'docs\build\html', 'docs'),],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='eiisclient',
          debug=False,
          strip=False,
          upx=False,
          console=False)
