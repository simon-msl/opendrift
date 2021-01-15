#!/usr/bin/env python
"""
SCHISM native reader
==================================
"""

# 
#  Work in progress
# 
# interim script to develop and test an updated version of the SCHISM reader that uses 
# the new methods in unstructured.py 
# 
# 


import numpy as np
from datetime import timedelta, datetime
from opendrift.readers import reader_netCDF_CF_unstructured_SCHISM_v2
from opendrift.readers import reader_global_landmask
from opendrift.readers import reader_landmask_custom
from opendrift.models.oceandrift import OceanDrift

###############################
# MODEL
###############################
o = OceanDrift(loglevel=0)  # Set loglevel to 0 for debug information
###############################
# READERS
###############################
# Creating and adding reader using a native SCHISM netcdf output file
# SCHISM reader
# Landmask - (uses cartopy+rasterized GHSS shorelines)
reader_landmask = reader_global_landmask.Reader(
                    llcrnrlon=171.5, llcrnrlat=-43.5,
                    urcrnrlon=177.0, urcrnrlat=-38.0)

reader_custom = reader_landmask_custom.Reader(polygon_file = 'schism_marl_edit.shore')
# reader_custom.plot() # check reader was correctly loaded, close figure to continue

# NZTM proj4 string found at https://spatialreference.org/ref/epsg/nzgd2000-new-zealand-transverse-mercator-2000/
proj4str_nztm = '+proj=tmerc +lat_0=0 +lon_0=173 +k=0.9996 +x_0=1600000 +y_0=10000000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs'
# schism_native = reader_netCDF_CF_unstructured_SCHISM_v2.Reader(filename = 'https://thredds.met.no/thredds/dodsC/metusers/knutfd/thredds/netcdf_unstructured_samples/schism_marl20080101_00z_3D.nc', proj4 = proj4str_nztm, use_3d = True)
schism_native = reader_netCDF_CF_unstructured_SCHISM_v2.Reader(filename = '/media/simon/Seagate Backup Plus Drive/metocean/0472_SpatNZ_MarlboroughSounds/schism_flows_netcdf/schism_marl20080505_00z_3D.nc', proj4 = proj4str_nztm, use_3d = True)

# schism_native.plot(variable = 'sea_floor_depth_below_sea_level') # check reader was correctly loaded, close figure to continue

o.add_reader([reader_custom,schism_native])
o.set_config('general:use_auto_landmask', False) # prevent opendrift from making a new dynamical landmask with global_landmask

if False:
    o.add_reader([schism_native])
    o.set_config('general:use_auto_landmask', True) # prevent opendrift from making a new dynamical landmask with global_landmask

# Seed elements at defined positions, depth and time
o.seed_elements(lon=174.046669, lat=-40.928116, radius=20, number=100,
                z=np.linspace(0,-10, 100), time=schism_native.start_time)

o.seed_elements(lon= 173.8839, lat=-40.9160, radius=20, number=100,
                z=np.linspace(0,-10, 100), time=schism_native.start_time)

o.seed_elements(lon=174.2940, lat=-41.0888, radius=20, number=100,
                z=np.linspace(0,-10, 100), time=schism_native.start_time)

o.disable_vertical_motion()  #Deactivate any vertical processes/advection"""
#%%
# Running model
o.run(time_step=900, 
	  end_time = schism_native.start_time+timedelta(days=1.0))
	  # outfile='schism_native_output.nc')

#%%
# import pdb;pdb.set_trace()
# Print and plot results
print(o)
o.plot(fast=True)
o.animation()
o.animation_profile()