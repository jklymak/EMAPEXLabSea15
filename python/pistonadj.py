#! /usr/bin/env python2
# pistonadj -- determine addwt and alpha using insitu data
# reads ballast file (default = ./info/balpt) for ballast point of each float

"""
./pistonadj.py 3763h
./pistonadj.py -w 17.5 -n 30 -a 3.5e-6 4980b
"""

# type next two into ipython to force reload of all modules every run
# import ipy_autoreload
# %autoreload 2

from __future__ import print_function

import sys
import os
from datetime import datetime
from optparse import OptionParser

import numpy
import scipy.io
import matplotlib
import matplotlib.pyplot as mplt
import matplotlib.dates  as mdates
import matplotlib.mlab   as mlab
import matplotlib.cbook  as cbook

from emalib import pistonneutral
from emalib import read_balpt
from emalib import sw_dens

parser = OptionParser(
  usage="%prog [Options] runid(s)", 
  version="%prog 1.0")

parser.add_option("-n", "--nprof", dest="nprof", default="10", 
  help="number of profiles to use", metavar="NPROF")

parser.add_option("-w", "--addwt", dest="addwt", default=None, 
  help="weight added (grams)", metavar="WTADD")

parser.add_option("-a", "--alpha", dest="alpha", default=None, 
  help="compressibility, dV/V/dbar", metavar="ALPHA")

parser.add_option("-f", "--fnbp", dest="fnbp", default="./info/balpt", 
  help="ballast point file name", metavar="FNBP")

parser.add_option("-v", "--verbose",
  action="store_true", dest="verbose", default=False,
  help="print status messages to stdout")

(options, args) = parser.parse_args()

if len(args) < 1:
  print('missing runid(s); use "-h" for help')
  sys.exit()

do_pdf = False
do_png = False

