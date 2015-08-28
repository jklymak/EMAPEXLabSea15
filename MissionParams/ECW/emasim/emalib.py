from __future__ import print_function
from time import strptime
from calendar import timegm

def lasthpid(datadir, runid):
  import sys
  import scipy.io
  import os

  decdir = str.format("{0}/{1}/matlab/dec",datadir,runid)
  vitfile = str.format("{0}/ema-{1}-vit.mat",decdir,runid)
  # print("lasthpid(): vitfile=["+vitfile+"]")

  if not os.path.isfile(vitfile):
    print("lasthpid(): vitfile=",vitfile,'is not a file; skipped')
    return None

  try:
    VIT = scipy.io.loadmat(vitfile)
  except IOError:
#   print("lasthpid(): Cannot open " + vitfile)
    sys.exit(1)

  hpid = int(VIT['hpid'][0][-1]) # last hpid
  # print('hpid=',hpid)

  return hpid

def getctd(datadir, runid, hpid):
  import collections
  import numpy
  import scipy.io
  import os
  import sys

  ctd = collections.namedtuple('CTD', [])
  decdir = str.format("{0}/{1}/matlab/dec",datadir,runid)
  ctdfile = str.format("{0}/ema-{1}-{2:04d}-ctd.mat", decdir,runid, hpid)

  if not os.path.isfile(ctdfile):
    # print("lasthpid(): ctdfile=",ctdfile,'is not a file; skipped')
    return None

  try:
    CTD = scipy.io.loadmat(ctdfile)
  except:
    return None

  ctd.P   = numpy.array(CTD['P'][0],  dtype='double')
  ctd.T   = numpy.array(CTD['T'][0],  dtype='double')
  ctd.S   = numpy.array(CTD['S'][0],  dtype='double')
  ctd.UXT = numpy.array(CTD['UXT'][0],dtype='double')
  ctd.MLT = ctd.UXT / 86400 + 719529 - 366

  return ctd

def lastctd(runid):
  import scipy.io
  import numpy
  import os

  datadir = '/home/dunlap/emapex/emarun/data'
  decdir = str.format("{0}/{1}/matlab/dec",datadir,runid)

  misfile = str.format("{0}/ema-{1}-mis.mat",decdir,runid)
  if not os.path.isfile(misfile):
    print("lasthpid(): misfile=",misfile,'is not a file')
    sys.exit(1)
  MIS = scipy.io.loadmat(misfile)

  vitfile = str.format("{0}/ema-{1}-vit.mat",decdir,runid)
  if not os.path.isfile(vitfile):
    print("lasthpid(): vitfile=",vitfile,'is not a file')
    sys.exit(1)
  VIT = scipy.io.loadmat(vitfile)

  hpid = int(VIT['hpid'][0][-1]) # last hpid

  ctdfile = str.format("{0}/ema-{1}-{2:04d}-ctd.mat", decdir,runid, hpid)
  if not os.path.isfile(ctdfile):
    print("lasthpid(): ctdfile=",ctdfile,'is not a file')
    sys.exit(1)
  CTD = scipy.io.loadmat(ctdfile)

  P = numpy.array(CTD['P'][0],dtype='double')
  T = numpy.array(CTD['T'][0],dtype='double')
  S = numpy.array(CTD['S'][0],dtype='double')

  # values from last profile
  pcbp  = float(MIS['PistonStoragePosition'][0][-1])
  Tbp   = float(MIS['TemperatureBallastPoint'][0][-1])
  Pbp   = float(MIS['PressureBallastPoint'][0][-1])
  Sbp   = float(MIS['SalinityBallastPoint'][0][-1])
  alpha = float(MIS['FloatAlpha'][0][-1])
  beta  = float(MIS['FloatBeta'][0][-1])
  mass  = float(MIS['FloatMass'][0][-1])

  return {'P':P, 'T':T, 'S':S, \
    'pcbp':pcbp, 'salbp':Sbp, 'tempbp':Tbp, 'presbp':Pbp, \
    'mass':mass, 'alpha':alpha, 'beta':beta}


def pistonneutral (P,T,S,Pbp,Tbp,Sbp,PCbp,addwt,alpha,beta):
  # air weight  (g)
  mass = 27900.0

  # new piston scale factor from Dana July 2004
  pccpc  = 252.0 / (227.0 - 9.0)

  # density of seawater and float are equal at ballast point
  rhobp = sw_dens(Sbp,Tbp,Pbp) / 1000.0

  # volume (cc) of float and seawater at ballast point
  vbp = mass / rhobp

  rho = sw_dens(S,T,P) / 1000.0

  # volume (cc) of seawater of float's mass ref'd to ballast point
  vw = mass / rho - vbp

  # volume (cc) of float ref'd to ballast point
  # with piston at ballast point
  vfp = -alpha * mass * (P - Pbp)
  vft = mass * beta * (T - Tbp)
  vf = vfp + vft

  # volume (cc) of piston to be neutral
  vpn = vw - vf

  # adjust piston volumn for added weight in water
  vpn = vpn + addwt

  # piston counts to be neutral
  pcn = vpn / pccpc + PCbp

  return pcn

