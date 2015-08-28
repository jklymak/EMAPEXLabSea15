# geomag.py -- emavel.py calls geomag.c to get Fh and Fz

from __future__ import print_function
from time import strptime
from calendar import timegm
from subprocess import Popen, PIPE
from datetime import datetime
from sys import exit,stdin,stdout

def geomag(lat,lon,utc):
  gdir = '../geomag'
  modelfile = 'WMM2005.cof'

  cmd  = '{0}/geomag'.format(gdir)
  args = '{0}/{1}'.format(gdir,modelfile)
  # print('geomag: cmd=',cmd,'args=',args)

  if lat > 0:
    lath = 'N'
  else:
    lath = 'S'
    lat = -lat

  if lon > 0:
    lonh = 'E'
  else:
    lonh = 'W'
    lon = -lon
    
  latd = int(lat)
  latm = (lat - latd) * 60
  lond = int(lon)
  lonm = (lon - lond) * 60

  ymd = utc.strftime('%Y %m %d')
  latstr = '{0} {1:6.3f} {2}'.format(latd,latm,lath)
  lonstr = '{0} {1:6.3f} {2}'.format(lond,lonm,lonh)
  instr = 'mylbl {0} {1} {2}\n'.format(ymd,latstr,lonstr)
  # print('geomag: instr=',instr)
  stdout.flush()

  try:
    proc = Popen([cmd,args], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    outstr, errstr = proc.communicate(instr)
  except:
    print('geomag: cannot get Fh, Fz, Magvar; cmd=',cmd,'args=',args)
    exit(1)

  # print('geomag: outstr:')
  # print(outstr)
  # print('geomag: errstr:')
  # print(errstr)

  toks = None
  for line in outstr.split('\n'):
    if line.find('mylbl')==0:
      # print('line=',line)
      toks = line.split()
      # print('toks=',toks)
      break

  if toks != None:
    return float(toks[11]), float(toks[12]), float(toks[13])
  else:
    return None, None, None

  
if __name__ == '__main__':

  Fh, Fz, MagVar = geomag(47.2, -122.2, datetime.utcnow())
  print('Fh=',Fh)
  print('Fz=',Fz)
  print('MagVar=',MagVar)
