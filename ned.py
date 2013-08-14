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
  """A storage class for frequency vs. flux data from various sources"""
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
    self.extinction = 0.
    self.RM = None
    self.RM_err = None
    self.offset = None

    [setattr(self, *entry) for entry in data.items()] # set proper values

  def __repr__(self):
    """Formats and prints the frequency vs flux data for a space-separated .dat file"""
    return "%(index)d  %(name)s %(z).5f %(num)d   %(freq).3e %(flux).3e %(source)s  %(flag)c %(lat).5f %(lon).5f %(offset_from_ned).1f  %(extinction).3e  %(RM)s %(RM_err)s %(offset)s" % vars(self)

class Source:
  """Instances of this class represent extragalactic objects"""
  extinction = 1. # common for all sources?
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

    self.parse_polarisation()

  def __repr__(self):
    return "\n".join(map(repr, self.points))

  def parse_polarisation(self):
    """Picks out the redshift and rotation measure from the polarisation data and records them"""
    try:
      data = dict(zip(("RA","dec","ned_name","z","RM","RM_err"), self.polarisation.split(",")))
      self.name = data["ned_name"]
      self.z = data["z"]
      self.RM = data["RM"]
      self.RM_err = data["RM_err"]
    except: raise Exception("Can't find raw polarisation data!")

  def parse_ned_position(self):
    """Picks out the J2000.0 equatorial latitude/longitude (decimal degrees) and records them"""
    try:
      for key, name in [("ned_lat", "pos_ra_equ_J2000_d"), ("ned_lon", "pos_dec_equ_J2000_d")]:
        setattr(self, key, self.ned_position.array[name].data.item())
    except: raise Exception("Can't find raw NED position data!")

  def parse_ned_sed(self):
    """Picks out the frequency vs flux data and records them as data points"""
    try:
      [self.points.append(DataPoint({"index": 0, "name": self.name.replace(" ",""), "z": float(self.z), "num": 0, "freq": freq, "flux": flux, "source": "NED", "flag": 'a', "lat": self.ned_lat, "lon": self.ned_lon, "offset_from_ned": 0., "extinction": self.extinction, "RM": self.RM, "RM_err": self.RM_err, "offset": "0"})) for freq, flux in zip(map(float, self.ned_sed.array["Frequency"].data.tolist()), map(float, self.ned_sed.array["NED Photometry Measurement"].data.tolist()))]
    except: raise Exception("Can't find raw NED SED data!")

  def parse_wise(self):
    try:
      pass
    except: raise Exception("Can't find raw WISE data!")

  def parse_twomass(self):
    try:
      pass
    except: raise Exception("Can't find raw 2MASS data!")

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

#.###############################################.#

# temporary test data
_test_polarisation_data = [
"1.59417,-0.07364,FBQS J0006-0004,1.037,22.5,3.3",
"197.16317,-9.84211,PKS 1306-09,0.46685,-27.3,2.0"
]

_sources = [Source(entry) for entry in _test_polarisation_data]
[setattr(_source, "ned_position", get_votable(NED_POSITION_SEARCH_PATH % _source.name.replace(" ","+"))) for _source in _sources] # fetch ned position data
[setattr(_source, "ned_sed", get_votable(NED_SED_SEARCH_PATH % _source.name.replace(" ","+"))) for _source in _sources] # fetch ned sed data
[_source.parse_ned_position() for _source in _sources] # parse and store ned position data
[setattr(_source, "wise", get_votable(WISE_SEARCH_PATH % {"lat": _source.ned_lat, "lon": _source.ned_lon})) for _source in _sources] # fetch wise data
[setattr(_source, "twomass", get_votable(TWOMASS_SEARCH_PATH % {"lat": _source.ned_lat, "lon": _source.ned_lon})) for _source in _sources] # fetch 2mass data

[_source.parse_ned_sed() for _source in _sources] # parse and store ned sed data
[_source.parse_wise() for _source in _sources] # parse and store wise data
[_source.parse_twomass() for _source in _sources] # parse and store 2mass data

# let's see if it works
for _source in _sources: print _source
