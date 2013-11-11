"""This module provides tools for querying the NASA\IPAC Extragalactic Database (NED),
   the Wide-field Infrared Survey Explorer (WISE) database, the Two Micron All Sky Survey (2MASS) database
   and the Galaxy Evolution Explorer (GALEX) database."""

import urllib, astropy.io.votable, time, warnings, math, mechanize, bs4, re, numpy, xml.etree.ElementTree

KNOWN_INPUT_FIELDS = {
  "input_lat": "(-?[0-9]+(\.[0-9]+)?)?",
  "input_lon": "(-?[0-9]+(\.[0-9]+)?)?",
  "ned_name": ".*?",
  "z": "(-?[0-9]+(\.[0-9]+)?([eE]-?[0-9]+)?)?",
  "nvss_id": ".*?"
 } # all should optionally match nothing for the case of empty fields
input_regexp = None
input_fields = [] # user-specified input fields

NED_POSITION_SEARCH_PATH = "http://nedwww.ipac.caltech.edu/cgi-bin/nph-objsearch?of=xml_posn\
&objname=%s"
NED_SED_SEARCH_PATH = "http://nedwww.ipac.caltech.edu/cgi-bin/nph-datasearch?search_type=Photometry&of=xml_all\
&objname=%s"
DUST_SEARCH_PATH = "http://irsa.ipac.caltech.edu/cgi-bin/DUST/nph-dust?\
locstr=%(lat).5f+%(lon).5f"
WISE_SEARCH_PATH = "http://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query?catalog=wise_allsky_4band_p3as_psd&outfmt=3\
&objstr=%(lat).5f+%(lon).5f"
TWOMASS_SEARCH_PATH = "http://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query?catalog=fp_psc&outfmt=3\
&objstr=%(lat).5f+%(lon).5f"
GALEX_SEARCH_PAGE = "http://galex.stsci.edu/GR6/?page=sqlform"
GALEX_SQL_QUERY = "SELECT TOP 100 p.objid, p.ra, p.dec, n.distance, p.band, p.fuv_mag, p.nuv_mag, p.fuv_flux, p.nuv_flux, p.e_bv \
FROM PhotoObjAll AS p, dbo.fGetNearbyObjEq(%(lat).5f, %(lon).5f, 0.2) AS n \
WHERE p.objID=n.objID \
ORDER BY n.distance ASC, p.fuv_mag ASC, p.nuv_mag ASC, p.e_bv ASC"

O_M = 0.27 # mass density parameter
O_Lambda = 0.73 # dark energy density parameter
H_0 = 71 # hubble constant
c = 299793000 # speed of light
R_V = 3.1 # extinction factor

class DataPoint:
  """A storage class for frequency vs flux data from various sources"""
  repr_format_string = ""

  def __init__(self, source, data): # source refers to the source the data point is describing
    # initialise point-specific default values with correct types for output string
    self.index = -1
    self.num = -1
    self.freq = float("inf")
    self.flux = float("inf")
    self.data_source = None # refers to the data source name
    self.flag = 'a'
    self.lat = float("inf")
    self.lon = float("inf")
    self.offset_from_ned = float("inf")
    self.extinction = 1. # default extinction value for all sources?

    [setattr(self, *entry) for entry in data.items()] # set proper values
    [setattr(self, key, value) for key, value in vars(source).items() if key not in vars(self)] # set any missing values with their source-wide defaults
    self.name = self.name.replace(" ","") # remove spaces to make output easier to parse

  def __repr__(self):
    """Formats the frequency vs flux data for a space-separated .dat file given a user-specified format string."""
    return self.repr_format_string % vars(self) # only includes instance variables

