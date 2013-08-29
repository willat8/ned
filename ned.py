#!/usr/bin/env python2

import libned, argparse, sys, os

parser = argparse.ArgumentParser(description="Scripts to access NASA/IPAC Extragalactic Database (NED), Wide-Field Infrared Survey Explorer (WISE), Two Micron All Sky Survey (2MASS), and Galaxy Evolution Explorer (GALEX) online data.")
parser.add_argument("input", nargs="?", type=argparse.FileType("rU"), default=sys.stdin, help="polarisation catalog or NED names input data (will take manual input if not specified)")
parser.add_argument("-f", "--file", type=argparse.FileType("w"), default=sys.stdout, help="output filename")
parser.add_argument("-p", "--plot", metavar="DIR", type=str, help="plot mode (must specify directory for output data)")
args = vars(parser.parse_args())
in_file = args["input"] # a file-like object
out_file = args["file"] # a file-like object
plot_dir = args["plot"] # a string of a directory

print "READING CONFIGURATION FILE ned.conf"
try:
  libned.DataPoint.repr_format_string = " ".join(line.rstrip("\n") for line in open("ned.conf", "rU") if line.lstrip() and line.lstrip()[0] != "#") # could upgrade this to config parse module in the future
except:
  print "COULD NOT READ CONFIGURATION FILE ned.conf"
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
      plot_file = open(os.path.join(plot_dir, source.name.replace(" ","").replace(os.sep, "") + ".dat"), "w")
      print >> plot_file, source.plot_output()
      plot_file.close()
      print "%s PLOT OUTPUT WRITTEN TO %s" % (source.name, plot_file.name)
    except:
      print "COULD NOT WRITE PLOT OUTPUT FOR %s" % source.name
print
print "FINISHED"
out_file.close() # close it at end since still need to print to stdout
