# Environment setup notes
# cd C:\Users\15038\Desktop\HardWare\mm_report 
# python -m venv venv
# .\venv\Scripts\Activate.ps1
# python issues.py
# pip install requests PyGithub pyinstaller
# pyinstaller --onefile --name mm_test.exe equips_v0.py

"""equip driver Module deal with base equips operation.
  new equips are encouraged to be inherited from bATEinst_base
"""

import time
import traceback
import re
import struct
import math
import os
import sys
import scipy.interpolate as intpl 
from scipy.io import savemat,loadmat
from pyvisa import constants as pyconst
import pyvisa as visa
import serial
import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple
from mapping import Mapping

class bATEinst_Exception(Exception):pass

class ResourceBase:
    _RM = None

    @classmethod
    def open_VisaRM(cls):
        if cls._RM is None:
            cls._RM = visa.ResourceManager()
        return cls._RM
    
    @classmethod
    def close_VisaRM(cls):
        if cls._RM is not None:
            try:
                cls._RM.close()
            except Exception:
                pass
            finally:
                cls._RM = None

class bATEinst_base(object):
    Equip_Type = "None"
    Model_Supported = ["None"]
    bATEinst_doEvent = None
    isRunning = False
    RequestStop = False
    VisaRM = None   
    
    def __init__(self, name="", visa_address=""):
        self.Name = name
        self.VisaAddress = visa_address
        self.Inst = None
        self.chan_num = 0

    def __del__(self):
        self.close()

    def set_error(self, ss):
        raise(bATEinst_Exception("Equip %s error:\n%s" % (self.Name, ss)))
    
    def isvalid(self):
        return True if self.VisaAddress else False
    
    def inst_open(self):
        if self._is_open():
            return self.Inst

        if not self.Inst:
            if not self.VisaAddress:
                self.set_error("Equip Address has not been set!")
            try:
                self.Inst = ResourceBase.open_VisaRM().open_resource(self.VisaAddress)
            except:
                time.sleep(2)
                ResourceBase.close_VisaRM()
                ResourceBase.open_VisaRM()
                if not self.Inst:
                    self.Inst = ResourceBase.open_VisaRM().open_resource(self.VisaAddress)
        return self.Inst
        
    def inst_close(self):
        if self.Inst:
            try:
                self.Inst.close()
            except:
                pass
            finally:
                self.Inst = None
            
    def callback_after_open(self): pass
    
    def set_visa_timeout_value(self,tmo):
        self.Inst.set_visa_attribute(pyconst.VI_ATTR_TMO_VALUE,tmo)

    def _is_open(self) -> bool:
        inst = getattr(self, "Inst", None)
        if inst is None:
            return False
        try:
            return getattr(inst, "session", None) is not None
        except Exception:
            return False

        
    def check_open(self):
        if not self._is_open():
            self.inst_open()
        
    def close(self):
        try:
            if self.Inst:
                self.inst_close()
        except:
            pass
        self.Inst = None

    # from resource manager, import available instruments and return their visa address
    @staticmethod
    def get_insts():
        insts = ResourceBase.open_VisaRM().list_resources()

        return insts
    
    def read(self):
        self.check_open()
        try:
            ss = self.Inst.read()
        except Exception as e:
            self.set_error("read error\n info:" +str(e))
        return ss
    
    def write(self, ss):
        self.check_open()
        try:
            if isinstance(ss,list):
                for k in ss:
                    self.Inst.write(k)
            else:
                self.Inst.write(ss)
        except Exception as e:
            self.set_error("Write error\n info:" +str(e))

    def query(self, ss):
        self.write(ss)
        return self.read()

    def write_raw(self, vv: list):
        self.check_open()
        if isinstance(vv, list):
            vv = bytes(vv)
        self.Inst.write_raw(vv)

    def read_raw(self, n: int):
        self.check_open()
        ss = self.Inst.read_bytes(n)
        return ss

    def write_block(self, v):
        self.write_raw(list(("#8%08d" % len(v)).encode()) + v)

    def read_block(self,cmd=None):
        if cmd:
            self.write(cmd)
        ss = self.read_raw(2)
        if ss[0] != b'#'[0]:
            self.set_error("Equip read block error")
        sz = self.read_raw(int(ss[1])-48)
        n = int(bytes(sz).decode())
        return self.read_raw(n)
        
    def delay (self, sec):
        time.sleep(sec)
        
    def x_write(self, vvs, chx=""):
        if isinstance(vvs, str):
            vvs = vvs.splitlines()
        res = []
        for cc in vvs:
            cc = cc.strip()
            if not cc:
                continue
            # Replace the $CHX$ placeholder with the provided channel string.
            cc = cc.replace("$CHX$", chx)
            if re.match(r"\$WAIT *= *(\d+) *\$",cc):
                self.delay(int(re.match(r"\$WAIT *= *(\d+) *\$", cc).group(1))/1000)
            else:
                if cc.find("?") >= 0:
                    res += [self.query(cc)]
                else:
                    self.write(cc)
        return res

    def is_number(self, str):
        try:
            if str=='NaN':
                return False
            float(str)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def fn_relative(fn=None, sub_folder=None):
        if fn and os.path.isabs(fn):
            return fn
        else:
            if getattr(sys, 'frozen', False):
                hd = os.path.dirname(sys.executable)
            else:
                hd, _ = os.path.split(os.path.realpath(__file__))

            if sub_folder is None:
                # No sub_folder and no fn means use the program directory.
                path = hd if fn is None else os.path.join(hd, fn)
            else:
                # Build the subdirectory path first.
                folder = os.path.join(hd, sub_folder)
                if fn is None:
                    path = folder   # Just return the folder path.
                else:
                    path = os.path.join(folder, fn)

            path = os.path.realpath(path)

            # Ensure parents exist for files, or create the directory itself.
            if fn is None:
                os.makedirs(path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(path), exist_ok=True)

            return path

    def get_filelist(self, fpp,modes=".py" ):
        Filelist = []
        for home, dirs, files in os.walk(fpp ):
            for filename in files:
                if filename.lower().endswith(modes):
                    Filelist.append(os.path.join(home, filename))
        return Filelist

    def load_cal_cable_loss(self,fn,freq_unit_rate=1e6, domain='V'):        
        """ freq_unit_rate: used to make sure all units is consistent inside the driver,default 1e6
        """
        if isinstance(freq_unit_rate, str):
            freq_unit_rate = {"MHz":1e6,"KHz":1e3,"Hz":1}[freq_unit_rate]
            
        if self.is_number(fn):
            freq = [0,1e9]
            loss = [float(fn)]*2 #[10**(float(fn/20))]*2
        else:
            with open(self.fn_relative(fn,"calibration"), "rt") as fid:
                xys = fid.readlines()
            freq = [float(k.split("\t")[0])*freq_unit_rate for k in xys]
            loss = [float(k.split("\t")[1]) for k in xys] 
            loss = [10**(k/20) for k in loss] if domain == 'V' else loss
        return intpl.interp1d(freq,loss,bounds_error=False, fill_value="extrapolate")
    
    def load_matfile(self, fn):
        return loadmat(fn)
    
    def save_matfile(self, fn, mm):        
        try:
            # Pre-check the data types to catch format issues early.
            # self._check_mat_data(mm)
            # Perform the save.
            savemat(fn, mm)
            return True
        except Exception as e:
            # Log detailed errors to aid troubleshooting.
            print(f"Failed to save MAT file: {str(e)}")
            print("Traceback:\n", traceback.format_exc())
            return False
        
    def _check_mat_data(self, data_dict):
        for key, value in data_dict.items():
            if isinstance(value, (list, np.ndarray)):
                # Check whether the list/array mixes types.
                types = set(type(x) for x in value) if isinstance(value, list) else {value.dtype.type}
                if len(types) > 1:
                    raise ValueError(f"Data '{key}' mixes types {types} and cannot be stored in a MAT file")