class Source:
  """Instances of this class represent extragalactic objects."""
  tolerance = 10. # global 10 arcsecond position offset tolerance

  def __init__(self, line):
    # common for all data points for this source, can be overwritten by user-specified fields
    self.ned_name = None
    self.nvss_id = None
    self.z = float("inf")
    self.input_lat = float("inf")
    self.input_lon = float("inf")

    [setattr(self, *entry) for entry in parse_line(line).items()] # set provided values
    [setattr(self, input_field, "") for input_field in input_fields if not hasattr(self, input_field)] # set unspecified input strings to the empty string
    self.input_lat = float(self.input_lat) # fix up types
    self.input_lon = float(self.input_lon) # fix up types
    self.name = self.ned_name if self.ned_name else (self.nvss_id if self.nvss_id else "%.5f_%.5f" % (self.input_lat, self.input_lon)) # set a unique name
    self.z = float(self.z) # fix up types

    # common for all data points for this source, will overwrite any clashing user-specified fields
    self.points = []
    self.line = line # raw input specifying source
    self.ned_position = None
    self.dust = None
    self.ned_sed = None
    self.wise = None
    self.twomass = None
    self.galex = None
    self.search_name = None
    self.ned_lat = float("inf")
    self.ned_lon = float("inf")
    self.input_offset_from_ned = float("inf")
    self.e_bv = float("inf")

    print "  Recognised source:", self.name

  def __repr__(self):
    return "\n".join(map(repr, self.points))

  def plot_output(self):
    """Builds and formats output for plotting by a utility such as gnuplot."""
    # we need to calculate the total line-of-sight comoving distance for this redshift
    # D_C = c/H_0 * integral [0, z] dz/E(z)
    # first we calculate the integral
    # E(z) = sqrt( O_M(1+z)^3 + O_k(1+z)^2 + O_Lambda )
    O_k = 1 - O_M - O_Lambda
    num_intervals = 10000 # fineness of integration
    partition = (x*self.z/num_intervals for x in xrange(num_intervals))

    E = lambda z: math.sqrt(O_M*(1+z)**3 + O_k*(1+z)**2 + O_Lambda)
    I = numpy.trapz([1/x for x in map(E, partition) if x is not 0.], dx=self.z/num_intervals)
    D_C = (c/1000)/H_0 * I # c in km/s

    # assuming a flat universe the transverse comoving distance equals the radial comoving distance
    D_M = D_C

    # the luminosity distance is given by D_L = (1+z)D_M (in units of Mpc)
    D_L = (1+self.z)*D_M

    # converting to units of metres
    d_l = 3.086e22*D_L

    # now we generate the plot output
    luminosity = lambda flux, extinction: 4*math.pi*(d_l**2)*flux*extinction*1e-26/(1+self.z)
    format_strings = {"NED": "%.5e 0 0 0", "WISE": "0 %.5e 0 0", "2MASS": "0 0 %.5e 0", "GALEX": "0 0 0 %.5e"}
    return "freq NED WISE 2MASS GALEX\n" + "\n".join("%.5e " % ((1+self.z)*point.freq) + format_strings[point.data_source] % luminosity(point.flux, point.extinction) for point in self.points)

  def search_lat(self):
    """Returns the NED latitude if it exists, otherwise returns the input-provided latitude."""
    try:
      int(self.ned_lat) + int(self.ned_lon) # will error if either are nan or inf
      return self.ned_lat
    except:
      return self.input_lat

  def search_lon(self):
    """Returns the NED longitude if it exists, otherwise returns the input-provided longitude."""
    try:
      int(self.ned_lat) + int(self.ned_lon) # will error if either are nan or inf
      return self.ned_lon
    except:
      return self.input_lon

  def get_and_parse_ned_position(self):
    """Builds the correct URL and fetches and parses the source's NED position votable.
       Records the J2000.0 equatorial latitude/longitude (decimal degrees).
       Depends on NED name or NVSS ID."""
    for search_name in (self.ned_name, self.nvss_id): # determine which name alternative between ned name and nvss id should be used
      if not search_name: # try the other name if this one isn't specified
        continue
      self.ned_position = get_votable(NED_POSITION_SEARCH_PATH % urllib.quote_plus(search_name))
      try:
        for key, name in (("ned_lat", "pos_ra_equ_J2000_d"), ("ned_lon", "pos_dec_equ_J2000_d")):
          setattr(self, key, float(self.ned_position.array[name].data.item()))
        self.search_name = search_name # will be set if above is successful
        self.input_offset_from_ned = math.hypot(self.ned_lat-self.input_lat, self.ned_lon-self.input_lon)*3600 # will be set if above is successful
        print "  Found NED position data:", self.name
        return # don't continue with the loop
      except:
        continue # try again using nvss id
    print "  Can't find NED position:", self.name

  def get_dust_xml(self):
    """Builds the correct URL and fetches and parses to xml the source's extinction E(B-V) xml file."""
    try:
      int(self.search_lat()) + int(self.search_lon()) # will error if inf or nan
    except:
      return # don't try downloading if no coordinates are known
    try:
      url = DUST_SEARCH_PATH % {"lat": self.search_lat(), "lon": self.search_lon()}
      print " ", url
      xml_file = urllib.urlopen(url) # grab xml file-like-object from the web
      time.sleep(1) # respect request throttling recommendations
      return xml.etree.ElementTree.parse(xml_file) # parse xml
    except:
      print "  Could not download or interpret data from %s. You may not be connected to the Internet or the input data contains unrecognised names or coordinates." % url
    return

  def get_ned_sed_votable(self):
    """Builds the correct URL and fetches the source's NED SED votable.
       Depends on NED name or NVSS ID."""
    if self.search_name: # check if ned recognises the provided ned name
      return get_votable(NED_SED_SEARCH_PATH % urllib.quote_plus(self.search_name))
    return

  def get_wise_votable(self):
    """Builds the correct URL and fetches the source's WISE votable.
       Depends on position."""
    try:
      int(self.search_lat()) + int(self.search_lon()) # will error if inf or nan
      return get_votable(WISE_SEARCH_PATH % {"lat": self.search_lat(), "lon": self.search_lon()})
    except: return

  def get_twomass_votable(self):
    """Builds the correct URL and fetches the source's 2MASS votable.
       Depends on position."""
    try:
      int(self.search_lat()) + int(self.search_lon()) # will error if inf or nan
      return get_votable(TWOMASS_SEARCH_PATH % {"lat": self.search_lat(), "lon": self.search_lon()})
    except: return

  def get_galex_votable(self):
    """Browses to the GALEX search page, sets the output format to votable and the correct SQL query,
       submits the form and finds the output xml which is then parsed to astropy votable and returned.
       Depends on position."""
    try:
      int(self.search_lat()) + int(self.search_lon()) # will error if inf or nan
    except: return
    try:
      browser = mechanize.Browser()
      browser.open(GALEX_SEARCH_PAGE)
      browser.select_form(nr=0) # assume only one form on the page

      browser.form["_ctl10:QueryTextbox"] = GALEX_SQL_QUERY % {"lat": self.search_lat(), "lon": self.search_lon()}
      browser.form["_ctl10:ofmt"] = ["VOT"] # set the output to votable xml

      response = browser.submit() # send off the modified form
      time.sleep(1) # respect request throttling recommendations

      html = bs4.BeautifulSoup(response.get_data()) # read data into html parser
      browser.close()

      popup_js = html.find("script", text=re.compile("^window.open\('tmp\/galex_\S+\.xml'\)$")).find(text=True) # returns the content of the script tag
      url = "http://galex.stsci.edu/GR6/" + re.compile("tmp\/galex_\S+\.xml").search(popup_js).group() # grabs the temp file name and constructs the url

      return get_votable(url)
    except:
      print "  Could not download or interpret data from %s. You may not be connected to the Internet or the input data contains unrecognised NED names." % GALEX_SEARCH_PAGE

  def parse_dust(self):
    """Picks out the E(B-V) reddening value and records it."""
    try:
      e_bv_result_node = filter(lambda node: node.find("desc").text.strip() == "E(B-V) Reddening", self.dust.findall("./result[desc]"))[0]
      self.e_bv = float(re.compile("^(?P<e_bv>[0-9]+(\.[0-9]+)?)\s*\(mag\)$", re.IGNORECASE).match(e_bv_result_node.find("statistics/meanValueSandF").text.strip()).groupdict()["e_bv"])
      print "  Found extinction data:", self.name
    except:
      print "  Can't find extinction data:", self.name

  def parse_ned_sed(self, index):
    """Picks out the frequency vs flux data and records them as data points."""
    all_fields_filter_regexp = re.compile(""" # for finding not allowed patterns in all fields of ned sed output
      ^line\\b # word line at start of field
      |
      ^1983ApJ\.\.\.272\.\.400H\\b # this ref code only at start of field
      |
      \\bmodel # word or prefix model anywhere in field
      |
      \\bcount\s+statistics\\b # phrase count statistics anywhere in field
      """, re.VERBOSE | re.IGNORECASE)

    try:
      [self.points.append(DataPoint(self, {\
         "index": index, \
         "num": len(self.points)+1, \
         "freq": freq, \
         "flux": flux, \
         "data_source": "NED", \
         "lat": self.ned_lat, \
         "lon": self.ned_lon, \
         "offset_from_ned": 0., \
         "extinction": e_bv_to_extinction(self.e_bv, freq)\
        })) \
       for freq, flux, line, passband \
       in zip(\
         map(float, self.ned_sed.array["Frequency"].data.tolist()), \
         map(float, self.ned_sed.array["NED Photometry Measurement"].data.tolist()), \
         (map(str, line) for line in self.ned_sed.array.tolist()), \
         map(str, self.ned_sed.array["Observed Passband"].data.tolist())\
        ) \
       if \
         True not in (not not all_fields_filter_regexp.search(entry) for entry in line) \
         and (\
           re.search("(^|\s)\(SDSS\\b(?!\s+PSF\)(\s|$)) # in passband matches anything (including nothing) except for psf after sdss", passband, re.VERBOSE | re.IGNORECASE) \
           if re.search("(^|\s)\(SDSS\\b # in passband matches sdss at start of field or after whitespace", passband, re.VERBOSE | re.IGNORECASE) \
           else not re.search(""" # search passband for various not allowed patterns
             \\b(
             ._K20
             |
             ._14arcsec
             |
             ._25
             |
             ._26
             |
             HST
             |
             Spitzer
             |
             ISAAC
             |
             m_p
             |
             CIT
             |
             UKIRT
             |
             GALEX
             )\\b
             """, passband, re.VERBOSE | re.IGNORECASE)\
          ) \
         and not math.isnan(flux) \
         and flux > 0 \
         and not math.isnan(freq) \
         and freq > 0\
      ].pop() # pop to trigger error if list empty
      print "  Found NED SED data:", self.name
    except:
      print "  Can't find NED SED data:", self.name

  def parse_wise(self, index):
    """Picks out the frequency vs flux data and records them as data points."""
    try: # see if 2mass data is included
      [int(self.wise.array[name].data.item()) for name in ("%s_m_2mass" % letter for letter in ("j", "h", "k"))]  # will error if no 2mass data
      self.twomass = self.wise # if gets to here then 2mass is included in wise
    except: pass # will try to fetch 2mass later
    try:
      wise_lat = float(self.wise.array["ra"].data.item())
      wise_lon = float(self.wise.array["dec"].data.item())
      wise_offset = math.hypot(self.ned_lat-wise_lat, self.ned_lon-wise_lon)*3600
      [self.points.append(DataPoint(self, {\
         "index": index, \
         "num": len(self.points)+1, \
         "freq": freq, \
         "flux": flux, \
         "data_source": "WISE", \
         "lat": wise_lat, \
         "lon": wise_lon, \
         "offset_from_ned": wise_offset, \
         "extinction": e_bv_to_extinction(self.e_bv, freq)\
        })) \
       for freq, flux \
       in zip(\
         (8.856e+13, 6.445e+13, 2.675e+13, 1.346e+13), \
         map(float.__mul__, (306.682, 170.663, 29.045, 8.284), (10**(-.4*float(self.wise.array["w%dmpro" % number].data.item())) for number in range(1,5)))\
        ) \
       if math.hypot(self.search_lat()-wise_lat, self.search_lon()-wise_lon)*3600 <= self.tolerance and not math.isnan(flux) and flux > 0\
      ]
      print "  Found WISE data:", self.name
    except:
      print "  Can't find WISE data:", self.name

  def parse_twomass(self, index):
    """Picks out the frequency vs flux data and records them as data points."""
    try:
      twomass_lat = float(self.twomass.array["ra"].data.item())
      twomass_lon = float(self.twomass.array["dec"].data.item())
      twomass_offset = math.hypot(self.ned_lat-twomass_lat, self.ned_lon-twomass_lon)*3600
      [self.points.append(DataPoint(self, {\
         "index": index, \
         "num": len(self.points)+1, \
         "freq": freq, \
         "flux": flux, \
         "data_source": "2MASS", \
         "lat": twomass_lat, \
         "lon": twomass_lon, \
         "offset_from_ned": twomass_offset, \
         "extinction": e_bv_to_extinction(self.e_bv, freq)\
        })) \
       for freq, flux \
       in zip(\
         (2.429e14, 1.805e14, 1.390e14), \
         map(float.__mul__, (1594., 1024., 667.), (10**(-.4*float(self.twomass.array["%c_m" % letter + "_2mass"*(self.twomass==self.wise)].data.item())) for letter in ("j", "h", "k")))\
        ) \
       if math.hypot(self.search_lat()-twomass_lat, self.search_lon()-twomass_lon)*3600 <= self.tolerance and not math.isnan(flux) and flux > 0\
      ]
      print "  Found 2MASS data:", self.name
    except:
      print "  Can't find 2MASS data:", self.name

  def parse_galex(self, index):
    """Picks out the frequency vs flux data and records them as data points."""
    try:
      galex_lats = map(float, self.galex.array["ra"].data.tolist())
      galex_lons = map(float, self.galex.array["dec"].data.tolist())
      galex_offsets_from_ned = [offset*3600 for offset in map(math.hypot, (self.search_lat()-lat for lat in galex_lats), (self.search_lon()-lon for lon in galex_lons))]

      mean_filter = lambda (lat, lon, offset, flux, e_bv): offset <= self.tolerance and not math.isnan(flux) and flux > 0 and not math.isnan(e_bv) and e_bv > 0 # -999 indicates no data

      for freq, flux_name in zip((1.963e15, 1.321e15), ("fuv_flux", "nuv_flux")):
        galex_averages = dict(\
          (key, numpy.mean(value)) \
          for key, value \
          in zip(\
            ("lat", "lon", "offset", "flux", "e_bv"), \
            zip(*filter(\
              mean_filter, \
              zip(\
                galex_lats, \
                galex_lons, \
                galex_offsets_from_ned, \
                map(float, self.galex.array[flux_name].data.tolist()), \
                map(float, self.galex.array["e_bv"].data.tolist())\
               )\
             ))\
           )\
         ) # only wanted data remains

        try:
          self.points.append(DataPoint(self, {\
            key: value for key, value in (\
              ("index", index), \
              ("num", len(self.points)+1), \
              ("freq", freq), \
              ("flux", galex_averages["flux"]/1e6), \
              ("data_source", "GALEX"), \
              ("flag", 'm'*(not not len(galex_offsets_from_ned) > 1)), \
              ("lat", galex_averages["lat"]), \
              ("lon", galex_averages["lon"]), \
              ("offset_from_ned", math.hypot(self.ned_lat-galex_averages["lat"], self.ned_lon-galex_averages["lon"])*3600), \
              ("extinction", e_bv_to_extinction(galex_averages["e_bv"], freq))
             )
            if not (key == "flag" and not value)\
           })) # don't include flag if not changed from default
        except: pass # keep going with the loop

      galex_offsets_from_ned.pop() # will error if empty
      print "  Found GALEX data:", self.name # successfully found at least some data
    except:
      print "  Can't find GALEX data:", self.name