def read_balpt(runid, bpfn): # read ballast point file
  import sys
  import collections

  bp = collections.namedtuple('BP', [])

  try:
    bpfd = open(bpfn,'rt')
  except:
    print('read_balpt(): cannot open bpfn=',bpfn)
    sys.exit(1)

  bp.P = None
  bp.T = None
  bp.S = None
  bp.PC = None
  bp.addwt = 0.0;
  bp.alpha = 3.75e-6; # dV/V per dbar
  bp.beta  = 32.0e-6; # dV/V per degC

  lineno = 0
  for line in bpfd:
    lineno += 1

    if '#' in line:
      i = line.find('#')
      if i == 0:
        continue
      line = line[0:i]

    line = line.strip()

    if len(line) == 0:
      continue

    tok = line.split()
    ntok = len(tok)

    if ntok < 5 or ntok > 8:
      print('read_balpt(): bad line.  lineno=', lineno,'ntok=',ntok,'line=',line)
      sys.exit()

    if tok[0].strip() != runid:
      continue

    bp.P = float(tok[1].strip())
    bp.T = float(tok[2].strip())
    bp.S = float(tok[3].strip())
    bp.PC = float(tok[4].strip())
    if len(tok) >= 6:
      bp.addwt = float(tok[5].strip())
    if len(tok) >= 7:
      bp.alpha = float(tok[6].strip())
    if len(tok) >= 8:
      bp.beta  = float(tok[7].strip())
  bpfd.close()
  if bp.P == None:
    print('read_balpt(): did not find entry for runid=',runid,'in file=',bpfn)
    sys.exit(1)
  return bp


def default_params(mp):
  import collections
  import sys

  mp.CtdType                     = 4
  mp.DateCycleStarted            = 0
  mp.DateForRecovery             = 0
  mp.DateNextLevel2              = 0
  mp.DatePreludeEnded            = 0
  mp.DurationFastProfiling       = 0
  mp.EmaProcessNslide            = 25
  mp.EmaProcessNvals             = 50
  mp.FirstTwoProfsSpecial        = 0
  mp.FloatAlpha                  = -3.673e-06
  mp.FloatBeta                   =  3.2e-05
  mp.HeartBeatHolding            = 300
  mp.HeartBeatPark               = 3600
  mp.HeartBeatProf               = 6
  mp.IdFirstLevel2               = 0
  mp.NstuckThreshold             = 0
  mp.OpenAirValveAfter           = 1
  mp.PistonBuoyancyNudge         = 15
  mp.PistonFollowDefault         = 0
  mp.PistonFullExtension         = 227
  mp.PistonFullRetraction        = 9
  mp.PistonInitAscentHoldLong    = 93
  mp.PistonInitAscentHoldShort   = 93
  mp.PistonInitAscentLevel1      = 94
  mp.PistonInitAscentLevel2      = 82
  mp.PistonInitDescentProf       = 70
  mp.PistonInitDescentProfFirst  = 9
  mp.PistonInitialBuoyancyNudge  = 22
  mp.PistonParkPosition          = 42
  mp.PnpCycleLength              = 0
  mp.PrBotHoldLong               = 0.0
  mp.PrBotHoldShort              = 0.0
  mp.PrBotLevel1                 = 500.0
  mp.PrBotLevel2                 = 1000.0
  mp.PrBotYoyo                   = 0.0
  mp.PreludePressureThreshold    = 20.0
  mp.PreludeRepPeriod            = 100
  mp.PressureAnticipate          = 3.0
  mp.PressureDeep                = 1950
  mp.PressureFollowDefault       = 0.0
  mp.PressureFollowMax           = 0
  mp.PressureFollowMin           = 0
  mp.PressureMaxRecordRaw        = 100
  mp.PressureNearSurface         =  3.0
  mp.PressurePark                = 1000
  mp.PrTopHoldLong               = 0.0
  mp.PrTopHoldShort              = 0.0
  mp.PrTopYoyo                   = 0.0
  mp.RawEfSaveRep                = 10
  mp.RawEfSendFlagProfiling      = 1
  mp.RawEfSendFlagRecovery       = 0
  mp.RecoveryRepPeriod           = 900
  mp.TimeCycleHoldLongBeg        = 0
  mp.TimeCycleHoldLongEnd        = 0
  mp.TimeCycleRep                = 0
  mp.TimeCycleYoyoBeg            = 0
  mp.TimeCycleYoyoEnd            = 0
  mp.TimeDescentDeep             = 15000
  mp.TimeDescentPark             = 40000
  mp.TimeDescentProf             = 25000
  mp.TimeDescentProfHoldLong     = 0
  mp.TimeDescentProfHoldShort    = 0
  mp.TimeDown                    = 43200
  mp.TimeForRecovery             = 0
  mp.TimeGpsUpdateRep            = 180
  mp.TimeGpsGrabRep              = 30
  mp.TimeHoldLong                = 0
  mp.TimeHoldShort               = 0
  mp.TimeLevel2Rep               = 0
  mp.TimeOutNudge                = 8
  mp.TimePistonIfNoObs           = 0
  mp.TimePrelude                 = 0
  mp.TimeUp                      = 50000
  mp.TimeYoyoOnceBeg             = 0
  mp.TimeYoyoOnceEnd             = 0
  mp.TmoAscent                   = 40000
  mp.TmoGpsShort                 = 300
  mp.TmoGpsAfter                 = 180
  mp.TmoTelemetry                = 600
  mp.TmoXfrFastProfiling         = 1800
  mp.TmoConnect                  = 300
  mp.use_iPiston                 = 1
  mp.Vmin                        = 0.12
  mp.VstuckThreshold             = 0.01
  

