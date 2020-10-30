# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['eiisclient\\main.py'],
             pathex=['C:\\Users\\mb.petrov.66\\workspace\\python\\eiisrepo\\client'],
             binaries=[],
             datas=[(r'docs\build\html', 'docs'), ('LICENSE', '.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='eiisclient',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          icon=r'eiisclient\gui\ico\update-96.ico',
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               upx_exclude=[],
               name='eiisclient')
