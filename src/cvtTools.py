import re
import math
import numpy as np  

class CvtTools:

    @staticmethod
    def parse_general_val(input: str, default_unit: str=None) -> float|int:
        """
        Parse a numeric string with an optional prefix and return the scaled value.
        Empty or invalid text resolves to 0, and unknown prefixes default to a scale of 1.
        """
        input = input.replace(" ", "")
        input_match = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]?)", input)
        input_val = input_match.group(1)
        input_unit = input_match.group(2)

        try:
            input_val = int(input_val) if input_val.isdigit() else float(input_val)
        except:
            return 0.0
        
        if not input_unit: 
            val = input_val * CvtTools.convert_general_unit(default_unit)
            # Prefer ints for integral results so downstream callers can treat counts as integers.
            try:
                return int(val) if float(val).is_integer() else val
            except Exception:
                return val
        prefix = input_unit[0]

        if prefix in ('G', 'g'):       scale = 1e9
        elif prefix == 'M':            scale = 1e6
        elif prefix in ('k', 'K'):     scale = 1e3
        elif prefix == 'm':            scale = 1e-3
        elif prefix in ('u', 'µ', 'μ'):scale = 1e-6
        elif prefix in ('n', 'N'):     scale = 1e-9
        elif prefix in ('p', 'P'):     scale = 1e-12
        else:                          scale = 1
        
        val = input_val * scale
        try:
            return int(val) if float(val).is_integer() else val
        except Exception:
            return val
    
    @staticmethod
    def convert_general_unit(unit: str) -> float|int:
        """
        Parse the prefix multiplier only; empty strings and unknown prefixes return 1.
        """
        if not unit: return 1
        input_match = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]?)", unit)
        input_unit = input_match.group(2)

        if not input_unit: return 1
        prefix = input_unit[0]

        if prefix in ('G', 'g'):       scale = 1e9
        elif prefix == 'M':            scale = 1e6
        elif prefix in ('k', 'K'):     scale = 1e3
        elif prefix == 'm':            scale = 1e-3
        elif prefix in ('u', 'µ', 'μ'):scale = 1e-6
        elif prefix in ('n', 'N'):     scale = 1e-9
        elif prefix in ('p', 'P'):     scale = 1e-12
        else:                          scale = 1

        return scale
    
    @staticmethod
    def parse_to_hz(freq: str, default_unit: str = "") -> float:
        """
        Parse frequency text with an optional default unit.
        """
        new_freq = CvtTools.parse_general_val(input=freq, default_unit=default_unit)
        
        return new_freq if new_freq else 0
    
    @staticmethod
    def parse_to_Vpp(vpp: str) -> float:
        """
        Parse voltage text and convert it to Vpp.
        Supports: Vpp = 1x, Vpk = 2x, Vrms = sqrt(8) * Vpp, and an optional milli prefix.
        """
        vpp = vpp.replace(" ", "")
        vpp_macth = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]*)", vpp)
        vpp_val = vpp_macth.group(1)
        vpp_unit = vpp_macth.group(2)

        if not vpp_val: return ""
        vpp_val = float(vpp_val)

        if not vpp_unit:              scale = 1
        elif "Vpp".lower() in vpp_unit.lower():   scale = 1
        elif "Vpk".lower() in vpp_unit.lower():   scale = 2 
        elif "Vrms".lower() in vpp_unit.lower():  scale = math.sqrt(8) 
        else:                                     scale = 1 

        if vpp_unit and vpp_unit[0] == "m": scale *= 0.001
        return vpp_val * scale
    
    @staticmethod
    def parse_to_V(volts: str):
        """
        Generic voltage parser helper.
        """
        return CvtTools.parse_general_val(input=volts)
    
    @staticmethod
    def _parabolic_interp_delta(m1, m0, p1):
        """
        Estimate the peak offset via log|X| parabolic interpolation on three points.
        """
        eps = 1e-30
        m1 = np.log(max(m1, eps))
        m0 = np.log(max(m0, eps))
        p1 = np.log(max(p1, eps))
        denom = (m1 - 2*m0 + p1)
        if abs(denom) < 1e-12: return 0.0
        return 0.5 * (m1 - p1) / denom

    @staticmethod
    def _complex_tone_at(times, volts_ac, f_hz, window=None):
        """
        Compute a single-point DFT at f_hz and return the complex coefficient.
        """
        if window is None:
            return np.sum(volts_ac * np.exp(-1j * 2*np.pi * f_hz * times))
        return np.sum(window * volts_ac * np.exp(-1j * 2*np.pi * f_hz * times))