def read_params(ifile):
  import collections
  mp = collections.namedtuple('MP',[])

  default_params(mp)

  ifp = open(ifile, mode='rt')
  if ifp < 0:
    print('read_params() cannot open ', ifile)
    exit (1)

  lineno = 0
  for line in ifp:
    lineno += 1

    if '#' in line:
      i = line.find('#')
      line = line[0:i]

    line = line.strip()

    if line.find('=') > 0:
      tok = line.split('=')
      if len(tok) != 2:
        print('read_params() line should have 2 tokens')
        print('  lineno=',lineno,'line=',line)
        sys.exit(1)

      varnam = tok[0].strip()
      varval = tok[1].strip()

      if not isvarnam(varnam):
        print('Note: read_params({0})'.format(ifile),end='')
        print(', lineno=',lineno,', unknown varnam skipped:',varnam)
        # print('  lineno=',lineno,'line=',line)
        continue

      if not isvarval(varnam, varval):
        print('read_params() variable name=',varnam,'has bad value=',varval)
        print('  ifile=',ifile,'lineno=',lineno,'line=',line)
        print('  quitting')
        sys.exit(1)

      if varnam == 'TimeDescentProf':
        mp.TimeDescentProf = int(varval)
      elif varnam == 'TmoAscent':
        mp.TmoAscent = int(varval)
      elif varnam == 'PreludeRepPeriod':
        mp.PreludeRepPeriod = int(varval)
      elif varnam == 'PreludePressureThreshold':
        mp.PreludePressureThreshold = float(varval)
      elif varnam == 'TimeYoyoOnceBeg':
        mp.TimeYoyoOnceBeg = int(varval)
      elif varnam == 'TimeYoyoOnceEnd':
        mp.TimeYoyoOnceEnd = int(varval)
      elif varnam == 'TimeCycleRep':
        mp.TimeCycleRep = int(varval)
      elif varnam == 'TimeCycleYoyoBeg':
        mp.TimeCycleYoyoBeg = int(varval)
      elif varnam == 'TimeCycleYoyoEnd':
        mp.TimeCycleYoyoEnd = int(varval)
      elif varnam == 'TimeCycleHoldLongBeg':
        mp.TimeCycleHoldLongBeg = int(varval)
      elif varnam == 'TimeCycleHoldLongEnd':
        mp.TimeCycleHoldLongEnd = int(varval)
      elif varnam == 'TimeHoldLong':
        mp.TimeHoldLong = int(varval)
      elif varnam == 'TimeHoldShort':
        mp.TimeHoldShort = int(varval)
      elif varnam == 'TimeLevel2Rep':
        mp.TimeLevel2Rep = int(varval)
      elif varnam == 'PrTopYoyo':
        mp.PrTopYoyo = float(varval)
      elif varnam == 'PrBotYoyo':
        mp.PrBotYoyo = float(varval)
      elif varnam == 'PrBotLevel1':
        mp.PrBotLevel1 = float(varval)
      elif varnam == 'PrBotLevel2':
        mp.PrBotLevel2 = float(varval)
      elif varnam == 'Vmin':
        mp.Vmin = float(varval)
      elif varnam == 'PistonInitAscentLevel1':
        mp.PistonInitAscentLevel1 = int(varval)
      elif varnam == 'PistonInitAscentLevel2':
        mp.PistonInitAscentLevel2 = int(varval)
      elif varnam == 'PistonInitDescentProf':
        mp.PistonInitDescentProf = int(varval)
      elif varnam == 'PistonInitDescentProfFirst':
        mp.PistonInitDescentProfFirst = int(varval)
      elif varnam == 'PressureFollowDefault':
        mp.PressureFollowDefault = float(varval)
      elif varnam == 'PressureFollowMax':
        mp.PressureFollowMax = float(varval)
      elif varnam == 'PressureFollowMin':
        mp.PressureFollowMin = float(varval)
      elif varnam == 'PistonFollowDefault':
        mp.PistonFollowDefault = int(varval)
      elif varnam == 'PrTopHoldLong':
        mp.PrTopHoldLong = float(varval)
      elif varnam == 'PrBotHoldLong':
        mp.PrBotHoldLong = float(varval)
      elif varnam == 'PrTopHoldShort':
        mp.PrTopHoldShort = float(varval)
      elif varnam == 'PrBotHoldShort':
        mp.PrBotHoldShort = float(varval)
      elif varnam == 'TimeDescentProfHoldLong':
        mp.TimeDescentProfHoldLong = int(varval)
      elif varnam == 'TimeDescentProfHoldShort':
        mp.TimeDescentProfHoldShort = int(varval)
      elif varnam == 'PistonInitAscentHoldLong':
        mp.PistonInitAscentHoldLong = int(varval)
      elif varnam == 'PistonInitAscentHoldShort':
        mp.PistonInitAscentHoldShort = int(varval)
      elif varnam == 'VstuckThreshold':
        mp.VstuckThreshold = float(varval)
      elif varnam == 'NstuckThreshold':
        mp.NstuckThreshold = int(varval)
      elif varnam == 'PistonBuoyancyNudge':
        mp.PistonBuoyancyNudge = int(varval)
      elif varnam == 'PistonInitialBuoyancyNudge':
        mp.PistonInitialBuoyancyNudge = int(varval)
      elif varnam == 'HeartBeatProf':
        mp.HeartBeatProf = int(varval)
      elif varnam == 'HeartBeatHolding':
        mp.HeartBeatHolding = int(varval)
      elif varnam == 'FloatAlpha':
        mp.FloatAlpha = float(varval)
      elif varnam == 'PressureNearSurface':
        mp.PressureNearSurface = float(varval)
      elif varnam == 'PressureAnticipate':
        mp.PressureAnticipate = float(varval)
      elif varnam == 'EmaProcessNvals':
        mp.EmaProcessNvals = float(varval)
      elif varnam == 'EmaProcessNslide':
        mp.EmaProcessNslide = float(varval)
      elif varnam == 'PistonFullRetraction':
        mp.PistonFullRetraction = float(varval)
      elif varnam == 'PistonFullExtension':
        mp.PistonFullExtension = float(varval)
      elif varnam == 'use_iPiston':
        mp.use_iPiston = int(varval)
      elif varnam == 'IdFirstLevel2':
        mp.IdFirstLevel2 = int(varval)
      elif varnam == 'PistonParkPosition':
        mp.PistonParkPosition = int(varval)
      elif varnam == 'TimeUp':
        mp.TimeUp = int(varval)
      elif varnam == 'TimeDown':
        mp.TimeDown = int(varval)
      elif varnam == 'RecoveryRepPeriod':
        mp.RecoveryRepPeriod = int(varval)
      elif varnam == 'TimePistonIfNoObs':
        mp.TimePistonIfNoObs = int(varval)
      elif varnam == 'DurationFastProfiling':
        mp.DurationFastProfiling = int(varval)
      elif varnam == 'CtdType':
        mp.CtdType = int(varval)
      elif varnam == 'ModeHoldLong':
        mp.ModeHoldLong = int(varval)
      elif varnam == 'ModeHoldShort':
        mp.ModeHoldShort = int(varval)
      elif varnam == 'TmoTelemetry':
        mp.TmoTelemetry = int(varval)
      elif varnam == 'PressureMaxRecordRaw':
        mp.PressureMaxRecordRaw = int(varval)
      elif varnam == 'TmoGpsShort':
        mp.TmoGpsShort = int(varval)
      elif varnam == 'TmoGpsAfter':
        mp.TmoGpsAfter = int(varval)
      elif varnam == 'TmoConnect':
        mp.TmoConnect = int(varval)
      elif varnam == 'TmoXfrMin':
        mp.TmoXfrMin = int(varval)
      elif varnam == 'TimeForRecovery':
        mp.TimeForRecovery = int(varval)
      elif varnam == 'TimeGpsGrabRep':
        mp.TimeGpsGrabRep = int(varval)
      elif varnam == 'TimeGpsUpdateRep':
        mp.TimeGpsUpdateRep = int(varval)
      elif varnam == 'TimeOutNudge':
        mp.TimeOutNudge = int(varval)
      elif varnam == 'TimePrelude':
        mp.TimePrelude = int(varval)
      elif varnam == 'TmoGpsUpdate':
        mp.TmoGpsUpdate = int(varval)
      elif varnam == 'TmoXfrFastProfiling':
        mp.TmoXfrFastProfiling = int(varval)
      elif varnam == 'TmoXfrProfiling':
        mp.TmoXfrProfiling = int(varval)
      elif varnam == 'TmoXfrRecovery':
        mp.TmoXfrRecovery = int(varval)
      elif varnam == 'TimeDescentPark':
        mp.TimeDescentPark = int(varval)
      elif varnam == 'TimeDescentDeep':
        mp.TimeDescentDeep = int(varval)
      elif varnam == 'TemperatureBallastPoint':
        mp.TemperatureBallastPoint = float(varval)
      elif varnam == 'SigmaThetaFollow':
        mp.SigmaThetaFollow = int(varval)
      elif varnam == 'SendOnlyGps':
        mp.SendOnlyGps = int(varval)
      elif varnam == 'SendCurrentGpsFirst':
        mp.SendCurrentGpsFirst = int(varval)
      elif varnam == 'SalinityBallastPoint':
        mp.SalinityBallastPoint = float(varval)
      elif varnam == 'RecoveryNRepConnect':
        mp.RecoveryNRepConnect = int(varval)
      elif varnam == 'RecoveryIRepConnect':
        mp.RecoveryIRepConnect = int(varval)
      elif varnam == 'RawSvBytesStop':
        mp.RawSvBytesStop = int(varval)
      elif varnam == 'RawEfSendFlagRecovery':
        mp.RawEfSendFlagRecovery = int(varval)
      elif varnam == 'RawEfSendFlagProfiling':
        mp.RawEfSendFlagProfiling = int(varval)
      elif varnam == 'RawEfSaveRep':
        mp.RawEfSaveRep = int(varval)
      elif varnam == 'PressurePark':
        mp.PressurePark = float(varval)
      elif varnam == 'PressureDeep':
        mp.PressureDeep = float(varval)
      elif varnam == 'PressureBallastPoint':
        mp.PressureBallastPoint = float(varval)
      elif varnam == 'PnpCycleLength':
        mp.PnpCycleLength = int(varval)
      elif varnam == 'PistonStoragePosition':
        mp.PistonStoragePosition = int(varval)
      elif varnam == 'PistonDeepProfilePosition':
        mp.PistonDeepProfilePosition = int(varval)
      elif varnam == 'PistonCountsPerCC':
        mp.PistonCountsPerCC = float(varval)
      elif varnam == 'OptodeMode':
        mp.OptodeMode = int(varval)
      elif varnam == 'OptodeMaxPr':
        mp.OptodeMaxPr = float(varval)
      elif varnam == 'OpenAirValveAfter':
        mp.OpenAirValveAfter = int(varval)
      elif varnam == 'OkVacuumCount':
        mp.OkVacuumCount = int(varval)
      elif varnam == 'MaxAirBladder':
        mp.MaxAirBladder = int(varval)
      elif varnam == 'KermitRtt':
        mp.KermitRtt = int(varval)
      elif varnam == 'KermitBps':
        mp.KermitBps = int(varval)
      elif varnam == 'IridiumNRep':
        mp.IridiumNRep = int(varval)
      elif varnam == 'IridiumIRep':
        mp.IridiumIRep = int(varval)
      elif varnam == 'HeartBeatPark':
        mp.HeartBeatPark = int(varval)
      elif varnam == 'GpsAlmanacOkAtLaunch':
        mp.GpsAlmanacOkAtLaunch = int(varval)
      elif varnam == 'FloatMass':
        mp.FloatMass = float(varval)
      elif varnam == 'FloatBeta':
        mp.FloatBeta = float(varval)
      elif varnam == 'FlbbMode':
        mp.FlbbMode = int(varval)
      elif varnam == 'FlbbMaxPr':
        mp.FlbbMaxPr = float(varval)
      elif varnam == 'FirstTwoProfsSpecial':
        mp.FirstTwoProfsSpecial = int(varval)
      elif varnam == 'EfCoefFactor':
        mp.EfCoefFactor = float(varval)
      elif varnam == 'DescentCtdScanType':
        mp.DescentCtdScanType = int(varval)
      elif varnam == 'DateForRecovery':
        mp.DateForRecovery = decode_date(varval)
        # print(varval,'mp.DateForRecovery=',mp.DateForRecovery)
      else:
        print('read_params(): varnam=[{0:s}]'.format(varnam),' not decoded')
        print('read_params(): varval=[{0:s}]'.format(varval),' not decoded')
        print('  ifile=',ifile,'lineno=',lineno,'line=',line)
        print('  using default value')
  ifp.close()
  return mp

