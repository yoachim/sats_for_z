## Coppied over from lsst.sims.featureScheduler branch u/yoachim/satellite_dodging

import numpy as np
from astropy import time
from astropy import units as u
from astropy import constants as const
import ephem
#from lsst.sims.featureScheduler.utils import read_fields, gnomonic_project_toxy
import healpy as hp


__all__ = ["tle_from_orbital_parameters", "create_constellation",
           "starlink_constellation", "Constellation", "Constellation_p"]


def gnomonic_project_toxy(RA1, Dec1, RAcen, Deccen):
    """Calculate x/y projection of RA1/Dec1 in system with center at RAcen, Deccen.
    Input radians. Grabbed from sims_selfcal"""
    # also used in Global Telescope Network website
    cosc = np.sin(Deccen) * np.sin(Dec1) + np.cos(Deccen) * np.cos(Dec1) * np.cos(RA1-RAcen)
    x = np.cos(Dec1) * np.sin(RA1-RAcen) / cosc
    y = (np.cos(Deccen)*np.sin(Dec1) - np.sin(Deccen)*np.cos(Dec1)*np.cos(RA1-RAcen)) / cosc
    return x, y

def satellite_mean_motion(altitude, mu=const.GM_earth, r_earth=const.R_earth):
    '''
    Compute mean motion of satellite at altitude in Earth's gravitational field.

    See https://en.wikipedia.org/wiki/Mean_motion#Formulae
    '''
    no = np.sqrt(4.0 * np.pi ** 2 * (altitude + r_earth) ** 3 / mu).to(u.day)
    return 1 / no


def tle_from_orbital_parameters(sat_name, sat_nr, epoch, inclination, raan,
                                mean_anomaly, mean_motion):
    '''
    Generate TLE strings from orbital parameters.

    Note: epoch has a very strange format: first two digits are the year, next three
    digits are the day from beginning of year, then fraction of a day is given, e.g.
    20180.25 would be 2020, day 180, 6 hours (UT?)
    '''

    # Note: RAAN = right ascention (or longitude) of ascending node

    def checksum(line):
        s = 0
        for c in line[:-1]:
            if c.isdigit():
                s += int(c)
            if c == "-":
                s += 1
        return '{:s}{:1d}'.format(line[:-1], s % 10)

    tle0 = sat_name
    tle1 = checksum(
        '1 {:05d}U 20001A   {:14.8f}  .00000000  00000-0  50000-4 '
        '0    0X'.format(sat_nr, epoch))
    tle2 = checksum(
        '2 {:05d} {:8.4f} {:8.4f} 0001000   0.0000 {:8.4f} '
        '{:11.8f}    0X'.format(
            sat_nr, inclination.to_value(u.deg), raan.to_value(u.deg),
            mean_anomaly.to_value(u.deg), mean_motion.to_value(1 / u.day)
        ))

    return '\n'.join([tle0, tle1, tle2])


def create_constellation(altitudes, inclinations, nplanes, sats_per_plane, epoch=22050.1, name='Test', seed=42):
    np.random.seed(seed)
    my_sat_tles = []
    sat_nr = 8000
    for alt, inc, n, s in zip(
            altitudes, inclinations, nplanes, sats_per_plane):

        if s == 1:
            # random placement for lower orbits
            mas = np.random.uniform(0, 360, n) * u.deg
            raans = np.random.uniform(0, 360, n) * u.deg
        else:
            mas = np.linspace(0.0, 360.0, s, endpoint=False) * u.deg
            mas += np.random.uniform(0, 360, 1) * u.deg
            raans = np.linspace(0.0, 360.0, n, endpoint=False) * u.deg
            mas, raans = np.meshgrid(mas, raans)
            mas, raans = mas.flatten(), raans.flatten()

        mm = satellite_mean_motion(alt)
        for ma, raan in zip(mas, raans):
            my_sat_tles.append(
                tle_from_orbital_parameters(
                    name+' {:d}'.format(sat_nr), sat_nr, epoch,
                    inc, raan, ma, mm))
            sat_nr += 1

    return my_sat_tles


