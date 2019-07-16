#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import find_packages, setup

from eiisclient.version import get_version

requirements = [ ]

setup_requirements = [ ]

test_requirements = [ ]

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
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    description="Обновление подсистем ЕИИС Соцстрах",
    install_requires=requirements,
    license="BSD license",
    # long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='eiisclient',
    name='eiisclient',
    packages=find_packages(include=['eiisclient']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    # url='https://github.com//eiisclient',
    version=get_version(),
    zip_safe=False,
)
