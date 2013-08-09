"""This module provides tools for querying the NASA\IPAC Extragalactic Database (NED)"""

import urllib, astropy.io.votable, time

NED_SEARCH_PATH = "http://nedwww.ipac.caltech.edu/cgi-bin/datasearch?search_type=Photometry&of=xml_all\
&objname=%s"

class Source:
  """Instances of this class represent extragalactic objects"""
  def __init__(self, data):
    [setattr(self, *entry) for entry in data] # set instance vars

def get_votable(source):
  """Fetches and returns NED data for a source, in a astropy votable"""
  xml_file = urllib.urlopen(NED_SEARCH_PATH % source.ned_name) #grab xml file-like-object from ned
  return astropy.io.votable.parse_single_table(xml_file) #parse xml to astropy votable

def store_data(source, votable):
  """Picks out the frequency and flux data and records them as lists"""
  source.freq = votable.array["Frequency"].data.tolist()
  source.flux = votable.array["NED Photometry Measurement"].data.tolist()
  source.uncertainty = votable.array["NED Uncertainty"].data.tolist()
  source.units = votable.array["NED Units"].data.tolist()

# temporary test data
_test_source_data_list = [
"1.59417,-0.07364,FBQS J0006-0004,1.037,22.5,3.3",
"197.16317,-9.84211,PKS 1306-09,0.46685,-27.3,2.0"]

_sources = []
[_sources.append(Source(zip(("RA","dec","ned_name","z","RM","RM_err"), _test_source_data.lower().replace(" ","+").split(",")))) for _test_source_data in _test_source_data_list]

# let's see if it works
for _source in _sources:
  store_data(_source, get_votable(_source))
  print "Name: ", _source.ned_name.upper()
  print "Frequency: ", _source.freq
  print "Flux: ", zip(_source.flux, _source.uncertainty, _source.units)
  print
  time.sleep(1)
