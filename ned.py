#!/usr/bin/python2

import libned, argparse, sys

parser = argparse.ArgumentParser(description="Scripts to access NASA/IPAC Extragalactic Database")
parser.add_argument("input", nargs="?", type=argparse.FileType("r"), default=sys.stdin, help="input data (will take manual input if not specified)")
parser.add_argument("-f", "--file", type=str, default=sys.stdout, help="output filename")
in_file = vars(parser.parse_args())["input"] # a file-like object
out_file = vars(parser.parse_args())["file"] # a string of a filename

print "ANALYSING INPUT DATA..."
_sources = [libned.Source(line) for line in in_file if libned.parse_entry(line)] # could be memoized
print
print "DOWNLOADING NED DATA..."
[setattr(_source, "ned_position", _source.get_ned_position_votable()) for _source in _sources] # fetch ned position data
[setattr(_source, "ned_sed", _source.get_ned_sed_votable()) for _source in _sources] # fetch ned sed data
print
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

# let's see if it works
print
print "RESULTS"
for _source in _sources: print _source
