"""This module provides tools for querying the NASA\IPAC Extragalactic Database (NED),
   the Wide-field Infrared Survey Explorer (WISE) database, the Two Micron All Sky Survey (2MASS) database
   and the Galaxy Evolution Explorer (GALEX) database."""

import urllib, astropy.io.votable, time, warnings, math, mechanize, bs4, re, numpy

POLARISATION_REGEXP = re.compile(""" # assumes no leading or trailing white space
  ^
  (?P<pol_lat>-?[0-9]+\.?[0-9]+) # lat
  \s+(?P<pol_lon>-?[0-9]+\.?[0-9]+) # lon
  \s+"(?P<name>.+)" # ned name
  \s+(?P<z>-?[0-9]+(\.?[0-9]*)?([eE][0-9]+)?) # z
  \s+(?P<RM>-?[0-9]+(\.?[0-9]*)?) # RM
  \s+(?P<RM_err>-?[0-9]+(\.?[0-9]*)?) # RM error
  \s+(?P<RMM>-?[0-9]+(\.?[0-9]*)?) # RMM
  \s+(?P<RMM_err>-?[0-9]+(\.?[0-9]*)?) # RMM error
  \s+"(?P<nvis_id>.*)" # nvis id
  $
  """, re.VERBOSE)
NED_NAME_REGEXP = re.compile(""" # assumes no leading or trailing white space
  ^
  (?P<name>\S+\s+\S+\s*\S*) # ned name assuming conventions at http://cdsweb.u-strasbg.fr/vizier/Dic/iau-spec.htx
  $
  """, re.VERBOSE)

NED_POSITION_SEARCH_PATH = "http://nedwww.ipac.caltech.edu/cgi-bin/nph-objsearch?of=xml_posn\
&objname=%s"
NED_SED_SEARCH_PATH = "http://nedwww.ipac.caltech.edu/cgi-bin/nph-datasearch?search_type=Photometry&of=xml_all\
&objname=%s"
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
c = 299793 # speed of light

class DataPoint:
  """A storage class for frequency vs flux data from various sources"""
  repr_format_string = ""

  def __init__(self, data):
    # initialise default values with correct types for output string
    self.index = -1
    self.name = None
    self.z = float("inf")
    self.num = -1
    self.freq = float("inf")
    self.flux = float("inf")
    self.source = None # refers to the data source name
    self.flag = 'a'
    self.lat = float("inf")
    self.lon = float("inf")
    self.offset_from_ned = float("inf")
    self.extinction = 1. # default extinction value for all sources?
    self.RM = None
    self.RM_err = None
    self.RMM = None
    self.RMM_err = None
    self.nvis_id = None
    self.pol_offset_from_ned = float("inf")

    [setattr(self, *entry) for entry in data.items()] # set proper values

  def __repr__(self):
    """Formats the frequency vs flux data for a space-separated .dat file given a user-specified format string."""
    return self.repr_format_string % vars(self)

