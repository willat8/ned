#!/usr/bin/python2

import libned, urllib

# temporary test data
_test_polarisation_data = [
"1.59417,-0.07364,FBQS J0006-0004,1.037,22.5,3.3",
"197.16317,-9.84211,PKS 1306-09,0.46685,-27.3,2.0"
]

print "ANALYSING POLARISATION DATA..."
_sources = [libned.Source(entry) for entry in _test_polarisation_data]
print
print "DOWNLOADING NED DATA..."
[setattr(_source, "ned_position", libned.get_votable(libned.NED_POSITION_SEARCH_PATH % urllib.quote_plus(_source.name))) for _source in _sources] # fetch ned position data
[setattr(_source, "ned_sed", libned.get_votable(libned.NED_SED_SEARCH_PATH % urllib.quote_plus(_source.name))) for _source in _sources] # fetch ned sed data
print
print "ANALYSING NED POSITION DATA..."
[_source.parse_ned_position() for _source in _sources] # parse and store ned position data
print "ANALYSING NED SED DATA..."
[_source.parse_ned_sed(index+1) for index, _source in enumerate(_sources)] # parse and store ned sed data
print
print "DOWNLOADING WISE DATA..."
[setattr(_source, "wise", libned.get_votable(libned.WISE_SEARCH_PATH % {"lat": _source.ned_lat, "lon": _source.ned_lon})) for _source in _sources] # fetch wise data
print "ANALYSING WISE DATA..."
[_source.parse_wise(index+1) for index,_source in enumerate(_sources)] # parse and store wise data (including any 2mass data)
print
print "DOWNLOADING ANY MISSING 2MASS DATA..."
[setattr(_source, "twomass", libned.get_votable(libned.TWOMASS_SEARCH_PATH % {"lat": _source.ned_lat, "lon": _source.ned_lon})) for _source in _sources if not _source.twomass] # fetch 2mass data if missing
print "ANALYSING 2MASS DATA..."
[_source.parse_twomass(index+1) for index,_source in enumerate(_sources)] # parse and store 2mass data

# let's see if it works
print
print "RESULTS"
for _source in _sources: print _source
