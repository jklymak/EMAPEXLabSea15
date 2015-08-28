#!/usr/bin/env python2
# emadec.py -- decode uploaded files from emapex floats
# makes .mat and .txt files
# uses './emainfo'

# todo:
# some variables not handled -- see lines with "fixme"
# add first & last string date/time in headers
# LOG and TMP data not handled yet
# fix getbuf() & decode_ema() so if one file type is bad others are used

"""
./emadec.py 3763h
"""

from __future__ import print_function

import numpy as np
import struct
import sys
import collections
import matplotlib
# matplotlib.use('Agg')
# import matplotlib.pyplot as mplot
import scipy.io as sio
from time import strptime, strftime, mktime
from datetime import datetime, timedelta
from optparse import OptionParser
import string
from getinfo import getinfo, split_ifile, mkinfo, getfltid, getinfoinit
from os import makedirs, path, listdir

# python time to unix seconds
def pyt2uxt(pyt):
  dif = pyt - datetime(1970,1,1)
  return dif.days * 86400 + dif.seconds + dif.microseconds * 1e-6 

def uxt2iso(secs):
  pyt = datetime(1970,1,1) + timedelta(0,secs)
  return pyt.strftime('%Y%m%dT%H%M%S')

def uxt2str(secs):
  pyt = datetime(1970,1,1) + timedelta(0,secs)
  return pyt.strftime('%Y-%m-%d %H:%M:%S')

def tirid2str(val):
  pyt = datetime(2007, 3, 8, 3,50,21) + timedelta(0,val * 0.090)
  return pyt.strftime('%Y-%m-%d %H:%M:%S')

def toks2date(ymd,hms):
  year   = int(ymd[0:4])
  month  = int(ymd[4:6])
  day    = int(ymd[6:8])
  hour   = int(hms[0:2])
  minute = int(hms[2:4])
  second = int(hms[4:6])
  return datetime(year,month,day,hour,minute,second)

def gpsclear(gps):
  gps.hms      = ''
  gps.hms_rms  = ''
  gps.hpid     = None
  gps.uxt      = []
  gps.pyt      = []
  gps.secs     = []
  gps.lat      = []
  gps.lon      = []
  gps.stat     = []
  gps.nsat     = []
  gps.hdop     = []
  gps.alt      = []
  gps.age      = []
  gps.refstn   = []
  gps.nbytes = 0

def decode_gps(buf, gps):
  typ  = struct.unpack('>4s',buf[0:4])[0]
  uxt  = struct.unpack('<I',buf[4:8])[0]
  hpid = struct.unpack('<H',buf[8:10])[0]
  ngps = struct.unpack('<H',buf[10:12])[0]
  nbytes = 12 + ngps


  if gps.nobs == 0:
    gpsclear(gps)

  gps.nbytes += nbytes

  fmt = str.format('>{0:d}s',ngps-2)
  nmea = struct.unpack(fmt,buf[12:12+ngps-2])[0]

# print(typ,'nobs=',nobs,'hpid=',hpid,'nbytes=',nbytes)
# print(nmea)
  tok = nmea.split(',')

  if tok[0] == '$GPRMC':
    gps.gprmc = nmea
    gps.hms_rmc = tok[1]
    gps.dmy = tok[9]

  if tok[0] == '$GPGGA':
    gps.gpgga = nmea
    gps.hms = tok[1]
    gps.tok = tok

  if gps.hms == gps.hms_rmc:
    tok = gps.tok

    gps.nobs = gps.nobs + 1
    gps.hpid = hpid
    gps.typ = typ

    day    = int(gps.dmy[0:2])
    month  = int(gps.dmy[2:4])
    year   = int(gps.dmy[4:6]) + 2000
    hour   = int(gps.hms[0:2])
    minute = int(gps.hms[2:4])
    second = int(gps.hms[4:6])
    pyt = datetime(year,month,day,hour,minute,second)
    secs = pyt2uxt(pyt)
    gps.hms = ''
    gps.hms_rms = ''

    # print('gps.tok',gps.tok)
    
    try:
      latd = float(gps.tok[2][0:2])
      latm = float(gps.tok[2][2:])
      lath = gps.tok[3];
      lat = latd + latm / 60.0
      if lath == 'S':
        lat = -lat
    except:
      lat = np.nan

    try:
      lond = float(gps.tok[4][0:3])
      lonm = float(gps.tok[4][3:])
      lonh = gps.tok[5];
      lon = lond + lonm / 60.0
      if lonh == 'W':
        lon = -lon
    except:
      lon = np.nan

    try:
      stat = int(gps.tok[6]);
    except:
      stat = -1

    try:
      nsat = int(gps.tok[7]);
    except:
      nsat = -1

    try:
      hdop = float(gps.tok[8]);
    except:
      hdop = np.nan

    try:
      alt  = float(gps.tok[9]);
    except:
      alt = np.nan

    try:
      age  = int(gps.tok[13]);
    except:
      age = -1

    try:
      refstn  = int(gps.tok[14]);
    except:
      refstn = -1

    if stat <= 0:
      lat = np.nan
      lon = np.nan

    gps.uxt.append(uxt)
    gps.pyt.append(pyt)
    gps.secs.append(secs)
    gps.lat.append(lat)
    gps.lon.append(lon)
    gps.stat.append(stat)
    gps.nsat.append(nsat)
    gps.hdop.append(hdop)
    gps.alt.append(alt)
    gps.age.append(age)
    gps.refstn.append(refstn)

  return nbytes, hpid
# endof decode_gps

def gps2np(gps,hpid):
  gps.hpid = hpid # overwrite original hpid

  gps.UXT  = np.array(gps.uxt,dtype=np.long);
  gps.PYT  = np.array(gps.pyt);
  gps.SECS = np.array(gps.secs,dtype=np.long);
  gps.LAT  = np.array(gps.lat,dtype=np.double);
  gps.LON  = np.array(gps.lon,dtype=np.double);
  gps.STAT = np.array(gps.stat,dtype=np.long);
  gps.NSAT = np.array(gps.nsat,dtype=np.long);
  gps.HDOP = np.array(gps.hdop,dtype=np.float);
  gps.ALT  = np.array(gps.alt,dtype=np.float);
  gps.AGE  = np.array(gps.age,dtype=np.long);
  gps.REFSTN = np.array(gps.refstn,dtype=np.long);

def writemat_gps(gps):
  if options.verbose >= 2:
    print('writemat_gps: hpid=',gps.hpid,'nobs=',gps.nobs)
  # to zero arrays
  # gps.nobs = 0
  ofile = str.format('ema-{0:s}-{1:04d}-gps.mat',ema.info.runid,gps.hpid)
  if options.verbose >= 2:
    print('writemat_gps: ',ema.odir + '/' + ofile)
  sio.savemat(ema.odir + '/' + ofile, {\
    'hpid':gps.hpid, \
    'typ':gps.typ, \
    'nobs':gps.nobs, \
    'nbytes':gps.nbytes, \
    'runid':ema.info.runid, \
    'UXT_APF9':gps.UXT, \
    'UXT_GPS':gps.SECS, \
    'LAT':gps.LAT, \
    'LON':gps.LON, \
    'STAT':gps.STAT, \
    'NSAT':gps.NSAT, \
    'HDOP':gps.HDOP, \
    'ALT':gps.ALT, \
    'AGE':gps.AGE, \
    'REFSTN':gps.REFSTN \
    }, format='4')
  ema.ofile_list.append(ofile)


def writetxt_gps(gps):
  if options.verbose >= 2:
    print('writetxt_gps: hpid=',gps.hpid,'nobs=',gps.nobs)

  ofile = str.format("ema-{0:s}-{1:04d}-gps.txt",ema.info.runid,gps.hpid)
  if options.verbose >= 2:
    print('writetxt_gps: ',ema.odir + '/' + ofile)

  try:
    ofp = open(ema.odir + '/' + ofile,'wt')
  except:
    print('writetxt_gps: cannot open output file',ofile)
    sys.exit(1)

  print("# ofile = {0:s}".format(ofile),file=ofp)
  print("# runid = {0:s}".format(ema.info.runid),file=ofp)
  print("# hpid = {0:d}".format(gps.hpid),file=ofp)
  print("# nobs = {0:d}".format(gps.nobs),file=ofp)
  print("# nbytes = {0:d}".format(gps.nbytes),file=ofp)
  print("# typ = {0}".format(gps.typ),file=ofp)
  print("# vars = LAT,LON,STAT,NSAT,HDOP,ALT,AGE,REFSTN,UXT_GPS,UXT_APF9",file=ofp)
  print("#DATA#",file=ofp)

  for i in range(0,gps.nobs):
    print("{0:.6f},".format(gps.LAT[i]),file=ofp,end="")
    print("{0:.6f},".format(gps.LON[i]),file=ofp,end="")
    print("{0},".format(gps.STAT[i]),file=ofp,end="")
    print("{0},".format(gps.NSAT[i]),file=ofp,end="")
    print("{0},".format(gps.HDOP[i]),file=ofp,end="")
    print("{0},".format(gps.ALT[i]),file=ofp,end="")
    print("{0},".format(gps.AGE[i]),file=ofp,end="")
    print("{0},".format(gps.REFSTN[i]),file=ofp,end="")
    print("{0},".format(gps.SECS[i]),file=ofp,end="")
    print("{0}".format(gps.UXT[i]),file=ofp)

  print("#EOD#",file=ofp)
  ofp.close()


def decode_eoa(buf,eoa):
  eoa.typ = struct.unpack('>4s',buf[0:4])[0]
  if eoa.typ != 'EOAa':
    print('Error: decode_eoa: only coded for EOAa')
    sys.exit(1)
  eoa.uxt  = struct.unpack('<I',buf[4:8])[0]
  eoa.hpid = struct.unpack('<H',buf[8:10])[0]
  eoa.neoa = struct.unpack('<H',buf[10:12])[0]
  eoa.nobs = struct.unpack('<H',buf[12:14])[0]
  eoa.nbytes =  14 + eoa.neoa

  if options.verbose:
    print(eoa.typ,'uxt=',uxt2str(eoa.uxt),'hpid=',eoa.hpid,'nobs=',eoa.nobs,'nbytes=',eoa.nbytes)

  nbpo = 8
  if eoa.nobs * nbpo != eoa.neoa:
    print('Error: decode_eoa: nobs & neoa do not agree')
    sys.exit(1)

  eoa.P   = np.empty(eoa.nobs,dtype=np.double)
  eoa.UXT = np.empty(eoa.nobs,dtype=np.long)

  ib = 14
  for iobs in range(eoa.nobs):
    P, UXT = struct.unpack('<fi',buf[ib:ib+nbpo])
    ib += nbpo
    eoa.P[iobs] = P
    eoa.UXT[iobs] = UXT

  if ib != eoa.nbytes:
    print('Error: decode_eoa: ib & nbytes do not agree')
    sys.exit(1)

  return eoa.nbytes, eoa.hpid

def writemat_eoa(eoa):
  if options.verbose >= 2:
    print('writemat_eoa: hpid=',eoa.hpid,'nobs=',eoa.nobs)
  ofile = str.format("ema-{0:s}-{1:04d}-eoa.mat",ema.info.runid,eoa.hpid)
  if options.verbose >= 2:
    print('writemat_eoa: ',ema.odir + '/' + ofile)
  sio.savemat(ema.odir + '/' + ofile, {\
    'P':eoa.P, \
    'UXT':eoa.UXT, \
    'hpid':eoa.hpid, \
    'typ':eoa.typ, \
    'runid':ema.info.runid, \
    'ofile':ofile, \
    }, format='4')
  ema.ofile_list.append(ofile)
  return

def writetxt_eoa(eoa):
  if options.verbose >= 2:
    print('writetxt_eoa: hpid=',eoa.hpid,'nobs=',eoa.nobs)

  ofile = str.format("ema-{0:s}-{1:04d}-eoa.txt",ema.info.runid,eoa.hpid)
  if options.verbose >= 2:
    print('writetxt_eoa: ',ema.odir + '/' + ofile)

  try:
    ofp = open(ema.odir + '/' + ofile,'wt')
  except:
    print('writetxt_eoa: cannot open output file',ofile)
    sys.exit(1)

  print("# ofile = {0:s}".format(ofile),file=ofp)
  print("# runid = {0:s}".format(ema.info.runid),file=ofp)
  print("# hpid = {0:d}".format(eoa.hpid),file=ofp)
  print("# nobs = {0:d}".format(eoa.nobs),file=ofp)
  print("# nbytes = {0:d}".format(eoa.nbytes),file=ofp)
  print("# typ = {0}".format  (eoa.typ),file=ofp)
  print("# uxt = {0} = {1}".format(eoa.uxt,uxt2str(eoa.uxt)),file=ofp)
  print("# vars = P,UXT",file=ofp)
  print("#DATA#",file=ofp)

  for i in range(0,eoa.nobs):
    print("{0:.2f},".format(eoa.P[i]),file=ofp,end="")
    print("{0}".format(eoa.UXT[i]),file=ofp)

  print("#EOD#",file=ofp)
  ofp.close()
  return

def decode_pts(buf,ctd):

  ctd.typ = struct.unpack('>4s',buf[0:4])[0]
  if ctd.typ != 'CTDi' and ctd.typ != 'HOLa':
    print('Error: decode_pts: only coded for "CTDi" or "HOLa", typ=',repr(ctd.typ))
    sys.exit(1)

  ctd.uxt  = struct.unpack('<I',buf[4:8])[0]  # ctdtime in ema2mat.c
  ctd.hpid = struct.unpack('<H',buf[8:10])[0]      # ctdhpid in ema2mat.c
  ctd.nctd = struct.unpack('<H',buf[10:12])[0]
  ctd.nobs = struct.unpack('<H',buf[12:14])[0]     # nout_ctd in ema2mat.c
  ctd.nbytes =  14 + ctd.nctd
  if options.verbose:
    print(ctd.typ,'uxt=',uxt2str(ctd.uxt),'hpid=', ctd.hpid, 'nobs=',ctd.nobs, 'nbytes=',ctd.nbytes)

  nbpo = 12
  if ctd.nobs * nbpo != ctd.nctd:
    print('Error: decode_pts: nobs & nctd do not agree')
    sys.exit(1)

  ctd.P   = np.empty(ctd.nobs,dtype=np.double)
  ctd.pc  = np.empty(ctd.nobs,dtype=np.long)
  ctd.T   = np.empty(ctd.nobs,dtype=np.double)
  ctd.S   = np.empty(ctd.nobs,dtype=np.double)
  ctd.UXT = np.empty(ctd.nobs,dtype=np.long)

  c0 = 1.0 / 1024.0
  c1 = -8192.0

  ib = 14
  for i in range(0,ctd.nobs):
    P, T, S, UXT = struct.unpack('<IHHi',buf[ib:ib+nbpo])
    ib += nbpo
    ctd.pc[i] = (P >> 24) & 0xFF
    ctd.P[i]  = (P & 0xFFFFFF) * c0 + c1
    ctd.T[i] = T * 0.0009765625 - 4.096
    ctd.S[i] = S * 0.0009765625 - 4.096
    ctd.UXT[i] = UXT

  if ib != ctd.nbytes:
    print('Error: decode_pts: ib & nbytes do not agree')
    sys.exit(1)

  return ctd.nbytes, ctd.hpid

def writemat_ctd(ctd):
  writemat_pts(ctd,'ctd')
def writemat_hol(hol):
  writemat_pts(hol,'hol')

