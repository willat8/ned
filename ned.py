"""This module provides tools for querying the NASA\IPAC Extragalactic Database (NED)
   and the Wide-field Infrared Survey Explorer (WISE) database."""

import urllib, astropy.io.votable, time, warnings

NED_POSITION_SEARCH_PATH = "http://nedwww.ipac.caltech.edu/cgi-bin/nph-objsearch?of=xml_posn\
&objname=%s"
NED_SED_SEARCH_PATH = "http://nedwww.ipac.caltech.edu/cgi-bin/nph-datasearch?search_type=Photometry&of=xml_all\
&objname=%s"
WISE_SEARCH_PATH = "http://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query?catalog=wise_allsky_4band_p3as_psd&outfmt=3\
&objstr=%(lat).5f+%(lon).5f"

class Source:
  """Instances of this class represent extragalactic objects"""
  def __init__(self, data):
    [setattr(self, *entry) for entry in data] # set instance vars

def get_ned_position_votable(source):
  """Fetches and returns NED position data for a source, in a astropy votable
     Depends on NED name"""
  xml_file = urllib.urlopen(NED_POSITION_SEARCH_PATH % source.ned_name) #grab xml file-like-object from ned
  with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    return astropy.io.votable.parse_single_table(xml_file) #parse xml to astropy votable

def get_ned_sed_votable(source):
  """Fetches and returns NED spectral energy distribution (SED) data for a source, in a astropy votable
     Depends on NED name"""
  xml_file = urllib.urlopen(NED_SED_SEARCH_PATH % source.ned_name) #grab xml file-like-object from ned
  with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    return astropy.io.votable.parse_single_table(xml_file) #parse xml to astropy votable

def get_wise_votable(source):
  """Fetches and returns WISE All-Sky Source Catalog data for a source, in a astropy votable.
     Depends on NED latitutde/longitude"""
  xml_file = urllib.urlopen(WISE_SEARCH_PATH % {"lat": round(source.lat, 5), "lon": round(source.lon, 5)}) #grab xml file-like object from wise (note the position rounding)
  with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    return astropy.io.votable.parse_single_table(xml_file)

def store_ned_position_data(source, votable):
  """Picks out the J2000.0 equatorial latitude/longitude (decimal degrees) and records them"""
  source.lat = votable.array["pos_ra_equ_J2000_d"].data.item()
  source.lon = votable.array["pos_dec_equ_J2000_d"].data.item()

def store_ned_sed_data(source, votable):
  """Picks out the frequency and flux data and records them as lists"""
  source.freq = votable.array["Frequency"].data.tolist()
  source.flux = votable.array["NED Photometry Measurement"].data.tolist()
  source.uncertainty = votable.array["NED Uncertainty"].data.tolist()
  source.units = votable.array["NED Units"].data.tolist()

def store_wise_data(source, votable):
  """Stores all the WISE data in a tuple"""
  source.wise = votable.array.item()

# temporary test data
_test_source_data_list = [
"1.59417,-0.07364,FBQS J0006-0004,1.037,22.5,3.3",
"197.16317,-9.84211,PKS 1306-09,0.46685,-27.3,2.0"]

_sources = []
[_sources.append(Source(zip(("RA","dec","ned_name","z","RM","RM_err"), _test_source_data.lower().replace(" ","+").split(",")))) for _test_source_data in _test_source_data_list]

# let's see if it works
for _source in _sources:
  store_ned_position_data(_source, get_ned_position_votable(_source))
  time.sleep(1)
  store_ned_sed_data(_source, get_ned_sed_votable(_source))
  store_wise_data(_source, get_wise_votable(_source))
  time.sleep(1)
  print "NED Name:", _source.ned_name.upper()
  print "Latitude (J200.0 deg):", _source.lat
  print "Longitude (J200.0 deg):", _source.lon
  print "Frequency:", _source.freq
  print "Flux:", zip(_source.flux, _source.uncertainty, _source.units)
  print "WISE:", _source.wise
  print
