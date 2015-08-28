#! /usr/bin/env python2
# emasim.py -- simulate EM-APEX firmware to test various missions
# many variable names are the same as in emapex firmware
# at emaxag/src.  See: control.c, descent.c, ascent.c

"""
./emasim.py 6416  info/balpt pts/saanich mp/saanich1 10000
./emasim.py 6416  info/balpt pts/saanich mp/saanich1 10000
./emasim.py 6416  info/balpt pts/saanich mp/saanich2 10000
./emasim.py 9002k info/balpt pts/jamstec mp/jamstec  40000
./emasim.py 9002k info/balpt pts/jamstec mp/jamstec1 20000
./emasim.py 9002k info/balpt pts/jamstec mp/jamstec2 20000
./emasim.py 9002k info/balpt pts/jamstec mp/zero     20000
./emasim.py nick  info/balpt pts/cblast mp/nick     300000
"""

from __future__ import print_function

import sys
import os
import math
from scipy import interpolate
import numpy as np

import matplotlib
matplotlib.use('MacOSX')
import matplotlib.pyplot

from optparse import OptionParser
import collections

from emalib import read_balpt
from emalib import read_pts
from emalib import read_params
from emalib import pistonneutral


def ProperPowerOff(alarmsecs):
  global power_is_on
  power_is_on = False
  while alarmsecs > itimer() and tnow < endsecs:
    do_tstep()
  power_is_on = True

def dpdtcalc(pc, pcneut):
  bouyancy = (pc - pcneut) * 0.86      # grams per piston count
  if bouyancy > 0:
    dpdt = -math.sqrt(bouyancy) * 0.02 # ascend
  else:
    dpdt = math.sqrt(-bouyancy) * 0.02 # descend
  if dpdt < 0 and Pnow <= 0:
    dpdt = 0
  return dpdt

def print_info(note,trmchr):
  # global tnow, hpid, dpdt, PistonNow, Pnow
  print('{0:20s}'.format(note),end='')
  print(', tn={0:7.0f}'.format(tnow),end='')
  print(', it={0:7.0f}'.format(itimer()),end='')
  print(', hpid={0:3d}'.format(hpid),end='')
  print(', dP/dt={0:7.3f}'.format(dpdt),end='')
  print(', PC={0:6.1f}'.format(PistonNow),end='')
  print(', P={0:7.1f}'.format(Pnow),end=trmchr)

def iPistonInit():
  pass

def PreludeInit():
  global itime, state, Follow, mp, SetNextHoldTimeZero, PrfId, hpid, Pnow, PistonNow

  state = 'PRELUDE'
  PrfId = 0
  hpid = 0
  itime = 0
  SetNextHoldTimeZero = 0
  iPistonInit()
  if mission.TimePrelude == 0:
    PistonNow = mission.PistonFullRetraction
  else:
    PistonNow = mission.PistonFullExtension
  Pnow = 0
  Follow.Pressure = mission.PressureFollowDefault
  Follow.Piston = mission.PistonFollowDefault
  EmaMissionInit()
  mission.DateNextLevel2 = 0
  mission.DatePreludeEnded = 0
  mission.DateCycleStarted = 0


def EmaMissionInit():
  efpro_init()

def EmaHalfProfileInit(refsf):
  efpro_init()

def EmaControlAgent():
  ema_proc()

def efpro_init():
  print_info('efpro_init','\n')
  global ef
  ef.tef  = tnow
  ef.naccum = 0
  ef.nout = 0

def PreludeRun():
  print_info('prelude check','\n')
  if Pnow > mission.PreludePressureThreshold:
    PreludeTerminate()

def PreludeTerminate():
  print_info('PreludeTerminate','\n')
  mission.DatePreludeEnded = tnow;
  mission.DateCycleStarted = tnow;

def IsPreludeDone():
  if mission.DatePreludeEnded > 0:
    return True
  else:
    return False

def SequencePointsSetup ():
  global SeqPoint, vitals
  status = 1

# print('SequencePointsSetup(), vitals.FastProfilingFlag=',vitals.FastProfilingFlag)
# print('  mission.TmoAscent=',mission.TmoAscent)
  if vitals.FastProfilingFlag:
    SeqPoint.Descent = vitals.TimeDescentProf  # set in DescentProfInit()
    SeqPoint.Park = mission.TimeDescentProf
    SeqPoint.GoDeep = mission.TimeDescentProf
    SeqPoint.Ascent = vitals.TimeDescentProf + mission.TmoAscent
    SeqPoint.Telemetry = vitals.TimeDescentProf + mission.TimeUp
    SeqPoint.Recovery = mission.RecoveryRepPeriod
#   print('  vitals.TimeDescentProf=',vitals.TimeDescentProf)
  else:
    SeqPoint.Descent = mission.TimeDescentPark
    if DeepProfile():
      SeqPoint.Park = mission.TimeDown - mission.TimeDescentDeep
    else:
      SeqPoint.Park = mission.TimeDown
    SeqPoint.GoDeep = mission.TimeDown
    SeqPoint.Ascent = mission.TimeDown + mission.TmoAscent
    SeqPoint.Telemetry = mission.TimeDown + mission.TimeUp
    SeqPoint.Recovery = mission.RecoveryRepPeriod
#   print('  mission.TimeDown=',mission.TimeDown)
# print('  SeqPoint.Ascent 1 =',SeqPoint.Ascent)

  if SeqPoint.Ascent > SeqPoint.Telemetry and vitals.FastProfilingFlag == False:
    print('*** WARNING: SequencePointsSetup(): SeqPoint.Ascent > SeqPoint.Telemetry')
    print('  changing SeqPoint.Ascent from',SeqPoint.Ascent,end='')
    SeqPoint.Ascent = mission.TimeDown + mission.TimeUp / 2
    print(' to',SeqPoint.Ascent)
    # vitals.status |= BadSeqPnt; fixme

  if SeqPoint.Park > SeqPoint.GoDeep and vitals.FastProfilingFlag == False:
    SeqPoint.Park = mission.TimeDown
    # vitals.status |= BadSeqPnt; fixme

  if SeqPoint.Descent > SeqPoint.Park and vitals.FastProfilingFlag == False:
    SeqPoint.Descent = SeqPoint.Park / 2
    # vitals.status |= BadSeqPnt; fixme