def decode_date(varval):
  return timegm(strptime(varval,'%Y/%m/%d %H:%M:%S'))

def read_pts (ifile):
  import collections
  import sys

  pts = collections.namedtuple('PTS', [])

  ifd = open(ifile, mode='rt')
  if ifd < 0:
    print('error: cannot open ', ifile)
    sys.exit (1)

  pts.P = []
  pts.T = []
  pts.S = []

  lineno = 0

  for line in ifd:
    lineno += 1

    if '#' in line:
      i = line.find('#')
      line = line[0:i]

    if len(line.strip()) == 0:
      continue

    tup = line.split()
    if len(tup) != 3:
      print('pts should have 3 values: lineno=',lineno,'line=',line)
      sys.exit(1)

    try:
      pres  = float(tup[0].strip())
      temp  = float(tup[1].strip())
      sal   = float(tup[2].strip())
    except:
      print('cannot decode lineno=',lineno,'line=',line)
      sys.exit(1)

    pts.P.append(pres);
    pts.T.append(temp);
    pts.S.append(sal);

  ifd.close()

  if len(pts.P) == 0:
    print('error: no pts found')
    exit (1)

  return pts




def crc3kermit (buf):
  crcta = [0,4225,8450,12675,16900,21125,25350,29575, \
          33800,38025,42250,46475,50700,54925,59150,63375]
  crctb = [0,4489,8978,12955,17956,22445,25910,29887, \
          35912,40385,44890,48851,51820,56293,59774,63735]
  crc = 0
  for i in range(0,len(buf)):
    c    = crc ^ ord(buf[i])
    hi4  = (c & 240) >> 4
    lo4  = c & 15
    crc  = (crc >> 8) ^ (crcta[hi4] ^ crctb[lo4])
  return crc

