#!/usr/bin/env python

import os
import subprocess
from processInputGeometry import process_input_geometry
from namelist import update_namelist
import configparser
import xarray
from mpas_tools.mesh.conversion import convert, cull
from mpas_tools.io import write_netcdf


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('Ocean0.cfg')

    init_cores = config['execution'].getint('init_cores')
    parallel_executable = config['execution'].get('parallel_executable')
    update_namelist('namelist.ocean', config['namelist'])

    filter_sigma = config['geometry'].getfloat('filter_sigma')
    min_ice_thickness = config['geometry'].getfloat('min_ice_thickness')

    scaling = config['forcing'].get('scaling')
    scaling = [float(s) for s in scaling.split(',')]
    years = config['forcing'].get('years')
    years = [int(y) for y in years.split(',')]
    if years[0] != 1:
        raise ValueError('The first year in the forcing must be 0001')

    process_input_geometry('input_geometry.nc', 'input_geometry_processed.nc',
                           filterSigma=filter_sigma,
                           minIceThickness=min_ice_thickness, scale=scaling[0])

    dsMesh = convert(xarray.open_dataset('base_mesh.nc'),
                     graphInfoFileName='graph.info')
    write_netcdf(dsMesh, 'mesh.nc', format='NETCDF3_64BIT')

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

    dsCulled = cull(xarray.open_dataset('ocean.nc'))
    dsCulled.attrs['is_periodic'] = 'NO'
    write_netcdf(dsCulled, 'culled_mesh.nc', format='NETCDF3_64BIT')