# print('  SeqPoint.Ascent 2 =',SeqPoint.Ascent)


def DescentProfInit():
  global state, itime_ref, vitals, SeqPoint, hpid
  global SetNextHoldTimeZero, DescentProfControl

  PrfIdIncrement()
  hpid = PrfId * 2 - 1
  print('')
  print_info('DescentProfInit','\n')

  state = 'DESCENT_PROF'
  itime_ref = tnow
  vitals.DateStartedDown = tnow

  if PrfId == 1:
    DescentProfControl.PistonTarget = mission.PistonInitDescentProfFirst
  else:
    DescentProfControl.PistonTarget = mission.PistonInitDescentProf

  print_info('DescentProfInit',', PistonTarget={0:.0f}\n'.format(DescentProfControl.PistonTarget))

  vitals.PrfId = PrfId
  vitals.ProfilingFlag = True
  vitals.FastProfilingFlag = True
  vitals.DescentProfIsDone = False

  vitals.TimeDescentProf = mission.TimeDescentProf

  vitals.UsingPvt = False
  vitals.AscentIsDone = False
  vitals.RawEfSaveFlag = False
  vitals.LongHoldFlag = False

  if vitals.UsingPvt:
    lvl2 = False
  elif mission.TimeLevel2Rep == 0:
    lvl2 = False
  elif mission.IdFirstLevel2 == 0:
    lvl2 = False
  elif PrfId == mission.IdFirstLevel2:
    lvl2 = True
  elif PrfId > mission.IdFirstLevel2 \
  and mission.DateNextLevel2 > 0 \
  and tnow > mission.DateNextLevel2:
    lvl2 = True
  else:
    lvl2 = False

  if lvl2:
    vitals.Level2Flag = True
    vitals.LowerPressure = mission.PrBotLevel2
    vitals.UpperPressure = 0.0
    if mission.TimeLevel2Rep > 0:
      mission.DateNextLevel2 = tnow + mission.TimeLevel2Rep
    else:
      mission.DateNextLevel2 = 0
  else:
    vitals.Level2Flag = False
    vitals.LowerPressure = mission.PrBotLevel1
    vitals.UpperPressure = 0.0

  if mission.TimeCycleRep > 0:
    if mission.DateCycleStarted > 0 \
    and tnow >= mission.DateCycleStarted + mission.TimeCycleRep:
      ddt = tnow-mission.DateCycleStarted
      mission.DateCycleStarted = tnow
      print('DateCycleStarted %d %d dt last cycle: %d'%(tnow,mission.TimeCycleRep,ddt)) 

    if mission.DateCycleStarted > 0 \
    and mission.TimeCycleHoldLongBeg > 0 \
    and mission.TimeCycleHoldLongEnd > 0 \
    and tnow >= mission.DateCycleStarted + mission.TimeCycleHoldLongBeg \
    and tnow <= mission.DateCycleStarted + mission.TimeCycleHoldLongEnd:
      print('Long Starting: %d'%tnow) 
      vitals.LongHoldFlag = True
      DescentProfControl.TimeHold = mission.TimeHoldLong
      DescentProfControl.ModeHold = mission.ModeHoldLong
      vitals.UpperPressure = mission.PrTopHoldLong
      vitals.LowerPressure = mission.PrBotHoldLong
      if mission.TimeDescentProfHoldLong > 0:
        vitals.TimeDescentProf = mission.TimeDescentProfHoldLong
    else:
      print('Short Starting: %d'%tnow) 
      vitals.LongHoldFlag = True
      DescentProfControl.TimeHold = mission.TimeHoldShort      # about 2 hours
      DescentProfControl.ModeHold = mission.ModeHoldShort
      vitals.UpperPressure = mission.PrTopHoldShort
      vitals.LowerPressure = mission.PrBotHoldShort
      if mission.TimeDescentProfHoldShort > 0:
        vitals.TimeDescentProf = mission.TimeDescentProfHoldShort

  if vitals.LongHoldFlag:
    print_info('LongHoldFlag','\n')

  if SetNextHoldTimeZero:
    DescentProfControl.TimeHold = 0
    SetNextHoldTimeZero = 0

  vitals.YoyoFlag = 0

  if mission.TimeYoyoOnceBeg > 0 \
  and mission.TimeYoyoOnceEnd > 0 \
  and mission.DatePreludeEnded > 0 \
  and tnow >= mission.DatePreludeEnded + mission.TimeYoyoOnceBeg \
  and tnow < mission.DatePreludeEnded + mission.TimeYoyoOnceEnd:
    vitals.YoyoFlag = 1

# print('YoyoFlag=',vitals.YoyoFlag)
# print('  tnow=',tnow)
# print('  TimeYoyoOnceBeg=',mission.TimeYoyoOnceBeg)
# print('  TimeYoyoOnceEnd=',mission.TimeYoyoOnceEnd)
# print('  DatePreludeEnded=',mission.DatePreludeEnded)

  if mission.TimeCycleRep > 0 \
  and mission.TimeCycleYoyoBeg > 0 \
  and mission.TimeCycleYoyoEnd > 0 \
  and mission.DateCycleStarted > 0 \
  and tnow >= mission.DateCycleStarted + mission.TimeCycleYoyoBeg \
  and tnow < mission.DateCycleStarted + mission.TimeCycleYoyoEnd:
    vitals.YoyoFlag = 2

  if vitals.YoyoFlag:
    vitals.UpperPressure = mission.PrTopYoyo
    vitals.LowerPressure = mission.PrBotYoyo
    SetNextHoldTimeZero = 1    # used above to set this hold time
    print('YoyoFlag=',vitals.YoyoFlag,'LowerPressure=',vitals.LowerPressure)

  SequencePointsSetup()

  if not mission.OpenAirValveAfter:
    AirValveOpen()

  iPistonMoveAbs(DescentProfControl.PistonTarget)

  if mission.OpenAirValveAfter:
    AirValveOpen()

  DescentProfControl.RefTime = itimer ()
  DescentProfControl.TimeStampDpdt = DescentProfControl.RefTime + 60
  DescentProfControl.TimeStampObs = DescentProfControl.RefTime

  DescentProfControl.Holding = 0;

  EmaHalfProfileInit (vitals.RawEfSaveFlag)

  vitals.Pdeepest = 0


