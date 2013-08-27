#!/bin/sh
# Pass in a plot-ready .dat file and gnuplot will generate a plot in postscript format.
# Output plot will be stored in the same directory as the input .dat file.

fullname="$1"
filename=$(basename "$fullname")

source_name="${filename%.*}"
out_file="${fullname%.*}.ps"
in_file="$fullname"
log_file="${fullname%.*}.log"

gnuplot <<EOF
  set term postscript enhanced color
  set output "$out_file"
  set fit logfile "$log_file"
  set samples 1001 # high quality

  lower_cutoff = 10**14.8 # lowest uv freq
  upper_cutoff = 1e17 # highest uv freq
  alpha = 0
  C = 0
  f(x) = alpha*x+C
  fit [log10(lower_cutoff):log10(upper_cutoff)] f(x) "$in_file" using (log10(\$1)):(log10(\$2+\$3+\$4+\$5)) via alpha, C

  # the ionising photon rate is integral [lower_cutoff, inf] L_v/hv dv
  # where L_v is the luminosity at frequency v
  # this simplifies to ionising photon rate = -10^C/ah * v^a
  # where a is the spectral index (gradient of fit curve) and C is the intercept of the fit curve
  # note must have a < 0
  h = 6.62606957e-34 # planck constant
  ion_rate = (alpha<0) ? log10(-10**C/(alpha*h)*lower_cutoff**alpha) : NaN
  print "" # newline
  print "Ionising photon rate (log10) for $source_name: ", ion_rate

  set title "$source_name"
  set logscale
  set key autotitle columnhead
  set xrange[1e7:1e18]
  set format x "%L"
  set xlabel "Rest-frame frequency, log_{10}({/Symbol-Oblique n}_{rest}) [Hz]"
  set yrange[1e15:1e30]
  set format y "%L"
  set ylabel "Luminosity, log_{10}(L_{/Symbol-Oblique n}) [W Hz^{-1}]"
  set arrow from lower_cutoff,graph 0 to lower_cutoff,graph 1 nohead linetype 0 # vertical dashed line at lower cutoff freq
  set arrow from upper_cutoff,graph 0 to upper_cutoff,graph 1 nohead linetype 0 # vertical dashed line at upper cutoff freq
  set label gprintf("Ionising photon rate: %.1f", ion_rate) at graph 0.1,0.1

  plot 10**f(log10((lower_cutoff<x && x<upper_cutoff) ? x : 1/0)) title "UV fit", for [col=2:5] "$in_file" using 1:col # plot fit in between cutoffs only
EOF