def build_input_regexp():
  """Given the input string build a regexp to match against valid lines of data input."""
  quotation_mark_match_names = {}
  for input_field in input_fields: # generate non-clashing ids to be used for quotation matches
    suffix = 0
    while "%s_quotation_mark%d" % (input_field, suffix) in input_fields:
      suffix+=1
    quotation_mark_match_names[input_field] = "%s_quotation_mark%d" % (input_field, suffix)
  try:
    # assumes no leading or trailing white space and not a comment
    # unrecognised fields are strings with no whitespace
    # optional quotation marks allowed around all (possibly empty) fields
    return re.compile(\
      "^" + \
      "\s+".join(\
        "(?P<%(quotation_mark_match_name)s>\")?(?P<%(input_field)s>%(pattern)s)(?(%(quotation_mark_match_name)s)\")" % \
          {"quotation_mark_match_name": quotation_mark_match_names[input_field], "input_field": input_field, "pattern": KNOWN_INPUT_FIELDS.get(input_field, "\S*?")} \
        for input_field \
        in input_fields\
       ) + \
      "$", \
      re.IGNORECASE\
     )
  except:
    print "Unable to build input regexp!"

def parse_line(line):
  """Parses to a dictionary the data on a given line of input."""
  try:
    1/line.find("#") # errors if hash at beginning of line
    return {key: value for key, value in input_regexp.match(line.strip()).groupdict().items() if value and (key in input_fields)} # errors if no match, filters blanks
  except: return # skip line