def DescentParkInit():
  global state, vitals, PrfId, itime_ref

  PrfIdIncrement()
  hpid = PrfId * 2 - 1
  print('')
  print_info('DescentParkInit','\n')

  state = 'DESCENT_PARK'
  itime_ref = tnow
  vitals.DateStartedDown = tnow

  vitals.PrfId = PrfId
  vitals.ProfilingFlag = True
  vitals.FastProfilingFlag = False
  vitals.DescentProfIsDone = False

  vitals.UsingPvt = False
  vitals.AscentIsDone = False
  vitals.RawEfSaveFlag = False
  vitals.LongHoldFlag = False

  vitals.ParkPOutOfBand = 0
  vitals.ActiveBallastAdjustments = 0

  SequencePointsSetup()
  vitals.SurfacePressure = Pnow
  AirValveOpen()
  iPistonMoveAbs(mission.PistonParkPosition)

def DescentParkRun():
  print_info('DescentParkRun','\n')
  return 1

def DescentParkTerminate():
  print_info('DescentParkTerminate','\n')
  return DescentParkRun()

def DeepProfile():
  if vitals.FastProfilingFlag:
    return 0
  if mission.PnpCycleLength > 0:
    if PrfId % mission.PnpCycleLength == 0:
      return 1
  return 0

def ParkInit():
  global state, vitals
  print()
  print_info('ParkInit','\n')
  state = 'PARK'
  vitals.ParkPOutOfBand = 0
  return 1

def ParkRun():
  global vitals
  MaxErr = 10;
  MaxP = mission.PressurePark + MaxErr;
  MinP = mission.PressurePark - MaxErr;
  if Pnow < MinP:
    if vitals.ParkPOutOfBand <= 0:
      vitals.ParkPOutOfBand -= 1
    else:
      vitals.ParkPOutOfBand = -1
    if vitals.ParkPOutOfBand <= -3:
      iPistonMoveRel(-1)
      vitals.ActiveBallastAdjustments += 1
      vitals.ParkPOutOfBand = 0
  elif Pnow > MaxP:
    if vitals.ParkPOutOfBand >= 0:
      vitals.ParkPOutOfBand += 1;
    else:
      vitals.ParkPOutOfBand = 1;
    if vitals.ParkPOutOfBand >= 3:
      iPistonMoveRel (1)
      vitals.ActiveBallastAdjustments += 1
      vitals.ParkPOutOfBand = 0
  else:
    vitals.ParkPOutOfBand = 0
  return 1

def ParkTerminate():
  global mission
  mission.PistonParkPosition = PistonNow
  return 1

def GoDeepInit():
  global state, vitals
  print('')
  print_info('GoDeepInit()','\n')
  state = 'GODEEP'
  # vitals.status |= DeepPrf; fixme
  iPistonMoveAbs(mission.PistonDeepProfilePosition)

def GoDeepRun():
  if Pnow >= mission.PressureDeep:
    GoDeepTerminate ('EXTEND')
    AscentInit()
    return False
  else:
    return True

def GoDeepTerminate(pistonadj):
  print()
  print_info('GoDeepTerminate()','\n')
  if pistonadj == 'EXTEND':
    if mission.PistonDeepProfilePosition < mission.PistonFullExtension:
      mission.PistonDeepProfilePosition += 1
  elif pistonadj == 'RETRACT':
    mission.PistonDeepProfilePosition -= 1
  else:
    print('GoDeepTerminate(): unknown pistonadj=',pistonadj)
    sys.exit(1)

def AscentInit():
  global state, hpid, watch_for_rising, ef, AscentControl, vitals
  hpid = PrfId * 2
  print('')
  print_info('AscentInit','\n')
  vitals.AscentIsDone = False
  
  state = 'ASCENT'

  if vitals.FastProfilingFlag:
    if mission.TimeCycleRep == 0:
      if vitals.Level2Flag:
        AscentControl.PistonTarget = mission.PistonInitAscentLevel2;
      else:
        AscentControl.PistonTarget = mission.PistonInitAscentLevel1;
    else:
      if vitals.LongHoldFlag:
        AscentControl.PistonTarget = mission.PistonInitAscentHoldLong;
      else:
        AscentControl.PistonTarget = mission.PistonInitAscentHoldShort;
  else:
    pcw = int(PistonNow) + mission.PistonInitialBuoyancyNudge;
    AscentControl.PistonTarget = pcw;

  AscentControl.InitialExtension = AscentControl.PistonTarget

  if dpdt > 0:
    watch_for_rising = True
  iPistonMoveAbs(AscentControl.PistonTarget)
  AscentControl.itimer_started_up = itimer()

  AscentControl.RefPressure = Pnow
  AscentControl.RefTime = itimer()

  AscentControl.TimeStamp = AscentControl.RefTime + 60
  AscentControl.TimeStampObs = AscentControl.RefTime;
  AscentControl.TimeStampNudge = AscentControl.RefTime;

  EmaHalfProfileInit(vitals.RawEfSaveFlag)

def AscentRun():
  global air_valve_closed
  global state
  global DescentProfControl

  if UpperPressureDetect (Pnow):
    print_info('AscentIsDone','\n')
    vitals.AscentIsDone = True
    if mission.CtdType == 4:
      tfin = tnow + Sbe41cpBinningSecs(vitals.Pdeepest)
      while tnow < tfin and tnow < endsecs:
        do_tstep()
      print_info('Sbe41cp_downloaded','\n')
    return

  EmaControlAgent()

  # firmware updates this when grabbing CTD data
  AscentControl.TimeStampObs = itimer()

  it = itimer()
  AscentAgent()
  if itimer() > it + 5:
    EmaControlAgent()

