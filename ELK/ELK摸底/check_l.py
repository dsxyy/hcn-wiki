#!/usr/bin/python
# -*- coding: utf-8 -*-


import commands
import datetime
import time


SCPU = 0.0
SMEM = 0.0
COUNT = 0


def check(filename):
    global SCPU, SMEM, COUNT

    f = open(filename, 'a')

    f.write(datetime.datetime.now().ctime() + '\n')

    scpu = float(commands.getoutput(
        "ps aux |grep shipper| grep -v grep | awk '{print $3}'"))
    smem = float(commands.getoutput(
        "ps aux |grep shipper| grep -v grep | awk '{print $4}'"))
    f.write("shipper: cpu_util = %f; mem_util = %f.\n" % (scpu, smem))
    SCPU += scpu
    SMEM += smem

    COUNT += 1

    if COUNT == 24:
        f.write('\n' + datetime.datetime.now().ctime() + '\n')
        f.write("oneday average scpu_util = %f; smem_util = %f.\n\n" % (
            SCPU / 24, SMEM / 24))

        SCPU = 0.0
        SMEM = 0.0
        COUNT = 0

    f.close()


if __name__ == "__main__":

    hostname = commands.getoutput("hostname")
    filename = '/home/' + hostname + '_check.txt'

    while True:
        check(filename)
        time.sleep(60 * 60)