def starlink_constellation(supersize=False):
    """
    Create a list of satellite TLE's
    """
    altitudes = np.array([550, 1110, 1130, 1275, 1325, 345.6, 340.8, 335.9])
    inclinations = np.array([53.0, 53.8, 74.0, 81.0, 70.0, 53.0, 48.0, 42.0])
    nplanes = np.array([72, 32, 8, 5, 6, 2547, 2478, 2493])
    sats_per_plane = np.array([22, 50, 50, 75, 75, 1, 1, 1])

    if supersize:
        # Let's make 4 more altitude and inclinations
        new_altitudes = []
        new_inclinations = []
        new_nplanes = []
        new_sat_pp = []
        for i in np.arange(0, 4):
            new_altitudes.append(altitudes+i*20)
            new_inclinations.append(inclinations+3*i)
            new_nplanes.append(nplanes)
            new_sat_pp.append(sats_per_plane)

        altitudes = np.concatenate(new_altitudes)
        inclinations = np.concatenate(new_inclinations)
        nplanes = np.concatenate(new_nplanes)
        sats_per_plane = np.concatenate(new_sat_pp)

    altitudes = altitudes * u.km
    inclinations = inclinations * u.deg
    my_sat_tles = create_constellation(altitudes, inclinations, nplanes, sats_per_plane, name='Starl')

    return my_sat_tles


def inside_circle(p1, p2, radius=np.radians(3.5)):
    # https://codereview.stackexchange.com/questions/86421/line-segment-to-circle-collision-algorithm

    # XXX -- need to check this some more to make sure it works properly!
    vec = p2 - p1
    if np.size(p1.shape) == 1:
        axis = 0
    else:
        axis = 1

    a = np.sum(vec*vec, axis=axis)
    b = 2.*np.sum(vec*p1, axis=axis)
    c = np.sum(p1*p1, axis=axis) - 2.*radius**2

    disc = b**2 - 4*a*c

    result = np.ones(np.size(disc), dtype=int)
    result[np.where(disc < 0)] = 0

    sqrt_disc = np.sqrt(disc)
    t1 = (-b + sqrt_disc)/(2. * a)
    t2 = (-b - sqrt_disc)/(2. * a)

    outside = np.where(((t1 < 0) | (t1 > 1)) & ((t2 < 0) | (t2 > 1)))
    result[outside] = 0
    return result