def writemat_pts(ctd,which):
  if which != 'ctd' and which != 'hol':
    print('Error: writemat_pts must have which == "ctd" or "hol"')
    sys.exit(1)
  if options.verbose >= 2:
    print('writemat_pts: hpid=',ctd.hpid,'nobs=',ctd.nobs,'which=',which)
  ofile = str.format("ema-{0:s}-{1:04d}-{2:s}.mat",ema.info.runid,ctd.hpid,which)
  if options.verbose >= 2:
    print('writemat_pts: ',ema.odir + '/' + ofile)
  sio.savemat(ema.odir + '/' + ofile, {\
    'P':ctd.P, \
    'T':ctd.T, \
    'S':ctd.S, \
    'UXT':ctd.UXT, \
    'pc':ctd.pc, \
    'uxt':ctd.uxt, \
    'nobs':ctd.nobs, \
    'nbytes':ctd.nbytes, \
    'pc':ctd.pc, \
    'hpid':ctd.hpid, \
    'typ':ctd.typ, \
    'runid':ema.info.runid, \
    'which':which, \
    'ofile':ofile, \
    }, format='4')
  ema.ofile_list.append(ofile)

def writetxt_ctd(ctd):
  writetxt_pts(ctd,'ctd')
def writetxt_hol(hol):
  writetxt_pts(hol,'hol')

def writetxt_pts(ctd,which):
  if which != 'ctd' and which != 'hol':
    print('Error: writetxt_pts must have which == "ctd" or "hol"')
    sys.exit(1)
  if options.verbose >= 2:
    print('writetxt_pts: hpid=',ctd.hpid,'nobs=',ctd.nobs,'which=',which)

  ofile = str.format("ema-{0:s}-{1:04d}-{2:s}.txt",ema.info.runid,ctd.hpid,which)
  if options.verbose >= 2:
    print('writetxt_pts: ',ema.odir + '/' + ofile)

  try:
    ofp = open(ema.odir + '/' + ofile,'wt')
  except:
    print('writetxt_pts: cannot open output file',ofile)
    sys.exit(1)

  print("# ofile = {0:s}".format(ofile),file=ofp)
  print("# runid = {0:s}".format(ema.info.runid),file=ofp)
  print("# hpid = {0:d}".format(ctd.hpid),file=ofp)
  print("# nobs = {0:d}".format(ctd.nobs),file=ofp)
  print("# nbytes = {0:d}".format(ctd.nbytes),file=ofp)
  print("# typ = {0}".format(ctd.typ),file=ofp)
  print("# uxt = {0} = {1}".format(ctd.uxt,uxt2str(ctd.uxt)),file=ofp)
# print("# pcmin =",np.min(ctd.pc),file=ofp)
# print("# pcmax =",np.max(ctd.pc),file=ofp)
  print("# vars = P,T,S,pc,UXT",file=ofp)
  print("#DATA#",file=ofp)

  for i in range(0,ctd.nobs):
    print("{0:.2f},".format(ctd.P[i]),file=ofp,end="")
    print("{0:.3f},".format(ctd.T[i]),file=ofp,end="")
    print("{0:.3f},".format(ctd.S[i]),file=ofp,end="")
    print("{0},".format(ctd.pc[i]),file=ofp,end="")
    print("{0}".format(ctd.UXT[i]),file=ofp)

  print("#EOD#",file=ofp)
  ofp.close()

def decode_flb(buf,flb):
  flb.typ = struct.unpack(">4s",buf[0:4])[0]
  flb.uxt  = struct.unpack("<I",buf[4:8])[0]
  flb.hpid = struct.unpack("<H",buf[8:10])[0]
  flb.nflb = struct.unpack("<H",buf[10:12])[0]
  flb.nobs = struct.unpack("<H",buf[12:14])[0]
  if options.verbose:
    print('decode_flb: uxt=',uxt2str(flb.uxt),'nobs=',flb.nobs)

  if flb.typ != 'FLBe':
    print('unknown flb.typ=',flb.typ)
    sys.exit(1)

  nbpo = 6
  if flb.nobs * nbpo != flb.nflb:
    print("Error: decode_flb nobs doesn't match nflb")
    sys.exit(1)

  flb.nbytes = 14 + flb.nflb

  flb.FSig   = np.empty(flb.nobs,dtype=np.long)
  flb.BSig   = np.empty(flb.nobs,dtype=np.long)
  flb.TSig   = np.empty(flb.nobs,dtype=np.long)
  flb.CtdObsIndex = np.empty(flb.nobs,dtype=np.long)

  ib = 14
  for i in range(0,flb.nobs):
    E0, E1, E2, E3, COI = struct.unpack('<BBBBH',buf[ib:ib+nbpo])
    ib += nbpo
    flb.FSig[i] = (E0<<4) | ((E1>>4) & 0x0F)
    flb.BSig[i] = ((E1 & 0x0F)<<8) | E2
    if E3 == 0x80 or E3 == 0xFF:
      TSig = -1
    elif E3 == 0x7F:
      TSig = 0xFFF
    elif E3 == 0x81:
      TSig = 0
    else:
      if E3 > 0x80:
        TSig = E3 - 0x100
      else:
        TSig = E3
      TSig += 0x200
    flb.TSig[i] = TSig
    flb.CtdObsIndex[i] = COI
  return flb.nbytes, flb.hpid

def writemat_flb(flb):
  if options.verbose >= 2:
    print('writemat_flb: hpid=',flb.hpid,'nobs=',flb.nobs)
  ofile = str.format("ema-{0:s}-{1:04d}-flb.mat",ema.info.runid,flb.hpid)
  if options.verbose >= 2:
    print('writemat_flb: ',ema.odir + '/' + ofile)
  sio.savemat(ema.odir + '/' + ofile, {\
    'uxt':flb.uxt, \
    'hpid':flb.hpid, \
    'typ':flb.typ, \
    'nobs':flb.nobs, \
    'nbytes':flb.nbytes, \
    'runid':ema.info.runid, \
    'FSig':flb.FSig, \
    'BSig':flb.BSig, \
    'TSig':flb.TSig, \
    'CtdObsIndex':flb.CtdObsIndex, \
  }, format='4')
  ema.ofile_list.append(ofile)

def writetxt_flb(flb):
  if options.verbose >= 2:
    print('writetxt_flb: hpid=',flb.hpid,'nobs=',flb.nobs)

  ofile = str.format("ema-{0:s}-{1:04d}-flb.txt",ema.info.runid,flb.hpid)
  if options.verbose >= 2:
    print('writetxt_flb: ',ema.odir + '/' + ofile)

  try:
    ofp = open(ema.odir + '/' + ofile,'wt')
  except:
    print('writetxt_flb: cannot open output file',ofile)
    sys.exit(1)

  print("# ofile = {0:s}".format(ofile),file=ofp)
  print("# runid = {0:s}".format(ema.info.runid),file=ofp)
  print("# hpid = {0:d}".format(flb.hpid),file=ofp)
  print("# nobs = {0:d}".format(flb.nobs),file=ofp)
  print("# nbytes = {0:d}".format(flb.nbytes),file=ofp)
  print("# typ = {0}".format(flb.typ),file=ofp)
  print("# uxt = {0} = {1}".format(flb.uxt,uxt2str(flb.uxt)),file=ofp)
  print("# vars = FSig,BSig,TSig,CtdObsIndex",file=ofp)
  print("#DATA#",file=ofp)

  for i in range(0,flb.nobs):
    print("{0},".format(flb.FSig[i]),file=ofp,end="")
    print("{0},".format(flb.BSig[i]),file=ofp,end="")
    print("{0},".format(flb.TSig[i]),file=ofp,end="")
    print("{0}".format(flb.CtdObsIndex[i]),file=ofp)

  print("#EOD#",file=ofp)
  ofp.close()

def decode_opt(buf,opt):
  opt.typ = struct.unpack(">4s",buf[0:4])[0]
  opt.uxt  = struct.unpack("<I",buf[4:8])[0]
  opt.hpid = struct.unpack("<H",buf[8:10])[0]
  opt.nopt = struct.unpack("<H",buf[10:12])[0]
  opt.nobs = struct.unpack("<H",buf[12:14])[0]
  if options.verbose:
    print('decode_opt: uxt=',uxt2str(opt.uxt),'nobs=',opt.nobs)

  if opt.typ != 'OPTa':
    print('unknown opt.typ=',opt.typ)
    sys.exit(1)

  nbpo = 14
  if opt.nobs * nbpo != opt.nopt:
    print("Error: decode_opt: nobs * nbpo doesn't match nopt")
    sys.exit(1)

  opt.nbytes = 14 + opt.nopt

  opt.TempDegC    = np.empty(opt.nobs,dtype=np.float)
  opt.Tphase      = np.empty(opt.nobs,dtype=np.float)
  opt.Rphase      = np.empty(opt.nobs,dtype=np.float)
  opt.CtdObsIndex = np.empty(opt.nobs,dtype=np.long)

  ib = 14
  for i in range(0,opt.nobs):
    f1, f2, f3, H4 = struct.unpack('<fffH',buf[ib:ib+nbpo])
    ib += nbpo
    opt.TempDegC[i]    = f1
    opt.Tphase[i]      = f2
    opt.Rphase[i]      = f3
    opt.CtdObsIndex[i] = H4
  return opt.nbytes, opt.hpid

def writemat_opt(opt):
  if options.verbose >= 2:
    print('writemat_opt: hpid=',opt.hpid,'nobs=',opt.nobs)
  ofile = str.format("ema-{0:s}-{1:04d}-opt.mat",ema.info.runid,opt.hpid)
  if options.verbose >= 2:
    print('writemat_opt: ',ema.odir + '/' + ofile)
  sio.savemat(ema.odir + '/' + ofile, {\
    'uxt':opt.uxt, \
    'hpid':opt.hpid, \
    'typ':opt.typ, \
    'runid':ema.info.runid, \
    'TempDegC':opt.TempDegC, \
    'Tphase':opt.Tphase, \
    'Rphase':opt.Rphase, \
    'CtdObsIndex':opt.CtdObsIndex, \
  }, format='4')
  ema.ofile_list.append(ofile)

def writetxt_opt(opt):
  if options.verbose >= 2:
    print('writetxt_opt: hpid=',opt.hpid,'nobs=',opt.nobs)

  ofile = str.format("ema-{0:s}-{1:04d}-opt.txt",ema.info.runid,opt.hpid)
  if options.verbose >= 2:
    print('writetxt_opt: ',ema.odir + '/' + ofile)

  try:
    ofp = open(ema.odir + '/' + ofile,'wt')
  except:
    print('writetxt_opt: cannot open output file',ofile)
    sys.exit(1)

  print("# ofile = {0:s}".format(ofile),file=ofp)
  print("# runid = {0:s}".format(ema.info.runid),file=ofp)
  print("# hpid = {0:d}".format(opt.hpid),file=ofp)
  print("# nobs = {0:d}".format(opt.nobs),file=ofp)
  print("# nbytes = {0:d}".format(opt.nbytes),file=ofp)
  print("# typ = {0}".format(opt.typ),file=ofp)
  print("# uxt = {0} = {1}".format(opt.uxt,uxt2str(opt.uxt)),file=ofp)
  print("# vars = TempDegC,Tphase,Rphase,CtdObsIndex",file=ofp)
  print("#DATA#",file=ofp)

  for i in range(0,opt.nobs):
    print("{0},".format(opt.TempDegC[i]),file=ofp,end="")
    print("{0},".format(opt.Tphase[i]),file=ofp,end="")
    print("{0},".format(opt.Rphase[i]),file=ofp,end="")
    print("{0}".format(opt.CtdObsIndex[i]),file=ofp)

  print("#EOD#",file=ofp)
  ofp.close()



def decode_scp(sbuf, scp):
  scp.typ = struct.unpack(">4s",sbuf[0:4])[0]
  scp.uxt  = struct.unpack("<I",sbuf[4:8])[0]
  scp.hpid = struct.unpack("<H",sbuf[8:10])[0]
  scp.nscp = struct.unpack("<H",sbuf[10:12])[0]
  scp.nobs = struct.unpack("<H",sbuf[12:14])[0]

  if scp.typ == "SCPa" or scp.typ == "SCPb":
    scp.nbytes = 14 + scp.nscp
  else:
    scp.nbytes = 14 + scp.nscp + 44

  if options.verbose:
    print(scp.typ,'uxt=',uxt2str(scp.uxt),'hpid=',scp.hpid,'nbytes=',scp.nbytes)

  if scp.nobs * 8 != scp.nscp:
    print("Error: decode_scp nobs doesn't match nscp")
    sys.exit(1)

  scp.P           = np.empty(scp.nobs,dtype=np.double)
  scp.T           = np.empty(scp.nobs,dtype=np.double)
  scp.S           = np.empty(scp.nobs,dtype=np.double)
  scp.NSampPerBin = np.empty(scp.nobs,dtype=np.double)

  ib = 14

  if scp.typ == "SCPa":
    for i in range(0,scp.nobs):
      x = struct.unpack("<I",sbuf[ib:ib+4])[0]; ib += 4
      scp.P[i] = (x & 0xffffff) * 0.0009765625 - 8192.0
      scp.NSampPerBin[i] = (x >> 24) & 0xff
      scp.T[i] = struct.unpack("<H",sbuf[ib:ib+2])[0] * .0009765625 - 4.096; ib += 2
      scp.S[i] = struct.unpack("<H",sbuf[ib:ib+2])[0] * .0009765625 - 4.096; ib += 2
  else:
    for i in range(0,scp.nobs):
      xN = struct.unpack("<H",sbuf[ib:ib+2])[0]; ib += 2
      xP = struct.unpack("<H",sbuf[ib:ib+2])[0]; ib += 2
      xT = struct.unpack("<H",sbuf[ib:ib+2])[0]; ib += 2
      xS = struct.unpack("<H",sbuf[ib:ib+2])[0]; ib += 2

      if xP > 32767:
        xP -= 65536
      if xT > 65536-4096:
        xT -= 65536
      if xS >  65536-4096:
        xS -= 65536

      scp.NSampPerBin[i] = xN
      scp.P[i] = xP * 0.1
      scp.T[i] = xT * 0.001
      scp.S[i] = xS * 0.001

  if scp.typ == "SCPc":
    scp.maxPress    = struct.unpack("<f",sbuf[ib:ib+4])[0]; ib += 4
    scp.nbins       = struct.unpack("<l",sbuf[ib:ib+4])[0]; ib += 4
    scp.navg        = struct.unpack("<l",sbuf[ib:ib+4])[0]; ib += 4
    scp.nrd         = struct.unpack("<l",sbuf[ib:ib+4])[0]; ib += 4
    scp.nbad        = struct.unpack("<l",sbuf[ib:ib+4])[0]; ib += 4
    scp.nshort      = struct.unpack("<l",sbuf[ib:ib+4])[0]; ib += 4
    scp.nother      = struct.unpack("<l",sbuf[ib:ib+4])[0]; ib += 4
    scp.elapsedsecs = struct.unpack("<l",sbuf[ib:ib+4])[0]; ib += 4
    scp.npts        = struct.unpack("<l",sbuf[ib:ib+4])[0]; ib += 4
    scp.nerr        = struct.unpack("<l",sbuf[ib:ib+4])[0]; ib += 4
    scp.ncount      = struct.unpack("<l",sbuf[ib:ib+4])[0]; ib += 4

  j = np.where(scp.NSampPerBin == 0)[0]
  scp.P[j] = np.nan
  scp.T[j] = np.nan
  scp.S[j] = np.nan
  
  return scp.nbytes, scp.hpid

