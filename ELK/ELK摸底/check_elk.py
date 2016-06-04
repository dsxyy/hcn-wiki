#!/usr/bin/python
# -*- coding: utf-8 -*-


import commands
import datetime
import time

ECPU = 0.0
EMEM = 0.0
SCPU = 0.0
SMEM = 0.0
ICPU = 0.0
IMEM = 0.0
KCPU = 0.0
KMEM = 0.0

COUNT = 0


def check(filename):
    global ECPU, EMEM, SCPU, SMEM, ICPU, IMEM, KCPU, KMEM, COUNT

    f = open(filename, 'a')

    f.write(datetime.datetime.now().ctime() + '\n')
    ecpu = float(commands.getoutput(
        "ps aux |grep elasticsearch| grep -v grep | awk '{print $3}'"))
    emem = float(commands.getoutput(
        "ps aux |grep elasticsearch| grep -v grep | awk '{print $4}'"))
    f.write("elasticsearch: cpu_util = %f; mem_util = %f.\n" % (ecpu, emem))
    f.write(commands.getoutput(
        "du /opt/elasticsearch/ --max-depth=1 -h") + "\n")
    ECPU += ecpu
    EMEM += emem

    scpu = float(commands.getoutput(
        "ps aux |grep shipper| grep -v grep | awk '{print $3}'"))
    smem = float(commands.getoutput(
        "ps aux |grep shipper| grep -v grep | awk '{print $4}'"))
    f.write("shipper: cpu_util = %f; mem_util = %f.\n" % (scpu, smem))
    SCPU += scpu
    SMEM += smem

    icpu = float(commands.getoutput(
        "ps aux |grep indexer| grep -v grep | awk '{print $3}'"))
    imem = float(commands.getoutput(
        "ps aux |grep indexer| grep -v grep | awk '{print $4}'"))
    f.write("indexer: cpu_util = %f; mem_util = %f.\n" % (icpu, imem))
    ICPU += icpu
    IMEM += imem

    kcpu = float(commands.getoutput(
        "ps aux |grep kibana| grep -v grep | awk '{print $3}'"))
    kmem = float(commands.getoutput(
        "ps aux |grep kibana| grep -v grep | awk '{print $4}'"))
    f.write("kibana: cpu_util = %f; mem_util = %f.\n" % (kcpu, kmem))
    KCPU += kcpu
    KMEM += kmem

    COUNT += 1

    if COUNT == 24:
        f.write('\n' + datetime.datetime.now().ctime() + '\n')
        f.write("oneday average ecpu_util = %f; emem_util = %f.\n\n" % (
            ECPU / 24, EMEM / 24))
        f.write("oneday average scpu_util = %f; smem_util = %f.\n\n" % (
            SCPU / 24, SMEM / 24))
        f.write("oneday average icpu_util = %f; imem_util = %f.\n\n" % (
            ICPU / 24, IMEM / 24))
        f.write("oneday average kcpu_util = %f; kmem_util = %f.\n\n" % (
            KCPU / 24, KMEM / 24))

        ECPU = 0.0
        EMEM = 0.0
        SCPU = 0.0
        SMEM = 0.0
        ICPU = 0.0
        IMEM = 0.0
        KCPU = 0.0
        KMEM = 0.0

        COUNT = 0

    f.close()


if __name__ == "__main__":

    hostname = commands.getoutput("hostname")
    filename = '/home/' + hostname + '_check.txt'

    while True:
        check(filename)
        time.sleep(60 * 60)
