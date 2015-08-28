#! /usr/bin/env python2
# mkmu -- make mission updates file

"""
./mkmu.py mkmu/in mkmu/out
"""

from __future__ import print_function


import io
import sys
from optparse import OptionParser

import sys
# sys.path.append('/home/dunlap/emapex/python/emalib')
from emalib import mkmuline

parser = OptionParser(usage="%prog [Options] IFILE [OFILE]")

parser.add_option("-v", "--verbose",
      action="store_true", dest="verbose", default=False,
                  help="print status messages to stderr")

(options, args) = parser.parse_args()

if len(args) < 1 or len(args) > 2:
  parser.print_help()
  sys.exit(1)

ifile = args[0];
ifd = open(ifile, mode='rt')

if len(args) == 2:
  ofile = args[1]
else:
  ofile = None

if ofile == None:
  ofd = sys.stdout
else:
  ofd = open(ofile, mode='wt')

if options.verbose:
  print('ifile:',ifile, file=sys.stderr)
  print('ofile:',ofile, file=sys.stderr)

lineno = 0

for linein in ifd:
  lineno += 1

  linein = linein.strip()

  lineout = mkmuline(linein)

  if lineout == None:
#   print('mkmu.py: skipped line=',linein)
    continue

  ofd.write(lineout + '\n')

ifd.close()

if ofile != None:
  ofd.close()

if options.verbose:
  print('number of lines:',lineno,file=sys.stderr)
