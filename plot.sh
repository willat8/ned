#!/bin/sh
# Pass in a plot-ready .dat file and gnuplot will generate a plot in postscript format.
# Output plot will be stored in the same directory as the input .dat file.

fullname="$1"
filename=$(basename "$fullname")

source_name="${filename%.*}"
out_file="${fullname%.*}.ps"
in_file="$fullname"

gnuplot <<EOF
  set term postscript enhanced color
  set output "$out_file"

  set logscale
  set xrange[1e7:1e18]
  set yrange[1e15:1e30]

  set key autotitle columnhead
  set xlabel "Rest-frame frequency, log_{10}({/Symbol-Oblique n}_{rest}) [Hz]"
  set format x "%L"
  set ylabel "Luminosity, log_{10}(L_{/Symbol-Oblique n}) [W Hz^{-1}]"
  set format y "%L"
  set title "$source_name"

  cutoff_freq = 1e15 # lowest uv freq
  set arrow from cutoff_freq,graph(0,0) to cutoff_freq,graph(1,1) nohead linetype 0 # vertical dashed line at cutoff freq

  plot for [col=2:5] "$in_file" using 1:col 
EOF