class InstrumentBase(bATEinst_base):

    Equip_Type = ""  
    Model_Supported = []

    default_update_frequency = 50

    def __init__(self, name="", visa_address=""):
        super().__init__(name, visa_address)

    def rst(self):
        self.x_write("*RST")

    @staticmethod
    def normalize_imp_str(imp) -> str:
        """
        Normalize user input so the driver always receives a canonical impedance string.
        - Accepts: "50", "INF", "HiZ"/"hiz"/"HIZ", etc.
        - Returns: normalized strings such as "50" or "INF".
        """
        if imp is None:
            return None
        s = str(imp).strip()
        if s.lower() in ("hiz", "hi-z", "hi_z"):
            return Mapping.mapping_imp_high_z  # "INF"
        return s

class instAWG(InstrumentBase):
    Equip_Type = "awg"
    AWG_MODE_DC = "DC"
    AWG_MODE_SIN = "SIN"
    max_amp_mapping: dict[int, float] = None
    min_amp: float = None

    chan_num = 2 

    def __init__(self, name="", visa_address=""):
        super().__init__(name, visa_address)

    def set_amp(self, amp: float, ch: int):
        self.set_error("Function not implemented")

    def get_amp(self, ch: int) -> float:
        self.set_error("Function not implemented")

    def set_freq(self, freq: float, ch: int|str):
        self.set_error("Function not implemented")

    def get_freq(self, ch: int) -> float:
        self.set_error("Function not implemented")

    def set_imp(self, imp: str, ch: int):
        self.set_error("Function not implemented")

    def set_on(self, ch:int):
        self.set_error("Function not implemented")

    def rst(self):
        super().rst()

class instOSC(InstrumentBase):
    Equip_Type = "osc"
    chan_num = 4

    def __init__(self, name="", visa_address=""):
        super().__init__(name, visa_address)
        self.sampling_rate = 0 

    def set_x(self, xscale: float, xoffset: float=None):
        self.set_error("Function not implemented")

    def set_y(self, ch: int, yscale: float, yoffset: float):
        self.set_error("Function not implemented")

    def get_y(self, ch: int) -> Tuple[float]:
        self.set_error("Function not implemented")

    def get_sample_rate(self) -> int:
        self.set_error("Function not implemented")

    def quick_measure(self):
        self.set_error("Function not implemented")

    def trig_measure(self, ch: int):
        self.set_error("Function not implemented")
    
    def read_raw_waveform(self, ch: int, points: int) -> Tuple[np.array]:
        self.set_error("Function not implemented")

    def set_free_run(self):
        self.set_error("Function not implemented")

    def set_trig_rise(self, ch: int, level: float):
        self.set_error("Function not implemented")
    
    def set_on(self, ch: int):
        self.set_error("Function not implemented")

    def set_imp(self, imp: str, ch: int):
        self.set_error("Function not implemented")

    def set_coup(self, coup: str, ch: int):
        self.set_error("Function not implemented")

    def rst(self):
        super().rst()

class instMM(InstrumentBase):

    # mappings
    Equip_Type = "MM"
    MM_MODE_V  = "V"
    MM_MODE_I  = "I"
    MM_MODE_R  = "R"
    MM_MODE_R4 = "R4"
    MM_RANGE_AUTO = "AUTO"
    MM_AC = "AC"
    MM_DC = "DC"

    chan_num = 2

    # alert messages
    alert_incompatible_mode = 'Mode is not supported'

    def __init__(self, name="", visa_address=""):
        super().__init__(name, visa_address)
        self.current_mode = None
        self.current_mode_for_equip = None
        self.current_ac_dc = None
        self.current_range = None
        self.chan_num = 2

    # change the mode setting
    def set_mode(self, mode=MM_MODE_V, ac_dc = MM_AC):
        self.set_error("Function not implemented")

    # measure and retun the current power(I/V) 
    def measure(self):
        self.set_error("Function not implemented")

    def measure_quick(self):
        return self.measure()

    # set the range
    def set_range(self, rng=MM_RANGE_AUTO):
        self.set_error("Function not implemented")

    def set_speed(self, speed):
        self.set_error("Function not implemented")

    def capture_waveform(self):
        self.set_error("Function not implemented")
        return []

    def measure_i(self):
        self.set_mode(self.MM_MODE_I)
        return self.measure()

    def measure_v(self):
        self.set_mode(self.MM_MODE_V)
        return self.measure()

    def measure_r(self):
        self.set_mode(self.MM_MODE_R)
        return self.measure()

class instKS_34461A(instMM):

    Equip_Type = "MM"
    MM_MODE_V  = "V"
    MM_MODE_I  = "I"
    MM_MODE_R  = "R"
    MM_MODE_R4 = "R4"
    MM_RANGE_AUTO = "AUTO"
    MM_AC = "AC"
    MM_DC = "DC"

    chan_num = 2

    def __init__(self, name="", visa_address=""):
        super().__init__(name)
        self.current_mode = None
        self.current_mode_for_equip = None
        self.current_ac_dc = None
        self.current_range = None
        self.VisaAddress   = visa_address
        self.chan_num = 2

    # change the mode setting
    def set_mode(self, mode=MM_MODE_V, ac_dc = MM_AC):

        # auto mapping for diifferent modes
        # throw alert if the input mode is invalid
        if len(mode) <= 2:
            mode = "VOLT" if mode == 'V' else "CURR" if mode == 'I' else None
            if mode == None: raise ValueError(self.alert_incompatible_mode)
        self.x_write(["CONF:%s:%s" %(mode, ac_dc), "*OPC?"] )

        # update the setting into the data collection
        self.current_mode = mode
        self.current_ac_dc = ac_dc

    # measure and retun the current power(I/V) 
    def measure(self):
        return float(self.x_write(f"MEAS:{self.current_mode}:{self.current_ac_dc}? {self.current_range}")[0])

    # set the range
    def set_range(self, rng=MM_RANGE_AUTO):
        self.x_write([f"CONF:{self.current_mode}:{self.current_ac_dc} {rng}", "*OPC?"])

        # update the setting into the data collection
        self.current_range = rng

