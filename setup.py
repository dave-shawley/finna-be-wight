#!/usr/bin/env python
#

import setuptools

import batcher


try:
    with open('LOCAL-VERSION', 'r') as version_file:
        version = batcher.version + version_file.readline()
except IOError:
    version = batcher.version

requirements = []
with open('requires/install.txt') as req_file:
    for line in req_file:
        if '#' in line:
            line = line[:line.index('#')]
        line = line.strip()
        if line:
            requirements.append(line)

setuptools.setup(
    name='batcher',
    version=version,
    packages=['batcher'],
    install_requires=requirements,
)