def isvarnam(varnam):
  varnam_list = [
    'MaxAirBladder',
    'OkVacuumCount',
    'PistonBuoyancyNudge',
    'PistonDeepProfilePosition',
    'PistonFullExtension',
    'PistonFullRetraction',
    'PistonInitialBuoyancyNudge',
    'PistonParkPosition',
    'PistonStoragePosition',
    'PnpCycleLength',
    'PressurePark',
    'PressureDeep',
    'TimePrelude',
    'TimeDescentProf',
    'TimeDescentPark',
    'TimeDescentDeep',
    'TimeDown',
    'TimeUp',
    'TmoAscent',
    'PreludeRepPeriod',
    'PreludePressureThreshold',
    'IdFirstLevel2',
    'TimeYoyoOnceBeg',
    'TimeYoyoOnceEnd',
    'TimeCycleRep',
    'TimeCycleYoyoBeg',
    'TimeCycleYoyoEnd',
    'TimeCycleHoldLongBeg',
    'TimeCycleHoldLongEnd',
    'TimeHoldLong',
    'TimeHoldShort',
    'TimeLevel2Rep',
    'PrTopYoyo',
    'PrBotYoyo',
    'PrBotLevel1',
    'PrBotLevel2',
    'RawEfSaveRep',
    'RawEfSendFlagProfiling',
    'RawEfSendFlagRecovery',
    'Vmin',
    'PistonInitAscentLevel1',
    'PistonInitAscentLevel2',
    'PistonInitDescentProf',
    'PistonInitDescentProfFirst',
    'DurationFastProfiling',
    'DateForRecovery',
    'TimeForRecovery',
    'RecoveryRepPeriod',
    'RecoveryNRepConnect',
    'RecoveryIRepConnect',
    'TmoConnect',
    'TmoXfrFastProfiling',
    'TmoXfrProfiling',
    'TmoXfrRecovery',
    'TmoXfrMin',
    'ModemType',
    'ModemBaudRate',
    'PhoneNumbers',
    'KermitPacketLength',
    'TmoTelemetry',
    'debuglevel',
    'logport_key',
    'logport_baud',
    'EmaProcessNvals',
    'EmaProcessNslide',
    'TmoGpsUpdate',
    'TmoGpsShort',
    'TmoGpsAfter',
    'TimeGpsUpdateRep',
    'TimeGpsGrabRep',
    'RawSvBytesStop',
    'PressureAnticipate',
    'PressureNearSurface',
    'SigmaThetaFollow',
    'PressureFollowDefault',
    'PressureFollowMin',
    'PressureFollowMax',
    'PistonFollowDefault',
    'SalinityBallastPoint',
    'TemperatureBallastPoint',
    'PressureBallastPoint',
    'PistonCountsPerCC',
    'FloatMass',
    'FloatAlpha',
    'FloatBeta',
    'use_iPiston',
    'HeartBeatProf',
    'HeartBeatHolding',
    'TimeOutNudge',
    'CtdSamplePrFirst',
    'CtdSampleDelPr1',
    'CtdSampleDelPr2',
    'CtdSampleDelPr3',
    'CtdSampleDelPr4',
    'CtdSampleN1',
    'CtdSampleN2',
    'CtdSampleN3',
    'CtdSampleN4',
    'SimulationDpdtCoef',
    'PressureMaxRecordRaw',
    'DescentCtdScanType',
    'SendOnlyGps',
    'SendCurrentGpsFirst',
    'KermitBps',
    'KermitRtt',
    'GpsAlmanacOkAtLaunch',
    'FirstTwoProfsSpecial',
    'ModeHoldShort',
    'ModeHoldLong',
    'IridiumNRep',
    'IridiumIRep',
    'OpenAirValveAfter',
    'TimePistonIfNoObs',
    'PrTopHoldLong',
    'PrBotHoldLong',
    'PrTopHoldShort',
    'PrBotHoldShort',
    'TimeDescentProfHoldLong',
    'TimeDescentProfHoldShort',
    'PistonInitAscentHoldLong',
    'PistonInitAscentHoldShort',
    'VstuckThreshold',
    'NstuckThreshold',
    'SimulationPrBot',
    'FlbbMode',
    'FlbbMaxPr',
    'LoginName',
    'Password',
    'EfCoefFactor',
    'KermitWindowSlots',
    'HeartBeatPark',
    'ConsoleBaudRate',
    'PvtDateRef',
    'PvtTimeRep',
    'PvtTimeAllowStartDown',
    'PvtTimeAllowStartUp',
    'PvtWaitAtSurface',
    'Pvt_alpha',
    'Pvt_b0',
    'Pvt_pmin_offset',
    'PvtPistonDiffMax',
    'CtdType',
    'CtdPmin',
    'TM_pstart',
    'TM_fft_size',
    'TM_fft_navg',
    'TM_freqType',
    'TM_fBeg',
    'TM_snf_filterType',
    'TM_snf_freqType',
    'TM_snf_threshFactor',
    'TM_profnum_offset',
    'TM_gProfNumRequested',
    'TM_gBlkNumRequested',
    'TM_snf_t1FreqLvl_N',
    'TM_snf_t1Freq_0',
    'TM_snf_t1Freq_1',
    'TM_snf_t1Freq_2',
    'TM_snf_t1Freq_3',
    'TM_snf_t1Freq_4',
    'TM_snf_t1Freq_5',
    'TM_snf_t1Freq_6',
    'TM_snf_t1Freq_7',
    'TM_snf_t1Freq_8',
    'TM_snf_t1Freq_9',
    'TM_snf_t1Level_0',
    'TM_snf_t1Level_1',
    'TM_snf_t1Level_2',
    'TM_snf_t1Level_3',
    'TM_snf_t1Level_4',
    'TM_snf_t1Level_5',
    'TM_snf_t1Level_6',
    'TM_snf_t1Level_7',
    'TM_snf_t1Level_8',
    'TM_snf_t1Level_9',
    'TM_snf_t2FreqLvl_N',
    'TM_snf_t2Freq_0',
    'TM_snf_t2Freq_1',
    'TM_snf_t2Freq_2',
    'TM_snf_t2Freq_3',
    'TM_snf_t2Freq_4',
    'TM_snf_t2Freq_5',
    'TM_snf_t2Freq_6',
    'TM_snf_t2Freq_7',
    'TM_snf_t2Freq_8',
    'TM_snf_t2Freq_9',
    'TM_snf_t2Level_0',
    'TM_snf_t2Level_1',
    'TM_snf_t2Level_2',
    'TM_snf_t2Level_3',
    'TM_snf_t2Level_4',
    'TM_snf_t2Level_5',
    'TM_snf_t2Level_6',
    'TM_snf_t2Level_7',
    'TM_snf_t2Level_8',
    'TM_snf_t2Level_9',
    'TM_betaMin',
    'TM_betaMax',
    'TM_betaNominal',
    'OptodeMode',
    'OptodeMaxPr',
    'simulate_pressure',
    'simulate_hardware',
    'FloatId',
    'DateCycleStarted',
    'DatePreludeEnded',
    'DateNextLevel2'
  ]

  for i in range(0,len(varnam_list)):
    if varnam_list[i] == varnam:
      return True
  return False

