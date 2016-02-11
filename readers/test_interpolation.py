#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of OpenDrift.
#
# OpenDrift is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2
#
# OpenDrift is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenDrift.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2015, Knut-Frode Dagestad, MET Norway

import unittest
import os
from datetime import datetime, timedelta
import inspect

import numpy as np
import matplotlib.pyplot as plt

import reader_netCDF_CF_generic
import reader_ROMS_native
from interpolation import ReaderBlock, LinearND2DInterpolator, \
                          NDImage2DInterpolator, Nearest2DInterpolator, \
                          Nearest1DInterpolator, Linear1DInterpolator

script_folder = os.path.dirname(
    os.path.abspath(inspect.getfile(inspect.currentframe())))


class TestInterpolation(unittest.TestCase):
    """Tests spatial interpolation"""


    def get_synthetic_data_dict(self):
        data_dict = {}
        data_dict['x'] = np.linspace(-70, 470, 200)
        data_dict['y'] = np.linspace(10, 340, 100)
        data_dict['z'] = np.array([-0, -3, -10, -25, -100])
        # Make a horizontal slice
        xg, yg = np.meshgrid(data_dict['x'], data_dict['y'])
        slice1 = np.ma.array(np.cos(np.radians(xg)) +
                             np.sin(np.radians(yg)))
        # Add some holes
        slice1[0:40, 50:60] = np.nan
        slice1[40:60, 100:120] = np.nan
        slice1[20:22, 30:32] = np.nan
        slice1 = np.ma.masked_invalid(slice1)

        # Make another horizontal slice ("below") with more holes
        slice2 = slice1*1.1
        slice2[70:80, 20:28] = np.nan
        
        # Add a 2D and a 3D variable to dictionary
        data_dict['var2d'] = slice1
        data_dict['var3d'] = np.ma.array([slice1, slice2, 1.2*slice1,
                                          1*3*slice1, 10*slice1])
        data_dict['time'] = datetime.now()

        # Generate some points
        x = np.linspace(data_dict['x'].min(), data_dict['x'].max(), 100)
        y = np.linspace(data_dict['y'].min(), data_dict['y'].max(), 100)
        z = np.linspace(data_dict['z'].min(), data_dict['z'].max(), 100)

        return data_dict, x, y, z

    def test_interpolation_horizontal(self):

        data_dict, x, y, z = self.get_synthetic_data_dict()
        # Make block from dictionary, and apply tests
        b = ReaderBlock(data_dict)
        self.assertEqual(b.data_dict['var2d'].shape,
                         (len(b.y), len(b.x)))
        self.assertEqual(b.data_dict['var3d'].shape,
                         (len(b.z), len(b.y), len(b.x)))
        # Make some element positions
        interpolator2d = b.Interpolator2DClass(b.x, b.y, x, y)
        values = interpolator2d(data_dict['var2d'])
        # Checking output is as expected
        self.assertEqual(values[10], 1.6487979858538129)
        self.assertEqual(sum(values.mask), 15)

    def test_interpolation_vertical(self):

        # 3 elements, 4 depths
        zgrid = np.array([0, 1, 3, 10])
        z = np.array([.5, 3, 9])
        data = np.array([[0, 0, 0],
                         [1, 1, 1],
                         [2, 2, 2],
                         [3, 3, 3]])
        interpolator = Nearest1DInterpolator(zgrid, z)
        self.assertTrue(np.allclose(interpolator(data), [0, 2, 3]))
        interpolator = Linear1DInterpolator(zgrid, z)
        self.assertTrue(np.allclose(interpolator(data),
                                    [0.5, 2, 2.85714286]))

        # And with exatrapolation (~to surface and bottom)
        zgrid = np.array([1, 3, 5, 10])
        z = np.array([.5, 6, 12])
        interpolator = Nearest1DInterpolator(zgrid, z)
        self.assertTrue(np.allclose(interpolator(data), [0, 2, 3]))
        interpolator = Linear1DInterpolator(zgrid, z)
        self.assertTrue(np.allclose(interpolator(data),
                                    [0.0, 2.2, 3]))

    def test_compare_interpolators(self):

        data_dict, x, y, z = self.get_synthetic_data_dict()
        arr = data_dict['var2d']
        # Make block from dictionary, and apply tests
        linearData = LinearND2DInterpolator(data_dict['x'], data_dict['y'],
                                            x, y)(data_dict['var2d'])
        nearestData = Nearest2DInterpolator(data_dict['x'], data_dict['y'],
                                            x, y)(data_dict['var2d'])
        ndimageData = NDImage2DInterpolator(data_dict['x'], data_dict['y'],
                                            x, y)(data_dict['var2d'])

        # Check that all interpolator give nearly equal values
        # for a given position
        i = 10
        self.assertAlmostEqual(linearData[i], nearestData[i], places=2)
        self.assertAlmostEqual(linearData[i], ndimageData[i], places=2)

    def test_interpolation_3dArrays(self):
        """Test interpolation."""
        reader = reader_netCDF_CF_generic.Reader(script_folder + 
            '/../test_data/14Jan2016_NorKyst_z_3d/NorKyst-800m_ZDEPTHS_his_00_3Dsubset.nc')

        # 100000 points within 50x50 pixels over sea (corner of domain)
        num_points = 1000
        np.random.seed(0)  # To get the same random numbers each time
        x = np.random.uniform(reader.xmin, reader.xmin+800*50, num_points)
        y = np.random.uniform(reader.ymax-800*50, reader.ymax, num_points)
        z = np.random.uniform(-200, 0, num_points)
        variables = ['x_sea_water_velocity', 'y_sea_water_velocity',
                     'sea_water_temperature']
        # Read a block of data covering the points
        data = reader.get_variables(variables, time=reader.start_time,
                                    x=x, y=y, z=z, block=True)

        b = ReaderBlock(data, interpolation_horizontal='nearest')
        env, prof = b.interpolate(x, y, z, variables,
                                  profiles=['sea_water_temperature'],
                                  profiles_depth=[-30, 0])
        self.assertAlmostEqual(env['x_sea_water_velocity'][100],
                               0.0750191849228)
        self.assertAlmostEqual(prof['sea_water_temperature'][0,11],
                               7.5499997138977051)
        self.assertAlmostEqual(prof['sea_water_temperature'][-1,11],
                               8.38000011444)
        self.assertEqual(prof['z'][-1], b.z[-1])


if __name__ == '__main__':
    unittest.main()