def writemat_scp(scp):
  if scp.typ != "SCPc":
    print('writemat_scp not coded yet for typ=',scp.typ,'skipped')
    return

  if options.verbose >= 2:
    print('writemat_scp: hpid=',scp.hpid,'nobs=',scp.nobs)

  ofile = str.format("ema-{0:s}-{1:04d}-scp.mat",ema.info.runid,scp.hpid)
  if options.verbose >= 2:
    print('writemat_scp: ',ema.odir + '/' + ofile)
  sio.savemat(ema.odir + '/' + ofile, {\
    'UXT':scp.uxt, \
    'hpid':scp.hpid, \
    'typ':scp.typ, \
    'runid':ema.info.runid, \
    'P':scp.P, \
    'T':scp.T, \
    'S':scp.S, \
    'NSampPerBin':scp.NSampPerBin, \
    'maxPress':scp.maxPress, \
    'nbins':scp.nbins, \
    'navg':scp.navg, \
    'nrd':scp.nrd, \
    'nbad':scp.nbad, \
    'nshort':scp.nshort, \
    'nother':scp.nother, \
    'elapsedsecs':scp.elapsedsecs, \
    'npts':scp.npts, \
    'nerr':scp.nerr, \
    'ncount':scp.ncount, \
    },format='4')
  ema.ofile_list.append(ofile)

def writetxt_scp(scp):
  if scp.typ != "SCPc":
    print('writetxt_scp not coded yet for typ=',scp.typ,'skipped')
    return

  if options.verbose >= 2:
    print('writetxt_scp: hpid=',scp.hpid,'nobs=',scp.nobs)


  ofile = str.format("ema-{0:s}-{1:04d}-scp.txt",ema.info.runid,scp.hpid)
  if options.verbose >= 2:
    print('writetxt_scp: ',ema.odir + '/' + ofile)

  try:
    ofp = open(ema.odir + '/' + ofile,'wt')
  except:
    print('writetxt_scp: cannot open output file',ofile)
    sys.exit(1)

  print("# ofile = {0:s}".format(ofile),file=ofp)
  print("# runid = {0:s}".format(ema.info.runid),file=ofp)
  print("# hpid = {0:d}".format(scp.hpid),file=ofp)
  print("# nobs = {0:d}".format(scp.nobs),file=ofp)
  print("# nbytes = {0:d}".format(scp.nbytes),file=ofp)
  print("# typ = {0}".format(scp.typ),file=ofp)
  print("# nbins = {0}".format(scp.nbins),file=ofp)
  print("# navg = {0}".format(scp.navg),file=ofp)
  print("# nrd = {0}".format(scp.nrd),file=ofp)
  print("# nbad = {0}".format(scp.nbad),file=ofp)
  print("# nshort = {0}".format(scp.nshort),file=ofp)
  print("# nother = {0}".format(scp.nother),file=ofp)
  print("# elapsedsecs = {0}".format(scp.elapsedsecs),file=ofp)
  print("# npts = {0}".format(scp.npts),file=ofp)
  print("# nerr = {0}".format(scp.nerr),file=ofp)
  print("# ncount = {0}".format(scp.ncount),file=ofp)
  print("# vars = P,T,S,NSampPerBin",file=ofp)
  print("#DATA#",file=ofp)

  for i in range(0,scp.nobs):
    print("{0},".format(scp.P[i]),file=ofp,end="")
    print("{0},".format(scp.T[i]),file=ofp,end="")
    print("{0},".format(scp.S[i]),file=ofp,end="")
    print("{0}".format(scp.NSampPerBin[i]),file=ofp)

  print("#EOD#",file=ofp)
  ofp.close()

def decode_tmp(buf, tmp):
  tmp.typ = struct.unpack(">4s",buf[0:4])[0]
  if tmp.typ != 'TMPa':
    printf("Error: decode_tmp: currently only coded for TMPa, typ=",tmp.typ)
    sys.exit(1)

  tmp.uxt  = struct.unpack("<I",buf[4:8])[0]
  tmp.hpid = struct.unpack("<H",buf[8:10])[0]
  tmp.nbytes = struct.unpack("<H",buf[10:12])[0] + 12
  if options.verbose:
    print(tmp.typ,'uxt=',uxt2str(tmp.uxt),'hpid=',tmp.hpid,'nbytes=',tmp.nbytes)

  return tmp.nbytes, tmp.hpid


def writemat_tmp(tmp): # fixme
  if options.verbose:
    print('writemat_tmp: not coded yet')

def writetxt_tmp(tmp): # fixme
  if options.verbose:
    print('writetxt_tmp: not coded yet')

def decode_efp(buf, efp):

  efp.typ = struct.unpack(">4s",buf[0:4])[0]
  if efp.typ != 'EFPh':
    printf("Error: decode_efp: currently only coded for EFPh, typ=",efp.typ)
    sys.exit(1)

  efp.uxt  = struct.unpack("<I",buf[4:8])[0]
  efp.hpid = struct.unpack("<H",buf[8:10])[0]
  efp.nobs = struct.unpack("<H",buf[10:12])[0]
  efp.nbytes = 12 + 4 + efp.nobs * 48
  if options.verbose:
    print(efp.typ,'uxt=',uxt2str(efp.uxt),'hpid=',efp.hpid,'nbytes=',efp.nbytes)

  efp.EfCoefFactor =  struct.unpack("<f",buf[12:16])[0]
  EfCoefMult = 1.0 / efp.EfCoefFactor

  fmtI = str.format("<{0:d}I",efp.nobs)
  fmti = str.format("<{0:d}i",efp.nobs)
  fmtH = str.format("<{0:d}H",efp.nobs)
  fmth = str.format("<{0:d}h",efp.nobs)
  nI = efp.nobs * 4
  nH = efp.nobs * 2
  ib = 16

  # scale factors convert back to floating-point ADC values in firmware

  efp.UXT = np.array(struct.unpack(fmti,buf[ib:ib+nI]))
  ib += nI

  efp.ROTP_HX = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.002
  ib += nH
  efp.ROTP_HY = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.002
  ib += nH

  efp.PISTON_C0 = np.array(struct.unpack(fmth,buf[ib:ib+nH])) * 0.01
  ib += nH

  efp.E1MEAN4 = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 250.0
  ib += nH
  efp.E1SDEV4 = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * EfCoefMult
  ib += nH
  efp.E1COEF40 = np.array(struct.unpack(fmth,buf[ib:ib+nH])) * EfCoefMult
  ib += nH
  efp.E1COEF41 = np.array(struct.unpack(fmth,buf[ib:ib+nH])) * EfCoefMult
  ib += nH

  efp.E2MEAN4 = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 250.0
  ib += nH
  efp.E2SDEV4 = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * EfCoefMult
  ib += nH
  efp.E2COEF40 = np.array(struct.unpack(fmth,buf[ib:ib+nH])) * EfCoefMult
  ib += nH
  efp.E2COEF41 = np.array(struct.unpack(fmth,buf[ib:ib+nH])) * EfCoefMult
  ib += nH


  efp.HX_SDEV = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.05
  ib += nH
  efp.HY_SDEV = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.05
  ib += nH

  efp.BT_MEAN = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.05
  ib += nH

  efp.HZ_MEAN = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.05
  ib += nH

  efp.AX_MEAN = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.05
  ib += nH
  efp.AX_SDEV = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.05
  ib += nH

  efp.AY_MEAN = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.05
  ib += nH
  efp.AY_SDEV = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.05
  ib += nH

  efp.AZ_MEAN = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.05
  ib += nH

  efp.HX_MEAN = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.05
  ib += nH
  efp.HY_MEAN = np.array(struct.unpack(fmtH,buf[ib:ib+nH])) * 0.05
  ib += nH

  if ib != efp.nbytes:
    print('Error: decode_efp: ib=',ib,'nbytes=',nbytes)
    sys.exit(1)

  return efp.nbytes, efp.hpid

def writemat_efp(efp):
  if options.verbose >= 2:
    print('writemat_efp: hpid=',efp.hpid,'nobs=',efp.nobs)
  ofile = str.format("ema-{0:s}-{1:04d}-efp.mat",ema.info.runid,efp.hpid)
  if options.verbose >= 2:
    print('writemat_efp: ',ema.odir + '/' + ofile)
  sio.savemat(ema.odir + '/' + ofile, {\
    'hpid':     efp.hpid,      \
    'typ':      efp.typ,       \
    'runid':    ema.info.runid, \
    'ROTP_HX':  efp.ROTP_HX,   \
    'ROTP_HY':  efp.ROTP_HY,   \
    'PISTON_C0':efp.PISTON_C0, \
    'E1MEAN4':  efp.E1MEAN4,   \
    'E1SDEV4':  efp.E1SDEV4,   \
    'E1COEF40': efp.E1COEF40,  \
    'E1COEF41': efp.E1COEF41,  \
    'E2MEAN4':  efp.E2MEAN4,   \
    'E2SDEV4':  efp.E2SDEV4,   \
    'E2COEF40': efp.E2COEF40,  \
    'E2COEF41': efp.E2COEF41,  \
    'HX_SDEV':  efp.HX_SDEV,   \
    'HY_SDEV':  efp.HY_SDEV,   \
    'BT_MEAN':  efp.BT_MEAN,   \
    'HZ_MEAN':  efp.HZ_MEAN,   \
    'AX_MEAN':  efp.AX_MEAN,   \
    'AX_SDEV':  efp.AX_SDEV,   \
    'AY_MEAN':  efp.AY_MEAN,   \
    'AY_SDEV':  efp.AY_SDEV,   \
    'AZ_MEAN':  efp.AZ_MEAN,   \
    'HX_MEAN':  efp.HX_MEAN,   \
    'HY_MEAN':  efp.HY_MEAN,   \
    'UXT':      efp.UXT       \
    }, format='4')
  ema.ofile_list.append(ofile)

def writetxt_efp(efp):
  if options.verbose >= 2:
    print('writetxt_efp: hpid=',efp.hpid,'nobs=',efp.nobs)

  ofile = str.format("ema-{0:s}-{1:04d}-efp.txt",ema.info.runid,efp.hpid)
  if options.verbose >= 2:
    print('writetxt_efp: ',ema.odir + '/' + ofile)

  try:
    ofp = open(ema.odir + '/' + ofile,'wt')
  except:
    print('writetxt_efp: cannot open output file',ofile)
    sys.exit(1)

  print("# ofile = {0:s}".format(ofile),file=ofp)
  print("# runid = {0:s}".format(ema.info.runid),file=ofp)
  print("# hpid = {0:d}".format(efp.hpid),file=ofp)
  print("# nobs = {0:d}".format(efp.nobs),file=ofp)
  print("# nbytes = {0:d}".format(efp.nbytes),file=ofp)
  print("# typ = {0}".format(efp.typ),file=ofp)

  print("# vars = ROTP_HX,ROTP_HY,PISTON_C0,E1MEAN4,E1SDEV4,E1COEF40,E1COEF41,"+\
    "E2MEAN4,E2SDEV4,E2COEF40,E2COEF41,HX_SDEV,HY_SDEV,BT_MEAN,HZ_MEAN,"+\
    "AX_MEAN,AX_SDEV,AY_MEAN,AY_SDEV,AZ_MEAN,HX_MEAN,HY_MEAN,UXT",file=ofp)
  print("#DATA#",file=ofp)

  for i in range(0,efp.nobs):
    print("{0},".format(efp.ROTP_HX[i]),file=ofp,end="")
    print("{0},".format(efp.ROTP_HY[i]),file=ofp,end="")
    print("{0},".format(efp.PISTON_C0[i]),file=ofp,end="")
    print("{0},".format(efp.E1MEAN4[i]),file=ofp,end="")
    print("{0},".format(efp.E1SDEV4[i]),file=ofp,end="")
    print("{0},".format(efp.E1COEF40[i]),file=ofp,end="")
    print("{0},".format(efp.E1COEF41[i]),file=ofp,end="")
    print("{0},".format(efp.E2MEAN4[i]),file=ofp,end="")
    print("{0},".format(efp.E2SDEV4[i]),file=ofp,end="")
    print("{0},".format(efp.E2COEF40[i]),file=ofp,end="")
    print("{0},".format(efp.E2COEF41[i]),file=ofp,end="")
    print("{0},".format(efp.HX_SDEV[i]),file=ofp,end="")
    print("{0},".format(efp.HY_SDEV[i]),file=ofp,end="")
    print("{0},".format(efp.BT_MEAN[i]),file=ofp,end="")
    print("{0},".format(efp.HZ_MEAN[i]),file=ofp,end="")
    print("{0},".format(efp.AX_MEAN[i]),file=ofp,end="")
    print("{0},".format(efp.AX_SDEV[i]),file=ofp,end="")
    print("{0},".format(efp.AY_MEAN[i]),file=ofp,end="")
    print("{0},".format(efp.AY_SDEV[i]),file=ofp,end="")
    print("{0},".format(efp.AZ_MEAN[i]),file=ofp,end="")
    print("{0},".format(efp.HX_MEAN[i]),file=ofp,end="")
    print("{0},".format(efp.HY_MEAN[i]),file=ofp,end="")
    print("{0}".format(efp.UXT[i]),file=ofp)

  print("#EOD#",file=ofp)
  ofp.close()

def decode_vitmis(mvbuf, vit, mis):
  vit.typ  = struct.unpack(">4s",mvbuf[0:4])[0]
  vit.vitvers = vit.typ[3]
  vit.versnum = ord(vit.vitvers)

  if vit.versnum < ord('e' or vit.versnum > 'w'):
    print("decode_vitmis not yet coded for typ=",vit.typ)
    sys.exit(1)

  vit.uxt  = struct.unpack("<I", mvbuf[4:8])[0]
  vit.hpid = struct.unpack("<H", mvbuf[8:10])[0]
  vit.nvit = struct.unpack("<H", mvbuf[26:28])[0]
  vit.nmis = struct.unpack("<H", mvbuf[28+vit.nvit:30+vit.nvit])[0]

  vit.nbytes = 30 + vit.nvit + vit.nmis

