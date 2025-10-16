'''
    gbscamper.py - Scamper interfacing for Gameboard load_application
'''

import sys
import scamper
import datetime

def _feedme(ctrl, inst, vps):
  if len(vps[inst]) == 0:
    inst.done()
  else:
    ctrl.do_ping(vps[inst].pop(0), inst=inst)

def _pingall(mux_path):
  vps = {}
  ctrl = scamper.ScamperCtrl(morecb=_feedme, param=vps, mux=mux_path)
  ctrl.add_vps(ctrl.vps())
  for inst in ctrl.instances():
    vps[inst] = ['8.8.8.8', '8.8.4.4']

  # issue measurements as each VP asks for a new measurement
  while not ctrl.is_done():
    o = None
    try:
      o = ctrl.poll(timeout=datetime.timedelta(seconds=10))
    except Exception as e:
      print(f'got exception {e}')
      continue

    # if ctrl.poll() returns None, either all measurements are
    # complete, or we timed out.  say what happened.
    if o is None:
      if ctrl.is_done():
        print('done')
      else:
        print('timed out')
      break

    print(f'{o.inst.name} {o.dst} {o.min_rtt}')

  return 0


def _get_vps(mux_path):
  vps = {}
  ctrl = scamper.ScamperCtrl(morecb=_feedme, param=vps, mux=mux_path)
  ctrl.add_vps(ctrl.vps())
  for inst in ctrl.instances():
    vps[inst] = ['8.8.8.8', '8.8.4.4']

  # issue measurements as each VP asks for a new measurement
  while not ctrl.is_done():
    o = None
    try:
      o = ctrl.poll(timeout=datetime.timedelta(seconds=10))
    except Exception as e:
      print(f'got exception {e}')
      continue

    # if ctrl.poll() returns None, either all measurements are
    # complete, or we timed out.  say what happened.
    if o is None:
      if ctrl.is_done():
        print('done')
      else:
        print('timed out')
      break

    print(f'{o.inst.name} {o.dst} {o.min_rtt}')

  return 0


if __name__ == '__main__':
    
  sys.exit(_main(sys.argv[1]))