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

import os
import numpy as np
from datetime import datetime

#from opendrift import OpenDriftSimulation
from opendrift3D import OpenDrift3DSimulation, Lagrangian3DArray


# Defining the oil element properties
class Oil3D(Lagrangian3DArray):
    """Extending LagrangianArray with variables relevant for oil particles."""

    variables = Lagrangian3DArray.add_variables([
        ('diameter', {'dtype': np.float32,
                       'units': 'm',
                       'default': 0.0001}), # Typical from litterture
        ('mass_oil', {'dtype': np.float32,
                      'units': 'kg',
                      'default': 1}),
        ('viscosity', {'dtype': np.float32,
                       #'unit': 'mm2/s (centiStokes)',
                       'units': 'N s/m2 (Pa s)',
                       'default': 0.5}),
        ('density', {'dtype': np.float32,
                     'units': 'kg/m^3',
                     'default': 880}),
        ('age_seconds', {'dtype': np.float32,
                         'units': 's',
                         'default': 0}),
        ('age_exposure_seconds', {'dtype': np.float32,
                                  'units': 's',
                                  'default': 0}),
        ('age_emulsion_seconds', {'dtype': np.float32,
                                  'units': 's',
                                  'default': 0}),
        ('mass_emulsion', {'dtype': np.float32,
                           'units': 'kg',
                           'default': 0}),
        ('mass_dispersed', {'dtype': np.float32,
                           'units': 'kg',
                           'default': 0}),
        ('mass_evaporated', {'dtype': np.float32,
                                 'units': 'kg',
                                 'default': 0}),
        ('fraction_evaporated', {'dtype': np.float32,
                                 'units': '%',
                                 'default': 0}),
        ('water_content', {'dtype': np.float32,
                           'units': '%',
                           'default': 0})])


