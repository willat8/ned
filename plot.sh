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

  lower_cutoff = 1e15 # lowest uv freq
  upper_cutoff = 1e17 $ highest uv freq
  freq_filter(x) = (x>lower_cutoff && x<upper_cutoff) ? x : 1/0
  m = 0
  b = 0
  f(x) = m*x+b

  fit f(x) "$in_file" using (log10(freq_filter(\$1))):(log10(\$2+\$3+\$4+\$5)) via m, b

  set title "$source_name"
  set logscale
  set key autotitle columnhead
  set xrange[1e7:1e18]
  set format x "%L"
  set xlabel "Rest-frame frequency, log_{10}({/Symbol-Oblique n}_{rest}) [Hz]"
  set yrange[1e15:1e30]
  set format y "%L"
  set ylabel "Luminosity, log_{10}(L_{/Symbol-Oblique n}) [W Hz^{-1}]"
  set arrow from lower_cutoff,graph(0,0) to lower_cutoff,graph(1,1) nohead linetype 0 # vertical dashed line at lower cutoff freq
  set arrow from upper_cutoff,graph(0,0) to upper_cutoff,graph(1,1) nohead linetype 0 # vertical dashed line at upper cutoff freq

  plot 10**f(log10(freq_filter(x))) title "UV fit", for [col=2:5] "$in_file" using 1:col 
EOF
