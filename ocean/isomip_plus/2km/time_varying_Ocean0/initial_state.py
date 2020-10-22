#!/usr/bin/env python

import os
import subprocess
import configparser
from namelist import update_namelist


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('Ocean0.cfg')

    update_namelist('namelist.ocean', config['namelist'])

    init_cores = config['execution'].getint('init_cores')
    parallel_executable = config['execution'].get('parallel_executable')

    subprocess.check_call(['gpmetis', 'graph.info', '{}'.format(init_cores)])
    print("\n")
    print("     *****************************")
    print("     ** Starting model run step **")
    print("     *****************************")
    print("\n")
    os.environ['OMP_NUM_THREADS'] = '1'

    subprocess.check_call([parallel_executable, '-n', '{}'.format(init_cores),
                           './ocean_model', '-n', 'namelist.ocean',
                           '-s', 'streams.ocean'])
    print("\n")
    print("     *****************************")
    print("     ** Finished model run step **")
    print("     *****************************")
    print("\n")