# decode vitals
  ib = 10
  vit.x_irid     = struct.unpack("<h", mvbuf[ib:ib+2])[0]; ib += 2
  vit.y_irid     = struct.unpack("<h", mvbuf[ib:ib+2])[0]; ib += 2
  vit.z_irid     = struct.unpack("<h", mvbuf[ib:ib+2])[0]; ib += 2
  vit.t_irid     = struct.unpack("<L", mvbuf[ib:ib+4])[0]; ib += 4
  vit.geoloc_new = struct.unpack("<h", mvbuf[ib:ib+2])[0]; ib += 2
  vit.signal_1st = struct.unpack("<h", mvbuf[ib:ib+2])[0]; ib += 2
  vit.signal_new = struct.unpack("<h", mvbuf[ib:ib+2])[0]; ib += 2
  
  # decode struct Engineering, src/control.c
  ib0 = 28
  ib = ib0
  vit.ActiveBallastAdjustments = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  vit.AirBladderPressure       = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  vit.AirPumpAmps              = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  vit.AirPumpVolts             = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  vit.BuoyancyPumpOnTime       = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.BuoyancyPumpAmps         = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  vit.BuoyancyPumpVolts        = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  vit.ParkDescentP             = struct.unpack("<7B",mvbuf[ib:ib+7]); ib += 7
  vit.ParkDescentPCnt          = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  vit.ParkPOutOfBand           = struct.unpack("<b",mvbuf[ib:ib+1])[0]; ib += 1
  ib += 1
  vit.ParkObsP                 = struct.unpack("<f",mvbuf[ib:ib+4])[0]; ib += 4
  vit.ParkObsT                 = struct.unpack("<f",mvbuf[ib:ib+4])[0]; ib += 4
  vit.ParkObsS                 = struct.unpack("<f",mvbuf[ib:ib+4])[0]; ib += 4
  vit.ParkObsDate              = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.ParkObsPiston            = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  ib += 1
  vit.QuiescentAmps            = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  vit.QuiescentVolts           = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  vit.Sbe41Amps                = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  vit.Sbe41Status              = struct.unpack("<H",mvbuf[ib:ib+2])[0]; ib += 2
  ib += 1
  vit.Sbe41Volts               = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  ib += 1
  vit.status                   = struct.unpack("<H",mvbuf[ib:ib+2])[0]; ib += 2
  vit.SurfacePistonPosition    = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  ib += 1
  vit.SurfacePressure          = struct.unpack("<f",mvbuf[ib:ib+4])[0]; ib += 4
  vit.Vacuum                   = struct.unpack("<B",mvbuf[ib:ib+1])[0]; ib += 1
  vit.YoyoFlag                 = struct.unpack("<b",mvbuf[ib:ib+1])[0]; ib += 1
  vit.UpperPressure            = struct.unpack("<f",mvbuf[ib:ib+4])[0]; ib += 4
  vit.Level2Flag               = struct.unpack("<b",mvbuf[ib:ib+1])[0]; ib += 1
  ib += 1
  vit.LowerPressure            = struct.unpack("<f",mvbuf[ib:ib+4])[0]; ib += 4
  vit.RawEfSaveFlag            = struct.unpack("<b",mvbuf[ib:ib+1])[0]; ib += 1
  ib += 1
  vit.DescentProfIsDone        = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
  vit.AscentIsDone             = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
  vit.ProfilingFlag            = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
  vit.FastProfilingFlag        = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
  vit.DateStartedDown          = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.PrfId                    = struct.unpack("<H",mvbuf[ib:ib+2])[0]; ib += 2
  vit.MissionCrcBadCount       = struct.unpack("<H",mvbuf[ib:ib+2])[0]; ib += 2
  vit.DatePreludeEnded         = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.DateNextLevel2           = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.DateCycleStarted         = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.MissionUpdateGotFile     = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
  vit.MissionUpdateChange      = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
  vit.DoGpsAfter               = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
  vit.TimeDescentProf          = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.LongHoldFlag             = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
  vit.emaR_count               = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.emaF_count               = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.errF_count               = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.nerrR_get                = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.nerrM_get                = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.nerrF_crc                = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.nerrM_crc                = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.nerr_seqno               = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.nerr_gps                 = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
  vit.imei                     = struct.unpack("<20s",mvbuf[ib:ib+20])[0]; ib += 20
  l = vit.imei.find(chr(0)); vit.imei = vit.imei[0:l]
  
  if vit.versnum >= ord('n'):
    vit.Vstuck                   = struct.unpack("<f",mvbuf[ib:ib+4])[0]; ib += 4
    vit.Nstuck                   = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2

  if vit.versnum >= ord('s') and vit.versnum <= ord('v'):
    vit.DateToStartDown          = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
    vit.DateToStopDown           = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
    vit.DateToStartUp            = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
    vit.DateToBeAtSfc            = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4
    vit.VminUse                  = struct.unpack("<f",mvbuf[ib:ib+4])[0]; ib += 4
    vit.VminUseDown1             = struct.unpack("<f",mvbuf[ib:ib+4])[0]; ib += 4
    vit.UsingPvt                 = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
    vit.WNeedDescent             = struct.unpack("<f",mvbuf[ib:ib+4])[0]; ib += 4
    vit.WNeedAscent              = struct.unpack("<f",mvbuf[ib:ib+4])[0]; ib += 4
    vit.TMicroFilesAvail         = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2

  if vit.versnum >= ord('u'):
    vit.FirmwareVersion          = struct.unpack("<L",mvbuf[ib:ib+4])[0]; ib += 4
    vit.AllStoreNum              = struct.unpack("<l",mvbuf[ib:ib+4])[0]; ib += 4

  if vit.versnum >= ord('w'):
    vit.NstuckAscent              = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
    vit.VstuckAscent              = struct.unpack("<f",mvbuf[ib:ib+4])[0]; ib += 4
    vit.IceDetected               = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
    vit.IceCount                  = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
    vit.IsWinter                  = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2
    vit.Switch2Winter             = struct.unpack("<h",mvbuf[ib:ib+2])[0]; ib += 2

  vit_ib = ib - ib0
  if vit_ib != vit.nvit:
    print('vit_ib mismatch, vit_ib=',vit_ib,'vit.nvit=',vit.nvit,'typ=',vit.typ)
    sys.exit(1)

  # decode struct MissionParams, src/control.c
  mbuf = mvbuf[30+vit.nvit:]
  ib = 0
  mis.FloatId =                     struct.unpack("<H",mbuf[ib:ib+2])[0]; ib += 2
  mis.MaxAirBladder =               struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.OkVacuumCount =               struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PistonBuoyancyNudge =         struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PistonDeepProfilePosition =   struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PistonFullExtension =         struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PistonFullRetraction =        struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PistonInitialBuoyancyNudge =  struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PistonParkPosition =          struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PistonStoragePosition =       struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PnpCycleLength =              struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PressurePark =                struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
  mis.PressureDeep =                struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimePrelude =                 struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeDescentProf =             struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeDescentPark =             struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeDescentDeep =             struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeDown =                    struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeUp =                      struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TmoAscent =                   struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.simulate_pressure =           struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.simulate_hardware =           struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PreludeRepPeriod =            struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.PreludePressureThreshold =    struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
  mis.IdFirstLevel2 =               struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
  mis.TimeYoyoOnceBeg =             struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeYoyoOnceEnd =             struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.DateCycleStarted =            struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeCycleRep =                struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeCycleYoyoBeg =            struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeCycleYoyoEnd =            struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeCycleHoldLongBeg =        struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeCycleHoldLongEnd =        struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeHoldLong =                struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeHoldShort =               struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeLevel2Rep =               struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.PrTopYoyo =                   struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
  mis.PrBotYoyo =                   struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
  mis.PrBotLevel1 =                 struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
  mis.PrBotLevel2 =                 struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
  mis.RawEfSaveRep =                struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
  mis.RawEfSendFlagProfiling =      struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.RawEfSendFlagRecovery =       struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.Vmin =                        struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
  mis.PistonInitAscentLevel1 =      struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PistonInitAscentLevel2 =      struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PistonInitDescentProf =       struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.PistonInitDescentProfFirst =  struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
  mis.DurationFastProfiling =       struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.DateForRecovery =             struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeForRecovery =             struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.RecoveryRepPeriod =           struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.RecoveryNRepConnect =         struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
  mis.RecoveryIRepConnect =         struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
  mis.TmoConnect =                  struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TmoXfrFastProfiling =         struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TmoXfrProfiling =             struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TmoXfrRecovery =              struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TmoXfrMin =                   struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.DatePreludeEnded =            struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.DateNextLevel2 =              struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.ModemType =                   struct.unpack("<1s",mbuf[ib:ib+1])[0]; ib += 1
  ib += 1 # for word alignment
  mis.ModemBaudRate =               struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.PhoneNumbers =                struct.unpack("<60s",mbuf[ib:ib+60])[0]; ib += 60
  l = mis.PhoneNumbers.find(chr(0)); mis.PhoneNumbers = mis.PhoneNumbers[0:l]
  mis.KermitPacketLength =          struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
  mis.TmoTelemetry =                struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.debuglevel =                  struct.unpack("<H",mbuf[ib:ib+2])[0]; ib += 2
  mis.logport_key =                 struct.unpack("<1s",mbuf[ib:ib+1])[0]; ib += 1
  ib += 1
  mis.logport_baud =                struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.EmaProcessNvals =             struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
  mis.EmaProcessNslide =            struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
  mis.TmoGpsUpdate =                struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TmoGpsShort =                 struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TmoGpsAfter =                 struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeGpsUpdateRep =            struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.TimeGpsGrabRep =              struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
  mis.RawSvBytesStop =              struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4

  if vit.versnum >= ord('e'):
    mis.PressureAnticipate =          struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.PressureNearSurface =         struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.SigmaThetaFollow =            struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.PressureFollowDefault =       struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.PressureFollowMin =           struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.PressureFollowMax =           struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.PistonFollowDefault =         struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    ib += 1
    mis.SalinityBallastPoint =        struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.TemperatureBallastPoint =     struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.PressureBallastPoint =        struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.PistonCountsPerCC =           struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.FloatMass =                   struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.FloatAlpha =                  struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.FloatBeta =                   struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.use_iPiston =                 struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    ib += 1
    mis.HeartBeatProf =               struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.HeartBeatHolding =            struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.TimeOutNudge =                struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.CtdSamplePrFirst =            struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.CtdSampleDelPr1 =             struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.CtdSampleDelPr2 =             struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.CtdSampleDelPr3 =             struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.CtdSampleDelPr4 =             struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.CtdSampleN1 =                 struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.CtdSampleN2 =                 struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.CtdSampleN3 =                 struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.CtdSampleN4 =                 struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.SimulationDpdtCoef =          struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4

  if vit.versnum >= ord('g'):
    mis.PressureMaxRecordRaw =        struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4

  if vit.versnum >= ord('f'):
    mis.DescentCtdScanType =          struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.SendOnlyGps =                 struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.SendCurrentGpsFirst =         struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.KermitBps =                   struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.KermitRtt =                   struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.GpsAlmanacOkAtLaunch =        struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.FirstTwoProfsSpecial =        struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2

  if vit.versnum >= ord('h'):
    mis.ModeHoldShort =               struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.ModeHoldLong =                struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.IridiumNRep =                 struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.IridiumIRep =                 struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.OpenAirValveAfter =           struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2

  if vit.versnum >= ord('i'):
    mis.TimePistonIfNoObs =           struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.PrTopHoldLong =               struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.PrBotHoldLong =               struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.PrTopHoldShort =              struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.PrBotHoldShort =              struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4

  if vit.versnum >= ord('j'):
    mis.TimeDescentProfHoldLong =     struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.TimeDescentProfHoldShort =    struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4

  if vit.versnum >= ord('k'):
    mis.PistonInitAscentHoldLong =    struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.PistonInitAscentHoldShort =   struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1

  if vit.versnum >= ord('n'):
    mis.VstuckThreshold =             struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.NstuckThreshold =             struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2

  if vit.versnum >= ord('o'):
    mis.SimulationPrBot =             struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4

  if vit.versnum >= ord('p'):
    mis.FlbbMode =                    struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.FlbbMaxPr =                   struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4

  if vit.versnum >= ord('q'):
    mis.LoginName =                   struct.unpack("<20s",mbuf[ib:ib+20])[0]; ib += 20
    l = mis.LoginName.find(chr(0)); mis.LoginName = mis.LoginName[0:l]
    mis.Password =                    struct.unpack("<20s",mbuf[ib:ib+20])[0]; ib += 20
    l = mis.Password.find(chr(0)); mis.Password = mis.Password[0:l]
    mis.EfCoefFactor =                struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.KermitWindowSlots =           struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2

  if vit.versnum >= ord('r'):
    mis.HeartBeatPark =               struct.unpack("<L",mbuf[ib:ib+4])[0]; ib += 4

  if vit.versnum >= ord('s'):
    mis.ConsoleBaudRate =             struct.unpack("<L",mbuf[ib:ib+4])[0]; ib += 4

  if vit.versnum >= ord('s') and vit.versnum <= ord('v'):
    mis.PvtDateRef =                  struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.PvtTimeRep =                  struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.PvtTimeAllowStartDown =       struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.PvtTimeAllowStartUp =         struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.PvtWaitAtSurface =            struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.Pvt_alpha =                   struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.Pvt_b0 =                      struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.Pvt_pmin_offset =             struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.PvtPistonDiffMax =            struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2

  if vit.versnum >= ord('s'):
    mis.CtdType =                     struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.CtdPmin =                     struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4

  if vit.versnum >= ord('s') and vit.versnum <= ord('v'):
    ib += 204 # skip TM_ (Tmicro) stuff

  if vit.versnum >= ord('t'):
    mis.OptodeMode =                  struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.OptodeMaxPr =                 struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4

  if vit.versnum >= ord('w'):
    mis.PrEoaNVals =                  struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.PrEoaDSecs =                  struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.IcePressureThreshold =        struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.DateIcePhone =                struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.IceCountMax =                 struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2

    mis.PtsHoldNRep =                  struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2

    mis.NstuckAscentThreshold =        struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.PstuckAscentThreshold =        struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.PstuckDescentThreshold =       struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4

    mis.WinterDoyBeg =        struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.WinterDoyEnd =        struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2

    mis.SummerTimeCycleRep =         struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerTimeCycleYoyoBeg =     struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerTimeCycleYoyoEnd =     struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerTimeCycleHoldLongBeg = struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerTimeCycleHoldLongEnd = struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerTimeHoldLong  =        struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerTimeHoldShort =        struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerTimeLevel2Rep =        struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4

    mis.SummerPrTopYoyo =      struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerPrBotYoyo =      struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerPrBotLevel1 =    struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerPrBotLevel2 =    struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerPrTopHoldLong =  struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerPrBotHoldLong =  struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerPrTopHoldShort = struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.SummerPrBotHoldShort = struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4

    mis.SummerModeHoldLong              = struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.SummerModeHoldShort             = struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.SummerPistonInitAscentLevel1    = struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.SummerPistonInitAscentLevel2    = struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.SummerPistonInitAscentHoldLong  = struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.SummerPistonInitAscentHoldShort = struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.SummerPistonInitDescentProf     = struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.SummerPistonFollowDefault       = struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.SummerPressureFollowDefault     = struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4

    
    mis.WinterTimeCycleRep =         struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterTimeCycleYoyoBeg =     struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterTimeCycleYoyoEnd =     struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterTimeCycleHoldLongBeg = struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterTimeCycleHoldLongEnd = struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterTimeHoldLong  =        struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterTimeHoldShort =        struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterTimeLevel2Rep =        struct.unpack("<l",mbuf[ib:ib+4])[0]; ib += 4

    mis.WinterPrTopYoyo =      struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterPrBotYoyo =      struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterPrBotLevel1 =    struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterPrBotLevel2 =    struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterPrTopHoldLong =  struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterPrBotHoldLong =  struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterPrTopHoldShort = struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4
    mis.WinterPrBotHoldShort = struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4

    mis.WinterModeHoldLong              = struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.WinterModeHoldShort             = struct.unpack("<h",mbuf[ib:ib+2])[0]; ib += 2
    mis.WinterPistonInitAscentLevel1    = struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.WinterPistonInitAscentLevel2    = struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.WinterPistonInitAscentHoldLong  = struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.WinterPistonInitAscentHoldShort = struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.WinterPistonInitDescentProf     = struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.WinterPistonFollowDefault       = struct.unpack("<B",mbuf[ib:ib+1])[0]; ib += 1
    mis.WinterPressureFollowDefault     = struct.unpack("<f",mbuf[ib:ib+4])[0]; ib += 4

  mis.crc =                         struct.unpack("<H",mbuf[ib:ib+2])[0]; ib += 2

  mis_ib = ib

  if mis_ib != vit.nmis:
    print('mis_ib mismatch, mis_ib=',mis_ib,'vit.nmis=',vit.nmis)

    sys.exit(1)

  if options.verbose:
    print(vit.typ, 'uxt=',uxt2str(vit.uxt), 'hpid=',vit.hpid,
      'nvit=',vit.nvit,  'nmis=',vit.nmis,'nbytes=',vit.nbytes)

  vit.FloatId = mis.FloatId

  mis.typ  = vit.typ
  mis.versnum = vit.versnum
  mis.vitvers = vit.vitvers
  mis.uxt  = vit.uxt 
  mis.hpid = vit.hpid
  mis.nvit = vit.nvit
  mis.nmis = vit.nmis
  mis.nbytes = vit.nbytes

  return vit.nbytes, vit.hpid