def AscentAgent():
  if itimer() - AscentControl.TimeStamp > 60:
    AscentControl.TimeStamp = itimer()

    if mission.TimePistonIfNoObs > 0 \
    and (itimer() - AscentControl.TimeStampObs) > mission.TimePistonIfNoObs \
    and (itimer() - AscentControl.TimeStampNudge) > mission.TimePistonIfNoObs:
      pcw = int(PistonNow + mission.PistonBuoyancyNudge)
      AscentControl.PistonTarget = pcw
      AscentControl.TimeStampNudge = itimer()
    elif -dpdt < mission.Vmin:
      pcw = int(min(PistonNow + mission.PistonBuoyancyNudge, \
                    mission.PistonFullExtension))
      if debug:
        print_info('beg extend','')
        print(', pcw=',pcw)
      AscentControl.PistonTarget = pcw

    AscentControl.RefTime = itimer()
    AscentControl.RefPressure = Pnow

  if AscentControl.PistonTarget > mission.PistonFullExtension:
    AscentControl.PistonTarget = mission.PistonFullExtension
  if AscentControl.PistonTarget < mission.PistonFullRetraction:
    AscentControl.PistonTarget = mission.PistonFullRetraction

  iPistonMoveAbsGo(AscentControl.PistonTarget)

def IsAscentDone():
  global vitals
  return vitals.AscentIsDone

def FindPistonFollow():
  pass

def AscentTerminate():
  print_info('AscentTerminate','\n')
  FindPistonFollow()
  StoreInFlash()

def TelemetryInit():
  print('')
  print_info('TelemetryInit','\n')
  global state, TelemetryIsDone
  state = 'TELEMETRY'
  TelemetryIsDone = False
  iPistonMoveAbs(vitals.SurfacePistonPosition + mission.PistonInitialBuoyancyNudge)
  AirValveClose()

def TelemetryRun():
  global TelemetryIsDone
  AirValveClose()
  SendHome()
  TelemetryIsDone = True

def IsTelemetryDone():
  return TelemetryIsDone

def AirValveOpen():
  global sho, air_valve_closed
  air_valve_closed = False
  print_info('AirValveOpen','\n')
  sho.t_air_valve_open.append(tnow)
  tend = tnow + 4 # use 4 seconds
  while tnow < tend:
    do_tstep()

def AirValveClose():
  global sho, air_valve_closed
  air_valve_closed = True
  print_info('AirValveClose','\n')
  sho.t_air_valve_close.append(tnow)
  tend = tnow + 4
  while tnow < tend:
    do_tstep()

def DescentProfRun():
  global DescentProfControl, watch_for_rising, vitals

  if Pnow > vitals.LowerPressure:
    print_info('DescentProfIsDone','')
    print(', LowerPressure=',vitals.LowerPressure)
    vitals.DescentProfIsDone = True
    watch_for_rising = True
    return

  if mission.NstuckThreshold > 0 and vitals.Nstuck >= mission.NstuckThreshold:
    print_info('DescentProfIsDone','')
    print(', Nstuck=',vitals.Nstuck)
    vitals.DescentProfIsDone = True
    watch_for_rising = True
    return

  if not DescentProfControl.Holding:
    EmaControlAgent()

  it = itimer()
  DescentProfAgent()

  if not DescentProfControl.Holding:
    if itimer() > it + 5:
      EmaControlAgent()

def DescentProfAgent():
  global Pnow, tnow,DescentProfControl
  stop_hold = 0
  start_hold = 0
  PistonMoveAllNowFlag = 0

  itimer_now = itimer()

  if DescentProfControl.Holding == 0 \
  and vitals.YoyoFlag == 0 \
  and Pnow > Follow.Pressure - mission.PressureAnticipate \
  and DescentProfControl.TimeHold > 0:
    if DescentProfControl.ModeHold == 1:
      # fixme -- this restarts a hold after holding once -- JHD Dec 27, 2012
      start_hold = 1
      DescentProfControl.iTimeStartedHold = itimer()
    elif DescentProfControl.ModeHold == 2 and mission.TimeCycleRep > 0:
      #print('time into cycle: %d time hold: %d'%(tnow-mission.DateCycleStarted,DescentProfControl.TimeHold)) 
      if tnow < mission.DateCycleStarted + DescentProfControl.TimeHold:
        start_hold = 2
    else:
      if itimer() < DescentProfControl.iTimeStartedDown +  \
                    DescentProfControl.TimeHold:
        start_hold = 3

    if start_hold:
      print('start_hold %d'%start_hold)
      print_info('Holding Starting','\n')
      DescentProfControl.Holding = start_hold
      DescentProfControl.PistonTarget = Follow.Piston
      PistonMoveAllNowFlag = 1

  elif DescentProfControl.Holding and DescentProfControl.TimeHold > 0:
    if DescentProfControl.ModeHold == 1:
      if itimer() >= DescentProfControl.iTimeStartedHold +  \
                    DescentProfControl.TimeHold:
        stop_hold = 1
    elif DescentProfControl.ModeHold == 2:
      #print('time into cycle: %d time hold: %d'%(tnow-mission.DateCycleStarted,DescentProfControl.TimeHold)) 
      if tnow >= mission.DateCycleStarted + DescentProfControl.TimeHold:
        stop_hold = 2
    else:
      if itimer() >= DescentProfControl.iTimeStartedDown +  \
                    DescentProfControl.TimeHold:
        stop_hold = 3

    if stop_hold > 0:
      print_info('Holding Stopping','\n')
      DescentProfControl.Holding = 0
      DescentProfControl.PistonTarget = Follow.Piston -  \
                    mission.PistonInitialBuoyancyNudge
      PistonMoveAllNowFlag = 1

  if DescentProfControl.Holding \
  and (Pnow < mission.PressureFollowMin or Pnow > mission.PressureFollowMax):
    Follow.Piston = mission.PistonFollowDefault
    Follow.Pressure = mission.PressureFollowDefault
    DescentProfControl.PistonTarget = Follow.Piston

  if not DescentProfControl.Holding \
  and itimer_now >= DescentProfControl.TimeStampDpdt + 60:
    DescentProfControl.TimeStampDpdt = itimer_now
    if dpdt < mission.Vmin:
      pcw = int(max(PistonNow - mission.PistonBuoyancyNudge, \
                    mission.PistonFullRetraction))
      if debug:
        print_info('beg retract','')
        print(', pcw=',pcw)
      DescentProfControl.PistonTarget = pcw

    DescentProfControl.RefTime = itimer_now;
    DescentProfControl.RefPressure = PistonNow;

  if PistonNow != DescentProfControl.PistonTarget:
    if PistonMoveAllNowFlag:
      PistonMoveAllNowFlag = 0;
      iPistonMoveAbs(DescentProfControl.PistonTarget)
    else:
      iPistonMoveAbsGo(DescentProfControl.PistonTarget)