class Source:
  """Instances of this class represent extragalactic objects."""
  tolerance = 10. # global 10 arcsecond position offset tolerance

  def __init__(self, line):
    self.points = []
    self.line = line # raw input specifying source
    self.ned_position = None
    self.ned_sed = None
    self.wise = None
    self.twomass = None
    self.galex = None

    # common for all data points for this source
    self.name = None
    self.ned_lat = float("inf")
    self.ned_lon = float("inf")
    self.z = float("inf")
    self.RM = None
    self.RM_err = None
    self.pol_lat = float("inf")
    self.pol_lon = float("inf")
    self.pol_offset_from_ned = float("inf")

    [setattr(self, *entry) for entry in parse_line(line).items()] # set provided values
    self.pol_lat = float(self.pol_lat) # fix up types
    self.pol_lon = float(self.pol_lon) # fix up types
    self.z = float(self.z) # fix up types
    print "  Recognised source", self.name

  def __repr__(self):
    return "\n".join(map(repr, self.points))

  def plot_output(self):
    """Builds and formats output for plotting by a utility such as gnuplot"""
    # we need to calculate the total line-of-sight comoving distance for this redshift
    # D_C = c/H_0 * integral [0, z] dz/E(z)
    # first we calculate the integral
    # E(z) = sqrt( O_M(1+z)^3 + O_k(1+z)^2 + O_Lambda )
    O_k = 1 - O_M - O_Lambda
    num_intervals = 10000 # fineness of integration
    partition = (x*self.z/num_intervals for x in xrange(num_intervals))

    E = lambda z: math.sqrt(O_M*(1+z)**3 + O_k*(1+z)**2 + O_Lambda)
    I = numpy.trapz([1/x for x in map(E, partition) if x is not 0.], dx=self.z/num_intervals)
    D_C = c/H_0 * I

    # assuming a flat universe the transverse comoving distance equals the radial comoving distance
    D_M = D_C

    # the luminosity distance is given by D_L = (1+z)D_M (in units of Mpc)
    D_L = (1+self.z)*D_M

    # converting to units of metres
    d_l = 3.086e22*D_L

    # now we generate the plot output
    luminosity = lambda flux, extinction: 4*3.14159*(d_l**2)*flux*extinction*1e-26/(1+self.z)
    format_strings = {"NED": "%.5e 0 0 0", "WISE": "0 %.5e 0 0", "2MASS": "0 0 %.5e 0", "GALEX": "0 0 0 %.5e"}
    return "freq NED WISE 2MASS GALEX\n" + "\n".join("%.5e " % ((1+self.z)*point.freq) + format_strings[point.source] % luminosity(point.flux, point.extinction) for point in self.points)

  def get_ned_position_votable(self):
    """Builds the correct URL and fetches the source's NED position votable.
       Depends on NED name."""
    return get_votable(NED_POSITION_SEARCH_PATH % urllib.quote_plus(self.name))

  def get_ned_sed_votable(self):
    """Builds the correct URL and fetches the source's NED SED votable.
       Depends on NED name."""
    return get_votable(NED_SED_SEARCH_PATH % urllib.quote_plus(self.name))

  def get_wise_votable(self):
    """Builds the correct URL and fetches the source's WISE votable.
       Depends on NED position."""
    return get_votable(WISE_SEARCH_PATH % {"lat": self.ned_lat, "lon": self.ned_lon})

  def get_twomass_votable(self):
    """Builds the correct URL and fetches the source's 2MASS votable.
       Depends on NED position."""
    return get_votable(TWOMASS_SEARCH_PATH % {"lat": self.ned_lat, "lon": self.ned_lon})

  def get_galex_votable(self):
    """Browses to the GALEX search page, sets the output format to votable and the correct SQL query,
       submits the form and finds the output xml which is then parsed to astropy votable and returned.
       Depends on NED position."""
    try:
      browser = mechanize.Browser()
      browser.open(GALEX_SEARCH_PAGE)
      browser.select_form(nr=0) # assume only one form on the page

      browser.form["_ctl10:QueryTextbox"] = GALEX_SQL_QUERY % {"lat": self.ned_lat, "lon": self.ned_lon}
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

  def parse_ned_position(self):
    """Picks out the J2000.0 equatorial latitude/longitude (decimal degrees) and records them."""
    try:
      for key, name in [("ned_lat", "pos_ra_equ_J2000_d"), ("ned_lon", "pos_dec_equ_J2000_d")]:
        setattr(self, key, float(self.ned_position.array[name].data.item()))
      self.pol_offset_from_ned = math.hypot(self.ned_lat-self.pol_lat, self.ned_lon-self.pol_lon)*3600 # will be set if above is successful
      print " ", self.name
    except:
      print "  Can't find raw NED position data! (%s)" % self.name

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
      [self.points.append(DataPoint({\
         "index": index, \
         "name": self.name.replace(" ",""), \
         "z": self.z, \
         "num": len(self.points)+1, \
         "freq": freq, \
         "flux": flux, \
         "source": "NED", \
         "lat": self.ned_lat, \
         "lon": self.ned_lon, \
         "offset_from_ned": 0., \
         "RM": self.RM, \
         "RM_err": self.RM_err, \
         "pol_offset_from_ned": self.pol_offset_from_ned\
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
             _K20
             |
             _14arcsec
             |
             _25
             |
             _26
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
      print " ", self.name
    except:
      print "  Can't find raw NED SED data! (%s)" % self.name

  def parse_wise(self, index):
    """Picks out the frequency vs flux data and records them as data points."""
    try: # see if 2mass data is included
      [int(self.wise.array[name].data.item()) for name in ["%s_m_2mass" % letter for letter in ("j", "h", "k")]]  # will error if no 2mass data
      self.twomass = self.wise # if gets to here then 2mass is included in wise
    except: pass # will try to fetch 2mass later
    try:
      wise_lat = float(self.wise.array["ra"].data.item())
      wise_lon = float(self.wise.array["dec"].data.item())
      wise_offset = math.hypot(self.ned_lat-wise_lat, self.ned_lon-wise_lon)*3600
      [self.points.append(DataPoint({\
         "index": index, \
         "name": self.name.replace(" ",""), \
         "z": self.z, \
         "num": len(self.points)+1, \
         "freq": freq, \
         "flux": flux, \
         "source": "WISE", \
         "lat": wise_lat, \
         "lon": wise_lon, \
         "offset_from_ned": wise_offset, \
         "RM": self.RM, \
         "RM_err": self.RM_err, \
         "pol_offset_from_ned": self.pol_offset_from_ned\
        })) \
       for freq, flux \
       in zip(\
         (8.856e+13, 6.445e+13, 2.675e+13, 1.346e+13), \
         map(float.__mul__, (306.682, 170.663, 29.045, 8.284), [10**(-.4*float(self.wise.array["w%dmpro" % number].data.item())) for number in range(1,5)])\
        ) \
       if wise_offset <= self.tolerance and not math.isnan(flux) and flux > 0\
      ]
      print " ", self.name
    except:
      print "  Can't find raw WISE data! (%s)" % self.name

  def parse_twomass(self, index):
    """Picks out the frequency vs flux data and records them as data points."""
    try:
      twomass_lat = float(self.twomass.array["ra"].data.item())
      twomass_lon = float(self.twomass.array["dec"].data.item())
      twomass_offset = math.hypot(self.ned_lat-twomass_lat, self.ned_lon-twomass_lon)*3600
      [self.points.append(DataPoint({\
         "index": index, \
         "name": self.name.replace(" ",""), \
         "z": self.z, \
         "num": len(self.points)+1, \
         "freq": freq, \
         "flux": flux, \
         "source": "2MASS", \
         "lat": twomass_lat, \
         "lon": twomass_lon, \
         "offset_from_ned": twomass_offset, \
         "RM": self.RM, \
         "RM_err": self.RM_err, \
         "pol_offset_from_ned": self.pol_offset_from_ned\
        })) \
       for freq, flux \
       in zip(\
         (2.429e14, 1.805e14, 1.390e14), \
         map(float.__mul__, (1594., 1024., 667.), [10**(-.4*float(self.twomass.array["%c_m" % letter + "_2mass"*(self.twomass==self.wise)].data.item())) for letter in ("j", "h", "k")])\
        ) \
       if twomass_offset <= self.tolerance and not math.isnan(flux) and flux > 0\
      ]
      print " ", self.name
    except:
      print "  Can't find raw 2MASS data! (%s)" % self.name

  def parse_galex(self, index):
    """Picks out the frequency vs flux data and records them as data points."""
    try:
      galex_lats = map(float, self.galex.array["ra"].data.tolist())
      galex_lons = map(float, self.galex.array["dec"].data.tolist())
      galex_offsets_from_ned = [offset*3600 for offset in map(math.hypot, (self.ned_lat-lat for lat in galex_lats), (self.ned_lon-lon for lon in galex_lons))]

      mean_filter = lambda (lat, lon, offset, flux, e_bv): offset <= self.tolerance and not math.isnan(flux) and flux > 0 and not math.isnan(e_bv) and e_bv > 0 # -999 indicates no data

      for freq, flux_name, extinction in zip((1.963e15, 1.321e15), ("fuv_flux", "nuv_flux"), (lambda e_bv: 10**(.4*e_bv*8.24), lambda e_bv: 10**(.4*e_bv*(8.24-e_bv*0.67)))):
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
          self.points.append(DataPoint({\
            key: value for key, value in (\
              ("index", index), \
              ("name", self.name.replace(" ","")), \
              ("z", self.z), \
              ("num", len(self.points)+1), \
              ("freq", freq), \
              ("flux", galex_averages["flux"]/1e6), \
              ("source", "GALEX"), \
              ("flag", 'm'*(not not len(galex_offsets_from_ned) > 1)), \
              ("lat", galex_averages["lat"]), \
              ("lon", galex_averages["lon"]), \
              ("offset_from_ned", math.hypot(self.ned_lat-galex_averages["lat"], self.ned_lon-galex_averages["lon"])*3600), \
              ("extinction", extinction(galex_averages["e_bv"])), \
              ("RM", self.RM), \
              ("RM_err", self.RM_err), \
              ("pol_offset_from_ned", self.pol_offset_from_ned)\
             )
            if not (key == "flag" and not value)\
           })) # don't include flag if not changed from default
        except: pass # keep going with the loop

      galex_offsets_from_ned.pop() # will error if empty
      print " ", self.name # successfully found at least some data
    except:
      print "  Can't find raw GALEX data! (%s)" % self.name

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
    print "  Could not download or interpret data from %s. You may not be connected to the Internet or the input data contains unrecognised NED names." % url

def parse_line(line):
  """Parses to a dictionary the data on a given line of input."""
  line = line.strip()
  for regexp in (POLARISATION_REGEXP, NED_NAME_REGEXP): # check if polarisation data or ned names (order of matches matters)
    try:
      return regexp.match(line).groupdict() # errors if no match
    except: continue # function evaluates false if never matches