def mkdict_vit(ema):
  vit = ema.vit
  vit.dict = { \
    'DateVit':vit.uxt, \
    'hpid':vit.hpid, \
    'typ':vit.typ, \
    "vitvers":vit.vitvers, \
    'runid':ema.info.runid, \
    "FloatId":vit.FloatId, \
    "nbytes":vit.nvit, \
    "x_irid":vit.x_irid, \
    "y_irid":vit.y_irid, \
    "z_irid":vit.z_irid, \
    "t_irid":vit.t_irid, \
    "geoloc_new":vit.geoloc_new, \
    "signal":vit.signal_1st, \
    "signal_new":vit.signal_new, \
    "ActiveBallastAdjustments":vit.ActiveBallastAdjustments, \
    "AirBladderPressure":vit.AirBladderPressure, \
    "AirPumpAmps":vit.AirPumpAmps, \
    "AirPumpVolts":vit.AirPumpVolts, \
    "BuoyancyPumpOnTime":vit.BuoyancyPumpOnTime, \
    "BuoyancyPumpAmps":vit.BuoyancyPumpAmps, \
    "BuoyancyPumpVolts":vit.BuoyancyPumpVolts, \
    "ParkDescentP":vit.ParkDescentP, \
    "ParkDescentPCnt":vit.ParkDescentPCnt, \
    "ParkPOutOfBand":vit.ParkPOutOfBand, \
    "ParkObsP":vit.ParkObsP , \
    "ParkObsT":vit.ParkObsT , \
    "ParkObsS":vit.ParkObsS , \
    "ParkObsDate":vit.ParkObsDate , \
    "ParkObsPiston":vit.ParkObsPiston , \
    "QuiescentAmps":vit.QuiescentAmps, \
    "QuiescentVolts":vit.QuiescentVolts, \
    "Sbe41Amps":vit.Sbe41Amps, \
    "Sbe41Status":vit.Sbe41Status, \
    "Sbe41Volts":vit.Sbe41Volts, \
    "status":vit.status, \
    "SurfacePistonPosition":vit.SurfacePistonPosition, \
    "SurfacePressure":vit.SurfacePressure, \
    "Vacuum":vit.Vacuum, \
    "YoyoFlag":vit.YoyoFlag, \
    "UpperPressure":vit.UpperPressure, \
    "Level2Flag":vit.Level2Flag, \
    "LowerPressure":vit.LowerPressure, \
    "RawEfSaveFlag":vit.RawEfSaveFlag, \
    "DescentProfIsDone":vit.DescentProfIsDone, \
    "AscentIsDone":vit.AscentIsDone, \
    "ProfilingFlag":vit.ProfilingFlag, \
    "FastProfilingFlag":vit.FastProfilingFlag, \
    }
  if vit.versnum >= ord('e'):
    vit.dict.update({\
    "DateStartedDown":vit.DateStartedDown, \
    "PrfId":vit.PrfId, \
    "MissionCrcBadCount":vit.MissionCrcBadCount, \
    "DatePreludeEnded":vit.DatePreludeEnded, \
    "DateNextLevel2":vit.DateNextLevel2, \
    "DateCycleStarted":vit.DateCycleStarted, \
    "MissionUpdateGotFile":vit.MissionUpdateGotFile, \
    "MissionUpdateChange":vit.MissionUpdateChange, \
    "DoGpsAfter":vit.DoGpsAfter, \
    })
  if vit.versnum >= ord('j'):
    vit.dict.update({\
    "TimeDescentProf":vit.TimeDescentProf, \
  })
  if vit.versnum >= ord('k'):
    vit.dict.update({\
    "LongHoldFlag":vit.LongHoldFlag, \
    })
  if vit.versnum >= ord('l'):
    vit.dict.update({\
    "emaR_count":vit.emaR_count, \
    "emaF_count":vit.emaF_count, \
    "errF_count":vit.errF_count, \
    "nerrR_get":vit.nerrR_get, \
    "nerrM_get":vit.nerrM_get, \
    "nerrF_crc":vit.nerrF_crc, \
    "nerrM_crc":vit.nerrM_crc, \
    "nerr_seqno":vit.nerr_seqno, \
    "nerr_gps":vit.nerr_gps, \
    })
  if vit.versnum >= ord('m'):
    vit.dict.update({\
    "IMEI":vit.imei, \
    })
  if vit.versnum >= ord('n'):
    vit.dict.update({\
    "Vstuck":vit.Vstuck, \
    "Nstuck":vit.Nstuck, \
    })
  if vit.versnum >= ord('s') and vit.versnum <= ord('v'):
    vit.dict.update({\
      "DateToStartDown":vit.DateToStartDown, \
      "DateToStopDown":vit.DateToStopDown, \
      "DateToStartUp":vit.DateToStartUp, \
      "DateToBeAtSfc":vit.DateToBeAtSfc, \
      "VminUse":vit.VminUse, \
      "VminUseDown1":vit.VminUseDown1, \
      "UsingPvt":vit.UsingPvt, \
      "WNeedDescent":vit.WNeedDescent, \
      "WNeedAscent":vit.WNeedAscent, \
      "TMicroFilesAvail":vit.TMicroFilesAvail, \
    })
  if vit.versnum >= ord('u'):
    vit.dict.update({\
    "FirmwareVersion":vit.FirmwareVersion, \
    "AllStoreNum":vit.AllStoreNum, \
    })
  if vit.versnum >= ord('w'):
    vit.dict.update({\
    "NstuckAscent":vit.NstuckAscent, \
    "VstuckAscent":vit.VstuckAscent, \
    "IceDetected":vit.IceDetected, \
    "IceCount":vit.IceCount, \
    "IsWinter":vit.IsWinter, \
    "Switch2Winter":vit.Switch2Winter, \
    })

def writemat_vit(ema):
  vit = ema.vit
  if options.verbose >= 2:
    print('writemat_vit: hpid=',vit.hpid,'nbytes=',vit.nbytes)
  ofile = str.format("ema-{0:s}-{1:04d}-vit.mat",ema.info.runid,vit.hpid)
  if options.verbose >= 2:
    print('writemat_vit: ',ema.odir + '/' + ofile)
  sio.savemat(ema.odir + '/' + ofile, ema.vit.dict, format = '4')
  ema.ofile_list.append(ofile)

def print_vit(ema):
  vit = ema.vit
  writetxt_vit(vit, 'stdout')

def fprint_vit(ema):
  vit = ema.vit
  ofile = str.format("ema-{0:s}-{1:04d}-vit.txt",ema.info.runid,vit.hpid)
  writetxt_vit(vit, ofile)

def writetxt_vit(vit, ofile):
  if ofile == 'stdout':
    ofp = sys.stdout
  else:
    try:
      ofp = open(ema.odir + '/' + ofile,'wt')
    except:
      print('Error: writetxt_vit: cannot open',ofile)
      sys.exit(1)
    if options.verbose >= 2:
      print('writetxt_vit: ',ema.odir + '/' + ofile)

  print('# nbytes = ',vit.nvit,file=ofp)

  for nam in sorted(vit.dict):
    val = vit.dict[nam]

    if type(val) is float:
      print("{0:25s} = {1:.7g}".format(nam,val),end="",file=ofp)
    elif nam.find('Date') >= 0:
      print("{0:25s} = {1}".format(nam,uxt2str(val)),end="",file=ofp)
    else:
      print("{0:25s} = {1}".format(nam,val),end="",file=ofp)

    if nam.find('Amps') >= 0:
      print('\t # {0:.3f} A'.format(val * 16.5 / 4095.0),end="",file=ofp)
    if nam.find('Volts') >= 0:
      print('\t # {0:.2f} V'.format(val * 16.0 * 3.3 * 5.99 / 4095.0),end="",file=ofp)
    if nam == 'Vacuum' or nam == 'AirBladderPressure':
      print('\t # {0:.0f} mbar'.format(val / 3.456 * 33.86),end="",file=ofp)
    if nam == 'FirmwareVersion':
      print("\t # {0:#08x}".format(val),end="",file=ofp)
    if nam.find('Date') >= 0:
      print("\t # ",uxt2str(val),end="",file=ofp)
    if nam == 'status' or nam == 'Sbe41Status':
      print("\t # {0:#016b}".format(val),end="",file=ofp)
    if nam == 't_irid':
      print("\t # ",tirid2str(val),end="",file=ofp)
    print("",file=ofp)

  if ofile != 'stdout':
    ofp.close()

def fprint_mis(ema):
  mis = ema.mis
  ofile = str.format("ema-{0:s}-{1:04d}-mis.txt",ema.info.runid,mis.hpid)
  writetxt_mis(mis, ofile)

def writetxt_mis(mis, ofile):
  if ofile == 'stdout':
    ofp = sys.stdout
  else:
    try:
      ofp = open(ema.odir + '/' + ofile,'wt')
    except:
      print('Error: writetxt_mis: cannot open',ofile)
      sys.exit(1)
    if options.verbose >= 2:
      print('writetxt_mis: ',ema.odir + '/' + ofile)

  print('# nbytes   = ',mis.nmis,file=ofp)

  for nam in sorted(mis.dict):
    val = mis.dict[nam]
    if type(val) is float:
      print("{0:25s} = {1:.7g}".format(nam,val),end='',file=ofp)
    elif nam.find('Date') >= 0:
      print("{0:25s} = {1}".format(nam,uxt2str(val)),end="",file=ofp)
    else:
      print("{0:25s} = {1}".format(nam,val),end='',file=ofp)
    if nam == 'OkVacuumCount' or nam == 'MaxAirBladder':
      print('\t # {0:.0f} mbar'.format(val / 3.456 * 33.86),end="",file=ofp)
    if (nam.find('Time') == 0 or nam.find('Tmo') == 0 or nam.find('Duration')>=0) and val >= 300:
      print("\t # {0:.1f} hours".format(val/3600.0),end="",file=ofp)
    if nam == 'CtdType':
      if val == 1:
        print("\t # SBE 41-ALACE V 2.5",end="",file=ofp)
      elif val == 2:
        print("\t # SBE 41-ALACE V 2.6",end="",file=ofp)
      elif val == 3:
        print("\t # SBE 41-STD V 3.0",end="",file=ofp)
      elif val == 4:
        print("\t # SBE 41CP UW V 2.0",end="",file=ofp)
      else:
        print("\t # CTD TYPE UNKNOWN",end="",file=ofp)
    print("",file=ofp)
  if ofile != 'stdout':
    ofp.close()