for runid in args:

  print(runid)

  bp = read_balpt(runid,options.fnbp)

  if options.addwt != None:
    addwt = float(options.addwt)
  else:
    addwt = bp.addwt

  if options.alpha != None:
    alpha = float(options.alpha)
  else:
    alpha = bp.alpha

  nprof = int(options.nprof)

  if options.verbose:
    print("addwt:",addwt)
    print("nprof:",nprof)
    print("fnbp:",options.fnbp)

  decdir = '/data/emapex/emarun/data/' + runid + '/matlab/dec'
  decdir = '/home/emapex/proc/dec/' + runid
  if options.verbose:
    print('decdir=',decdir)

  if do_pdf:
    pdfdir = '/home/dunlap/public_html/emapex-pistonadj'
    pdfdir = './pdf'
    if options.verbose:
      print('pdfdir=',pdfdir)

  files = []
  for file in sorted(os.listdir(decdir)):
    if file.endswith("-ctd.mat"):
      tup = file.split('-')
      hpid = int(tup[2]);
      if runid == '3767a' and hpid > 122: # Salin = 0
        continue
      files.append(file)

  print('last file:',file,hpid)

  nums = matplotlib.pyplot.get_fignums()
  if len(nums) == 0:
    fig = mplt.figure()
  else:
    fig = mplt.figure(nums[0])

  fig.clf()
  pltname = 'ema-' + runid + '-pistonadj'

  ax1 = fig.add_subplot(311)
  ax2 = fig.add_subplot(312)
  ax3 = fig.add_subplot(313)

  mplt.subplots_adjust(hspace=0.5)

  ax1.hold(True)
  ax2.hold(True)
  ax3.hold(True)

  if nprof >= len(files) or nprof <= 0:
    nprof = len(files)

  for loop in (1,2):
    if options.verbose:
      print('loop=',loop)
    for file in files[-nprof:]:
      if options.verbose:
        print(file)
      
      CTD = scipy.io.loadmat(decdir + '/' + file)

      if len(CTD['UXT']) and len(CTD['UXT'][0])==0:
        continue

      UXT = numpy.array(CTD['UXT'][0],dtype='double')
      P = numpy.array(CTD['P'][0],dtype='double')
      T = numpy.array(CTD['T'][0],dtype='double')
      S = numpy.array(CTD['S'][0],dtype='double')
      pca = numpy.array(CTD['pc'][0],dtype='double')

      tup = file.split('-')

      hol_file = tup[0] + '-' + tup[1] + '-' + tup[2] + '-hol.mat'
      try:
        HOL = scipy.io.loadmat(decdir + '/' + hol_file)
        got_hol = True
      except:
        got_hol = False

      if got_hol:
        if len(HOL['UXT']) and len(HOL['UXT'][0])==0:
          got_hol = False

      if got_hol:
        if options.verbose:
          print('hol_file=',hol_file,'nobs=',len(HOL['UXT'][0]))

        UXT = numpy.append(UXT,HOL['UXT'][0])
        P   = numpy.append(P  ,HOL['P'  ][0])
        T   = numpy.append(T  ,HOL['T'  ][0])
        S   = numpy.append(S  ,HOL['S'  ][0])
        pca = numpy.append(pca,HOL['pc' ][0])

      vit_file = tup[0] + '-' + tup[1] + '-' + tup[2] + '-vit.mat'
      try:
        VIT = scipy.io.loadmat(decdir + '/' + vit_file)
        got_vit = True
      except:
        got_vit = False

      if got_vit and VIT['FastProfilingFlag'][0]==0 and VIT['ProfilingFlag'][0]==1:
        use_ParkObs = True
        ParkObsDate   = VIT['ParkObsDate'][0]
        ParkObsP      = VIT['ParkObsP'][0]
        ParkObsT      = VIT['ParkObsT'][0]
        ParkObsS      = VIT['ParkObsS'][0]
        ParkObsPiston = VIT['ParkObsPiston'][0]
        ParkObsSigmat = sw_dens(ParkObsS,ParkObsT,ParkObsP) - 1000
        ParkObsPcn    = pistonneutral(ParkObsP,ParkObsT,ParkObsS,\
                        bp.P,bp.T,bp.S,bp.PC,addwt,alpha,bp.beta)
        ParkObsPcfn   = ParkObsPiston - ParkObsPcn
      else:
        use_ParkObs = False

      dpdt = numpy.diff(P) / numpy.diff(UXT)

      sigmat = numpy.empty(len(P))
      pcn = numpy.empty(len(P))
      for i in range(len(P)):
        sigmat[i] = sw_dens(S[i],T[i],P[i]) - 1000
        pcn[i] = pistonneutral(P[i],T[i],S[i],\
                  bp.P,bp.T,bp.S,bp.PC,addwt,alpha,bp.beta)

      # piston counts from neutral
      pcfn = pca - pcn

      ax1.plot(pcfn[1:],-dpdt,'b.',markersize=1)
      if use_ParkObs:
        ax1.plot(ParkObsPcfn,0.0,'go')

      if loop == 1:
        ax2.plot(pcn,P,'b.',markersize=1)
        ax3.plot(pcn,sigmat,'b.',markersize=1)

      if loop == 2:
        dpdt_thresh = 0.01
        j = numpy.nonzero(abs(dpdt) < dpdt_thresh)
        ax2.plot(pca[j],P[j],'r.',markersize=4)
        ax3.plot(pca[j],sigmat[j],'r.',markersize=4)
        if use_ParkObs:
          ax2.plot(ParkObsPiston, ParkObsP, 'go')
          ax3.plot(ParkObsPiston, ParkObsSigmat,'go')

  ax1.set_ylim((-0.2,0.2))
  ax1.set_xlim((-50.0,50.0))

  ylim = ax1.get_ylim()
  xlim = ax1.get_xlim()
  ax1.plot((0,0),ylim,'k')
  ax1.plot(xlim,(0,0),'k')
  ax1.set_ylim(ylim)
  ax1.set_xlim(xlim)

  ax1.hold(False)
  ax2.hold(False)
  ax3.hold(False)

  ax1.grid(True)
  ax2.grid(True)
  ax3.grid(True)

  ax2.invert_yaxis()
  ax3.invert_yaxis()

  mplt.axes(ax1)
  mplt.ylabel('-dP/dt, dbar/s')
  mplt.xlabel('Piston Counts from Neutral')
  mplt.title(str.format('{0}, addwt={1} g, alpha={2}, adjust so Y-intercept=0',runid,addwt,alpha))

  mplt.axes(ax2)
  mplt.ylabel('Pressure, dbar')
  mplt.xlabel(str.format('Piston Counts: Blue: to be Neutral, Red: |dP/dt| < {0}',dpdt_thresh))

  mplt.axes(ax3)
  mplt.ylabel('Sigma-T')
  mplt.xlabel(str.format('Piston Counts: Blue: to be Neutral, Red: |dP/dt| < {0}, ({1})',
    dpdt_thresh,pltname))

# subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=None, hspace=None)
# left  = 0.125  # the left side of the subplots of the figure
# right = 0.9    # the right side of the subplots of the figure
# bottom = 0.1   # the bottom of the subplots of the figure
# top = 0.9      # the top of the subplots of the figure
# wspace = 0.2   # the amount of width reserved for blank space between subplots
# hspace = 0.5   # the amount of height reserved for white space between subplots


  if do_pdf:
    pdffile = pdfdir + '/' + pltname + '.pdf'
    mplt.savefig(pdffile)

  if do_png:
    pngfile = pngdir + '/' + pltname + '.png'
    mplt.savefig(pngfile)

  if do_pdf or do_png:
    os.system('/home/dunlap/bin/updateframe.run ' + pdfdir);
  else:
    if False and sys.hexversion >= 0x02070000:
      mplt.show(block=False)
    else:
      mplt.show()