class instOSC_DS1104(InstrumentBase):
    Model_Supported = ["DS1104"]
    
    def __init__(self):
        super().__init__("osc")
        self.VisaAddress="USB0::0x05E6::0x2450::04542396::INSTR"
        
    def callback_after_open(self):
        self.set_visa_timeout_value(10000)
    
    def set_x(self, xscale=None, offset=None):
        self.x_write([":TIM:SCAL %6e" %xscale, "*OPC?"] if xscale else [] 
                    +[":TIM:OFFS %6e" %offset, "*OPC?"] if offset is not None else [] 
        )

    def set_y(self,ch, yscale=None, yoffset=None):
        self.x_write([":CHAN%d:SCAL %6e" %(ch, yscale), "*OPC?"] if yscale else [] 
                    +[":CHAN%d:OFFS %6e" %(ch, yoffset), "*OPC?"] if yoffset is not None else [] 
        )
    
    def measure(self):
        # Stop -> single acquisition and wait for the trigger to complete.
        self.x_write([":STOP", "*OPC?", "SING", "$WAIT=1$"])
        t0 = time.time()
        # Poll for up to 20 seconds until the scope reports STOP.
        while time.time() - t0 < 20.0:
            try:
                stat = self.query(":TRIG:STAT?").strip()
            except Exception:
                break
            if stat.upper().startswith("STOP"):
                break
            time.sleep(0.1)
    def start(self):
        self.x_write([":RUN"])
    
    def load_setup(self, fn):
        self.x_write([":LOAD:SET '%s'" % fn, "*OPC?"])
        
    def save_image(self, fn):
        self.x_write([":STORage:IMAGe:TYPE PNG", "*OPC?"])
        self.write(":DISPlay:DATA?")
        dd = self.read_block()
        with open(fn, "wb") as fid:
            fid.write(dd)

    def save_waveform(self, fn):
        res = [k.strip() == "1" for k in self.x_write([":CHAN1:DISP?", ":CHAN2:DISP?", ":CHAN3:DISP?", ":CHAN4:DISP?"])]
        chs = []
        for k in range(len(res)):
            if res[k]:
                chs.append(k + 1)
        vvs = []
        for ch in chs:
            self.x_write([":WAV:SOUR CHAN%d" % ch,
                          ":WAV:MODE RAW", ":WAV:FORM BYTE",
                          ])
            point, av, xinc, xor, xref, yinc, yor, yref = [float(k) for k in
                                                           self.x_write(":WAV:PRE?")[0].split(",")[2:]]
            dd = []
            for st in range(1, int(point) + 1, 125000):
                self.x_write(
                    [":WAV:STAR %d" % st, ":WAV:STOP %d" % (st + 125000 - 1 if point >= st + 125000 - 1 else point)])
                self.write(":WAV:DATA?")
                dd += self.read_block()
            vvs.append([(k - yor - yref) * yinc for k in dd])
        pp = min([len(k) for k in vvs])
        with open(fn, "wt") as fid:
            for tt in range(pp):
                fid.write("\t".join(["%g" % ((tt - xor - xref) * xinc)]
                                     + ["%g" % vvs[k][tt] for k in range(len(chs))]) + "\n")
                           
class instOSC_MDO34(instOSC):
    Model_Supported = ["MDO34", "MDO3024"]
    chan_num = 4

    def __init__(self, name, visa_address: str):
        super().__init__(name=name, visa_address=visa_address)
        self.chan_num = 4

    def set_time_base(self, time_scale: float):
        xscale=time_scale
        self.set_x(xscale=xscale)

    def set_x(self, xscale: float, xoffset: float = 0.0):
        self.x_write([":HORizontal:SCAle %6e" %xscale, "*OPC?"])

        if xoffset is not None:
            self.x_write([":HORizontal:POSition %6e" %xoffset, "*OPC?"])

    def set_y(self,ch: int, yscale:float, yoffset:float = None):
        self.x_write([":CH%d:SCAL %6e" %(ch, yscale), "*OPC?"])

        if yoffset is not None:
            self.x_write([":CH%d:OFFS %6e" %(ch, yoffset), "*OPC?"])

    def get_y(self, ch: int) -> Tuple[float]:

        scale = float(self.x_write(f"CH{ch}:SCAL?")[0].strip())
        offs = float(self.x_write(f"CH{ch}:OFFS?")[0].strip())

        return scale, offs
    
    def trig_measure(self):
        self.x_write([
            "*CLS",                    
            "ACQuire:STATE 0",
            "ACQuire:STOPAfter SEQuence",   
            "TRIGger:A:MODe NORMal",      
            "ACQuire:STATE 1",        
        ])

        t0 = time.time()
        while time.time()-t0 < 15.0:        
            if self.query("ACQuire:STATE?").strip() == "0":
                break
            time.sleep(0.05)

    def quick_measure(self):
        self.x_write(["*CLS",
                      "ACQuire:STOPAfter SEQuence",
                      "ACQuire:STATE RUN"])
        
        t0 = time.time()
        while time.time() - t0 < 4.0:
            try:
                st = self.query("TRIGger:STATE?").strip().upper()
                if st != "RUN":
                    break
            except Exception:
                pass
            time.sleep(0.05)
        
        self.x_write(["TRIGger FORCe"])
        
        t0 = time.time()
        while time.time()-t0 < 15.0:        
            if self.query("ACQuire:STATE?").strip() == "0":
                break
            time.sleep(0.05)
        
    def auto_run(self):
        self.x_write(["TRIGger:A:MODe AUTO", "ACQuire:STOPAfter RUNStop", "ACQuire:STATE 1"])
    
    def load_setup(self, fn):
        self.x_write([":LOAD:SET '%s'" % fn, "*OPC?"])
        
    def save_image(self, fn):
        self.x_write([":SAV:IMAG:FILEF PNG", "SAV:IMAG "+fn, "*OPC?"])
        # dd = self.read_block()
        # with open(fn, "wb") as fid:
        #     fid.write(dd)

    def save_waveform(self, fn: str, ch: int = None):
        self.x_write([":WFMO:ENC BIN",":WFMO:BN_FMT RI",":WFMO:BYT_O MSB",":WFMO:BYT_N 1",f":DAT:SOU CH{ch if ch else 1}",
                      ":DAT:START 1",":DAT:STOP 20000000","*OPC?"])
        pre = self.x_write(":WFMO?")[0].split(";")
        n = int(pre[6])
        x_inc = float(pre[10])
        x_off = float(pre[11])
        y_inc = float(pre[14])
        y_off = float(pre[15])
        n_block = 200000
        with open(fn, "wb") as fid:
            hd = struct.pack("5d",n, x_inc,x_off,y_inc,y_off)
            fid.write(hd)
            for k in range(1,n,n_block):
                self.x_write([f":DAT:SOU CH{ch}", ":DAT:START %d" % k,":DAT:STOP %d" % (k+n_block-1 if (k+n_block-1) <=n else n ),"*OPC?"])
                self.write("CURV?")
                dd = self.read_block()
                fid.write(dd)

    def read_raw_waveform(self, ch: int = None, points: int = None) -> Tuple[np.array]:

        time.sleep(0.2)

        try:
            _pts = int(points) if points is not None else None
        except Exception:
            _pts = None
        self.x_write([":WFMO:ENC BIN",
                      ":WFMO:BN_FMT RI",
                      ":WFMO:BYT_O MSB",
                      ":WFMO:BYT_N 1",
                      f":DAT:SOU CH{ch if ch else 1}",
                      ":DAT:START 1",
                      f":DAT:STOP {_pts if _pts else 20000000}",
                      "*OPC?"])
        
        n_total = int(float(self.x_write(":WFMO:NR_PT?")[0]))
        x_inc   = float(self.x_write(":WFMO:XINCR?")[0])
        x_zero  = float(self.x_write(":WFMO:XZERO?")[0])
        pt_off  = int(float(self.x_write(":WFMO:PT_OFF?")[0]))
        y_mult  = float(self.x_write(":WFMO:YMULT?")[0])
        y_off   = float(self.x_write(":WFMO:YOFF?")[0])  
        y_zero  =  float(self.x_write(":WFMO:YZEro?")[0])

        n = n_total if _pts is None else min(n_total, int(_pts))
        n = int(n)
        raw_bytes = bytearray(n)
        n_block = 20000

        for k in range(1, n, n_block):
            start = k
            stop = min(k + n_block - 1, n)
            self.x_write([f":DAT:SOU CH{ch}", 
                          f":DAT:START {start}",
                          f":DAT:STOP {stop}",
                          "*OPC?"])
            self.write("CURV?")
            block = self.read_block()
            raw_bytes[start - 1 : start - 1 + len(block)] = block

        raw     = np.frombuffer(raw_bytes, dtype=np.int8)
        idx   = np.arange(n, dtype=np.float64)
        times = x_zero + x_inc * (idx - pt_off)
        volts   = (raw.astype(np.float64) - y_off) * y_mult + y_zero

        return times, volts

    def read_raw_data(self):
        self.x_write(("CURV?"))

    def get_sample_rate(self) -> int:
        sampling_rate = int(float(self.x_write(["ACQ:MAXS?"])[0].strip()))
        return sampling_rate
    
    def set_free_run(self):
        self.x_write(["*CLS", "TRIGger:A:MODe AUTO"])
    
    def set_trig_rise(self, ch:int, level:float):
        self.x_write(["*CLS", 
                      "TRIGger:A:TYPe EDGE", 
                      f"TRIGger:A:EDGE:SOURce CH{ch}", 
                      "TRIGger:A:EDGE:SLOpe RISE", 
                      f"TRIGger:A:LEVel {level}"
        ])

    def set_on(self, ch:int):
        self.x_write(f":SELect:CH{ch} ON")

    def set_imp(self, imp: str, ch: int=None):
        if imp == Mapping.mapping_imp_high_z:
            imp = "1e6"
        self.x_write(f"CH{ch}:TERmination {imp}")    

    def set_coup(self, coup: str, ch):
        self.x_write(f":CH{ch}:COUP {coup}")

    def rst(self):
        super().rst()    
            
