#!/usr/bin/env python

from setuptools import setup

PACKAGE = 'worklog'

setup(name='EduTracTicketWorklog',
      description='Plugin to manage the which tickets users are currently working on',
      keywords='trac plugin ticket working log',
      version='0.1',
      url='',
      license='MIT',
      author='Colin Guthrie, Aleksey A. Porfirov',
      author_email='lexqt@yandex.ru',
      packages=[PACKAGE],
      package_data={PACKAGE : ['templates/*.cs', 'templates/*.html', 'htdocs/*.css', 'htdocs/*.png', 'htdocs/*.js']},
      entry_points={'trac.plugins': '%s = %s' % (PACKAGE, PACKAGE)})


#### AUTHORS ####
## Author of original trac Worklog plugin:
## Colin Guthrie
## http://colin.guthr.ie/
## trac@colin.guthr.ie
## trac-hacks user: coling
##
## Author of EduTrac adaptation and enhancements:
## Aleksey A. Porfirov
## lexqt@yandex.ru
## github: lexqt