def isvarval(varnam, varval):
  import re # regular expressions

  if varnam.find('Date') >= 0:
    if re.search('^\d\d\d\d/\d\d/\d\d \d\d:\d\d:\d\d$',varval):
      return True
  elif varnam == 'PhoneNumbers':
    return True
  elif varnam == 'ModemType':
    return True
  elif varnam == 'LoginName':
    return True
  elif varnam == 'Password':
    return True
  elif varnam == 'logport_key':
    return True
  elif varnam == 'ModemType':
    return True
  else: # the rest are numbers 
    if re.search('^[-]?\d+$',varval):
      return True
    if re.search('^[-]?\d+[.]\d*$',varval):
      return True
    if re.search('^[-]?\d+[eE][+-]\d+$',varval):
      return True
    if re.search('^[-]?\d+[.]\d*[eE][+-]\d+$',varval):
      return True
  return False

def mkmuline(line):

  if '#' in line:
    i = line.find('#')
    line = line[0:i]
    
  tup = line.split('=')

  if len(tup) != 2:
    print('mkmuline(): line should have "name = value"')
    return None

  varnam = tup[0].strip()
  varval = tup[1].strip()

  if not isvarnam(varnam):
    print('mkmuline(): bad varnam=',varnam)
    return None

  if not isvarval(varnam, varval):
    print('mkmuline(): bad varval=',varval,'varnam=',varnam)
    return None

  svv = str.format('{0}({1})',varnam,varval)

  crc = crc3kermit(svv)

  svvc = str.format('{0} {1:04x}',svv,crc)

  return svvc