class instOSC_MDO3024(instOSC):
    Model_Supported = ["MDO3024", "MDO34"]
    chan_num = 4

    def __init__(self, name, visa_address: str):
        super().__init__(name=name, visa_address=visa_address)
        self.chan_num = 4

    def set_time_base(self, time_scale: float):
        xscale=time_scale
        self.set_x(xscale=xscale)

    def set_x(self, xscale: float, xoffset: float = 0.0):
        self.x_write([":HORizontal:SCAle %6e" %xscale, "*OPC?"])

        if xoffset is not None:
            self.x_write([":HORizontal:POSition %6e" %xoffset, "*OPC?"])

    def set_y(self,ch: int, yscale:float, yoffset:float = None):
        self.x_write([":CH%d:SCAL %6e" %(ch, yscale), "*OPC?"])

        if yoffset is not None:
            self.x_write([":CH%d:OFFS %6e" %(ch, yoffset), "*OPC?"])

    def get_y(self, ch: int) -> Tuple[float]:
        
        scale = float(self.x_write(f"CH{ch}:SCAL?")[0].strip())
        offs = float(self.x_write(f"CH{ch}:OFFS?")[0].strip())

        return scale, offs
    
    def trig_measure(self):
        self.x_write([
            "*CLS",                    
            "ACQuire:STATE 0",
            "ACQuire:STOPAfter SEQuence",   
            "TRIGger:A:MODe NORMal",      
            "ACQuire:STATE 1",        
        ])

        t0 = time.time()
        while time.time()-t0 < 15.0:        
            if self.query("ACQuire:STATE?").strip() == "0":
                break
            time.sleep(0.05)

    def quick_measure(self):
        time.sleep(0.1)
        self.x_write(["*CLS",
                      "ACQuire:STOPAfter SEQuence",
                      "ACQuire:STATE RUN"])

        t0 = time.time()
        while time.time() - t0 < 4.0:
            time.sleep(0.05)
            try:
                st = self.query("TRIGger:STATE?").strip().upper()
                if st == "READY" or st == "ARMED":
                    break
                elif st == "SAVE": 
                    time.sleep(0.5)
                    if self.query("TRIGger:STATE?").strip().upper() == "SAVE":
                        return
            except Exception:
                pass

        time.sleep(0.5)
        self.x_write(["TRIGger FORCe"])

        while time.time()-t0 < 10.0:        
            if self.query("ACQuire:STATE?").strip() == "0":
                return
            time.sleep(0.1)
        
    def auto_run(self):
        self.x_write(["TRIGger:A:MODe AUTO", "ACQuire:STOPAfter RUNStop", "ACQuire:STATE 1"])
    
    def load_setup(self, fn):
        self.x_write([":LOAD:SET '%s'" % fn, "*OPC?"])
        
    def save_image(self, fn):
        self.x_write([":SAV:IMAG:FILEF PNG", "SAV:IMAG "+fn, "*OPC?"])
        # dd = self.read_block()
        # with open(fn, "wb") as fid:
        #     fid.write(dd)

    def save_waveform(self, fn: str, ch: int = None):
        self.x_write([":WFMO:ENC BIN",":WFMO:BN_FMT RI",":WFMO:BYT_O MSB",":WFMO:BYT_N 1",f":DAT:SOU CH{ch if ch else 1}",
                      ":DAT:START 1",":DAT:STOP 20000000","*OPC?"])
        pre = self.x_write(":WFMO?")[0].split(";")
        n = int(pre[6])
        x_inc = float(pre[10])
        x_off = float(pre[11])
        y_inc = float(pre[14])
        y_off = float(pre[15])
        n_block = 200000
        with open(fn, "wb") as fid:
            hd = struct.pack("5d",n, x_inc,x_off,y_inc,y_off)
            fid.write(hd)
            for k in range(1,n,n_block):
                self.x_write([f":DAT:SOU CH{ch}", ":DAT:START %d" % k,":DAT:STOP %d" % (k+n_block-1 if (k+n_block-1) <=n else n ),"*OPC?"])
                self.write("CURV?")
                dd = self.read_block()
                fid.write(dd)

    def read_raw_waveform(self, ch: int = None, points: int = None) -> Tuple[np.array]:

        time.sleep(0.2)

        try:
            _pts = int(points) if points is not None else None
        except Exception:
            _pts = None
        self.x_write([":WFMO:ENC BIN",
                      ":WFMO:BN_FMT RI",
                      ":WFMO:BYT_O MSB",
                      ":WFMO:BYT_N 1",
                      f":DAT:SOU CH{ch if ch else 1}",
                      ":DAT:START 1",
                      f":DAT:STOP {_pts if _pts else 20000000}",
                      "*OPC?"])
        
        n_total = int(float(self.x_write(":WFMO:NR_PT?")[0]))
        x_inc   = float(self.x_write(":WFMO:XINCR?")[0])
        x_zero  = float(self.x_write(":WFMO:XZERO?")[0])
        pt_off  = int(float(self.x_write(":WFMO:PT_OFF?")[0]))
        y_mult  = float(self.x_write(":WFMO:YMULT?")[0])
        y_off   = float(self.x_write(":WFMO:YOFF?")[0])  
        y_zero  =  float(self.x_write(":WFMO:YZEro?")[0])

        n = n_total if _pts is None else min(n_total, int(_pts))
        n = int(n)
        raw_bytes = bytearray(n)
        n_block = 20000

        for k in range(1, n, n_block):
            start = k
            stop = min(k + n_block - 1, n)
            self.x_write([f":DAT:SOU CH{ch}", 
                          f":DAT:START {start}",
                          f":DAT:STOP {stop}",
                          "*OPC?"])
            self.write("CURV?")
            block = self.read_block()
            raw_bytes[start - 1 : start - 1 + len(block)] = block

        raw     = np.frombuffer(raw_bytes, dtype=np.int8)
        idx   = np.arange(n, dtype=np.float64)
        times = x_zero + x_inc * (idx - pt_off)
        volts   = (raw.astype(np.float64) - y_off) * y_mult + y_zero

        return times, volts

    def read_raw_data(self):
        self.x_write(("CURV?"))

    def get_sample_rate(self) -> int:
        sampling_rate = int(float(self.x_write(["ACQ:MAXS?"])[0].strip()))
        return sampling_rate
    
    def set_free_run(self):
        self.x_write(["*CLS", "TRIGger:A:MODe AUTO"])
    
    def set_trig_rise(self, ch:int, level:float):
        self.x_write(["*CLS", 
                      "TRIGger:A:TYPe EDGE", 
                      f"TRIGger:A:EDGE:SOURce CH{ch}", 
                      "TRIGger:A:EDGE:SLOpe RISE", 
                      f"TRIGger:A:LEVel {level}"
        ])

    def set_on(self, ch:int):
        self.x_write(f":SELect:CH{ch} ON")

    def set_imp(self, imp: str, ch: int=None):
        if imp == Mapping.mapping_imp_high_z:
            imp = "1e6"
        self.x_write(f"CH{ch}:TERmination {imp}") 

    def set_coup(self, coup: str, ch):
        self.x_write(f":CH{ch}:COUP {coup}")

    def rst(self):
        super().rst()

