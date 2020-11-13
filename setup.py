#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""
import os
import sys
from pathlib import Path

from setuptools import find_packages, setup

from eiisclient.__version__ import __version__

requirements = [ ]

setup_requirements = [ ]

test_requirements = [ ]


# сборка программы и документации

def build_exe():
    pyi = r'C:\Users\mb.petrov.66\workspace\python\eiisrepo\client\.venv\py34\Scripts\pyinstaller.exe'

    spec = Path(__file__).parent / 'eiisclient.spec'
    wd = Path(__file__).parent / 'build'
    dp = Path(__file__).parent / 'dist'
    os.system('{} -y --distpath {} --workpath {}  --clean {}'.format(pyi, dp, wd, spec))

def build_doc():
    make_path = Path(__file__).parent / 'docs' / 'make.bat'
    os.system('{} html'.format(make_path))


def build_installer():
    nsis = r'"C:\Program Files (x86)\NSIS\bin\makensis.exe"'
    spec = Path(__file__).parent / 'eiisclient_mui.nsi'
    os.environ['CLIENTVER'] = __version__
    os.system('{} /INPUTCHARSET UTF8 -- {}'.format(nsis, spec))


cmd = sys.argv[-1]

if cmd == 'exe':
    build_exe()
    sys.exit()
elif cmd == 'doc':
    build_doc()
    sys.exit()
elif cmd == 'ins':
    build_installer()
    sys.exit()
elif cmd == 'bin':
    build_exe()
    build_installer()
    sys.exit()
elif cmd == 'all':
    build_doc()
    build_exe()
    build_installer()
    sys.exit()


setup(
    author="Michael Petroff",
    author_email='adm_fil_02@ro66.fss.ru',
    classifiers=[
        'Development Status :: 0 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        ],
    description="Обновление ЕИИС Соцстрах. Клиент",
    install_requires=requirements,
    license="Apache 2.0 license",
    # long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='eiisclient',
    name='eiisclient',
    packages=find_packages(include=['eiisclient']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    # url='https://github.com//eiisclient',
    version=__version__,
    zip_safe=False,
        )