def mkdict_mis(ema):
  mis = ema.mis
  mis.dict = {\
    'DateMis':mis.uxt, \
    'hpid':mis.hpid, \
    'typ':mis.typ, \
    "vitvers":mis.vitvers, \
    'runid':ema.info.runid, \
    "nbytes":mis.nmis, \
    "FloatId":mis.FloatId, \
    "MaxAirBladder":mis.MaxAirBladder, \
    "OkVacuumCount":mis.OkVacuumCount, \
    "PistonBuoyancyNudge":mis.PistonBuoyancyNudge, \
    "PistonDeepProfilePosition":mis.PistonDeepProfilePosition, \
    "PistonFullExtension":mis.PistonFullExtension, \
    "PistonFullRetraction":mis.PistonFullRetraction, \
    "PistonInitialBuoyancyNudge":mis.PistonInitialBuoyancyNudge, \
    "PistonParkPosition":mis.PistonParkPosition, \
    "PistonStoragePosition":mis.PistonStoragePosition, \
    "PnpCycleLength":mis.PnpCycleLength, \
    "PressurePark":mis.PressurePark, \
    "PressureDeep":mis.PressureDeep, \
    "TimePrelude":mis.TimePrelude, \
    "TimeDescentProf":mis.TimeDescentProf, \
    "TimeDescentPark":mis.TimeDescentPark, \
    "TimeDescentDeep":mis.TimeDescentDeep, \
    "TimeDown":mis.TimeDown, \
    "TimeUp":mis.TimeUp, \
    "TmoAscent":mis.TmoAscent, \
    "simulate_pressure":mis.simulate_pressure, \
    "simulate_hardware":mis.simulate_hardware, \
    "PreludeRepPeriod":mis.PreludeRepPeriod, \
    "PreludePressureThreshold":mis.PreludePressureThreshold, \
    "IdFirstLevel2":mis.IdFirstLevel2, \
    "TimeYoyoOnceBeg":mis.TimeYoyoOnceBeg, \
    "TimeYoyoOnceEnd":mis.TimeYoyoOnceEnd, \
    "DateCycleStarted":mis.DateCycleStarted, \
    "TimeCycleRep":mis.TimeCycleRep, \
    "TimeCycleYoyoBeg":mis.TimeCycleYoyoBeg, \
    "TimeCycleYoyoEnd":mis.TimeCycleYoyoEnd, \
    "TimeCycleHoldLongBeg":mis.TimeCycleHoldLongBeg, \
    "TimeCycleHoldLongEnd":mis.TimeCycleHoldLongEnd, \
    "TimeHoldLong":mis.TimeHoldLong, \
    "TimeHoldShort":mis.TimeHoldShort, \
    "TimeLevel2Rep":mis.TimeLevel2Rep, \
    "PrTopYoyo":mis.PrTopYoyo, \
    "PrBotYoyo":mis.PrBotYoyo, \
    "PrBotLevel1":mis.PrBotLevel1, \
    "PrBotLevel2":mis.PrBotLevel2, \
    "RawEfSaveRep":mis.RawEfSaveRep, \
    "RawEfSendFlagProfiling":mis.RawEfSendFlagProfiling, \
    "RawEfSendFlagRecovery":mis.RawEfSendFlagRecovery, \
    "Vmin":mis.Vmin, \
    "PistonInitAscentLevel1":mis.PistonInitAscentLevel1, \
    "PistonInitAscentLevel2":mis.PistonInitAscentLevel2, \
    "PistonInitDescentProf":mis.PistonInitDescentProf, \
    "PistonInitDescentProfFirst":mis.PistonInitDescentProfFirst, \
    "DurationFastProfiling":mis.DurationFastProfiling, \
    "DateForRecovery":mis.DateForRecovery, \
    "TimeForRecovery":mis.TimeForRecovery, \
    "RecoveryRepPeriod":mis.RecoveryRepPeriod, \
    "RecoveryNRepConnect":mis.RecoveryNRepConnect, \
    "RecoveryIRepConnect":mis.RecoveryIRepConnect, \
    "TmoConnect":mis.TmoConnect, \
    "TmoXfrFastProfiling":mis.TmoXfrFastProfiling, \
    "TmoXfrProfiling":mis.TmoXfrProfiling, \
    "TmoXfrRecovery":mis.TmoXfrRecovery, \
    "TmoXfrMin":mis.TmoXfrMin, \
    "DatePreludeEnded":mis.DatePreludeEnded, \
    "DateNextLevel2":mis.DateNextLevel2, \
    "ModemType":mis.ModemType, \
    "ModemBaudRate":mis.ModemBaudRate, \
    "PhoneNumbers":mis.PhoneNumbers, \
    "KermitPacketLength":mis.KermitPacketLength, \
    "TmoTelemetry":mis.TmoTelemetry, \
    "debuglevel":mis.debuglevel, \
    "logport_key":mis.logport_key, \
    "logport_baud":mis.logport_baud, \
    "EmaProcessNvals":mis.EmaProcessNvals, \
    "EmaProcessNslide":mis.EmaProcessNslide, \
    "TmoGpsUpdate":mis.TmoGpsUpdate, \
    "TmoGpsShort":mis.TmoGpsShort, \
    "TmoGpsAfter":mis.TmoGpsAfter, \
    "TimeGpsUpdateRep":mis.TimeGpsUpdateRep, \
    "TimeGpsGrabRep":mis.TimeGpsGrabRep, \
    "RawSvBytesStop":mis.RawSvBytesStop, \
    }
  if mis.versnum >= ord('e'):
    mis.dict.update({\
    "PressureAnticipate":mis.PressureAnticipate, \
    "PressureNearSurface":mis.PressureNearSurface, \
    "SigmaThetaFollow":mis.SigmaThetaFollow, \
    "PressureFollowDefault":mis.PressureFollowDefault, \
    "PressureFollowMin":mis.PressureFollowMin, \
    "PressureFollowMax":mis.PressureFollowMax, \
    "PistonFollowDefault":mis.PistonFollowDefault, \
    "SalinityBallastPoint":mis.SalinityBallastPoint, \
    "TemperatureBallastPoint":mis.TemperatureBallastPoint, \
    "PressureBallastPoint":mis.PressureBallastPoint, \
    "PistonCountsPerCC":mis.PistonCountsPerCC, \
    "FloatMass":mis.FloatMass, \
    "FloatAlpha":mis.FloatAlpha, \
    "FloatBeta":mis.FloatBeta, \
    "use_iPiston":mis.use_iPiston, \
    "HeartBeatProf":mis.HeartBeatProf, \
    "HeartBeatHolding":mis.HeartBeatHolding, \
    "TimeOutNudge":mis.TimeOutNudge, \
    "CtdSamplePrFirst":mis.CtdSamplePrFirst, \
    "CtdSampleDelPr1":mis.CtdSampleDelPr1, \
    "CtdSampleDelPr2":mis.CtdSampleDelPr2, \
    "CtdSampleDelPr3":mis.CtdSampleDelPr3, \
    "CtdSampleDelPr4":mis.CtdSampleDelPr4, \
    "CtdSampleN1":mis.CtdSampleN1, \
    "CtdSampleN2":mis.CtdSampleN2, \
    "CtdSampleN3":mis.CtdSampleN3, \
    "CtdSampleN4":mis.CtdSampleN4, \
    "SimulationDpdtCoef":mis.SimulationDpdtCoef, \
    })
  if mis.versnum >= ord('g'):
    mis.dict.update({\
    "PressureMaxRecordRaw":mis.PressureMaxRecordRaw, \
    })
  if mis.versnum >= ord('f'):
    mis.dict.update({\
    "DescentCtdScanType":mis.DescentCtdScanType, \
    "SendOnlyGps":mis.SendOnlyGps, \
    "SendCurrentGpsFirst":mis.SendCurrentGpsFirst, \
    "KermitBps":mis.KermitBps, \
    "KermitRtt":mis.KermitRtt, \
    "GpsAlmanacOkAtLaunch":mis.GpsAlmanacOkAtLaunch, \
    "FirstTwoProfsSpecial":mis.FirstTwoProfsSpecial, \
    })
  if mis.versnum >= ord('h'):
    mis.dict.update({\
    "ModeHoldShort":mis.ModeHoldShort, \
    "ModeHoldLong":mis.ModeHoldLong, \
    "IridiumNRep":mis.IridiumNRep, \
    "IridiumIRep":mis.IridiumIRep, \
    "OpenAirValveAfter":mis.OpenAirValveAfter, \
    })
  if mis.versnum >= ord('i'):
    mis.dict.update({\
    "TimePistonIfNoObs":mis.TimePistonIfNoObs, \
    "PrTopHoldLong":mis.PrTopHoldLong, \
    "PrBotHoldLong":mis.PrBotHoldLong, \
    "PrTopHoldShort":mis.PrTopHoldShort, \
    "PrBotHoldShort":mis.PrBotHoldShort, \
    })
  if mis.versnum >= ord('j'):
    mis.dict.update({\
    "TimeDescentProfHoldLong":mis.TimeDescentProfHoldLong, \
    "TimeDescentProfHoldShort":mis.TimeDescentProfHoldShort, \
    })
  if mis.versnum >= ord('k'):
    mis.dict.update({\
    "PistonInitAscentHoldLong":mis.PistonInitAscentHoldLong, \
    "PistonInitAscentHoldShort":mis.PistonInitAscentHoldShort, \
    })
  if mis.versnum >= ord('n'):
    mis.dict.update({\
    "VstuckThreshold":mis.VstuckThreshold, \
    "NstuckThreshold":mis.NstuckThreshold, \
    })
  if mis.versnum >= ord('o'):
    mis.dict.update({\
    "SimulationPrBot":mis.SimulationPrBot, \
    })
  if mis.versnum >= ord('p'):
    mis.dict.update({\
    "FlbbMode":mis.FlbbMode, \
    "FlbbMaxPr":mis.FlbbMaxPr, \
    "LoginName":mis.LoginName, \
    "Password":mis.Password, \
    })
  if mis.versnum >= ord('q'):
    mis.dict.update({\
    "EfCoefFactor":mis.EfCoefFactor, \
    "KermitWindowSlots":mis.KermitWindowSlots, \
    })
  if mis.versnum >= ord('r'):
    mis.dict.update({\
    "HeartBeatPark":mis.HeartBeatPark, \
    })
  if mis.versnum >= ord('s'):
    mis.dict.update({\
      "ConsoleBaudRate":mis.ConsoleBaudRate, \
    })
  if mis.versnum >= ord('s') and mis.versnum <= ord('v'):
    mis.dict.update({\
    "PvtDateRef":mis.PvtDateRef, \
    "PvtTimeRep":mis.PvtTimeRep, \
    "PvtTimeAllowStartDown":mis.PvtTimeAllowStartDown, \
    "PvtTimeAllowStartUp":mis.PvtTimeAllowStartUp, \
    "PvtWaitAtSurface":mis.PvtWaitAtSurface, \
    "Pvt_alpha":mis.Pvt_alpha, \
    "Pvt_b0":mis.Pvt_b0, \
    "Pvt_pmin_offset":mis.Pvt_pmin_offset, \
    "PvtPistonDiffMax":mis.PvtPistonDiffMax, \
    })
  if mis.versnum >= ord('s'):
    mis.dict.update({\
    "CtdPmin":mis.CtdPmin, \
    "CtdType":mis.CtdType, \
    })
  if mis.versnum >= ord('t'):
    mis.dict.update({\
    "OptodeMode":mis.OptodeMode, \
    "OptodeMaxPr":mis.OptodeMaxPr, \
    })
  if mis.versnum >= ord('w'):
    mis.dict.update({\
      "PrEoaNVals":mis.PrEoaNVals, \
      "PrEoaDSecs":mis.PrEoaDSecs, \

      "IcePressureThreshold":mis.IcePressureThreshold, \
      "DateIcePhone":mis.DateIcePhone, \
      "IceCountMax":mis.IceCountMax, \

      "PtsHoldNRep":mis.PtsHoldNRep, \

      "NstuckAscentThreshold":mis.NstuckAscentThreshold, \
      "PstuckAscentThreshold":mis.PstuckAscentThreshold, \
      "PstuckDescentThreshold":mis.PstuckDescentThreshold, \

      "WinterDoyBeg":mis.WinterDoyBeg, \
      "WinterDoyEnd":mis.WinterDoyEnd, \

      "SummerTimeCycleRep":mis.SummerTimeCycleRep, \
      "SummerTimeCycleYoyoBeg":mis.SummerTimeCycleYoyoBeg, \
      "SummerTimeCycleYoyoEnd":mis.SummerTimeCycleYoyoEnd, \
      "SummerTimeCycleHoldLongBeg":mis.SummerTimeCycleHoldLongBeg, \
      "SummerTimeCycleHoldLongEnd":mis.SummerTimeCycleHoldLongEnd, \
      "SummerTimeHoldLong":mis.SummerTimeHoldLong, \
      "SummerTimeHoldShort":mis.SummerTimeHoldShort, \
      "SummerTimeLevel2Rep":mis.SummerTimeLevel2Rep, \

      "SummerPrTopYoyo":mis.SummerPrTopYoyo, \
      "SummerPrBotYoyo":mis.SummerPrBotYoyo, \
      "SummerPrBotLevel1":mis.SummerPrBotLevel1, \
      "SummerPrBotLevel2":mis.SummerPrBotLevel2, \
      "SummerPrTopHoldLong":mis.SummerPrTopHoldLong, \
      "SummerPrBotHoldLong":mis.SummerPrBotHoldLong, \
      "SummerPrTopHoldShort":mis.SummerPrTopHoldShort, \
      "SummerPrBotHoldShort":mis.SummerPrBotHoldShort, \

      "SummerModeHoldLong":mis.SummerModeHoldLong, \
      "SummerModeHoldShort":mis.SummerModeHoldShort, \
      "SummerPistonInitAscentLevel1":mis.SummerPistonInitAscentLevel1, \
      "SummerPistonInitAscentLevel2":mis.SummerPistonInitAscentLevel2, \
      "SummerPistonInitAscentHoldLong":mis.SummerPistonInitAscentHoldLong, \
      "SummerPistonInitAscentHoldShort":mis.SummerPistonInitAscentHoldShort, \
      "SummerPistonInitDescentProf":mis.SummerPistonInitDescentProf, \
      "SummerPistonFollowDefault":mis.SummerPistonFollowDefault, \
      "SummerPressureFollowDefault":mis.SummerPressureFollowDefault, \

      "WinterTimeCycleRep":mis.WinterTimeCycleRep, \
      "WinterTimeCycleYoyoBeg":mis.WinterTimeCycleYoyoBeg, \
      "WinterTimeCycleYoyoEnd":mis.WinterTimeCycleYoyoEnd, \
      "WinterTimeCycleHoldLongBeg":mis.WinterTimeCycleHoldLongBeg, \
      "WinterTimeCycleHoldLongEnd":mis.WinterTimeCycleHoldLongEnd, \
      "WinterTimeHoldLong":mis.WinterTimeHoldLong, \
      "WinterTimeHoldShort":mis.WinterTimeHoldShort, \
      "WinterTimeLevel2Rep":mis.WinterTimeLevel2Rep, \

      "WinterPrTopYoyo":mis.WinterPrTopYoyo, \
      "WinterPrBotYoyo":mis.WinterPrBotYoyo, \
      "WinterPrBotLevel1":mis.WinterPrBotLevel1, \
      "WinterPrBotLevel2":mis.WinterPrBotLevel2, \
      "WinterPrTopHoldLong":mis.WinterPrTopHoldLong, \
      "WinterPrBotHoldLong":mis.WinterPrBotHoldLong, \
      "WinterPrTopHoldShort":mis.WinterPrTopHoldShort, \
      "WinterPrBotHoldShort":mis.WinterPrBotHoldShort, \

      "WinterModeHoldLong":mis.WinterModeHoldLong, \
      "WinterModeHoldShort":mis.WinterModeHoldShort, \
      "WinterPistonInitAscentLevel1":mis.WinterPistonInitAscentLevel1, \
      "WinterPistonInitAscentLevel2":mis.WinterPistonInitAscentLevel2, \
      "WinterPistonInitAscentHoldLong":mis.WinterPistonInitAscentHoldLong, \
      "WinterPistonInitAscentHoldShort":mis.WinterPistonInitAscentHoldShort, \
      "WinterPistonInitDescentProf":mis.WinterPistonInitDescentProf, \
      "WinterPistonFollowDefault":mis.WinterPistonFollowDefault, \
      "WinterPressureFollowDefault":mis.WinterPressureFollowDefault, \

    })

def writemat_mis(ema):
  mis = ema.mis
  if options.verbose >= 2:
    print('writemat_mis: hpid=',mis.hpid)
  ofile = str.format("ema-{0:s}-{1:04d}-mis.mat",ema.info.runid,mis.hpid)
  if options.verbose >= 2:
    print('writemat_mis: ',ema.odir + '/' + ofile)
  sio.savemat(ema.odir + '/' + ofile, mis.dict, format='4')
  ema.ofile_list.append(ofile)

def escape(inp):
  outp = []
  for c in inp:
    if c in string.printable:
      outp.append(c)
    else:
      outp.append('{0:#02x}'.format(ord(c)))
  return outp

def decode_ema(ema, fbuf):
  if fbuf == None:
    return False

  # emapex bytes sent by kermit firmware are rotated +64
  if options.xmodem == False:
    fbuf -= 64

  ngps = 0
  jb = 0
  while(jb < len(fbuf)):
    typ = struct.unpack(">3s",fbuf[jb:jb+3])[0]

    if typ == 'GPS':
      nb, hpid = decode_gps(fbuf[jb:],ema.gps)
    elif typ == 'CTD':
      nb, hpid = decode_pts(fbuf[jb:],ema.ctd)
      writemat_ctd(ema.ctd)
      writetxt_ctd(ema.ctd)
    elif typ == 'HOL': # ctd during hold
      nb, hpid = decode_pts(fbuf[jb:],ema.hol)
      writemat_hol(ema.hol)
      writetxt_hol(ema.hol)
    elif typ == 'EOA': # pressure at end of ascent
      nb, hpid = decode_eoa(fbuf[jb:],ema.eoa)
      writemat_eoa(ema.eoa)
      writetxt_eoa(ema.eoa)
    elif typ == 'SCP':
      nb, hpid = decode_scp(fbuf[jb:],ema.scp)
      if ema.scp.typ == "SCPc":
        writemat_scp(ema.scp)
        writetxt_scp(ema.scp)
      else:
        global nskip_scp
        nskip_scp += 1
    elif typ == 'FLB':
      nb, hpid = decode_flb(fbuf[jb:],ema.flb)
      writemat_flb(ema.flb)
      writetxt_flb(ema.flb)
    elif typ == 'OPT':
      nb, hpid = decode_opt(fbuf[jb:],ema.opt)
      writemat_opt(ema.opt)
      writetxt_opt(ema.opt)
    elif typ == 'EFP':
      nb, hpid = decode_efp(fbuf[jb:],ema.efp)
      writemat_efp(ema.efp)
      writetxt_efp(ema.efp)
    elif typ == 'VIT':
      nb, hpid = decode_vitmis(fbuf[jb:],ema.vit,ema.mis)
      mkdict_vit(ema)
      mkdict_mis(ema)
      writemat_vit(ema)
      writemat_mis(ema)
      fprint_vit(ema)
      fprint_mis(ema)
    elif typ == 'EFR':
      nb, hpid = decode_efr(fbuf[jb:],ema.efr)
    elif typ == 'EFM':
      nb, hpid = decode_efm(fbuf[jb:],ema.efm)
    elif typ == 'TMP':
      nb, hpid = decode_tmp(fbuf[jb:],ema.tmp)
      writemat_tmp(ema.tmp)
      writetxt_tmp(ema.tmp)
    elif typ == 'LOG':
      print('need code to skip over LOG records')
      sys.exit(1)
    elif typ == '\x1a\x1a\x1a':
      if options.verbose:
        print('typ == three ctrl-z')
      jb = len(fbuf)
      break
    else:
      print('  decode_ema: unknown typ=',repr(typ),
            'jb=',jb,'len(fbuf)=',len(fbuf),'skipped:')
      for f in ema.ifiles:
        print('    ifile=',f)
      print('exit')
      sys.exit(1)
      return False

    ema.hpids_saved.append(hpid)

    if nb < 0:
      print('decode_ema: Error: nb<0, typ=',typ)
      print('jb=',jb,'nb=',nb)
      for f in ema.ifiles:
        print('  ifile=',f)
      sys.exit(1)
      
    # move the buffer pointer to the next segment
    jb += nb