class instOSC_DHO1202(instOSC):
    Model_Supported = ["DHO1202", "DHO1204"]
    chan_num = 2

    def set_x(self, xscale: float, xoffset: float = None):
        """
        Configure horizontal scale (seconds/div) and optional horizontal offset.
        """
        cmds = []
        if xscale is not None:
            cmds.append(f":TIMebase:MAIN:SCALe {xscale}")
        if xoffset is not None:
            cmds.append(f":TIMebase:MAIN:OFFSet {xoffset}")
        if cmds:
            cmds.append("*OPC?")
            self.x_write(cmds)

    def set_y(self, ch: int, yscale: float, yoffset: float = None):
        """
        Configure vertical scale (volts/div) and vertical offset.
        """
        cmds = []
        if yscale is not None:
            cmds.append(f":CHANnel{ch}:SCALe {yscale}")
        if yoffset is not None:
            cmds.append(f":CHANnel{ch}:OFFSet {yoffset}")
        if cmds:
            cmds.append("*OPC?")
            self.x_write(cmds)

    def get_y(self, ch: int):
        """
        Read the current channel's (vertical scale, vertical offset) in V/div and volts.
        """
        scale = float(self.x_write(f":CHANnel{ch}:SCALe?")[0].strip())
        offs  = float(self.x_write(f":CHANnel{ch}:OFFSet?")[0].strip())
        return (scale, offs)

    def get_sample_rate(self) -> int:
        """
        Read the current sample rate in Hz.
        """
        sr = float(self.query(":ACQuire:SRATe?"))             
        self.sampling_rate = int(sr)
        return self.sampling_rate


    def trig_measure(self):
        """
        Triggered acquisition mode.
        """
        self.x_write(["*CLS", ":STOP", ":SINGle"])

        t0 = time.time()
        while time.time() - t0 < 15.0:
            try:
                if self.query(":TRIGger:STATus?").strip().upper() == "STOP": 
                    break
            except Exception:
                pass
            time.sleep(0.05)


    def quick_measure(self):
        """
        Quick acquisition mode.
        """
        self.x_write([
            "*CLS",                         
            ":STOP",                             
            ":SINGle"                            
        ])

        t0 = time.time()
        while time.time() - t0 < 2.0:
            try:
                if self.query(":TRIGger:STATus?").strip().upper() == "WAIT":  # Waiting for trigger
                    break
            except Exception:
                pass
            time.sleep(0.05)

        # Poll until the acquisition finishes.
        t0 = time.time()
        while time.time() - t0 < 15.0:
            try:
                if self.query(":TRIGger:STATus?").strip().upper() == "STOP":  # Acquisition complete
                    break
            except Exception:
                pass
            time.sleep(0.05)

    def read_raw_waveform(self, ch: int, points: int):
        """
        Read the raw waveform from a channel and convert it to time/voltage arrays.
        """

        time.sleep(0.2)

        self.x_write([":STOP"])  
        self.x_write([
            f":WAVeform:SOURce CHANnel{ch}",
            ":WAVeform:MODE RAW",
            ":WAVeform:FORMat BYTE",
        ])

        xinc = float(self.query(":WAVeform:XINCrement?"))   
        xorg = float(self.query(":WAVeform:XORigin?"))    
        xref = float(self.query(":WAVeform:XREFerence?"))
        yinc = float(self.query(":WAVeform:YINCrement?"))  
        yref = float(self.query(":WAVeform:YREFerence?"))
        yorg = float(self.query(":WAVeform:YORigin?"))

        raw_bytes = bytearray(points)
        block = 20000  

        for start in range(1, points + 1, block):
            stop = min(start + block - 1, points)
            self.x_write([f":WAVeform:STARt {start}", f":WAVeform:STOP {stop}"])
            chunk = self.read_block(":WAVeform:DATA?")
            raw_bytes[start - 1 : start - 1 + len(chunk)] = chunk

        data = np.frombuffer(raw_bytes, dtype=np.uint8)
        idx = np.arange(len(data), dtype=np.float64)

        times = xorg + xinc * (idx - xref)  
        volts = (data.astype(np.float64) - yorg - yref) * yinc

        return times, volts


    def set_free_run(self):
        """
        Enable free-run mode (trigger sweep AUTO).
        """
        # Switch to auto sweep; RUN/SINGle is controlled by the caller.
        self.x_write([":TRIGger:SWEep AUTO", "*OPC?"])

    def set_trig_rise(self, ch: int, level: float):
        """
        Configure rising-edge triggering: source channel, level (V), and NORM sweep.
        """
        cmds = [
            f":TRIGger:EDGE:SOURce CHANnel{ch}",
            ":TRIGger:EDGE:SLOPe POSitive",
            f":TRIGger:EDGE:LEVel {level:.9e}",
            ":TRIGger:SWEep NORMal", 
            "*OPC?",
        ]
        self.x_write(cmds)

    def set_on(self, ch: int):
        """Enable channel display/input."""
        self.x_write([f":CHANnel{ch}:DISPlay ON", "*OPC?"])

    def set_imp(self, imp: str, ch: int):
        """DHO1000 series only supports 1 MΩ."""
        pass

    def set_coup(self, coup: str, ch: int):
        """Set coupling mode: AC / DC."""
        self.x_write([f":CHANnel{ch}:COUPling {coup}", "*OPC?"])

    def rst(self):
        super().rst()

