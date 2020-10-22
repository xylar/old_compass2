#!/usr/bin/env python

import os
import subprocess
import configparser
import numpy
import netCDF4

from update_evaporationFlux import update_evaporation_flux
from namelist import update_namelist


def write_var(outFile, outVarName, field, attrs):
    outVar = outFile.createVariable(outVarName, 'f8', ('Time', 'nCells'))
    outVar[:, :] = field
    outVar.setncatts(attrs)


def process_land_ice_forcing(inFileName, outFileName, years, scaling):
    """
    Scale a reference set of land-ice pressure, draft and fraction data to
    create a time-dependent land-ice forcing dataset.  In the simulation, the
    ice pressure and ice draft will be determined by interpolation in time
    between fields at year boundaries.

    Parameters
    ----------
    inFileName : str
        A file with a reference ``landIceDraft``, ``landIcePressure`` and
        ``landIceFraction``

    outFileName : str
        A file where time-dependent versions of these same fields will be
        written out.

    years : list of int
        A list (or ndarray) of years at which scaled ice draft and ice pressure
        are to be defined

    scaling : list of float
        Fractions to multiply the ice draft and ice pressure by to get the
        time-dependent forcing field.
    """

    # interpolate
    mpasFile = netCDF4.Dataset(inFileName, 'r')
    inLandIceDraft = mpasFile.variables['landIceDraft'][:]
    inLandIcePressure = mpasFile.variables['landIcePressure'][:]
    inLandIceFraction = mpasFile.variables['landIceFraction'][:]
    nCells = len(mpasFile.dimensions['nCells'])
    mpasFile.close()

    StrLen = 64
    nTime = len(years)

    xtime = numpy.zeros((3,), 'S64')
    landIcePressure = numpy.zeros((nTime, nCells), float)
    landIceFraction = numpy.zeros(landIcePressure.shape)
    landIceDraft = numpy.zeros(landIcePressure.shape)

    scaling0 = scaling[0]
    scaling = [s/scaling0 for s in scaling]

    for tIndex in range(nTime):
        xtime[tIndex] = "{:04d}-01-01_00:00:00                               " \
                        "              ".format(years[tIndex])
        landIcePressure[tIndex, :] = scaling[tIndex]*inLandIcePressure
        landIceDraft[tIndex, :] = scaling[tIndex]*inLandIceDraft
        landIceFraction[tIndex, :] = inLandIceFraction

    outFile = netCDF4.Dataset(outFileName, 'w', format='NETCDF3_64BIT_OFFSET')
    outFile.createDimension('Time', size=None)
    outFile.createDimension('nCells', size=nCells)
    outFile.createDimension('StrLen', size=StrLen)

    outVar = outFile.createVariable('xtime', 'S1', ('Time', 'StrLen'))
    for tIndex in range(nTime):
        outVar[tIndex, :] = netCDF4.stringtochar(xtime[tIndex])

    outVar.setncatts({'units': 'unitless'})
    write_var(outFile, 'landIcePressureForcing', landIcePressure,
              {'units': 'Pa',
               'long_name': 'Pressure defined at the sea surface due to '
                            'land ice'})
    write_var(outFile, 'landIceFractionForcing', landIceFraction,
              {'units': 'unitless',
               'long_name': 'The fraction of each cell covered by land ice'})
    write_var(outFile, 'landIceDraftForcing', landIceDraft,
              {'units': 'unitless',
               'long_name': 'The elevation of the interface between land ice '
                            'and the ocean'})

    outFile.close()


def main():
    config = configparser.ConfigParser()
    config.read('Ocean0.cfg')

    cores = config['execution'].getint('simulation_cores')
    parallel_executable = config['execution'].get('parallel_executable')

    pio_tasks = config['execution'].getint('simulation_pio_tasks')
    pio_stride = cores//pio_tasks
    config.set('namelist', 'config_pio_num_iotasks', '{}'.format(pio_tasks))
    config.set('namelist', 'config_pio_stride', '{}'.format(pio_stride))

    scaling = config['forcing'].get('scaling')
    scaling = [float(s) for s in scaling.split(',')]
    if scaling[0] == 0.:
        raise ValueError('The first scaling in the forcing must be nonzero')

    years = list(range(1, len(scaling)+1))

    forcing_filename = 'land_ice_forcing.nc'
    if not os.path.exists(forcing_filename):
        process_land_ice_forcing('init.nc', forcing_filename, years, scaling)

    config.set('namelist',
               'config_time_varying_land_ice_forcing_cycle_duration',
               "'{:04d}-00-00_00:00:00'".format(len(scaling)))

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

    update_evaporation_flux('forcing_data_init.nc', 'forcing_data_updated.nc',
                            'forcing_data.nc')


if __name__ == '__main__':
    main()