# end of DescentProfAgent()

def IsDescentProfDone():
  global vitals
  return vitals.DescentProfIsDone

def Sbe41cpBinningSecs(Pmax): # time for SBE41cp data binning and transfer to APF9
  return Pmax / 90.0

def LoginSecs():
  return mission.TmoConnect

def IridiumSecs(): # time for Iridium data transfer
  global secs_carryover
  global vitals
  bytes  = mission.TmoGpsShort * 10.0
  bytes += vitals.Pdeepest * 30.0
  bytes += vitals.Nyoyo * vitals.Pdeepest * 30.0
  bytes += mission.TmoGpsAfter * 10.0
  if PrfId % mission.RawEfSaveRep == 1:
    n = mission.PressureMaxRecordRaw * 1600
    bytes += n
#   print('raw data saved:',n,'bytes')
  Bps = 200.0
  secs = LoginSecs() + bytes / Bps
  secs = int(secs + secs_carryover)
  secs_orig = secs
  if secs > mission.TmoXfrFastProfiling:
    print('secs=',secs,'limited to mission.TmoXfrFastProfiling=',mission.TmoXfrFastProfiling)
    secs = mission.TmoXfrFastProfiling
  if secs > mission.TmoTelemetry:
    print('secs=',secs,'limited to mission.TmoTelemetry=',mission.TmoTelemetry)
    secs = mission.TmoTelemetry
  secs_carryover = secs_orig - secs
  print('IridiumSecs=',secs,'carryover=',secs_carryover,' ',end='')
  print('Pdeepest={0:.1f}'.format(vitals.Pdeepest),'Nyoyo=',vitals.Nyoyo,'secs=',secs)
  vitals.Nyoyo = 0
  return secs

def SurfaceSecs():
  secs = mission.TmoGpsShort
  secs += IridiumSecs()
  secs += mission.TmoGpsAfter
  return secs

def DescentProfTerminate():
  print_info('DescentProfTerminate','')
  print(', PistonParkPosition=',mission.PistonParkPosition)
  iPistonMoveAbs(mission.PistonParkPosition)
  if mission.CtdType == 4:
    tfin = tnow + Sbe41cpBinningSecs(Pnow)
    while tnow < tfin and tnow < endsecs:
      do_tstep()
    print_info('Sbe41cp_downloaded','\n')
  StoreInFlash()

def iPistonMoveRel(pc):
  iPistonMoveAbs(PistonNow + pc)

def iPistonMoveAbs(pc):
  global piston_big_move, sho
  pc = int(pc)
  piston_big_move = True
  sho.t_big_move_beg.append(tnow)
  print_info('piston_big_move beg','')
  print(', PC move=',pc-PistonNow)
  iPistonMoveAbsGo(pc)
  while piston_big_move:
    do_tstep()
  sho.t_big_move_end.append(tnow)
  print_info('piston_big_move end','\n')

def iPistonMoveAbsGo(pc):
  global pcwant
  if pc > mission.PistonFullExtension:
    pc =  mission.PistonFullExtension
  if pc < mission.PistonFullRetraction:
    pc =  mission.PistonFullRetraction
  pcwant = int(pc)
# following is wrong:
# while PistonNow != pcwant and tnow < endsecs:
#   do_tstep()

def StoreInFlash():
  print_info('StoreInFlash','')
  print(', ef.nout=',ef.nout)

def UpperPressureDetect(p):
  global vitals
  if p < vitals.UpperPressure + mission.PressureNearSurface:
    vitals.SurfacePistonPosition = PistonNow
    return True
  else:
    return False

def ema_proc():
  global ef

  # account for EF data xfr & processing
  ef.tefprev = ef.tef
  ef.tef = tnow
  tdif = ef.tef - ef.tefprev

  if tdif > 30:
    #    print('t=',ef.tef,', EMA board had been sleeping for',tdif,'s')
    ef.nget = 0
  else:
    ef.nget = int(tdif / 1.024)

  ef.naccum += ef.nget
  if ef.naccum > 70:
    print('ef.naccum exceeded 70')
    sys.exit(1)

  ef.dur = ef.nget * 0.003                 # 3 ms/line to read data
  if ef.naccum >= mission.EmaProcessNvals:
    ef.dur += mission.EmaProcessNvals * 0.1 # time to compute LSQ
    ef.naccum -= mission.EmaProcessNslide
    if ef.naccum < 0:
      ef.naccum = 0
    ef.nout += 1

  if debug:
    print_info('ema_proc','')
    print(', dur=',ef.dur,', naccum=',ef.naccum)

  itime_stop = itimer() + ef.dur
  while itimer() < itime_stop and tnow < endsecs:
    do_tstep()