class instOSC_DHO1204(instOSC):
    Model_Supported = ["DHO1202", "DHO1204"]
    chan_num = 4

    def set_x(self, xscale: float, xoffset: float = None):
        """
        Configure horizontal scale (seconds/div) and optional offset.
        """
        cmds = []
        if xscale is not None:
            cmds.append(f":TIMebase:MAIN:SCALe {xscale}")
        if xoffset is not None:
            cmds.append(f":TIMebase:MAIN:OFFSet {xoffset}")
        if cmds:
            cmds.append("*OPC?")
            self.x_write(cmds)

    def set_y(self, ch: int, yscale: float, yoffset: float = None):
        """
        Configure vertical scale (volts/div) and vertical offset.
        """
        cmds = []
        if yscale is not None:
            cmds.append(f":CHANnel{ch}:SCALe {yscale}")
        if yoffset is not None:
            cmds.append(f":CHANnel{ch}:OFFSet {yoffset}")
            
        cmds.append("*OPC?")
        self.x_write(cmds)

    def get_y(self, ch: int):
        """
        Read the channel's vertical scale (V/div) and offset (V).
        """
        scale = float(self.x_write(f":CHANnel{ch}:SCALe?")[0].strip())
        offs  = float(self.x_write(f":CHANnel{ch}:OFFSet?")[0].strip())
        return (scale, offs)

    def get_sample_rate(self) -> int:
        """
        Read the current sampling rate in Hz.
        """
        sr = float(self.query(":ACQuire:SRATe?"))             
        self.sampling_rate = int(sr)
        return self.sampling_rate

    def trig_measure(self):
        """
        Triggered acquisition mode.
        """
        self.x_write(["*CLS", ":STOP", ":SINGle"])

        t0 = time.time()
        while time.time() - t0 < 15.0:
            try:
                if self.query(":TRIGger:STATus?").strip().upper() == "STOP": 
                    break
            except Exception:
                pass
            time.sleep(0.05)

    def quick_measure(self):
        """
        Quick acquisition mode.
        """
        self.x_write([
            "*CLS",                         
            ":STOP",                             
            ":SINGle"                            
        ])

        t0 = time.time()
        while time.time() - t0 < 2.0:
            try:
                if self.query(":TRIGger:STATus?").strip().upper() == "WAIT":  # Waiting for trigger
                    break
            except Exception:
                pass
            time.sleep(0.05)

        # Force a trigger once.
        self.x_write([":TFORce"])

        # Poll until acquisition finishes.
        t0 = time.time()
        while time.time() - t0 < 15.0:
            try:
                if self.query(":TRIGger:STATus?").strip().upper() == "STOP":  # Acquisition complete
                    break
            except Exception:
                pass
            time.sleep(0.05)

    def read_raw_waveform(self, ch: int, points: int):
        """
        Read raw waveform data for a channel and convert to time/voltage.
        """

        time.sleep(0.2)

        self.x_write([":STOP"])  
        self.x_write([
            f":WAVeform:SOURce CHANnel{ch}",
            ":WAVeform:MODE RAW",
            ":WAVeform:FORMat BYTE",
        ])

        xinc = float(self.query(":WAVeform:XINCrement?"))   
        xorg = float(self.query(":WAVeform:XORigin?"))    
        xref = float(self.query(":WAVeform:XREFerence?"))
        yinc = float(self.query(":WAVeform:YINCrement?"))  
        yref = float(self.query(":WAVeform:YREFerence?"))
        yorg = float(self.query(":WAVeform:YORigin?"))

        raw_bytes = bytearray(points)
        block = 20000  

        for start in range(1, points + 1, block):
            stop = min(start + block - 1, points)
            self.x_write([f":WAVeform:STARt {start}", f":WAVeform:STOP {stop}"])
            chunk = self.read_block(":WAVeform:DATA?")
            raw_bytes[start - 1 : start - 1 + len(chunk)] = chunk

        data = np.frombuffer(raw_bytes, dtype=np.uint8)
        idx = np.arange(len(data), dtype=np.float64)

        times = xorg + xinc * (idx - xref)  
        volts = (data.astype(np.float64) - yorg - yref) * yinc

        return times, volts


    def set_free_run(self):
        """
        Enable free-run mode (Trigger Sweep = AUTO).
        """
        # Switch to auto sweep; RUN/SINGle is controlled externally.
        self.x_write([":TRIGger:SWEep AUTO", "*OPC?"])

    def set_trig_rise(self, ch: int, level: float):
        """
        Configure rising-edge triggering: choose source channel/level (V) and use NORM sweep.
        """
        cmds = [
            f":TRIGger:EDGE:SOURce CHANnel{ch}",
            ":TRIGger:EDGE:SLOPe POSitive",
            f":TRIGger:EDGE:LEVel {level:.9e}",
            ":TRIGger:SWEep NORMal", 
            "*OPC?",
        ]
        self.x_write(cmds)

    def set_on(self, ch: int):
        """Enable the channel display/input."""
        self.x_write([f":CHANnel{ch}:DISPlay ON", "*OPC?"])

    def set_imp(self, imp: str, ch: int):
        """DHO1000 series only supports 1 MΩ."""
        pass

    def set_coup(self, coup: str, ch: int):
        """Set coupling mode: AC / DC."""
        self.x_write([f":CHANnel{ch}:COUPling {coup}", "*OPC?"])

    def rst(self):
        super().rst()
                
class instSW_CP2102(InstrumentBase):
    Model_Supported = ["3000072"]
    
    def __init__(self):
        super().__init__("sw")
        self.VisaAddress="COM7" #"ASRL7::INSTR"
        self.get_cal_amp = None
        self.current_freq = 0
    
    def inst_open(self):
        rr=re.match(r"COM(\d+)", self.VisaAddress)
        if rr:
            self.VisaAddress =f"ASRL{rr[1]}::INSTR"
        return super().inst_open()
    
    def callback_after_open(self):
        self.Inst.set_visa_attribute(pyconst.VI_ATTR_ASRL_RTS_STATE,0)
    
    def set_sw(self, on=None):
        """_summary_

        Be careful: the switch's default status is ON, when open, the status will be Off.   
        when Power on,  VI_ATTR_ASRL_RTS_STATE==0, on ==1 --> LED on, switch to rf spliter (outside of sw)
             Power off, VI_ATTR_ASRL_RTS_STATE==1, on ==0 --> LED off, switch to AWG ( inside of sw)
        """
        self.check_open()
        if isinstance(on, str):
            on = (on.lower() != "awg")
        self.Inst.set_visa_attribute(pyconst.VI_ATTR_ASRL_RTS_STATE,0 if on else 1)
        time.sleep(0.2)
        #self.close()
        #
    def test(self):
        self.set_sw(1)
        time.sleep(1)
        self.set_sw(0)
           
