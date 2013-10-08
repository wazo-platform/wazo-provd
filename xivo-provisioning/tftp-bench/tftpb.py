#!/usr/bin/python
# -*- coding: UTF-8 -*-

import argparse
import os
import socket
import subprocess
import sys
import time
from itertools import chain, repeat

SCCP_7912 = [
    # does not include the files not on the server
    'test1400',
    'test256',
    'test2K',
    'test16K',
    'test16',
    'test768',
]
SCCP_7940 = [
    # does not include the files not on the server
    'test1400',
    'test256',
    'test256',
    'test1400',
    'test1400',
    'test16',
    'test16',
]
FILENAMES = list(chain(SCCP_7912, SCCP_7940))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--simult', type=int, default=10,
                        help='number of simultaneous request')
    parser.add_argument('-l', '--loop', type=int, default=10,
                        help='number of request loop to run')
    parser.add_argument('hostname',
                        help='hostname')

    parsed_args = parser.parse_args()

    stats = Statistics()
    stats.on_start()
    try:
        run_tftp_bench(parsed_args.hostname, parsed_args.loop, parsed_args.simult, stats)
    finally:
        stats.on_end()
        stats.display()


class Statistics(object):

    def __init__(self):
        self._rrq_success = 0
        self._rrq_failure = 0

    def on_start(self):
        self._start_time = time.time()

    def on_end(self):
        self._end_time = time.time()

    def on_rrq_success(self):
        self._rrq_success += 1

    def on_rrq_failure(self):
        self._rrq_failure += 1

    def display(self):
        duration = self._end_time - self._start_time
        rrq_total = self._rrq_failure + self._rrq_success
        if rrq_total:
            rrq_failure_pct = '%.1f%%' % (self._rrq_failure / float(rrq_total) * 100)
        else:
            rrq_failure_pct = 'N/A'
        print 'Time: %.3f' % duration
        print 'Total number of RRQ: %s' % rrq_total
        print 'Total number of failed RRQ: %s (%s)' % (self._rrq_failure, rrq_failure_pct)


def run_tftp_bench(hostname, loop, simult, stats):
    if simult < 1:
        raise ValueError('invalid simult value %s' % simult)

    # keep reference to Popen object since they do a non blocking wait
    # when they are garbage collected, which is something we DON'T want
    process_by_pid = {}
    devnull_fd = os.open(os.devnull, os.O_RDWR)
    hostname_ip = socket.gethostbyname(hostname)
    try:
        cur_simult = 0
        for filename in filenames_generator(FILENAMES, loop):
            while cur_simult >= simult:
                pid, status = os.wait()
                if os.WIFEXITED(status):
                    if os.WEXITSTATUS(status):
                        stats.on_rrq_failure()
                    else:
                        stats.on_rrq_success()
                    del process_by_pid[pid]
                    cur_simult -= 1
            command = ['atftp', '-g', '-r', filename, '-l', os.devnull, hostname_ip]
            p = subprocess.Popen(command, stdin=devnull_fd, stdout=devnull_fd, stderr=devnull_fd)
            process_by_pid[p.pid] = p
            cur_simult += 1
    finally:
        os.close(devnull_fd)

    # XXX a bit ugly, more or less a copy/paste stuff above
    while cur_simult > 0:
        pid, status = os.wait()
        if os.WIFEXITED(status):
            if os.WEXITSTATUS(status):
                stats.on_rrq_failure()
            else:
                stats.on_rrq_success()
            cur_simult -= 1
            del process_by_pid[pid]


def filenames_generator(filenames, n):
    return chain.from_iterable(repeat(tuple(filenames), n))


main()