def AscentTimeOutInit():
  global ascent_timeout_is_done
  global vitals
  global rtc_finish
  global state
  print('')
  print_info('AscentTimeOutInit','\n')

  iPistonMoveAbs(mission.PistonFullExtension)
  vitals.AscentIsDone = False
  ascent_timeout_is_done = False
  rtc_finish = tnow + 43200     # 12 hours
  state = 'ASCENT_TIMEOUT'

def AscentTimeoutRun():
  global rtc_finish, ascent_timeout_is_done
  if tnow > rtc_finish:
    rtc_finish = 0
    ascent_timeout_is_done = True
    print_info('AscentTimeoutRun',', is finished\n')

def IsAscentTimeoutDone():
  return ascent_timeout_is_done

def RecoveryInit():
  global state
  print('')
  print_info('RecoveryInit','\n')
  state = 'RECOVERY'
  SetSeqPointRecovery()
  iPistonMoveAbs(mission.PistonFullExtension)
  # also should wait for Pnow < mission.PressureNearSurface # fixme

def RecoveryRun():
  global vitals
  vitals.SurfacePressure = Pnow
  SetSeqPointRecovery()
  SendHome()
  PrfIdIncrement()

def SendHome():
  itime_end = itimer() + SurfaceSecs()
  print(itime_end)
  print(itimer())
  print("SurfaceSecs(): %f"%SurfaceSecs())
  while itimer() < itime_end and tnow < endsecs:
    do_tstep()

def PrfIdIncrement():
  global PrfId
  PrfId += 1

def SetSeqPointRecovery():
  global SeqPoint
  SeqPoint.Recovery = mission.RecoveryRepPeriod

def plot_pvt():
  fig = matplotlib.pyplot.figure(num=1,figsize=(10,7))
  fig.canvas.set_window_title('EmaSim PVT')
  fig.clf()

  matplotlib.pyplot.subplots_adjust(hspace=0.1)

  ax1 = fig.add_subplot(3,1,1)
  ax2 = fig.add_subplot(3,1,2,sharex=ax1)
  ax3 = fig.add_subplot(3,1,3,sharex=ax1)

  ax1.plot(sho.t, sho.P,'.')
  ax1.invert_yaxis()
  ylim = ax1.get_ylim()
  ax1.set_ylim((ylim[0],-20.0))
  ax1.set_ylabel('Pressure')
  ax1.set_title('EM-APEX Simulation ' + paramfile)

  ax2.plot(sho.t, sho.dpdt,'.')
  ax2.invert_yaxis()
  ylim = ax2.get_ylim()
  ax2.set_ylim(ylim)
  ax2.set_ylabel('dP/dt')

  ax3.plot(sho.t, sho.pc,'.')
  ylim = ax3.get_ylim()
  ax3.set_ylim(ylim)
  ax3.set_xlabel('Time, s')
  ax3.set_ylabel('Piston Counts')

  for axn in (ax1, ax2, ax3):
    axn.hold(True)
    ylim = axn.get_ylim()
    if options.addlines:
      for i in range(len(sho.t_big_move_beg)):
        x = sho.t_big_move_beg[i]
        axn.plot((x,x),ylim,'c')
      for i in range(len(sho.t_big_move_end)):
        x = sho.t_big_move_end[i]
        axn.plot((x,x),ylim,'k')
      for i in range(len(sho.t_air_valve_open)):
        x = sho.t_air_valve_open[i]
        axn.plot((x,x),ylim,'r')
      for i in range(len(sho.t_deepest)):
        x = sho.t_deepest[i]
        axn.plot((x,x),ylim,'m')
    axn.set_ylim(ylim)
    axn.grid(True)

  xticklabels = ax1.get_xticklabels() + ax2.get_xticklabels()
  matplotlib.pyplot.setp(xticklabels, visible=False)

  matplotlib.pyplot.show()
  fig.show()
  pdffile = 'emasim.pdf'
  fig.savefig(pdffile)

def itimer():
  return itime

def do_tstep():
  global tnow, itime, sho, Pnow, dpdt, PistonNow
  global watch_for_rising
  global piston_big_move
  global DescentProfControl
  global AscentControl
  global vitals

  tnow += options.tstep
  itime = tnow - itime_ref

  if not mission.OpenAirValveAfter:
    print('not yet coded for mission.OpenAirValveAfter=',\
            mission.OpenAirValveAfter)
    sys.exit(1)

  if air_valve_closed:
    Pnow = 0
    dpdt = 0
  else:
    if Pnow >= 0:
      Tnow = interpolate.interp1d(pts.P,pts.T)(Pnow)
      Snow = interpolate.interp1d(pts.P,pts.S)(Pnow)
      pcneut = pistonneutral(Pnow,Tnow,Snow, \
        bp.P,bp.T,bp.S,bp.PC, bp.addwt, bp.alpha, bp.beta)
      dpdt  = dpdtcalc(PistonNow,pcneut)
      # add an internal wave below 50 m
      if Pnow>300.:
        waveom = 2.*np.pi/12.4/3600.
        waveamp = 0.
        dpdt+= waveamp*waveom*np.sin(waveom*tnow)
    else:
      Pnow = 0
      dpdt = 0

  Pnow += dpdt * options.tstep
  if Pnow > WaterDepth:
    Pnow = WaterDepth

  if watch_for_rising:
    if dpdt < 0:
      print_info('started rising','')
      print(', Overshoot={0:.1f} dbar'.format(Pnow-vitals.LowerPressure))
      sho.t_deepest.append(tnow)
      vitals.Pdeepest = Pnow
      watch_for_rising = False

  if power_is_on:

    if not mission.use_iPiston:
      print('not yet coded for use_iPiston=',use_iPiston)
      sys.exit(1)

    if PistonNow < pcwant: # extend
      PistonNow += 0.2 * options.tstep
      if PistonNow >= pcwant:
        PistonNow = pcwant
        if debug:
          print_info('end extend','\n')
        DescentProfControl.TimeStampDpdt = itimer()
        AscentControl.TimeStampDpdt = itimer()

    if PistonNow > pcwant: # retract
      PistonNow -= 0.2 * options.tstep
      if PistonNow <= pcwant:
        PistonNow = pcwant
        if debug:
          print_info('end retract','\n')
        DescentProfControl.TimeStampDpdt = itimer()
        AscentControl.TimeStampDpdt = itimer()

    if piston_big_move and PistonNow == pcwant:
      piston_big_move = False

  if tnow >= sho.tprev + options.tplt - 0.1:
    sho.tprev = tnow
    sho.t.append(tnow)
    sho.P.append(Pnow)
    sho.pc.append(PistonNow)
    sho.dpdt.append(dpdt)

