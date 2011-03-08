# -*- coding: UTF-8 -*-

# Depends on the following external programs:
#  -rsync

from shutil import copy
from subprocess import check_call


@target('7.4.7', 'xivo-cisco-spa-7.4.7')
def build_7_4_7(path):
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'common/', path])
    
    check_call(['rsync', '-rlp', '--exclude', '.*',
                '7.4.7/', path])


@target('legacy', 'xivo-cisco-spa-legacy')
def build_legacy(path):
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'common/', path])
    
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'legacy/', path])


@target('pap2t-5.1.6', 'xivo-cisco-pap2t-5.1.6')
def build_pap2t_5_1_6(path):
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'common/', path])
    
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'pap2t-5.1.6/', path])


@target('spa2102-5.2.10', 'xivo-cisco-spa2102-5.2.10')
def build_spa2102_5_2_10(path):
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'common/', path])
    
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'spa2102-5.2.10/', path])


@target('spa3102-5.1.10', 'xivo-cisco-spa3102-5.1.10')
def build_spa3102_5_1_10(path):
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'common/', path])
    
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'spa3102-5.1.10/', path])


@target('spa8000-6.1.3', 'xivo-cisco-spa8000-6.1.3')
def build_spa8000_6_1_3(path):
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'common/', path])
    
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'spa8000-6.1.3/', path])


@target('spa8800-6.1.7', 'xivo-cisco-spa8800-6.1.7')
def build_spa8800_6_1_7(path):
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'common/', path])
    
    check_call(['rsync', '-rlp', '--exclude', '.*',
                'spa8800-6.1.7/', path])