class OpenOil3D(OpenDrift3DSimulation):
    """Open source oil trajectory model based on the OpenDrift framework.

        Developed at MET Norway based on oil weathering parameterisations
        found in open/published litterature.

        Under construction.
    """

    ElementType = Oil3D

    required_variables = ['x_sea_water_velocity', 'y_sea_water_velocity',
                          'sea_surface_wave_significant_height',
                          'sea_surface_wave_to_direction',
                          'sea_ice_area_fraction',
                          'x_wind', 'y_wind', 'land_binary_mask',
                          'sea_floor_depth_below_sea_level',
                          'ocean_vertical_diffusivity',
                          'sea_water_temperature',
                          'sea_water_salinity'
                          #'upward_sea_water_velocity'
                          ]

    fallback_values = {'x_sea_water_velocity': 0,
                       'y_sea_water_velocity': 0,
                       'sea_surface_wave_significant_height': 0,
                       'sea_surface_wave_to_direction': 0,
                       'sea_ice_area_fraction': 0,
                       'x_wind': 0, 'y_wind': 0,
                       'sea_floor_depth_below_sea_level': 100,
                       'ocean_vertical_diffusivity': 0.02, #m2s-1
                       'sea_water_temperature': 10.,
                       'sea_water_salinity' : 34.
                       #'upward_sea_water_velocity': 0
                       }

    # Default colors for plotting
    status_colors = {'initial': 'green', 'active': 'blue',
                     'missing_data': 'gray', 'stranded': 'red',
                     'evaporated': 'yellow', 'dispersed': 'magenta'}

    # Read oil types from file (presently only for illustrative effect)
    oil_types = str([str(l.strip()) for l in open(
                    os.path.dirname(os.path.realpath(__file__))
                    + '/oil_types.txt').readlines()])[1:-1]
    default_oil = oil_types.split(',')[0].strip()


    # Configuration

    configspec = '''
        [input]
            readers = list(min=1, default=list(''))
            [[spill]]
                longitude = float(min=-360, max=360, default=5)
                latitude = float(min=-90, max=90, default=60)
                time = string(default='%s')
                oil_type = option(%s, default=%s)
        [processes]
            turbulentmixing = boolean(default=True)
            verticaladvection = boolean(default=False)
            dispersion = boolean(default=True)
            diffusion = boolean(default=True)
            evaporation = boolean(default=True)
            emulsification = boolean(default=True)
        [drift]
            wind_drift_factor = float(min=0, max=1, default=0.02)
            current_uncertainty = float(min=0, max=5, default=.1)
            wind_uncertainty = float(min=0, max=5, default=1)
            relative_wind = boolean(default=True)
        [turbulentmixing]
            timestep = float(min=0.1, max=3600, default=1.)
            verticalresolution = float(min=0.01, max=10, default = 1.)
            diffusivitymodel = string(default='environment')

    ''' % (datetime.now().strftime('%Y-%d-%m %H:00'), oil_types, default_oil)

    def __init__(self, *args, **kwargs):

        # Read oil properties from file
        self.oiltype_file = os.path.dirname(os.path.realpath(__file__)) + \
                                '/oilprop.dat'
        oilprop = open(self.oiltype_file)
        oiltypes = []
        linenumbers = []
        for i, line in enumerate(oilprop.readlines()):
            if line[0].isalpha():
                oiltype = line.strip()[:-2].strip()
                oiltypes.append(oiltype)
                linenumbers.append(i)
        oiltypes, linenumbers = zip(*sorted(zip(oiltypes, linenumbers)))
        self.oiltypes = oiltypes
        self.oiltypes_linenumbers = linenumbers

        # Calling general constructor of parent class
        super(OpenOil3D, self).__init__(*args, **kwargs)

    def update_terminal_velocity(self):
        """Calculate terminal velocity for oil droplets

        according to 
        Tkalich et al. (2002): Vertical mixing of oil droplets by breaking waves
        Marine Pollution Bulletin 44, 1219-1229
        """
        g = 9.81 # ms-2

        r = self.elements.diameter # particle radius
        T0 = self.environment.sea_water_temperature
        S0 = self.environment.sea_water_salinity
        rho_oil = self.elements.density
        rho_water = sea_water_density(T=T0, S=S0)

        # dynamic water viscosity
        my_w = 0.001*(1.7915 - 0.0538*T0 + 0.007*(T0**(2.0)) - 0.0023*S0) # ~0.0014 kg m-1 s-1
        # kinemativ water viscosity
        ny_w = my_w / rho_water
        # 
        rhopr = rho_oil/rho_water

        # terminal velocity for low Reynolds numbers
        kw = 2*g*(1-rhopr)/(9*ny_w)
        W = kw * r**2
        #print r[0:10], 'r'
        #print ny_w[0:10], 'ny_w'
        #print W[0:10], 'W before'

        #check if we are in a high Reynolds number regime
        Re = 2*r*W/ny_w
        highRe = np.where(Re > 50) 
        
        # Terminal velocity in high Reynolds numbers
        kw = (16*g*(1-rhopr)/3)**0.5
        W2 = kw*r**0.5

        W[highRe] = W2[highRe]
        #print W[0:10], 'W after'
        self.elements.terminal_velocity = W 

    def update(self):
        """Update positions and properties of oil particles."""

        self.elements.age_seconds += self.time_step.total_seconds()

        # Calculate windspeed, which is needed for emulsification,
        # and dispersion (if wave height is not given)
        windspeed = np.sqrt(self.environment.x_wind**2 +
                            self.environment.y_wind**2)

        ################
        ## Evaporation
        ################
        if self.config['processes']['evaporation'] is True:
            # Store evaporation fraction at beginning of timestep
            fraction_evaporated_previous = self.elements.fraction_evaporated

            # Evaporate only elements at surface
            at_surface = (self.elements.z == 0)
            if np.isscalar(at_surface):
                at_surface = at_surface*np.ones(self.num_elements_active(),
                                                dtype=bool)
            Urel = windspeed/self.model.reference_wind  # Relative wind
            h = 2  # Film thickness in mm, harcoded for now

            # Calculate exposure time
            #   presently without compensation for sea temperature
            delta_exposure_seconds = \
                (self.model.reference_thickness/h)*Urel * \
                self.time_step.total_seconds()
            if np.isscalar(self.elements.age_exposure_seconds):
                self.elements.age_exposure_seconds += delta_exposure_seconds
            else:
                self.elements.age_exposure_seconds[at_surface] += \
                    delta_exposure_seconds[at_surface]

            self.elements.fraction_evaporated = np.interp(
                self.elements.age_exposure_seconds,
                self.model.tref, self.model.fref)
            self.mass_evaporated = \
                self.elements.mass_oil*self.elements.fraction_evaporated
            # Remove evaporated part from mass_oil
            mass_evaporated_timestep = self.elements.mass_oil*(
                self.elements.fraction_evaporated -
                fraction_evaporated_previous)
            self.elements.mass_oil -= mass_evaporated_timestep
            self.elements.mass_evaporated += mass_evaporated_timestep

            # Evaporation probability equals the difference in fraction
            # evaporated at this timestep compared to previous timestep,
            # divided by the remaining fraction of the particle at
            # previous timestep
            evaporation_probability = ((self.elements.fraction_evaporated -
                                        fraction_evaporated_previous) /
                                       (1 - fraction_evaporated_previous))
            evaporation_probability[~at_surface] = 0
            evaporated_indices = (evaporation_probability >
                                  np.random.rand(self.num_elements_active(),))
            self.deactivate_elements(evaporated_indices, reason='evaporated')

        ##################
        # Emulsification
        ##################
        if self.config['processes']['emulsification'] is True:
            # Apparent emulsion age of particles
            Urel = windspeed/self.model.reference_wind  # Relative wind
            self.elements.age_emulsion_seconds += \
                Urel*self.time_step.total_seconds()

            self.elements.water_content = np.interp(
                self.elements.age_emulsion_seconds,
                self.model.tref, self.model.wmax)

        ###############
        # Dispersion
        ###############
        if self.config['processes']['dispersion'] is True:

            # From NOAA PyGnome model:
            # https://github.com/NOAA-ORR-ERD/PyGnome/
            v_entrain = 3.9E-8
            sea_water_density = 1028
            fraction_breaking_waves = 0.02
            wave_significant_height = \
                self.environment.sea_surface_wave_significant_height
            wave_significant_height[wave_significant_height == 0] = \
                0.0246*windspeed[wave_significant_height == 0]**2
            dissipation_wave_energy = \
                (0.0034*sea_water_density*9.81*wave_significant_height**2)
            c_disp = np.power(dissipation_wave_energy, 0.57) * \
                fraction_breaking_waves
            # Roy's constant
            C_Roy = 2400.0 * np.exp(-73.682*np.sqrt(
                self.elements.viscosity/self.elements.density))

            q_disp = C_Roy * c_disp * v_entrain / self.elements.density

            oil_mass_loss = (q_disp * self.time_step.total_seconds() *
                             self.elements.density)*self.elements.mass_oil

            self.elements.mass_oil -= oil_mass_loss
            self.elements.mass_dispersed += oil_mass_loss

            #self.elements.z = \
            #    self.environment.sea_surface_wave_significant_height

            ## Marks R. (1987), Marine aerosols and whitecaps in the
            ## North Atlantic and Greenland sea regions
            ## Deutsche Hydrografische Zeitschrift, Vol 40, Issue 2 , pp 71-79
            #whitecap_coverage = (2.54E-4)*np.power(windspeed, 3.58)

            ## Martinsen et al. (1994), The operational
            ## oil drift system at DNMI
            ## DNMI Technical report No 125, 51
            #wave_period = 3.85*np.sqrt(
            #    self.environment.sea_surface_wave_significant_height)  # sec

            #time_between_breaking_events = 3.85/whitecap_coverage  # TBC

            #rho_w = 1025  # kg/m3
            #wave_period[wave_period == 0] = 5  # NB: temporal fix for no waves
            #dissipation_energy = 0.0034*rho_w*9.81*(wave_period**2)
            #dsize_coeff = 2100  # Wettre et al., Appendix A
            #c_oil = dsize_coeff*np.power(self.elements.viscosity, -0.4)
            ## Random numbers between 0 and 1:
            #p = np.random.rand(self.num_elements_active(), )
            #oil_per_unit_surface = 1
            #droplet_size = np.power((p*oil_per_unit_surface)/(c_oil *
            #                        np.power(dissipation_energy, 0.57)),
            #                        1/1.17)
            #self.deactivate_elements(droplet_size < 5E-7, reason='dispersed')

        ###################
        # Turbulent Mixing
        ###################
        if self.config['processes']['turbulentmixing'] is True:

            self.update_terminal_velocity()
            self.vertical_mixing()

        ###################
        # Vertical advection
        ###################
        if self.config['processes']['verticaladvection'] is True:

            self.vertical_advection(self.environment.upward_sea_water_velocity)

        ####################################
        # Deactivate elements hitting coast
        ####################################
        self.deactivate_elements(self.environment.land_binary_mask == 1,
                                 reason='stranded')

        ##########################################
        # Do not let particles go below seafloor
        ##########################################
        self.elements.z[np.where(self.elements.z < \
            -self.environment.sea_floor_depth_below_sea_level)] = \
            -self.environment.sea_floor_depth_below_sea_level

        ########################################
        ## Deactivate elements hitting sea ice
        ########################################
        self.deactivate_elements(self.environment.sea_ice_area_fraction > 0.6,
                                 reason='oil-in-ice')

        ##############################################
        # Simply move particles with ambient current
        ##############################################
        self.update_positions(self.environment.x_sea_water_velocity,
                              self.environment.y_sea_water_velocity)

        ##############
        # Wind drag
        ##############
        wind_drift_factor = self.config['drift']['wind_drift_factor']
        if self.config['drift']['relative_wind'] is True:
            self.update_positions((self.environment.x_wind -
                                   self.environment.x_sea_water_velocity)*
                                   wind_drift_factor,
                                  (self.environment.y_wind -
                                   self.environment.y_sea_water_velocity)*
                                   wind_drift_factor)
        else:
            self.update_positions(self.environment.x_wind*wind_drift_factor,
                                  self.environment.y_wind*wind_drift_factor)

        ############################
        # Uncertainty / diffusion
        ############################
        if self.config['processes']['diffusion'] is True:
            # Current
            std_current_comp = self.config['drift']['current_uncertainty']
            if std_current_comp > 0:
                sigma_u = np.random.normal(0, std_current_comp,
                                           self.num_elements_active())
                sigma_v = np.random.normal(0, std_current_comp,
                                           self.num_elements_active())
            else:
                sigma_u = 0*self.environment.x_wind
                sigma_v = 0*self.environment.x_wind
            self.update_positions(sigma_u, sigma_v)

            # Wind
            std_wind_comp = self.config['drift']['wind_uncertainty']
            if wind_drift_factor > 0 and std_wind_comp > 0:
                sigma_u = np.random.normal(0, std_wind_comp*wind_drift_factor,
                                           self.num_elements_active())
                sigma_v = np.random.normal(0, std_wind_comp*wind_drift_factor,
                                           self.num_elements_active())
            else:
                sigma_u = 0*self.environment.x_wind
                sigma_v = 0*self.environment.x_wind
            self.update_positions(sigma_u, sigma_v)

    def plot_oil_budget(self):
        import matplotlib.pyplot as plt
        mass_oil, status = self.get_property('mass_oil')
        if 'stranded' not in self.status_categories:
            self.status_categories.append('stranded')
        mass_active = np.ma.sum(np.ma.masked_where(
                status==self.status_categories.index('stranded'),
                    mass_oil), axis=1)
        mass_stranded = np.ma.sum(np.ma.masked_where(
            status!=self.status_categories.index('stranded'),
            mass_oil), axis=1)
        mass_evaporated, status = self.get_property('mass_evaporated')
        mass_evaporated = np.sum(mass_evaporated, axis=1)
        mass_dispersed, status = self.get_property('mass_dispersed')
        mass_dispersed = np.sum(mass_dispersed, axis=1)

        budget = np.row_stack((mass_dispersed, mass_active,
                               mass_stranded, mass_evaporated))
        budget = np.cumsum(budget, axis=0)

        time, time_relative = self.get_time_array()
        time = np.array([t.total_seconds()/3600. for t in time_relative])
        fig = plt.figure()
        # Left axis showing oil mass
        ax1 = fig.add_subplot(111)
        # Hack: make some emply plots since fill_between does not support label
        ax1.add_patch(plt.Rectangle((0, 0), 0, 0,
                      color='salmon', label='dispersed'))
        ax1.add_patch(plt.Rectangle((0, 0), 0, 0,
                      color='royalblue', label='in water'))
        ax1.add_patch(plt.Rectangle((0, 0), 0, 0,
                      color='black', label='stranded'))
        ax1.add_patch(plt.Rectangle((0, 0), 0, 0,
                      color='skyblue', label='evaporated'))

        ax1.fill_between(time, 0, budget[0,:], facecolor='salmon')
        ax1.fill_between(time, budget[0,:], budget[1,:],
                         facecolor='royalblue')
        ax1.fill_between(time, budget[1,:], budget[2,:],
                         facecolor='black')
        ax1.fill_between(time, budget[2,:], budget[3,:],
                         facecolor='skyblue')
        ax1.set_ylim([0,budget.max()])
        ax1.set_xlim([0,time.max()])
        ax1.set_ylabel('Mass oil  [%s]' %
                        self.elements.variables['mass_oil']['units'])
        ax1.set_xlabel('Time  [hours]')
        # Right axis showing percent
        ax2 = ax1.twinx()
        ax2.set_ylim([0,100])
        ax2.set_ylabel('Percent')
        self.model.oiltype = 'unknown'  # Should be changed
        plt.title('%s - %s to %s' %
                  (self.model.oiltype,
                   self.start_time.strftime('%Y-%m-%d %H:%M'),
                   self.time.strftime('%Y-%m-%d %H:%M')))
        # Shrink current axis's height by 10% on the bottom
        box = ax1.get_position()
        ax1.set_position([box.x0, box.y0 + box.height * 0.1,
                         box.width, box.height * 0.9])
        ax2.set_position([box.x0, box.y0 + box.height * 0.1,
                         box.width, box.height * 0.9])
        ax1.legend(bbox_to_anchor=(0., -0.10, 1., -0.03), loc=1,
                   ncol=4, mode="expand", borderaxespad=0.)
        plt.show()


    def set_oiltype(self, oiltype):
        if oiltype not in self.oiltypes:
            raise ValueError('The following oiltypes are available: %s' %
                             str(self.oiltypes))
        indx = self.oiltypes.index(oiltype)
        linenumber = self.oiltypes_linenumbers[indx]
        oilfile = open(self.oiltype_file, 'r')
        for i in range(linenumber + 1):
            oilfile.readline()
        ref = oilfile.readline().split()
        self.model.reference_thickness = np.float(ref[0])
        self.model.reference_wind = np.float(ref[1])
        tref = []
        fref = []
        wmax = []
        while True:
            line = oilfile.readline()
            if not line[0].isdigit():
                break
            line = line.split()
            tref.append(line[0]) 
            fref.append(line[1]) 
            wmax.append(line[3]) 
        self.model.tref = np.array(tref, dtype='float')*3600.
        self.model.fref = np.array(fref, dtype='float')*.01
        self.model.wmax = np.array(wmax, dtype='float')
        self.model.oiltype = oiltype  # Store name of oil type

    def seed_elements(self, *args, **kwargs):
        if 'oiltype' in kwargs:
            oiltype = kwargs['oiltype']
            del kwargs['oiltype']
        else:
            oiltype = 'BALDER'  # Default
        self.set_oiltype(oiltype)

        super(OpenOil3D, self).seed_elements(*args, **kwargs)

    def seed_from_gml(self, gmlfile, num_elements=1000):
        """Read oil slick contours from GML file, and seed particles within."""

        # Specific imports
        import datetime
        import matplotlib.nxutils as nx
        from xml.etree import ElementTree
        from matplotlib.patches import Polygon
        from mpl_toolkits.basemap import pyproj

        namespaces = {'od': 'http://cweb.ksat.no/cweb/schema/geoweb/oil',
                      'gml': 'http://www.opengis.net/gml'}
        slicks = []

        with open(gmlfile, 'rt') as e:
            tree = ElementTree.parse(e)

        pos1 = 'od:oilDetectionMember/od:oilDetection/od:oilSpill/gml:Polygon'
        pos2 = 'gml:exterior/gml:LinearRing/gml:posList'

        # This retrieves some other types of patches, found in some files only
        # Should be combines with the above, to get all patches
        #pos1 = 'od:oilDetectionMember/od:oilDetection/od:oilSpill/gml:Surface/gml:polygonPatches'
        #pos2 = 'gml:PolygonPatch/gml:exterior/gml:LinearRing/gml:posList'

        # Find detection time
        time_pos = 'od:oilDetectionMember/od:oilDetection/od:detectionTime'
        oil_time = datetime.datetime.strptime(
            tree.find(time_pos, namespaces).text, '%Y-%m-%dT%H:%M:%S.%fZ')

        for patch in tree.findall(pos1, namespaces):
            pos = patch.find(pos2, namespaces).text
            c = np.array(pos.split()).astype(np.float)
            lon = c[0::2]
            lat = c[1::2]
            slicks.append(Polygon(zip(lon, lat)))

        # Find boundary and area of all patches
        lons = np.array([])
        lats = lons.copy()
        for slick in slicks:
            ext = slick.get_extents()
            lons = np.append(lons, [ext.xmin, ext.xmax])
            lats = np.append(lats, [ext.ymin, ext.ymax])
            # Make a stereographic projection centred on the polygon
        lonmin = lons.min()
        lonmax = lons.max()
        latmin = lats.min()
        latmax = lats.max()

        # Place n points within the polygons
        proj = pyproj.Proj('+proj=aea +lat_1=%f +lat_2=%f +lat_0=%f +lon_0=%f'
                           % (latmin, latmax,
                              (latmin+latmax)/2, (lonmin+lonmax)/2))
        slickarea = np.array([])
        for slick in slicks:
            lonlat = slick.get_xy()
            lon = lonlat[:, 0]
            lat = lonlat[:, 1]
            x, y = proj(lon, lat)

            area_of_polygon = 0.0
            for i in xrange(-1, len(x)-1):
                area_of_polygon += x[i] * (y[i+1] - y[i-1])
            area_of_polygon = abs(area_of_polygon) / 2.0
            slickarea = np.append(slickarea, area_of_polygon)  # in m2

        # Make points
        deltax = np.sqrt(np.sum(slickarea)/num_elements)

        lonpoints = np.array([])
        latpoints = np.array([])
        for i, slick in enumerate(slicks):
            lonlat = slick.get_xy()
            lon = lonlat[:, 0]
            lat = lonlat[:, 1]
            x, y = proj(lon, lat)
            xvec = np.arange(x.min(), x.max(), deltax)
            yvec = np.arange(y.min(), y.max(), deltax)
            x, y = np.meshgrid(xvec, yvec)
            lon, lat = proj(x, y, inverse=True)
            lon = lon.ravel()
            lat = lat.ravel()
            points = np.c_[lon, lat]
            ind = nx.points_inside_poly(points, slick.xy)
            lonpoints = np.append(lonpoints, lon[ind])
            latpoints = np.append(latpoints, lat[ind])

        # Finally seed at found positions
        kwargs = {}
        kwargs['lon'] = lonpoints
        kwargs['lat'] = latpoints
        kwargs['ID'] = np.arange(len(lonpoints)) + 1
        kwargs['mass_oil'] = 1
        self.schedule_elements(self.ElementType(**kwargs), oil_time)

def sea_water_density(T=10.,S=35.):
    '''The function gives the density of seawater at one atmosphere
    pressure as given in :

    N.P. Fofonoff and R.C. Millard Jr.,1983,
    Unesco technical papers in marine science no. 44.
    
    S   = Salinity in promille of the seawater
    T   = Temperature of the seawater in degrees Celsius
    '''

    R4=4.8314E-04
    DR350=28.106331

    #Pure water density at atmospheric pressure
    #Bigg P.H. (1967) BR. J. Applied Physics pp.:521-537

    R1 = ((((6.536332E-09*T-1.120083E-06)*T+1.001685E-04)*T-9.095290E-03)*T+6.793952E-02)*T-28.263737

    #Seawater density at atmospheric pressure
    #coefficients involving salinity :

    R2 = (((5.3875E-09*T-8.2467E-07)*T+7.6438E-05)*T-4.0899E-03)*T +8.24493E-01

    R3 = (-1.6546E-06*T+1.0227E-04)*T-5.72466E-03

    #International one-atmosphere equation of state of seawater :

    SIG = R1 + (R4*S + R3*np.sqrt(S) + R2)*S
    Dens0 = SIG + DR350 + 1000.
    return Dens0