def MissionAgent():
  # emulate MissionAgent() in control.c
  # called every power cycle

  global state, RecoveryFlag, vitals

  HeartBeat = 8

  SeqTime = itimer()
  alarm = SeqTime + HeartBeat

  if state != 'INACTIVE' \
  and mission.DateForRecovery > 0 \
  and tnow >= mission.DateForRecovery:
    RecoveryFlag = True
  elif state != 'INACTIVE' \
  and mission.TimeForRecovery > 0 \
  and mission.DatePreludeEnded > 0 \
  and tnow >= (mission.DatePreludeEnded + mission.TimeForRecovery):
    RecoveryFlag = True
  else:
    RecoveryFlag = False

  ##################################################################
  # first set of if, elif, ..., else checks for state changes
  ##################################################################

  if state == 'RECOVERY' and RecoveryFlag == False:
    print("RecoveryFlag has become unset in RECOVERY state so start descent\n")
    if mission.TimePrelude > 0:
      DescentParkInit()
    else:
      DescentProfInit()
  elif state == 'PRELUDE' and RecoveryFlag:
    PreludeTerminate ()
    # following seems wrong -- shouldn't we go to ascent? -- fixme?
    if mission.TimePrelude > 0:
      DescentParkInit()
    else:
      DescentProfInit()
  elif state == 'PRELUDE' and mission.TimePrelude > 0  \
                    and SeqTime >= mission.TimePrelude:
    PreludeTerminate()
    DescentParkInit()         # ARGO
  elif state == 'PRELUDE' and mission.TimePrelude == 0  \
                    and mission.DatePreludeEnded > 0:
    DescentProfInit()         # Hurricane and Eddies
  elif state == 'PRELUDE' and mission.DatePreludeEnded > 0:
    DescentProfInit()
  elif state == 'DESCENT_PARK' and RecoveryFlag:
    DescentParkTerminate()
    AscentInit()
  elif state == 'DESCENT_PARK' and SeqTime >= SeqPoint.Descent:
    DescentParkTerminate()
    ParkInit()
  elif state == 'DESCENT_PROF' and RecoveryFlag:
    DescentProfTerminate()
    AscentInit()
  elif state == 'DESCENT_PROF' and SeqTime >= SeqPoint.Descent:
    DescentProfTerminate()
    AscentInit()
  elif state == 'DESCENT_PROF' and IsDescentProfDone():
    DescentProfTerminate()
    AscentInit()
  elif state == 'PARK' and RecoveryFlag:
    ParkTerminate()
    AscentInit()
  elif state == 'PARK' and SeqTime >= SeqPoint.Park:
    ParkTerminate()
    if DeepProfile():
      GoDeepInit()
    else:
      AscentInit()
  elif state == 'GODEEP' and RecoveryFlag:
    AscentInit()
  elif state == 'GODEEP' and SeqTime >= SeqPoint.GoDeep:
    GoDeepTerminate('RETRACT')
    AscentInit()
  elif state == 'ASCENT' and SeqTime >= SeqPoint.Ascent:
    print('SeqTime=',SeqTime)
    print('SeqPoint.Ascent=',SeqPoint.Ascent)
    print('mission.TimeDown=',mission.TimeDown)
    print('mission.TmoAscent=',mission.TmoAscent)
    AscentTimeOutInit()
  elif state == 'ASCENT' and IsAscentDone():
    # print('ASCENT and IsAscentDone')
    AscentTerminate()
    if RecoveryFlag:
      RecoveryInit()
    elif vitals.YoyoFlag:
      vitals.Nyoyo += 1
      print('Nyoyo=',vitals.Nyoyo,'Pnow=',Pnow)
      DescentProfInit()
    else:
      TelemetryInit()
  elif state == 'ASCENT_TIMEOUT' and IsAscentTimeoutDone():
    AscentTerminate()
    if RecoveryFlag:
      RecoveryInit()
    else:
      TelemetryInit()
  elif state == 'TELEMETRY' \
  and (SeqTime >= SeqPoint.Telemetry or IsTelemetryDone()):
    print_info('TelemetryDone','')
    print(' secs_carryover=',secs_carryover)
    if RecoveryFlag:
      RecoveryInit()
    elif mission.TimePrelude > 0:
      DescentParkInit()       # standard for ARGO
    elif mission.DurationFastProfiling > 0 \
    and mission.DatePreludeEnded > 0 \
    and tnow >= mission.DatePreludeEnded + mission.DurationFastProfiling:
      DescentParkInit()
    else:
      DescentProfInit()

  #######################################################################
  # second set of if, elif, ..., else does stuff for the possibly new state
  #######################################################################


  if state == 'PRELUDE':
    PreludeRun()
    SeqTime = itimer()
    if IsPreludeDone():
      alarm = SeqTime + HeartBeat
    else:
      alarm = SeqTime - SeqTime % mission.PreludeRepPeriod  \
                    + mission.PreludeRepPeriod - 1
    if mission.TimePrelude > 0 and alarm > mission.TimePrelude:
      alarm = mission.TimePrelude + HeartBeat

  elif state == 'DESCENT_PARK':
    DescentParkRun()
    SeqTime = itimer()
    alarm = SeqTime - SeqTime % mission.HeartBeatPark + mission.HeartBeatPark
    if alarm > SeqPoint.Descent:
      alarm = SeqPoint.Descent + HeartBeat

  elif state == 'DESCENT_PROF':
    SeqTime1 = itimer()
    DescentProfRun()
    SeqTime = itimer()
    alarm = SeqTime + mission.HeartBeatProf
    if DescentProfControl.Holding > 0:
      alarm = SeqTime + mission.HeartBeatHolding
    if alarm < SeqTime + mission.HeartBeatProf:
      alarm = SeqTime + mission.HeartBeatProf
    if alarm > SeqPoint.Descent:
      alarm = SeqPoint.Descent + HeartBeat

  elif state == 'PARK':
    ParkRun()
    SeqTime = itimer()
    alarm = SeqTime - SeqTime % mission.HeartBeatPark + mission.HeartBeatPark
    if alarm > SeqPoint.Park:
        alarm = SeqPoint.Park + HeartBeat

  elif state == 'GODEEP':
    if GoDeepRun():
      SeqTime = itimer()
      alarm = SeqTime - SeqTime % 300 + 300
    else:
      # Ascent starts in one HeartBeat
      alarm = itimer() + HeartBeat
    if alarm > SeqPoint.GoDeep:
      alarm = SeqPoint.GoDeep + HeartBeat

  elif state == 'ASCENT_TIMEOUT':
    AscentTimeoutRun()
    if IsAscentTimeoutDone ():
      alarm = itimer() + HeartBeat
    else:
      alarm = itimer() + 3600
 
  elif state == 'ASCENT':
    SeqTime1 = itimer()
    AscentRun()
    SeqTime2 = itimer()
    alarm = SeqTime1 + mission.HeartBeatProf
    if alarm < SeqTime2 + mission.HeartBeatProf:
      alarm = SeqTime2 + mission.HeartBeatProf

  elif state == 'TELEMETRY':
    TelemetryRun()
    SeqTime = itimer()
    alarm = itimer() + 10
    if alarm > SeqPoint.Telemetry:
      alarm = SeqPoint.Telemetry + HeartBeat

  elif state == 'RECOVERY':
    RecoveryRun()
    SeqTime = itimer()
    alarm = SeqTime - SeqTime % mission.RecoveryRepPeriod \
             + mission.RecoveryRepPeriod - 1
    if alarm > SeqPoint.Recovery:
      alarm = SeqPoint.Recovery + HeartBeat

  else:
    print('unknown state=',state)
    sys.exit(1)

  # if alarm-itimer() > HeartBeat:
  #   print('state=',state,'long alarm-itimer()=',alarm-itimer())

  ProperPowerOff(alarm)
