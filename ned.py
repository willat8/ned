"""This module provides tools for querying the NASA\IPAC Extragalactic Database (NED)
   and the Wide-field Infrared Survey Explorer (WISE) database."""

import urllib, astropy.io.votable, time, warnings

NED_POSITION_SEARCH_PATH = "http://nedwww.ipac.caltech.edu/cgi-bin/nph-objsearch?of=xml_posn\
&objname=%s"
NED_SED_SEARCH_PATH = "http://nedwww.ipac.caltech.edu/cgi-bin/nph-datasearch?search_type=Photometry&of=xml_all\
&objname=%s"
WISE_SEARCH_PATH = "http://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query?catalog=wise_allsky_4band_p3as_psd&outfmt=3\
&objstr=%(lat).5f+%(lon).5f"
TWOMASS_SEARCH_PATH = "http://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query?catalog=fp_psc&outfmt=3\
&objstr=%(lat).5f+%(lon).5f"

class Source:
  """Instances of this class represent extragalactic objects"""
  def __init__(self, data):
    [setattr(self, *entry) for entry in data] # set instance vars
    #the below are to be determined
    self.lat = self.lon = None #from ned
    self.flux = self.freq = self.uncertainty = self.units = self.flag = None #from ned (TO DO self.flag)
    self.wise = None
    self.twomass = None
    self.extinction = 1 #TO DO
    self.offset = 0 #TO DO

def get_ned_position_votable(source):
  """Fetches and returns NED position data for a source, in an astropy votable.
     Depends on NED name."""
  xml_file = urllib.urlopen(NED_POSITION_SEARCH_PATH % source.ned_name.replace(" ","+")) #grab xml file-like-object from ned
  with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    return astropy.io.votable.parse_single_table(xml_file) #parse xml to astropy votable

def get_ned_sed_votable(source):
  """Fetches and returns NED spectral energy distribution (SED) data for a source, in an astropy votable.
     Depends on NED name."""
  xml_file = urllib.urlopen(NED_SED_SEARCH_PATH % source.ned_name.replace(" ","+")) #grab xml file-like-object from ned
  with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    return astropy.io.votable.parse_single_table(xml_file) #parse xml to astropy votable

def get_wise_votable(source):
  """Fetches and returns WISE All-Sky Source Catalog data for a source, in an astropy votable.
     Depends on NED latitude/longitude."""
  xml_file = urllib.urlopen(WISE_SEARCH_PATH % {"lat": round(source.lat, 5), "lon": round(source.lon, 5)}) #grab xml file-like object from wise (note the position rounding)
  with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    return astropy.io.votable.parse_single_table(xml_file)

def get_twomass_votable(source):
  """Fetches and returns 2MASS All-Sky Point Source Catalog data for a source, in an astropy votable.
     Depends on NED latitude/longitude."""
  xml_file = urllib.urlopen(TWOMASS_SEARCH_PATH % {"lat": round(source.lat, 5), "lon": round(source.lon, 5)}) #grab xml file-like object from 2mass (note the position rounding)
  with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    return astropy.io.votable.parse_single_table(xml_file)

def store_ned_position_data(source, votable):
  """Picks out the J2000.0 equatorial latitude/longitude (decimal degrees) and records them"""
  for key, name in [("lat", "pos_ra_equ_J2000_d"), ("lon", "pos_dec_equ_J2000_d")]:
    try: setattr(source, key, votable.array[name].data.item()) #if no results found will error
    except: continue

def store_ned_sed_data(source, votable):
  """Picks out the frequency and flux data and records them as lists"""
  for key, name in [("freq", "Frequency"), ("flux", "NED Photometry Measurement"), ("uncertainty", "NED Uncertainty"), ("units", "NED Units")]:
    try: setattr(source, key, votable.array[name].data.tolist()) #if no results found will error
    except: continue
  source.flag = "a" #TO DO

def store_wise_data(source, votable):
  """Stores all the WISE data in a tuple"""
  try: source.wise = votable.array.item() #if no results found will error
  except: pass

def store_twomass_data(source, votable):
  """Stores all the 2MASS data in a tuple"""
  try: source.twomass = votable.array.item() #if no results found will error
  except: pass

def output_dat(index, source):
  """Formats and prints the NED data for a space-separated .dat file"""
  for num, (freq, flux) in enumerate(zip(source.freq, source.flux)):
    print "%(index)d  %(name)s %(z).5f %(num)d   %(freq).3e %(flux).3e %(source)s  %(flag)c %(lat).5f %(lon).5f  %(extinction).3e  %(RM)s %(RM_err)s %(offset)s" % {"index": index, "name": source.ned_name.replace(" ",""), "z": float(source.z), "num": num+1, "freq": freq, "flux": flux, "source": "NED", "flag": source.flag, "lat": source.lat, "lon": source.lon, "extinction": source.extinction, "RM": source.RM, "RM_err": source.RM_err, "offset": source.offset}
  

# temporary test data
_test_source_data_list = [
"1.59417,-0.07364,FBQS J0006-0004,1.037,22.5,3.3",
"197.16317,-9.84211,PKS 1306-09,0.46685,-27.3,2.0"]

_sources = []
[_sources.append(Source(zip(("RA","dec","ned_name","z","RM","RM_err"), _test_source_data.split(",")))) for _test_source_data in _test_source_data_list]

# let's see if it works
for index, _source in enumerate(_sources):
  store_ned_position_data(_source, get_ned_position_votable(_source))
  store_wise_data(_source, get_wise_votable(_source))
  time.sleep(1)
  store_ned_sed_data(_source, get_ned_sed_votable(_source))
  if _source.wise is None:
    store_twomass_data(_source, get_twomass_votable(_source))
  time.sleep(1)
  output_dat(index+1, _source)
