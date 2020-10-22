#!/usr/bin/env python

import os
import errno
import subprocess
import numpy
from netCDF4 import Dataset
import configparser
import shutil

from namelist import update_namelist


def symlink_force(target, link_name):
    # https://stackoverflow.com/a/27103129/7728169
    try:
        os.symlink(target, link_name)
    except OSError as e:
        if e.errno == errno.EEXIST:
            os.remove(link_name)
            os.symlink(target, link_name)
        else:
            raise e


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('Ocean0.cfg')

    cores = config['execution'].getint('ssh_adjustment_cores')
    parallel_executable = config['execution'].get('parallel_executable')
    update_namelist('namelist.ocean', config['namelist'])

    iteration_count = config['ssh_adjustment'].getint('iteration_count')
    variable_to_modify = config['ssh_adjustment'].get('variable_to_modify')

    if variable_to_modify not in ['ssh', 'landIcePressure']:
        raise ValueError("Unknown variable to modify: {}".format(
            variable_to_modify))

    for iter_index in range(iteration_count):
        print(" * Iteration %i/%i" % (iter_index + 1, iteration_count))

        symlink_force('init{}.nc'.format(iter_index), 'init.nc')

        print("   * Running forward model")

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

        print("   - Complete")

        print("   * Updating SSH or land-ice pressure")

        # copy the init file first
        shutil.copyfile('init{}.nc'.format(iter_index),
                        'init{}.nc'.format(iter_index + 1))

        symlink_force('init{}.nc'.format(iter_index+1), 'init.nc')

        initFile = Dataset('init.nc', 'r+')

        nVertLevels = len(initFile.dimensions['nVertLevels'])
        initSSH = initFile.variables['ssh'][0, :]
        bottomDepth = initFile.variables['bottomDepth'][:]
        modifySSHMask = initFile.variables['modifySSHMask'][0, :]
        landIcePressure = initFile.variables['landIcePressure'][0, :]
        lonCell = initFile.variables['lonCell'][:]
        latCell = initFile.variables['latCell'][:]
        maxLevelCell = initFile.variables['maxLevelCell'][:]

        inSSHFile = Dataset('output_ssh.nc', 'r')
        nTime = len(inSSHFile.dimensions['Time'])
        finalSSH = inSSHFile.variables['ssh'][nTime - 1, :]
        topDensity = inSSHFile.variables['density'][nTime - 1, :, 0]
        inSSHFile.close()

        mask = numpy.logical_and(maxLevelCell > 0, modifySSHMask == 1)

        deltaSSH = mask * (finalSSH - initSSH)

        # then, modify the SSH or land-ice pressure
        if variable_to_modify == 'ssh':
            initFile.variables['ssh'][0, :] = finalSSH
            # also update the landIceDraft variable, which will be used to
            # compensate for the SSH due to land-ice pressure when computing
            # sea-surface tilt
            initFile.variables['landIceDraft'][0, :] = finalSSH
            # we also need to stretch layerThickness to be compatible with the
            # new SSH
            stretch = (finalSSH + bottomDepth) / (initSSH + bottomDepth)
            layerThickness = initFile.variables['layerThickness']
            for k in range(nVertLevels):
                layerThickness[0, :, k] *= stretch
        else:
            # Moving the SSH up or down by deltaSSH would change the land-ice
            # pressure by density(SSH)*g*deltaSSH. If deltaSSH is positive
            # (moving up), it means the land-ice pressure is too small and if
            # deltaSSH is negative (moving down), it means land-ice pressure is
            # too large, the sign of the second term makes sense.
            gravity = 9.80616
            deltaLandIcePressure = topDensity * gravity * deltaSSH

            landIcePressure = numpy.maximum(
                0.0, landIcePressure + deltaLandIcePressure)

            initFile.variables['landIcePressure'][0, :] = landIcePressure

            finalSSH = initSSH

        initFile.close()

        # Write the largest change in SSH and its lon/lat to a file
        logFile = open('maxDeltaSSH_{:03d}.log'.format(iter_index), 'w')

        indices = numpy.nonzero(landIcePressure)[0]
        index = numpy.argmax(numpy.abs(deltaSSH[indices]))
        iCell = indices[index]
        logFile.write('deltaSSHMax: {:g}, lon/lat: {:f} {:f}, ssh: {:g}, '
                      'landIcePressure: {:g}\n'.format(
                          deltaSSH[iCell], numpy.rad2deg(lonCell[iCell]),
                          numpy.rad2deg(latCell[iCell]), finalSSH[iCell],
                          landIcePressure[iCell]))
        logFile.close()

        print("   - Complete")
