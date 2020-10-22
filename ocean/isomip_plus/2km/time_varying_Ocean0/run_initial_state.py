#!/usr/bin/env python

import os
import subprocess
import configparser

from namelist import update_namelist


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('Ocean0.cfg')

    cores = config['execution'].getint('init_cores')
    parallel_executable = config['execution'].get('parallel_executable')

    pio_tasks = config['execution'].getint('init_pio_tasks')
    pio_stride = cores//pio_tasks
    config.set('namelist', 'config_pio_num_iotasks', '{}'.format(pio_tasks))
    config.set('namelist', 'config_pio_stride', '{}'.format(pio_stride))

    update_namelist('namelist.ocean', config['namelist'])

    subprocess.check_call(['gpmetis', 'graph.info', '{}'.format(cores)])
    print("\n")
    print("     *****************************")
    print("     ** Starting model run step **")
    print("     *****************************")
    print("\n")
    os.environ['OMP_NUM_THREADS'] = '1'

    subprocess.check_call([parallel_executable, '-n', '{}'.format(cores),
                           './ocean_model', '-n', 'namelist.ocean',
                           '-s', 'streams.ocean'])
    print("\n")
    print("     *****************************")
    print("     ** Finished model run step **")
    print("     *****************************")
    print("\n")