# Density of standard mean ocean water (pure water)
def sw_smow(T):
  a0 = 999.842594;
  a1 =   6.793952e-2;
  a2 =  -9.095290e-3;
  a3 =   1.001685e-4;
  a4 =  -1.120083e-6;
  a5 =   6.536332e-9;
  T68 = T * 1.00024;

  return a0 + (a1 + (a2 + (a3 + (a4 + a5*T68)*T68)*T68)*T68)*T68;

def sw_dens0(S, T):
  import math
  T68 = T * 1.00024;

  #     UNESCO 1983 eqn(13) p17.

  b0 =  8.24493e-1;
  b1 = -4.0899e-3;
  b2 =  7.6438e-5;
  b3 = -8.2467e-7;
  b4 =  5.3875e-9;

  c0 = -5.72466e-3;
  c1 = +1.0227e-4;
  c2 = -1.6546e-6;

  d0 = 4.8314e-4;

  return sw_smow(T) + (b0 + (b1 + (b2 + (b3 + b4*T68)*T68)*T68)*T68)*S + \
      (c0 + (c1 + c2*T68)*T68)*S*math.sqrt(S) + d0*S*S;

# Secant bulk modulus (K) of sea water
def sw_seck(S, T, P):
  import math
  T68 = T * 1.00024;

  #  Pure water terms of the secant bulk modulus at atmos pressure.
  #  UNESCO eqn 19 p 18

  h3 = -5.77905E-7;
  h2 = +1.16092E-4;
  h1 = +1.43713E-3;
  h0 = +3.239908;   # [-0.1194975];

  AW  = h0 + (h1 + (h2 + h3*T68)*T68)*T68;

  k2 =  5.2787E-8;
  k1 = -6.12293E-6;
  k0 =  +8.50935E-5;   # [+3.47718E-5];

  BW  = k0 + (k1 + k2*T68)*T68;

  e4 = -5.155288E-5;
  e3 = +1.360477E-2;
  e2 = -2.327105;
  e1 = +148.4206;
  e0 = 19652.21;    # [-1930.06];

  KW  = e0 + (e1 + (e2 + (e3 + e4*T68)*T68)*T68)*T68;   #  eqn 19

  # --------------------------------------------------------------------
  #  SEA WATER TERMS OF SECANT BULK MODULUS AT ATMOS PRESSURE.
  # --------------------------------------------------------------------
  j0 = 1.91075E-4;

  i2 = -1.6078E-6;
  i1 = -1.0981E-5;
  i0 =  2.2838E-3;

  SR = math.sqrt(S);

  A  = AW + (i0 + (i1 + i2*T68)*T68 + j0*SR)*S;


  m2 =  9.1697E-10;
  m1 = +2.0816E-8;
  m0 = -9.9348E-7;

  B = BW + (m0 + (m1 + m2*T68)*T68)*S;   #  eqn 18

  f3 =  -6.1670E-5;
  f2 =  +1.09987E-2;
  f1 =  -0.603459;
  f0 = +54.6746;

  g2 = -5.3009E-4;
  g1 = +1.6483E-2;
  g0 = +7.944E-2;

  K0 = KW + (  f0 + (f1 + (f2 + f3*T68)*T68)*T68 
        +   (g0 + (g1 + g2*T68)*T68)*SR         )*S;      #  eqn 16

  P = P/10;  # convert from db to atmospheric pressure units
  return K0 + (A + B*P)*P;  #  eqn 15

def sw_dens(S,T,P):
  densP0 = sw_dens0(S,T);
  K      = sw_seck(S,T,P);
  P      = P/10;  #  convert from db to atm pressure units
  return  densP0 / (1-P/K);