class Constellation(object):
    """
    Have a class to hold ephem satellite objects

    Parameters
    ----------
    sat_tle_list : list of str
        A list of satellite TLEs to be used
    tstep : float (5)
        The time step to use when computing satellite positions in an exposure
    """

    def __init__(self, sat_tle_list, alt_limit=20., fov=3.5):
        self.sat_list = [ephem.readtle(tle.split('\n')[0], tle.split('\n')[1], tle.split('\n')[2]) for tle in sat_tle_list]
        self.alt_limit_rad = np.radians(alt_limit)
        self.fov_rad = np.radians(fov)
        self._make_observer()

    def _alt_check(self, pointing_alt):
        if np.radians(pointing_alt) < self.alt_limit_rad:
            raise ValueError(f'altitude below limit where we are tracking satellites, tried {pointing_alt} deg, limit {np.degrees(self.alt_limit_rad)}')

    def _make_observer(self):
        #telescope = Site(name='LSST')

        self.observer = ephem.Observer()
        self.observer.lat = -0.527864360290173
        self.observer.lon = -1.234809973810476
        self.observer.elevation = 2650.0

    def advance_epoch(self, advance=100):
        """
        Advance the epoch of all the satellites
        """

        # Because someone went and put a valueError where there should have been a warning
        # I prodly present the hackiest kludge of all time
        for sat in self.sat_list:
            sat._epoch += advance

    def update_mjd(self, mjd):
        """
        observer : ephem.Observer object
        """

        self.observer.date = ephem.date(time.Time(mjd, format='mjd').datetime)

        self.altitudes_rad = []
        self.azimuth_rad = []
        self.eclip = []
        self.ras_rad = []
        self.decs_rad = []
        self.elevations = []

        for sat in self.sat_list:
            try:
                sat.compute(self.observer)
            except ValueError:
                self.advance_epoch()
                sat.compute(self.observer)
            self.altitudes_rad.append(sat.alt)
            self.azimuth_rad.append(sat.az)
            self.eclip.append(sat.eclipsed)
            self.ras_rad.append(sat.ra)
            self.decs_rad.append(sat.dec)
            self.elevations.append(sat.elevation)

        self.altitudes_rad = np.array(self.altitudes_rad)
        self.azimuth_rad = np.array(self.azimuth_rad)
        self.eclip = np.array(self.eclip)
        # Keep track of the ones that are up and illuminated
        self.above_alt_limit = np.where((self.altitudes_rad >= self.alt_limit_rad) & (self.eclip == False))[0]

    def return_sat_info(self, mjd=None):
        """
        Package up the information about the satellites as a numpy array
        """

        if mjd is not None:
            self.update_mjd(mjd)

        names = ['altitudes_rad', 'azimuth_rad', 'eclip', 'ras_rad', 'decs_rad', 'elevations']
        types = [float, float, bool, float, float, float]
        result = np.empty(self.altitudes_rad.size, dtype=list(zip(names, types)))
        for name in names:
            result[name] = getattr(self, name)

        return result

    def check_times(self, pointing_alt, pointing_az, mjd1, mjd2):
        """
        pointing_alt : float
            The altitude (degrees)
        pointing_az : float
            The azimuth (degrees)
        mjd1 : float
            The start of an exposure (days)
        mjd2 : float
            The end of an exposure (days)

        Returns
        -------
        0 if there are no satellite collisions, 1 if there is
        """
        
        result = 0
        self._alt_check(pointing_alt)

        self.update_mjd(mjd1)
        alt1_rad = self.altitudes_rad.copy()
        az1_rad = self.azimuth_rad.copy()

        self.update_mjd(mjd2)

        if np.size(self.above_alt_limit) == 0:
            return result

        alt1_rad = alt1_rad[self.above_alt_limit]
        az1_rad = az1_rad[self.above_alt_limit]

        alt2_rad = self.altitudes_rad[self.above_alt_limit].copy()
        az2_rad = self.azimuth_rad[self.above_alt_limit].copy()

        # Project to x,y centered on the pointing
        x1, y1 = gnomonic_project_toxy(az1_rad, alt1_rad, np.radians(pointing_az), np.radians(pointing_alt))
        x2, y2 = gnomonic_project_toxy(az2_rad, alt2_rad, np.radians(pointing_az), np.radians(pointing_alt))

        result = np.max(inside_circle(np.array([x1, y1]).T, np.array([x2, y2]).T, radius=self.fov_rad))

        return result


class Constellation_p(Constellation):
    """
    Break constellation into parallel bits
    need to start engines first with something like:
    ipcluster start -n 4

    """

    def __init__(self, sat_tle_list, alt_limit=30., fov=3.5, tstep=1., exptime=30.):
        import ipyparallel as ipp
        self.alt_limit_rad = np.radians(alt_limit)

        self.rc = ipp.Client()
        self.dview = self.rc[:]

        n_cores = len(self.rc)

        tle_chunks = np.array_split(sat_tle_list, n_cores)
        tle_chunks = [chunk.tolist() for chunk in tle_chunks]

        self.dview['c_kwargs'] = {'alt_limit': alt_limit, 'fov': fov, 'tstep': tstep, 'exptime': exptime}

        self.dview.execute('from lsst.sims.featureScheduler.utils import Constellation')
        for view, chunk in zip(self.rc, tle_chunks):
            view['tle'] = chunk

        self.dview.execute("constellation = Constellation(tle, **c_kwargs)")

    def check_pointing(self, pointing_alt, pointing_az, mjd):

        self._alt_check(pointing_alt)

        self.dview['pointing_alt'] = pointing_alt
        self.dview['pointing_az'] = pointing_az
        self.dview['mjd'] = mjd

        self.dview.execute("result = constellation.check_pointing(pointing_alt, pointing_az, mjd)")
        results = self.dview['result']
        results = np.sum(results, axis=0)
        return results

    def look_ahead(self, pointing_alt, pointing_az, mjds):

        self._alt_check(pointing_alt)

        # pass the pointings and mjds to the views
        self.dview['pointing_alt'] = pointing_alt
        self.dview['pointing_az'] = pointing_az
        self.dview['mjds'] = mjds

        self.dview.execute('result = constellation.look_ahead(pointing_alt, pointing_az, mjds)', block=True)
        results = self.dview['result']
        results = np.sum(results, axis=0)
        # Need to do a quick merge of these
        results[np.where(results > 0)] = 1

        return results

