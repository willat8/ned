#!/usr/bin/python2

import libned, argparse, sys

parser = argparse.ArgumentParser(description="Scripts to access NASA/IPAC Extragalactic Database (NED), Wide-Field Infrared Survey Explorer (WISE), Two Micron All Sky Survey (2MASS), and Galaxy Evolution Explorer (GALEX) online data.")
parser.add_argument("input", nargs="?", type=argparse.FileType("rU"), default=sys.stdin, help="polarisation catalog or NED names input data (will take manual input if not specified)")
parser.add_argument("-f", "--file", type=argparse.FileType("w"), default=sys.stdout, help="output filename")
in_file = vars(parser.parse_args())["input"] # a file-like object
out_file = vars(parser.parse_args())["file"] # a string of a filename

print "READING CONFIGURATION FILE ned.conf"
try:
  libned.DataPoint.repr_format_string = " ".join(line.rstrip("\n") for line in open("ned.conf", "rU") if line.lstrip() and line.lstrip()[0] != "#") # could upgrade this to config parse module in the future
except:
  print "COULD NOT READ CONFIGURATION FILE ned.conf"
print "OUTPUT FORMAT SET TO:"
print libned.DataPoint.repr_format_string
print
print "GETTING AND ANALYSING INPUT DATA..."
_sources = [libned.Source(line) for line in in_file if libned.parse_line(line)] # could be memoized
print
print "DOWNLOADING NED DATA..."
[setattr(_source, "ned_position", _source.get_ned_position_votable()) for _source in _sources] # fetch ned position data
[setattr(_source, "ned_sed", _source.get_ned_sed_votable()) for _source in _sources] # fetch ned sed data
print "ANALYSING NED POSITION DATA..."
[_source.parse_ned_position() for _source in _sources] # parse and store ned position data
print "ANALYSING NED SED DATA..."
[_source.parse_ned_sed(index+1) for index, _source in enumerate(_sources)] # parse and store ned sed data
print
print "DOWNLOADING WISE DATA..."
[setattr(_source, "wise", _source.get_wise_votable()) for _source in _sources] # fetch wise data
print "ANALYSING WISE DATA..."
[_source.parse_wise(index+1) for index,_source in enumerate(_sources)] # parse and store wise data (including any 2mass data)
print
print "DOWNLOADING ANY MISSING 2MASS DATA..."
[setattr(_source, "twomass", _source.get_twomass_votable()) for _source in _sources if not _source.twomass] # fetch 2mass data if missing
print "ANALYSING 2MASS DATA..."
[_source.parse_twomass(index+1) for index,_source in enumerate(_sources)] # parse and store 2mass data
print
print "DOWNLOADING GALEX DATA..."
[setattr(_source, "galex", _source.get_galex_votable()) for _source in _sources] # fetch galex data
print "ANALYSING GALEX DATA..."
[_source.parse_galex(index+1) for index,_source in enumerate(_sources)] # parse and store galex data
print
print "RESULTS"
for _source in _sources: print >> out_file, _source
print "OUTPUT WRITTEN TO %s" % out_file.name
out_file.close()