class instAWG_DSG836(instAWG):
    Model_Supported = ["DSG836"]
    
    def __init__(self, name, visa_address):
        super().__init__(name, visa_address)
        self.get_cal_amp:intpl.interp1d= None
        self.current_freq = 0
        
    def calib_level(self, val):
        if self.get_cal_amp:
            return val/ math.pow(10,float(self.get_cal_amp(self.current_freq))/20)
        else:
            return val

    def set_amp_v(self, amp: float):
        self.x_write([f":LEV {amp}V", "*OPC?"])
    
    def set_on(self, on=True, ch=None):
        # DSG836 is single-channel; ignore ch but keep the on/off flag.
        self.x_write([":OUTP %d" % (1 if on else 0), "*OPC?"])
        
    def set_lf_freq(self, freq):
        self.x_write([":LFO:FREQ %.2f" %freq, "*OPC?"] )
        self.current_freq = freq

    def set_lf_amp_v(self,amp_v):
        self.x_write([":LFO:LEV %.6fV" % amp_v, "*OPC?"])
    
    def set_lf_shape(self,shape="SINE"):
        """ shape: SINE, SQU"""
        self.x_write([":LFO:SHAP SINE"])
        
    def set_lf_on(self, on=True):
        self.x_write([":LFO %d" % (1 if on else 0), "*OPC?"])

    def set_amp(self, amp: float, ch=None):
        amp_vrms = amp/math.sqrt(8)
        self.x_write([f":LEV {amp_vrms}V", "*OPC?"])

    def get_amp(self, ch=None) -> float:
        dbm = self.x_write(":LEV?")[0].strip()

        P_w = 10**(float(dbm)/10) * 1e-3
        Vrms = math.sqrt(P_w * 50)
        Vpp = 2 * math.sqrt(2) * Vrms

        return Vpp

    def set_freq(self, freq: float, ch=None):
        self.x_write([f":FREQ {freq}", "*OPC?"] )

    def get_freq(self, ch=None) -> float:
        freq = float(self.x_write(":FREQ?")[0].strip())
        return freq

    def set_imp(self, imp = None, ch=None):
        pass

    # Remove redundant parameter-less versions; always call set_on(on=True, ch=None).

class instAWG_DG4102(instAWG):
    Model_Supported = ["DG4102"]
    chan_num = 2
    
    def __init__(self, name, visa_address):
        super().__init__(name, visa_address)
        self.ch = 1 # 1, 2
        self.get_cal_level= None  # a interpolate function table.
        self.freqs = [0,0]
        self.levels = None
        self.chan_num = 2
        
    def callback_after_open(self):
        pass
        #self.set_reset()

    def calib_level(self, ch, val,freq = None):
        if self.get_cal_level:
            freq = self.freqs[ch-1] if freq is None else freq
            return val/float(self.get_cal_level[ch-1](freq)) 
        else:
            return val

    def sel_chan(self,ch):
        self.ch = ch
                  
    class MODE:
        SIN = 1
        DC = 0
        PULSE = 2
        SQU = 3
    CH_ALL = 0
    
    def set_freq(self,freq, ch=None):
        self.x_write([f":SOUR{ch}:FREQ {freq}", "*OPC?"] )

    def get_freq(self, ch=None) -> float:
        freq = float(self.x_write(f"SOUR{ch}:FREQ?")[0].strip())
        return freq

    def ch2chs(self, ch):
        chs = self.ch if ch is None else ch
        if not isinstance(chs, list):
            chs = [chs]
        if chs == []:
            chs = [1,2]
        return chs

    def set_imp(self, imp: str, ch: int=None):
        if imp == Mapping.mapping_imp_high_z:
            imp = "INF"
        self.x_write([f":OUTP{ch}:IMP {imp}", "*OPC?"] )
        
    def set_output(self, on=True):
        self.set_on(on)
    
    def set_reset(self):
        self.x_write(["*RST", "*OPC?", ":OUTP1:IMP INF",":OUTP2:IMP INF"])

    def set_mode(self, mode = MODE.SIN, ch=None):
        if not isinstance(mode, str):
            mode = "PULSE" if mode ==2 else "DC" if mode ==0 else "SQU" if mode ==3 else "SIN"
        for ch in self.ch2chs(ch):
            self.x_write([":SOUR%d:APPL:%s" %(ch,mode), "*OPC?"] )
            
    def set_sine_mode(self,freq=1e8,amp=0.05, ch=None):   
        self.set_mode(self.MODE.SIN,ch)
        self.set_freq(freq,ch)
        self.set_amp(amp,ch)
        self.set_offset(0,ch)
        self.set_on(True, ch)     
             
    def set_dc_mode(self,dc=0,ch=None):   
        self.set_mode(self.MODE.SIN,ch)
        self.set_freq(1e-6,ch)
        self.set_amp(1e-3,ch)
        self.set_offset(dc,ch)
        self.set_on(True, ch)
        
    def set_phase(self, ph, ch=None):
        for ch in self.ch2chs(ch):
            self.x_write([":SOUR%d:PHAS:%s" %(ch,ph), "*OPC?"] )
            
    def phase_sync(self,ch=None):
        for ch in self.ch2chs(ch):
            self.x_write([":SOUR%d:PHAS:INIT" %(ch), "*OPC?"] )
                             
    def set_amp(self, amp: float, ch: int=None):
            self.x_write([f":SOUR{ch}:VOLT:UNIT VPP", "*OPC?"])
            self.x_write([f":SOUR{ch}:VOLT:AMPL {amp}", "*OPC?"] )

    def get_amp(self, ch:int) -> float:
        self.x_write([":SOUR%d:VOLT:UNIT VPP" %(ch), "*OPC?"])
        amp = float(self.x_write(f":SOUR{ch}:VOLT:AMPL?")[0].strip())
        return amp
   
    def set_burst_phase(self,ph, ch=None):
        for ch in self.ch2chs(ch):
            self.x_write([":SOUR%d:BURS:PHAS %.4f" %(ch,ph), "*OPC?"] )
            
    def set_offset(self, v, ch = None):
        if  isinstance(v, list):
            for ch,vv in enumerate(v):
                self.x_write([":SOUR%d:VOLT:OFFS %.4f" %(ch+1,self.calib_level(ch+1, vv, 0)), "*OPC?"] )
        else:          
            for ch in self.ch2chs(ch):
                self.x_write([":SOUR%d:VOLT:OFFS %.4f" %(ch,self.calib_level(ch, v, 0)), "*OPC?"] )
        
    def set_on(self,on=True,ch=None):
        for ch in self.ch2chs(ch):
            self.x_write([":OUTP%d %d" %(ch, (1 if on else 0)), "*OPC?"])
    
    def set_data_rate_test(self,afreq=200e3, bfreq=100, bursts=500,level=3.3):
        self.x_write(["*RST","*OPC?",
                      ":OUTP1:IMP INF",":OUTP2:IMP INF",
                      ":SOUR1:APPL:SQU %f, %.2f, %.2f,300" % (afreq,level/2,level/4),
                      ":SOUR2:APPL:SQU %f, %.2f, %.2f,0" % (bfreq,level/2,level/4),
                      "*OPC?",
                      ":SOUR2:TRIG:SOUR MAN",
                      ":SOUR2:BURS:MODE TRIG","*OPC?",
                      ":SOUR2:BURS:NCYC %d" % bursts,"*OPC?",
                      ":SOUR2:BURS ON",
                      ":OUTP1 1",
                      ":OUTP2 1", 
                      "*OPC?",
                      ])

    def fire_burst_manul_trigger(self,ch=None):
        for ch in self.ch2chs(ch):
            self.x_write([":SOUR%d:BURS:TRIG" % ch,"*OPC?"])
            
    def reset(self):
        self.x_write([":SYST:PRES DEF","*OPC?",":OUTP1:IMP INF",":OUTP2:IMP INF",
        "*OPC?",":SOUR1:APPL:SIN", ":SOUR2:APPL:SIN", "*OPC?" ])

    def rst(self):
        super().rst()
        