# end of MissionAgent.c


if __name__ == '__main__':

  print("emasim.py: simulate emapex pressure versus time")

  parser = OptionParser()

  parser.add_option("-v", "--verbose",
    action="store_true", dest="verbose", default=False,
    help="print status messages to stdout")

  parser.add_option("-a", "--addlines",
    action="store_true", dest="addlines", default=False,
    help="print status messages to stdout")

  parser.add_option("-s", "--tstep", dest="tstep",
    type="int", metavar="N", default=3, 
    help="integer sub-sample interval [default: %default]")

  parser.add_option("-p", "--tplt", dest="tplt",
    type="int", metavar="N", default=30, 
    help="integer sub-sample interval [default: %default]")

  (options, args) = parser.parse_args()

  debug = options.verbose

  if len(args) != 5:
    print('Usage: emasim.py <runid> <balptfile> <ptsfile> <paramfile> <endsecs>')
    parser.print_help()
    sys.exit(1)

  runid     = args[0]
  balptfile = args[1]
  ptsfile   = args[2]
  paramfile = args[3]
  endsecs   = int(args[4])


  # ballast point for this float
  bp  = read_balpt(runid,balptfile)

  pts = read_pts(ptsfile)       # simulation CTD profile
  mission  = read_params(paramfile)  # simulation mission parameters

  WaterDepth = pts.P[-1]

  sho      = collections.namedtuple('SHO', [])
  vitals   = collections.namedtuple('VITALS', [])
  ef       = collections.namedtuple('EF', [])
  SeqPoint = collections.namedtuple('SEQPOINT', [])
  DescentProfControl = collections.namedtuple('DPC',[])
  AscentControl      = collections.namedtuple('AC',[])
  Follow   = collections.namedtuple('FOLLOW', [])

  SeqPoint.PreludeFinished = False
  SeqPoint.Descent = 0
  SeqPoint.Park = 0
  SeqPoint.GoDeep = 0
  SeqPoint.Ascent = 0
  SeqPoint.Telemetry = 0
  SeqPoint.Recovery = 0

  DescentProfControl.TimeHold = 0


  # bp.addwt -= 80


  if mission.use_iPiston != 1:
    print('not coded yet for use_iPiston != 1')
    sys.exit(1)

  if mission.OpenAirValveAfter != 1:
    print('not coded yet for OpenAirValveAfter != 1')
    sys.exit(1)

  PistonNow  = mission.PistonFullRetraction

  # initial values
  PrfId = 0
  hpid = 0
  Pnow = 0       # pressure, dbar
  dpdt = 0       # dP/dt
  pcwant = PistonNow
  DescentProfControl.TimeStampDpdt = 0
  AscentControl.TimeStamp = 0
  watch_for_rising = False
  piston_big_move = False
  air_valve_closed = False
  secs_carryover = 0

  tnow = 0
  itime_ref = tnow

  sho.tprev = 0
  sho.t  = []
  sho.P  = []
  sho.pc = []
  sho.dpdt  = []
  sho.t_air_valve_open = []
  sho.t_air_valve_close = []
  sho.t_big_move_beg = []
  sho.t_big_move_end = []
  sho.t_deepest = []

  vitals.Nstuck = 0
  vitals.Nyoyo = 0

  power_is_on = True

  PreludeInit()

  while tnow < endsecs:
    do_tstep()
    MissionAgent()

  print('')
  print_info('end emasim','\n')
  print('len(sho.P)=',len(sho.P))

  plot_pvt()