def get_votable(url):
  """Fetches from the web and returns data for a source, in an astropy votable."""
  print " ", url
  try:
    xml_file = urllib.urlopen(url) # grab xml file-like-object from the web
    time.sleep(1) # respect request throttling recommendations
    with warnings.catch_warnings():
      warnings.simplefilter("ignore") # suppress astropy warnings
      return astropy.io.votable.parse_single_table(xml_file) # parse xml to astropy votable
  except:
    print "  Could not download or interpret data from %s. You may not be connected to the Internet or the input data contains unrecognised names or coordinates." % url

def e_bv_to_extinction(e_bv, freq):
  """Calculates an extinction given an E(B-V) and a frequency.
     See equations (1) through (4) in http://ads.nao.ac.jp/abs/1989ApJ...345..245C."""
  A_V = e_bv
  try:
    int(1/A_V) + int(A_V) # will error if zero, inf or nan
  except:
    return 1. # extinction defaults to 1
  x = (freq/c)/1e6 # wavenumber in inverse micrometres
  a = 0 # such that extinction will return 1 by default
  b = 0
  if 0.3<=x<=1.1: # infrared
    a = 0.574*x**1.61
    b = -0.527*x**1.61
  elif 1.1<=x<=3.3: # optical and near-infrared
    y = x - 1.82
    a = 1 + 0.17699*y - 0.50447*y**2 - 0.02427*y**3 + 0.72085*y**4 \
        + 0.01979*y**5 - 0.77530*y**6 + 0.32999*y**7
    b = 1.41338*y + 2.28305*y**2 + 1.07233*y**3 - 5.38434*y**4 \
        - 0.62251*y**5 + 5.30260*y**6 - 2.09002*y**7
  elif 3.3<=x<=8: # ultraviolet and far-ultraviolet
    F_a = -0.04473*(x - 5.9)**2 - 0.009779*(x - 5.9)**3 if 8>=x>=5.9 else 0
    F_b = 0.2130*(x - 5.9)**2 + 0.1207*(x - 5.9)**3 if 8>=x>=5.9 else 0
    a = 1.752 - 0.316*x - 0.104/((x - 4.67)**2 + 0.341) + F_a
    b = -3.090 + 1.825*x + 1.206/((x - 4.62)**2 + 0.263) + F_b

  A_lambda = A_V * (a + b/R_V) # R_V is extinction factor
  return 10**(0.4*A_lambda) # convert from magnitude