class instAWG_DG852(instAWG_DG4102):
    Model_Supported = ["DG852"]
    
    def __init__(self):
        super().__init__()
        self.VisaAddress="USB::0x1AB1::0x0646::DG8R262900659::INSTR"

    def set_reset(self):
        self.x_write(["*RST","$WAIT=1500$", "*OPC?", ":OUTP1:LOAD 50",":OUTP2:LOAD 50"])
        
    def set_amp(self,amp,ch=None):
        if  isinstance(amp, list):
            for ch,vv in enumerate(amp):
                self.x_write([":SOUR%d:VOLT %.4f" %(ch+1,self.calib_level(ch+1, vv)), "*OPC?"] )
        else:
            for ch in self.ch2chs(ch):
                self.x_write([":SOUR%d:VOLT %.4f" %(ch,self.calib_level(ch, amp)), "*OPC?"] )
                
    def phase_sync(self,ch=None):
        for ch in self.ch2chs(ch):
            self.x_write([":SOUR%d:PHAS:SYNC" %(ch), "*OPC?"] )
  
    def set_data_rate_test(self,afreq=200e3, bfreq=100, bursts=500,level=3.3):
        self.x_write(["*RST","$WAIT=1500$", "*OPC?",
                      ":OUTP1:LOAD 50",":OUTP2:LOAD 50",
                      ":SOUR1:APPL:SQU %f, %.2f, %.2f,300" % (afreq,level/2,level/4),
                      ":SOUR2:APPL:SQU %f, %.2f, %.2f,0" % (bfreq,level/2,level/4),
                      "*OPC?"])
        self.x_write([":SOUR2:TRIG:SOUR MAN",
                      ":SOUR2:BURS:MODE TRIG","*OPC?",
                      F":SOUR2:BURS:NCYC {bursts}","*OPC?",
                      ":SOUR2:BURS:STAT ON",
                      ":OUTP1 1",
                      ":OUTP2 1", 
                      "*OPC?",
                      ])
    def fire_burst_manul_trigger(self,ch=None):
        for ch in self.ch2chs(ch):
            self.x_write([F":TRIG{ch}","*OPC?"])
            
    def reset(self):
        self.x_write(["*RST","$WAIT=1500$", "*OPC?",":OUTP1:LOAD 50",":OUTP2:LOAD 50",
        "*OPC?",":SOUR1:APPL:SIN", ":SOUR2:APPL:SIN", "*OPC?" ])

class instDC_KA3003P(InstrumentBase):
    Model_Supported = ["KA3003P"]
    
    def __init__(self):
        super().__init__("dc")
        self.VisaAddress="ASRL7::INSTR"
        
    def measure_v(self):
        return float(self.x_write(["VOUT1?"] )[0])
        
    def measure_i(self):
        try:
            return float(self.x_write(["IOUT1?"] )[0])
        except:
            return float(self.x_write(["IOUT1?"] )[0])
    
    def measure_iv(self):
        return (self.measure_i(),self.measure_v())
        
    def set_v(self,v):
        self.x_write(["VSET1:%.2fV" % v])
        
    def set_i(self,v):
        self.x_write(["ISET1:%.3fV" % v])
    
    def set_on(self,on=True):
        self.x_write(["OUT%d" % (1 if on else 0)])
        time.sleep(0.5)
        
    def test(self):
        self.set_v(3.3)
        self.set_i(0.2)
        self.set_on(1)
        i = self.measure_i()
        v = self.measure_v()
        print((i,v))
        self.set_on(0)

class instTrigger(InstrumentBase):
    Model_Supported = [""]
    
    def __init__(self):
        super().__init__("pwm")
        self.VisaAddress="COM4"
        
    def measure_v(self):
        return float(self.x_write(["VOUT1?"] )[0])
    
    def inst_open(self):
        if not self.Inst:
            if not self.VisaAddress:
                self.set_error("Equip Address has not been set!")
            try:
                self.Inst = serial.Serial(self.VisaAddress, 115200, timeout=1)
            except serial.SerialException:
                time.sleep(2)
                self.Inst = serial.Serial(self.VisaAddress, 115200, timeout=1)
        return self.Inst
    
    def trigger(self, afreq,bfreq, csize):
        acycles = round(1e8/afreq)-1
        bcycles = round(afreq/bfreq)
        absize = acycles + (bcycles<<16)
        self.send(self.CMD_CCSIZE, 0x0000_0000 )
        self.send(self.CMD_ABSIZE,absize)
        self.send(self.CMD_CCSIZE, csize+0x8000_0000 )

    def wait_done(self,maxdelay=10):
        st = time.time()
        while time.time()-st < maxdelay:
            v = self.send(self.CMD_STATE, 0x0000_0000 )
            if ( v &0x03 == 2):
                break
            time.sleep(0.1)
        return  time.time()-st
    
    CMD_ABSIZE =0
    CMD_CCSIZE =1
    CMD_STATE = 2
    
    def send(self,cmd, value):
        self.check_open()
        for _ in range(2):
            if self.Inst.in_waiting>0:
                self.Inst.read(self.Inst.in_waiting)
            self.Inst.write(list("SV".encode("utf-8"))+[0,cmd]+list(struct.pack ("I",value)))
            ret=self.Inst.read(8)
            if len(ret) == 8 and ret[0] =='s': break
            self.Inst.write([0]*256)
            time.sleep(0.5)
        if len(ret)!=8:
            self.set_error("return error")
        return struct.unpack("II",ret)[1]
    
inst_mapping: dict[str, InstrumentBase] = {
    Mapping.mapping_DSG_4102: instAWG_DG4102, 
    Mapping.mapping_MDO_34: instOSC_MDO34, 
    Mapping.mapping_MDO_3024: instOSC_MDO3024, 
    Mapping.mapping_DSG_836: instAWG_DSG836,
    Mapping.mapping_DHO_1202: instOSC_DHO1202,
    Mapping.mapping_DHO_1204: instOSC_DHO1204,
}