#   print('jb=',jb)

    # gps.hpid before descent is wrong; should be +=1
    # this code is after other decode_*() so as to use their hpid
#   if typ != 'GPS' and ema.gps.nobs > 0:
#     gps2np(ema.gps,hpid)
#     writemat_gps(ema.gps)
#     writetxt_gps(ema.gps)
#     ema.gps.nobs = 0

#   if typ != 'EFR' and typ != 'EFM' and ema.efr.nobs > 0:
#     efr2np(ema.efr)
#     writemat_efr(ema.efr)
#     writetxt_efr(ema.efr)
#     ema.efr.nobs = 0

#   if typ != 'EFR' and typ != 'EFM' and ema.efm.nobs > 0:
#     efm2np(ema.efm)
#     writemat_efm(ema.efm)
#     writetxt_efm(ema.efm)

  if options.verbose:
    print('end of decoding fbuf loop')

  # output last gps group of file if any available
  if ema.gps.nobs > 0:
    gps2np(ema.gps,hpid)
    writemat_gps(ema.gps)
    writetxt_gps(ema.gps)

  if options.verbose:
    print('ema.efr.nobs=',ema.efr.nobs)

  if ema.efr.nobs > 0:
    efr2np(ema.efr)
    writemat_efr(ema.efr)
    writetxt_efr(ema.efr)
    ema.efr.nobs = 0

  if ema.efm.nobs > 0:
    efm2np(ema.efm)
    writemat_efm(ema.efm)
    writetxt_efm(ema.efm)

  if jb != len(fbuf):
    print('Error: jb=',jb,'len(fbuf)=',len(fbuf))
    sys.exit(1)

  return True

def decode_efr(buf, efr):
  # should check CRC

  efr.typ  = struct.unpack(">4s",buf[0:4])[0]
  uxt      = struct.unpack("<I",buf[4:8])[0]
  efr.hpid = struct.unpack("<H",buf[8:10])[0]
  pc       = struct.unpack("<B",buf[10:11])[0]
  efr.nefr = struct.unpack("<H",buf[11:13])[0]

  if options.verbose > 1:
    print(efr.typ,"uxt=",uxt,"nefr=",efr.nefr)

  if efr.nefr != 63:
    print('nefr is wrong')
    sys.exit(1)

  if efr.nobs == 0:
    efr.uxt = []
    efr.pc  = []
    efr.age = []
    efr.overflow = []
    efr.seqno =[]
    efr.zr = []; efr.zrpp  = []
    efr.bt = []; efr.btpp  = []
    efr.hz = []; efr.hzpp  = []
    efr.hy = []; efr.hypp  = []
    efr.hx = []; efr.hxpp  = []
    efr.az = []; efr.azpp  = []
    efr.ay = []; efr.aypp  = []
    efr.ax = []; efr.axpp  = []
    efr.e1 = []; efr.e1pp  = []
    efr.e2 = []; efr.e2pp  = []

  efr.uxt.append(uxt)
  efr.pc.append(long(pc))

  ib0 = 13
  ib = ib0
  efr.age.append     (struct.unpack(">B",buf[ib:ib+1])[0]); ib += 1
  efr.overflow.append(struct.unpack(">H",buf[ib:ib+2])[0]); ib += 2
  efr.seqno.append   (struct.unpack(">H",buf[ib:ib+2])[0]); ib += 2

  n,s,pp = struct.unpack(">BHH",buf[ib:ib+5]); ib += 5 
  efr.zr.append(float(s) / float(n)); efr.zrpp.append(pp)
  n,s,pp = struct.unpack(">BHH",buf[ib:ib+5]); ib += 5
  efr.bt.append(float(s) / float(n)); efr.btpp.append(pp)
  n,s,pp = struct.unpack(">BHH",buf[ib:ib+5]); ib += 5
  efr.hz.append(float(s) / float(n)); efr.hzpp.append(pp)
  n,s,pp = struct.unpack(">BHH",buf[ib:ib+5]); ib += 5
  efr.hy.append(float(s) / float(n)); efr.hypp.append(pp)
  n,s,pp = struct.unpack(">BHH",buf[ib:ib+5]); ib += 5
  efr.hx.append(float(s) / float(n)); efr.hxpp.append(pp)
  n,s,pp = struct.unpack(">BHH",buf[ib:ib+5]); ib += 5
  efr.az.append(float(s) / float(n)); efr.azpp.append(pp)
  n,s,pp = struct.unpack(">BHH",buf[ib:ib+5]); ib += 5
  efr.ay.append(float(s) / float(n)); efr.aypp.append(pp)
  n,s,pp = struct.unpack(">BHH",buf[ib:ib+5]); ib += 5
  efr.ax.append(float(s) / float(n)); efr.axpp.append(pp)

  n,s,pp1,pp2 = struct.unpack(">BLHB",buf[ib:ib+8]); ib += 8
  if n>0:
    efr.e1.append(float(s) / float(n));
  else:
    efr.e1.append(0);
  efr.e1pp.append(pp1*256 + pp2)

  n,s,pp1,pp2 = struct.unpack(">BLHB",buf[ib:ib+8]); ib += 8
  if n>0:
    efr.e2.append(float(s) / float(n));
  else:
    efr.e2.append(0);
  efr.e2pp.append(pp1*256 + pp2)

  nbytes = ib - ib0

  efr.nbytes += nbytes
  efr.nobs += 1
  return 13 + efr.nefr, efr.hpid

def efr2np(efr):
  efr.UXT  = np.array(efr.uxt , dtype=np.long)
  efr.PC   = np.array(efr.pc  , dtype=np.long)

  efr.ZR = np.array(efr.zr, dtype=np.float)
  efr.BT = np.array(efr.bt, dtype=np.float)
  efr.HZ = np.array(efr.hz, dtype=np.float)
  efr.HY = np.array(efr.hy, dtype=np.float)
  efr.HX = np.array(efr.hx, dtype=np.float)
  efr.AZ = np.array(efr.az, dtype=np.float)
  efr.AY = np.array(efr.ay, dtype=np.float)
  efr.AX = np.array(efr.ax, dtype=np.float)
  efr.E1 = np.array(efr.e1, dtype=np.float)
  efr.E2 = np.array(efr.e2, dtype=np.float)

  efr.ZRPP  = np.array(efr.zrpp, dtype=np.long)
  efr.BTPP  = np.array(efr.btpp, dtype=np.long)
  efr.HZPP  = np.array(efr.hzpp, dtype=np.long)
  efr.HYPP  = np.array(efr.hypp, dtype=np.long)
  efr.HXPP  = np.array(efr.hxpp, dtype=np.long)
  efr.AZPP  = np.array(efr.azpp, dtype=np.long)
  efr.AYPP  = np.array(efr.aypp, dtype=np.long)
  efr.AXPP  = np.array(efr.axpp, dtype=np.long)
  efr.E1PP  = np.array(efr.e1pp, dtype=np.long)
  efr.E2PP  = np.array(efr.e2pp, dtype=np.long)

def writemat_efr(efr):
  if options.verbose >= 1:
    print("writemat_efr: hpid=",efr.hpid,"nobs=",efr.nobs)
  ofile = str.format("ema-{0:s}-{1:04d}-efr.mat",ema.info.runid,efr.hpid)
  if options.verbose >= 1:
    print('writemat_efr:',ema.odir + '/' + ofile)
  sio.savemat(ema.odir + '/' + ofile, {\
    'hpid':efr.hpid, \
    'typ':efr.typ, \
    'runid':ema.info.runid, \
    'UXT':efr.uxt , \
    'PC':efr.PC  , \
    'ZR':efr.ZR, \
    'BT':efr.BT, \
    'HZ':efr.HZ, \
    'HY':efr.HY, \
    'HX':efr.HX, \
    'AZ':efr.AZ, \
    'AY':efr.AY, \
    'AX':efr.AX, \
    'E1':efr.E1, \
    'E2':efr.E2, \
    'ZRPP':efr.ZRPP, \
    'BTPP':efr.BTPP, \
    'HZPP':efr.HZPP, \
    'HYPP':efr.HYPP, \
    'HXPP':efr.HXPP, \
    'AZPP':efr.AZPP, \
    'AYPP':efr.AYPP, \
    'AXPP':efr.AXPP, \
    'E1PP':efr.E1PP, \
    'E2PP':efr.E2PP, \
    }, format='4')
  ema.ofile_list.append(ofile)

def writetxt_efr(efr):
  if options.verbose >= 2:
    print('writetxt_efr: hpid=',efr.hpid,'nobs=',efr.nobs)

  ofile = str.format("ema-{0:s}-{1:04d}-efr.txt",ema.info.runid,efr.hpid)
  if options.verbose >= 2:
    print('writetxt_efr:',ema.odir + '/' + ofile)

  try:
    ofp = open(ema.odir + '/' + ofile,'wt')
  except:
    print('writetxt_efr: cannot open output file',ofile)
    sys.exit(1)

  print("# ofile = {0:s}".format(ofile),file=ofp)
  print("# runid = {0:s}".format(ema.info.runid),file=ofp)
  print("# hpid = {0:d}".format(efr.hpid),file=ofp)
  print("# nobs = {0:d}".format(efr.nobs),file=ofp)
  print("# nbytes = {0:d}".format(efr.nbytes),file=ofp)
  print("# typ = {0}".format(efr.typ),file=ofp)

  print("# vars = uxt,pc,zr,bt,hz,hy,hx,az,ay,ax,e1,e2," + \
        "zrpp,btpp,hzpp,hypp,hxpp,azpp,aypp,axpp,e1pp,e2pp",file=ofp)
  print("#DATA#",file=ofp)

  for i in range(0,efr.nobs):
    print("{0:d},".format(efr.uxt[i]),file=ofp,end="")
    print("{0},".format(efr.PC[i]),file=ofp,end="")
    print("{0:.1f},".format(efr.ZR[i]),file=ofp,end="")
    print("{0:.1f},".format(efr.BT[i]),file=ofp,end="")
    print("{0:.1f},".format(efr.HZ[i]),file=ofp,end="")
    print("{0:.1f},".format(efr.HY[i]),file=ofp,end="")
    print("{0:.1f},".format(efr.HX[i]),file=ofp,end="")
    print("{0:.1f},".format(efr.AZ[i]),file=ofp,end="")
    print("{0:.1f},".format(efr.AY[i]),file=ofp,end="")
    print("{0:.1f},".format(efr.AX[i]),file=ofp,end="")
    print("{0:.1f},".format(efr.E1[i]),file=ofp,end="")
    print("{0:.1f},".format(efr.E2[i]),file=ofp,end="")
    print("{0},".format(efr.ZRPP[i]),file=ofp,end="")
    print("{0},".format(efr.BTPP[i]),file=ofp,end="")
    print("{0},".format(efr.HZPP[i]),file=ofp,end="")
    print("{0},".format(efr.HYPP[i]),file=ofp,end="")
    print("{0},".format(efr.HXPP[i]),file=ofp,end="")
    print("{0},".format(efr.AZPP[i]),file=ofp,end="")
    print("{0},".format(efr.AYPP[i]),file=ofp,end="")
    print("{0},".format(efr.AXPP[i]),file=ofp,end="")
    print("{0},".format(efr.E1PP[i]),file=ofp,end="")
    print("{0}".format(efr.E2PP[i]),file=ofp)

  print("#EOD#",file=ofp)
  ofp.close()

def decode_efm(buf, efm):
  # should check CRC

  efm.typ  = struct.unpack(">4s",buf[0:4])[0]
  uxt      = struct.unpack("<I",buf[4:8])[0]
  efm.hpid = struct.unpack("<H",buf[8:10])[0]
  efm.nefm = struct.unpack("<H",buf[10:12])[0]
  efm.nsum = struct.unpack(">B",buf[12:13])[0]
  if options.verbose > 1:
    print(efm.typ,"uxt=",uxt,"nefm=",efm.nefm,'nsum=',efm.nsum)

  if efm.nobs == 0:
    efm.uxt = []

    efm.hzavg_bef = []
    efm.hyavg_bef = []
    efm.hxavg_bef = []
    efm.hzavg_dur = []
    efm.hyavg_dur = []
    efm.hxavg_dur = []
    efm.hzavg_aft = []
    efm.hyavg_aft = []
    efm.hxavg_aft = []

    efm.hzmax_bef = []
    efm.hymax_bef = []
    efm.hxmax_bef = []
    efm.hzmax_dur = []
    efm.hymax_dur = []
    efm.hxmax_dur = []
    efm.hzmax_aft = []
    efm.hymax_aft = []
    efm.hxmax_aft = []

    efm.hzmin_bef = []
    efm.hymin_bef = []
    efm.hxmin_bef = []
    efm.hzmin_dur = []
    efm.hymin_dur = []
    efm.hxmin_dur = []
    efm.hzmin_aft = []
    efm.hymin_aft = []
    efm.hxmin_aft = []

  # note big-endian byte order here:
  # this buffer is from a Motorola processor
  ib = 13
  av = struct.unpack(">9H",buf[ib:ib+18]); ib += 18
  ma = struct.unpack(">9H",buf[ib:ib+18]); ib += 18
  mi = struct.unpack(">9H",buf[ib:ib+18]); ib += 18

  sf = 1.0 / float(efm.nsum)

  efm.uxt.append(uxt)
  efm.hzavg_bef.append(float(av[0])*sf)
  efm.hyavg_bef.append(float(av[1])*sf)
  efm.hxavg_bef.append(float(av[2])*sf)
  efm.hzavg_dur.append(float(av[3])*sf)
  efm.hyavg_dur.append(float(av[4])*sf)
  efm.hxavg_dur.append(float(av[5])*sf)
  efm.hzavg_aft.append(float(av[6])*sf)
  efm.hyavg_aft.append(float(av[7])*sf)
  efm.hxavg_aft.append(float(av[8])*sf)

  efm.hzmax_bef.append(ma[0])
  efm.hymax_bef.append(ma[1])
  efm.hxmax_bef.append(ma[2])
  efm.hzmax_dur.append(ma[3])
  efm.hymax_dur.append(ma[4])
  efm.hxmax_dur.append(ma[5])
  efm.hzmax_aft.append(ma[6])
  efm.hymax_aft.append(ma[7])
  efm.hxmax_aft.append(ma[8])

  efm.hzmin_bef.append(mi[0])
  efm.hymin_bef.append(mi[1])
  efm.hxmin_bef.append(mi[2])
  efm.hzmin_dur.append(mi[3])
  efm.hymin_dur.append(mi[4])
  efm.hxmin_dur.append(mi[5])
  efm.hzmin_aft.append(mi[6])
  efm.hymin_aft.append(mi[7])
  efm.hxmin_aft.append(mi[8])

  efm.nobs += 1
  return 12 + efm.nefm, efm.hpid

