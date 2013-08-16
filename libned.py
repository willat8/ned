"""This module provides tools for querying the NASA\IPAC Extragalactic Database (NED)
   and the Wide-field Infrared Survey Explorer (WISE) database."""

import urllib, astropy.io.votable, time, warnings, math

NED_POSITION_SEARCH_PATH = "http://nedwww.ipac.caltech.edu/cgi-bin/nph-objsearch?of=xml_posn\
&objname=%s"
NED_SED_SEARCH_PATH = "http://nedwww.ipac.caltech.edu/cgi-bin/nph-datasearch?search_type=Photometry&of=xml_all\
&objname=%s"
WISE_SEARCH_PATH = "http://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query?catalog=wise_allsky_4band_p3as_psd&outfmt=3\
&objstr=%(lat).5f+%(lon).5f"
TWOMASS_SEARCH_PATH = "http://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query?catalog=fp_psc&outfmt=3\
&objstr=%(lat).5f+%(lon).5f"

class DataPoint:
  """A storage class for frequency vs flux data from various sources"""
  def __init__(self, data):
    # initialise default values with correct types for output string
    self.index = 0
    self.name = None
    self.z = 0.
    self.num = 0
    self.freq = 0.
    self.flux = 0.
    self.source = None # refers to the data source
    self.flag = 0
    self.lat = 0.
    self.lon = 0.
    self.offset_from_ned = 0.
    self.extinction = 1. # default extinction value for all sources?
    self.RM = None
    self.RM_err = None
    self.offset_from_pol = 0.

    [setattr(self, *entry) for entry in data.items()] # set proper values

  def __repr__(self):
    """Formats and prints the frequency vs flux data for a space-separated .dat file"""
    return "%(index)d  %(name)s %(z).5f %(num)d   %(freq).3e %(flux).3e %(source)s  %(flag)c %(lat).5f %(lon).5f %(offset_from_ned).1f  %(extinction).3e  %(RM)s %(RM_err)s %(offset_from_pol).2f" % vars(self)

class Source:
  """Instances of this class represent extragalactic objects"""
  def __init__(self, polarisation):
    self.points = []
    self.polarisation = polarisation
    self.ned_position = None
    self.ned_sed = None
    self.wise = None
    self.twomass = None

    # common for all data points for this source
    self.name = None
    self.ned_lat = 0.
    self.ned_lon = 0.
    self.z = 0.
    self.RM = None
    self.RM_err = None
    self.pol_lat = 0.
    self.pol_lon = 0.

    self.parse_polarisation()

  def __repr__(self):
    return "\n".join(map(repr, self.points))

  def parse_polarisation(self):
    """Picks out the redshift and rotation measure from the polarisation data and records them"""
    try:
      data = dict(zip(("RA","dec","ned_name","z","RM","RM_err"), self.polarisation.split(",")))
      self.name = data["ned_name"]
      print self.name
      self.z = float(data["z"])
      self.RM = data["RM"]
      self.RM_err = data["RM_err"]
      self.pol_lat = float(data["RA"])
      self.pol_lon = float(data["dec"])
    except: raise Exception("Can't find raw polarisation data!")

  def parse_ned_position(self):
    """Picks out the J2000.0 equatorial latitude/longitude (decimal degrees) and records them"""
    print self.name
    try:
      for key, name in [("ned_lat", "pos_ra_equ_J2000_d"), ("ned_lon", "pos_dec_equ_J2000_d")]:
        setattr(self, key, float(self.ned_position.array[name].data.item()))
    except: raise Exception("Can't find raw NED position data!")

  def parse_ned_sed(self, index):
    """Picks out the frequency vs flux data and records them as data points"""
    print self.name
    try:
      [self.points.append(DataPoint({"index": index, "name": self.name.replace(" ",""), "z": self.z, "num": len(self.points)+1, "freq": freq, "flux": flux, "source": "NED", "flag": 'a', "lat": self.ned_lat, "lon": self.ned_lon, "RM": self.RM, "RM_err": self.RM_err, "offset_from_pol": math.hypot(self.pol_lat-self.ned_lat, self.pol_lon-self.ned_lon)*3600})) for freq, flux in zip(map(float, self.ned_sed.array["Frequency"].data.tolist()), map(float, self.ned_sed.array["NED Photometry Measurement"].data.tolist()))]
    except: raise Exception("Can't find raw NED SED data!")

  def parse_wise(self, index):
    """Picks out the frequency vs flux data and records them as data points"""
    print self.name
    try: # see if 2mass data is included
      [int(self.wise.array[name].data.item()) for name in ["%s_m_2mass" % letter for letter in ("j", "h", "k")]]  # will error if no 2mass data
      self.twomass = self.wise # if gets to here then 2mass is included in wise
    except: pass # will try to fetch 2mass later
    try:
      wise_lat = float(self.wise.array["ra"].data.item())
      wise_lon = float(self.wise.array["dec"].data.item())
      [self.points.append(DataPoint({"index": index, "name": self.name.replace(" ",""), "z": self.z, "num": len(self.points)+1, "freq": freq, "flux": flux, "source": "WISE", "flag": 'a', "lat": wise_lat, "lon": wise_lon, "offset_from_ned": math.hypot(self.ned_lat-wise_lat, self.ned_lon-wise_lon)*3600, "RM": self.RM, "RM_err": self.RM_err, "offset_from_pol": math.hypot(self.pol_lat-self.ned_lat, self.pol_lon-self.ned_lon)*3600})) for freq, flux in zip((8.856e+13, 6.445e+13, 2.675e+13, 1.346e+13), map(float.__mul__, (306.682, 170.663, 29.045, 8.284), [10**(-.4*float(self.wise.array["w%dmpro" % number].data.item())) for number in range(1,5)]))]
    except:
      print "Can't find raw WISE data! (%s)" % self.name

  def parse_twomass(self, index):
    """Picks out the frequency vs flux data and records them as data points"""
    try:
      twomass_lat = float(self.twomass.array["ra"].data.item())
      twomass_lon = float(self.twomass.array["dec"].data.item())
      [self.points.append(DataPoint({"index": index, "name": self.name.replace(" ",""), "z": self.z, "num": len(self.points)+1, "freq": freq, "flux": flux, "source": "2MASS", "flag": 'a', "lat": twomass_lat, "lon": twomass_lon, "offset_from_ned": math.hypot(self.ned_lat-twomass_lat, self.ned_lon-twomass_lon)*3600, "RM": self.RM, "RM_err": self.RM_err, "offset_from_pol": math.hypot(self.pol_lat-self.ned_lat, self.pol_lon-self.ned_lon)*3600})) for freq, flux in zip((2.429e14, 1.805e14, 1.390e14), map(float.__mul__, (1594., 1024., 667.), [10**(-.4*float(self.twomass.array["%c_m" % letter + "_2mass"*(self.twomass==self.wise)].data.item())) for letter in ("j", "h", "k")]))]
    except:
      print "Can't find raw 2MASS data! (%s)" % self.name

def get_votable(url):
  """Fetches from the web and returns data for a source, in an astropy votable"""
  print url
  try:
    xml_file = urllib.urlopen(url) # grab xml file-like-object from the web
    time.sleep(1) # respect request throttling recommendations
    with warnings.catch_warnings():
      warnings.simplefilter("ignore") # suppress astropy warnings
      return astropy.io.votable.parse_single_table(xml_file) # parse xml to astropy votable
  except: raise Exception("Could not download or interpret data. Are you connected to the Internet?")
