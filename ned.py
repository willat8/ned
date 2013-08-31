#!/usr/bin/env python2

import libned, argparse, sys, os, ConfigParser

parser = argparse.ArgumentParser(description="Scripts to access NASA/IPAC Extragalactic Database (NED), Wide-Field Infrared Survey Explorer (WISE), Two Micron All Sky Survey (2MASS), and Galaxy Evolution Explorer (GALEX) online data.")
parser.add_argument("input", nargs="?", type=argparse.FileType("rU"), default=sys.stdin, help="newline-separated custom input data (will take manual input if not specified)")
parser.add_argument("-f", "--file", type=argparse.FileType("w"), default=sys.stdout, help="output filename")
parser.add_argument("-p", "--plot", metavar="DIR", type=str, help="plot mode (must specify directory for output data)")
args = vars(parser.parse_args())
in_file = args["input"] # a file-like object
out_file = args["file"] # a file-like object
plot_dir = args["plot"] # a string of a directory

print "READING CONFIGURATION FILE ned.conf"
config = ConfigParser.RawConfigParser()
config.read("ned.conf")
print "BUILDING INPUT REGEXP..."
libned.input_fields = config.get("Format", "input").strip().split()
libned.input_regexp = libned.build_input_regexp()
print "INPUT REGEXP SET TO:"
print libned.input_regexp.pattern
print "VALIDATING OUTPUT FORMAT..."
libned.DataPoint.repr_format_string = config.get("Format", "output")
valid_output_fields = {\
  "index": -1, \
  "name": None, \
  "ned_name": None, \
  "nvss_id": None, \
  "z": float("inf"), \
  "num": -1, \
  "freq": float("inf"), \
  "flux": float("inf"), \
  "data_source": None, \
  "flag": 'a', \
  "lat": float("inf"), \
  "lon": float("inf"), \
  "ned_lat": float("inf"), \
  "ned_lon": float("inf"), \
  "input_lat": float("inf"), \
  "input_lon": float("inf"), \
  "offset_from_ned": float("inf"), \
  "input_offset_from_ned": float("inf"), \
  "extinction": 1.\
 }
for input_field in libned.input_fields: # add custom input fields to valid output fields
  if input_field not in valid_output_fields:
    valid_output_fields[input_field] = ""
try:
  libned.DataPoint.repr_format_string % valid_output_fields
except:
  raise Exception("Mismatch between output and input fields. Check ned.conf.")
else:
  print "OUTPUT FORMAT SET TO:"
  print libned.DataPoint.repr_format_string
print
print "GETTING AND ANALYSING INPUT DATA..."
sources = [libned.Source(line) for line in in_file if libned.parse_line(line)] # could be memoized
print
print "DOWNLOADING NED POSITION DATA..."
[setattr(source, "ned_position", source.get_ned_position_votable()) for source in sources] # fetch ned position data
print "ANALYSING NED POSITION DATA..."
[source.parse_ned_position() for source in sources] # parse and store ned position data
print "DOWNLOADING NED SED DATA..."
[setattr(source, "ned_sed", source.get_ned_sed_votable()) for source in sources] # fetch ned sed data
print "ANALYSING NED SED DATA..."
[source.parse_ned_sed(index+1) for index, source in enumerate(sources)] # parse and store ned sed data
print
print "DOWNLOADING WISE DATA..."
[setattr(source, "wise", source.get_wise_votable()) for source in sources] # fetch wise data
print "ANALYSING WISE DATA..."
[source.parse_wise(index+1) for index, source in enumerate(sources)] # parse and store wise data (including any 2mass data)
print
print "DOWNLOADING ANY MISSING 2MASS DATA..."
[setattr(source, "twomass", source.get_twomass_votable()) for source in sources if not source.twomass] # fetch 2mass data if missing
print "ANALYSING 2MASS DATA..."
[source.parse_twomass(index+1) for index, source in enumerate(sources)] # parse and store 2mass data
print
print "DOWNLOADING GALEX DATA..."
[setattr(source, "galex", source.get_galex_votable()) for source in sources] # fetch galex data
print "ANALYSING GALEX DATA..."
[source.parse_galex(index+1) for index, source in enumerate(sources)] # parse and store galex data
print
print "RESULTS"
for source in sources: print >> out_file, source
print "OUTPUT WRITTEN TO %s" % out_file.name

if plot_dir:
  print
  for source in sources:
    try:
      plot_file = open(os.path.join(plot_dir, source.unique_name().replace(" ","").replace(os.sep, "") + ".dat"), "w")
      print >> plot_file, source.plot_output()
      plot_file.close()
      print "%s PLOT OUTPUT WRITTEN TO %s" % (source.unique_name(), plot_file.name)
    except:
      print "COULD NOT WRITE PLOT OUTPUT FOR %s" % source.unique_name()
print
print "FINISHED"
out_file.close() # close it at end since still need to print to stdout