def efm2np(efm):
  efm.UXT  = np.array(efm.uxt , dtype=np.long)
  efm.NEFM = np.array(efm.nefm, dtype=np.long)
  efm.NSUM = np.array(efm.nsum, dtype=np.long)
  efm.HZAVG_BEF = np.array(efm.hzavg_bef, dtype=np.float)
  efm.HYAVG_BEF = np.array(efm.hyavg_bef, dtype=np.float)
  efm.HXAVG_BEF = np.array(efm.hxavg_bef, dtype=np.float)
  efm.HZAVG_DUR = np.array(efm.hzavg_dur, dtype=np.float)
  efm.HYAVG_DUR = np.array(efm.hyavg_dur, dtype=np.float)
  efm.HXAVG_DUR = np.array(efm.hxavg_dur, dtype=np.float)
  efm.HZAVG_AFT = np.array(efm.hzavg_aft, dtype=np.float)
  efm.HYAVG_AFT = np.array(efm.hyavg_aft, dtype=np.float)
  efm.HXAVG_AFT = np.array(efm.hxavg_aft, dtype=np.float)
  efm.HZMAX_BEF = np.array(efm.hzmax_bef, dtype=np.uint16)
  efm.HYMAX_BEF = np.array(efm.hymax_bef, dtype=np.uint16)
  efm.HXMAX_BEF = np.array(efm.hxmax_bef, dtype=np.uint16)
  efm.HZMAX_DUR = np.array(efm.hzmax_dur, dtype=np.uint16)
  efm.HYMAX_DUR = np.array(efm.hymax_dur, dtype=np.uint16)
  efm.HXMAX_DUR = np.array(efm.hxmax_dur, dtype=np.uint16)
  efm.HZMAX_AFT = np.array(efm.hzmax_aft, dtype=np.uint16)
  efm.HYMAX_AFT = np.array(efm.hymax_aft, dtype=np.uint16)
  efm.HXMAX_AFT = np.array(efm.hxmax_aft, dtype=np.uint16)
  efm.HZMIN_BEF = np.array(efm.hzmin_bef, dtype=np.uint16)
  efm.HYMIN_BEF = np.array(efm.hymin_bef, dtype=np.uint16)
  efm.HXMIN_BEF = np.array(efm.hxmin_bef, dtype=np.uint16)
  efm.HZMIN_DUR = np.array(efm.hzmin_dur, dtype=np.uint16)
  efm.HYMIN_DUR = np.array(efm.hymin_dur, dtype=np.uint16)
  efm.HXMIN_DUR = np.array(efm.hxmin_dur, dtype=np.uint16)
  efm.HZMIN_AFT = np.array(efm.hzmin_aft, dtype=np.uint16)
  efm.HYMIN_AFT = np.array(efm.hymin_aft, dtype=np.uint16)
  efm.HXMIN_AFT = np.array(efm.hxmax_aft, dtype=np.uint16)

def writemat_efm(efm):
  if options.verbose >= 2:
    print("writemat_efm: hpid=",efm.hpid,"nobs=",efm.nobs)
  efm.nobs = 0
  ofile = str.format("ema-{0:s}-{1:04d}-efm.mat",ema.info.runid,efm.hpid)
  if options.verbose >= 2:
    print('writemat_efm: ',ema.odir + '/' + ofile)
  sio.savemat(ema.odir + '/' + ofile, {\
    'hpid':efm.hpid, \
    'typ':efm.typ, \
    'runid':ema.info.runid, \
    'UXT':efm.UXT, \
    'NEFM':efm.NEFM, \
    'NSUM':efm.NSUM, \
    'HZAVG_BEF':efm.HZAVG_BEF, \
    'HYAVG_BEF':efm.HYAVG_BEF, \
    'HXAVG_BEF':efm.HXAVG_BEF, \
    'HZAVG_DUR':efm.HZAVG_DUR, \
    'HYAVG_DUR':efm.HYAVG_DUR, \
    'HXAVG_DUR':efm.HXAVG_DUR, \
    'HZAVG_AFT':efm.HZAVG_AFT, \
    'HYAVG_AFT':efm.HYAVG_AFT, \
    'HXAVG_AFT':efm.HXAVG_AFT, \
    'HZMAX_BEF':efm.HZMAX_BEF, \
    'HYMAX_BEF':efm.HYMAX_BEF, \
    'HXMAX_BEF':efm.HXMAX_BEF, \
    'HZMAX_DUR':efm.HZMAX_DUR, \
    'HYMAX_DUR':efm.HYMAX_DUR, \
    'HXMAX_DUR':efm.HXMAX_DUR, \
    'HZMAX_AFT':efm.HZMAX_AFT, \
    'HYMAX_AFT':efm.HYMAX_AFT, \
    'HXMAX_AFT':efm.HXMAX_AFT, \
    'HZMIN_BEF':efm.HZMIN_BEF, \
    'HYMIN_BEF':efm.HYMIN_BEF, \
    'HXMIN_BEF':efm.HXMIN_BEF, \
    'HZMIN_DUR':efm.HZMIN_DUR, \
    'HYMIN_DUR':efm.HYMIN_DUR, \
    'HXMIN_DUR':efm.HXMIN_DUR, \
    'HZMIN_AFT':efm.HZMIN_AFT, \
    'HYMIN_AFT':efm.HYMIN_AFT, \
    'HXMIN_AFT':efm.HXMIN_AFT, \
    }, format='4')
  ema.ofile_list.append(ofile)

def writetxt_efm(efp): # fixme
  if options.verbose:
    print('writetxt_efm: not coded yet')

def emazero(ema):
  ema.gps = collections.namedtuple('GPS', []); ema.gps.nobs = 0
  ema.ctd = collections.namedtuple('CTD', []); ema.ctd.nobs = 0
  ema.scp = collections.namedtuple('SCP', []); ema.scp.nobs = 0
  ema.flb = collections.namedtuple('FLB', []); ema.flb.nobs = 0
  ema.opt = collections.namedtuple('OPT', []); ema.opt.nobs = 0
  ema.efp = collections.namedtuple('EFP', []); ema.efp.nobs = 0
  ema.vit = collections.namedtuple('VIT', []); ema.vit.nobs = 0
  ema.mis = collections.namedtuple('MIS', []); ema.mis.nobs = 0
  ema.efr = collections.namedtuple('EFR', []); ema.efr.nobs = 0; ema.efr.nbytes = 0
  ema.efm = collections.namedtuple('EFM', []); ema.efm.nobs = 0
  ema.hol = collections.namedtuple('HOL', []); ema.hol.nobs = 0
  ema.eoa = collections.namedtuple('EOA', []); ema.eoa.nobs = 0
  ema.tmp = collections.namedtuple('TMP', []); ema.tmp.nobs = 0

  ema.ofile_list = []
  return ema

def getbuf(ema,hpid):
# idir = str.format('{0:s}/{1:s}/',ema.info.fltdir,ema.info.fltid)
# allfiles = sorted(listdir(idir))

  ema.ifiles = []
  ema.ibegs = []
  ema.iends = []

  for ifile in ema.myfiles:
    tok = split_ifile(ifile)
    if tok == None:
      continue

    if tok[0] != 'ema':
      continue

    fltid_got = tok[1]
    hpid_got  = int(tok[3])
    date_got = toks2date(tok[4],tok[5])

    if fltid_got == ema.info.fltid and hpid_got == hpid and \
      date_got >= ema.info.datebeg and date_got <= ema.info.dateend:
      ema.ifiles.append(ifile)
      ema.ibegs.append(int(tok[6]))
      ema.iends.append(int(tok[7]))

  if len(ema.ifiles) == 0:
    # print("Note: getbuf: no files selected")
    return None

  # indices of sorted ibegs
  inds = sorted(range(len(ema.ibegs)), key=ema.ibegs.__getitem__)

  obuf = np.array([],dtype=np.uint8)
  minibegs = min(ema.ibegs)

  if options.verbose:
    print('    file_hpid=',hpid,'nfiles=',len(ema.ifiles))
  for ind in inds:
    ioff = ema.ibegs[ind] - minibegs

    ifp = open(ema.idir + ema.ifiles[ind], "rb")
    ibuf = np.fromfile(ifp, dtype=np.uint8)
    ifp.close()

    if options.verbose:
      print('ind=',ind,ema.ifiles[ind],'len=',len(ibuf),'ioff=',ioff)

    if len(obuf) > ioff:
      old = obuf[ioff:]
      new = ibuf[0:len(old)]
      s = str.format('ema-{0:s}-{1:04d}:',ema.info.runid,hpid)
      if not np.array_equal(old,new):
        if options.verbose < 10:
          print(' ',s,'Warning:',len(obuf)-ioff,'overlapping bytes not the same')
          for f in ema.ifiles:
            print('    ifile=',f)
      else:
        if options.verbose:
          print(' ',s,'Note: found',len(obuf)-ioff,'identical overlapping bytes')
      obuf = obuf[0:ioff]
    if len(obuf) < ioff:
      s = str.format('ema-{0:s}-{1:04d}:',ema.info.runid,hpid)
      if options.verbose < 10:
        print(' ',s,'missing',ioff - len(obuf),'bytes','skipped:')
        for f in ema.ifiles:
          print('    ifile=',f)
      return None
    obuf = np.concatenate((obuf,ibuf))

  lenwant = max(ema.iends) - minibegs
  if len(obuf) != lenwant:
    if options.verbose < 10:
      print('  getbuf: len(obuf) wrong, len(obuf)=',len(obuf),'lenwant=',lenwant,'skipped:')
      for f in ema.ifiles:
        print('    ifile=',f)
    return None

  return obuf

def getmyfiles(ema):
  ema.myfiles = []

  ema.allfiles = sorted(listdir(ema.idir))

  ema.myfiles = []
  for ifile in ema.allfiles:
    if options.verbose >= 2:
      print('ifile=',ifile)
    if ifile.find('~') >= 0:
      if options.verbose < 10:
        print('skipped backup ifile=',ifile)
      continue
    if not all(c in string.printable for c in ifile):
      if options.verbose < 10:
        print('skipped non-printable ifile=',ifile)
      continue
    ema.myfiles.append(ifile)
  if options.verbose >= 2:
    print('ema.myfiles=',ema.myfiles)


def gethpids(ema):

  hpids = []
  for ifile in ema.myfiles:
    tok = split_ifile(ifile)
    if tok != None and len(tok) == 8 and tok[1] == ema.info.fltid \
    and tok[0] == 'ema':
      hpid  = int(tok[3])
      date_got = toks2date(tok[4],tok[5])
      if date_got >= ema.info.datebeg and date_got <= ema.info.dateend \
      and hpid >= ema.info.hpidmin and hpid <= ema.info.hpidmax:
        hpids.append(hpid)
  if len(hpids) == 0:
    print('  no files found in',ema.idir)
    print('    between',ema.info.datebeg,'and',ema.info.dateend)
    return hpids

  hpids = list(set(hpids)) # list of unique hpids
  return sorted(hpids) # list of sorted unique hpids

#def ourplot(ema):
#  mplot.figure(1).clf()
#  mplot.hold(True)
#  mplot.gca().invert_yaxis()
#  mplot.plot(ema.ctd.S,ema.ctd.P)
#  mplot.plot(ema.scp.S,ema.scp.P)
#  mplot.show()

if __name__ == '__main__':

  nskip_scp = 0

  parser = OptionParser()

  parser.add_option('-v', '--verbose', 
    action='count', dest='verbose', default=0,
    help='print status messages to stdout')

  parser.add_option('-i', '--info', '--infofile',
    dest='infofile', default='./emainfo',
    help='file with processing parameters for each runid')

  parser.add_option('-r', '--runid',
    dest='runid', default=None,
    help='runid to replace that determined from filename')

  parser.add_option('-x', '--xmodem',
    dest='xmodem', default=False, action="store_true", 
    help='flag to indicate xmodem used for file transfer from EM-APEX')

  (options, args) = parser.parse_args()

  # print('options.verbose=',options.verbose)

  if len(args) == 0:
    parser.print_help()
    sys.exit(1)

  for arg in args:

    ema = collections.namedtuple('EMA', [])

    if options.runid != None:
      ema.info = getinfoinit()
      ema.info.runid = options.runid
      ema.info.fltid = options.runid
      ema.info.fltdir = path.dirname(arg)
      ema.info.leafname = path.basename(arg)
      ema.ifile = arg
      ema.idir = path.dirname(ema.ifile)
      ema.odir = ema.info.decdir + '/' + ema.info.runid
      print('ema.info.fltdir=',ema.info.fltdir)
    elif arg.find('ema-') >= 0:
      # a specific file from float
      ema.info = mkinfo(arg,options.infofile)
      ema.odir = ema.info.odir
    else:
      ema.info = getinfo(arg, options.infofile)
      if ema.info.runid == None:
        ema.info.runid = arg
        ema.info.fltid = arg
      ema.odir = ema.info.decdir + '/' + ema.info.runid

#   if ema.info.fltid == None and ema.info.runid != None:
#     ema.info.fltid = getfltid(ema.info.runid)

    print('emadec: arg=',arg,'runid=',ema.info.runid,'fltid=',ema.info.fltid)

    if ema.info.fltid == None:
      print('emadec: cannot get fltid')
      continue

    ema.idir = str.format('{0:s}/{1:s}/',ema.info.fltdir,ema.info.fltid)

    if options.verbose:
      print('info.runid =',ema.info.runid)
      print('     fltid =',ema.info.fltid)
      print('      idir =',ema.idir)
      print('      odir =',ema.odir)
      print('   datebeg =',ema.info.datebeg)
      print('   dateend =',ema.info.dateend)

    if not path.exists(ema.idir):
      print('emadec.py: idir  =',ema.idir,'does not exist')
      print('  ema.info.fltdir=',ema.info.fltdir)
      print('  ema.info.fltid =',ema.info.fltid)
      continue

    if options.runid:
      makedirs(ema.odir)
      emazero(ema)
      buf = getbuf(ema,hpid)

      ifp = open(ema.ifile, "rb")
      ibuf = np.fromfile(ifp, dtype=np.uint8)
      ifp.close()

      if not decode_ema(ema, buf):
        print('cannot decode')
        os.exit(1)

      os.exit(0)
      


    getmyfiles(ema)
    hpids = gethpids(ema)
    if options.verbose:
      print('  number of hpids=',len(hpids))

    if len(hpids) == 0:
      continue

    try: 
      # like mkdir -p
      makedirs(ema.odir)
    except OSError:
      if not path.isdir(ema.odir):
        print('cannot create directory=',ema.odir)
        continue

    print('  idir=',ema.idir)
    print('  odir=',ema.odir)
    print('  ifiles have hpids from',hpids[0],'to',hpids[-1])

    ema.hpids_saved = []
    for hpid in hpids:
      emazero(ema)
      buf = getbuf(ema,hpid)
      if buf == None:
        continue
      if not decode_ema(ema, buf):
        continue
      # ourplot(ema)

    if nskip_scp > 0:
      print('nskip_scp=',nskip_scp)

    print('  runid=',ema.info.runid,'last hpid=',hpid)
  # print('  missing=',sorted(set(range(1,max(hpids)+1))-set(ema.hpids_saved)))
