import re
import tkinter as tk
from cvtTools import CvtTools

class TraceVal:
    """
    Input-field normalization helpers invoked on focus-out events:
    - Parse numbers and optional unit prefixes from the string.
    - Normalize prefixes (G/M/k/m/µ/n/p).
    - Reformat the text based on the physical quantity (freq/voltage/amplitude/etc).
    - Provide generic constraints such as positivity, integer enforcement, and IP range checks.
    """

    # ----------------------------- Frequency -----------------------------
    @staticmethod
    def freq_out_focus(freq: tk.StringVar, *args):
        """
        Normalize frequency input:
        - Parse the numeric value and prefix (k/M/G, etc.).
        - Rewrite as "<val> <prefix>Hz", e.g., "1.5k" -> "1.5 kHz".
        - Leave the text untouched when no unit is present.
        """
        freq_match = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]*)", freq.get().replace(" ", ""))

        freq_val = freq_match.group(1)
        freq_unit = freq_match.group(2)

        # Leave untouched when no unit is provided.
        if freq_unit == "":
            return

        prefix = freq_unit[0]
        unit = "Hz"   # Frequency suffix

        # Normalize the prefix (case-insensitive).
        if prefix in ('G', 'g'):         # Giga
            ini = "G"
        elif prefix == 'M':              # Mega
            ini = "M"
        elif prefix in ('k', 'K'):       # kilo
            ini = "k"
        elif prefix == 'm':              # milli
            ini = "m"
        elif prefix in ('u', 'µ', 'μ'):  # micro
            ini = "µ"
        elif prefix in ('n', 'N'):       # nano
            ini = "N"
        elif prefix in ('p', 'P'):       # pico
            ini = "P"
        elif prefix in ("h", "H"):       # Accept user input like "Hz".
            ini = ""
        else:
            # Unknown prefix: drop the unit to preserve the original intent.
            ini = ""
            unit = ""

        parse_freq = f"{freq_val} {ini}{unit}"
        freq.set(parse_freq)

    # ----------------------------- Voltage / current (shares "curr" naming, unit = V) -----------------------------
    @staticmethod
    def volts_out_focus(curr: tk.StringVar):
        """
        Normalize voltage/current text (expressed in volts):
        - Parse the numeric part and prefix.
        - Emit "<val> <prefix>V".
        """
        volts_match = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]*)", curr.get().replace(" ", ""))

        volts_val = volts_match.group(1)
        volts_unit = volts_match.group(2)

        prefix = volts_unit[0] if volts_unit != "" else ""
        unit = "V"

        if prefix in ('G', 'g'):
            ini = "G"
        elif prefix == 'M':
            ini = "M"
        elif prefix in ('k', 'K'):
            ini = "k"
        elif prefix == 'm':
            ini = "m"
        elif prefix in ('u', 'µ', 'μ'):
            ini = "µ"
        elif prefix in ('n', 'N'):
            ini = "N"
        elif prefix in ('p', 'P'):
            ini = "P"
        else:
            ini = ""

        parse_curr = f"{volts_val} {ini}{unit}"
        curr.set(parse_curr)

    # ----------------------------- Amplitude (Vpp/Vpk/Vrms/V) -----------------------------
    @staticmethod
    def vpp_out_focus(vpp: tk.StringVar):
        """
        Normalize amplitude input:
        - Parse the numeric part and prefix.
        - Detect units: Vpp / Vpk / Vrms / V (by substring).
        - Leave the unit blank if it cannot be identified.
        """
        vpp_match = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]*)", vpp.get().replace(" ", ""))

        vpp_val = vpp_match.group(1)
        vpp_unit = vpp_match.group(2)

        prefix = vpp_unit[0] if vpp_unit != "" else ""

        if prefix in ('G', 'g'):
            ini = "G"
        elif prefix == 'M':
            ini = "M"
        elif prefix in ('k', 'K'):
            ini = "k"
        elif prefix == 'm':
            ini = "m"
        elif prefix in ('u', 'µ', 'μ'):
            ini = "µ"
        elif prefix in ('n', 'N'):
            ini = "N"
        elif prefix in ('p', 'P'):
            ini = "P"
        else:
            ini = ""
        
        # Unit detection (case-insensitive).
        if "Vpp".lower() in vpp_unit.lower():
            unit = "Vpp"
        elif "Vpk".lower() in vpp_unit.lower():
            unit = "Vpk"
        elif "Vrms".lower() in vpp_unit.lower() or "vr" in vpp_unit.lower():
            unit = "Vrms"
        elif "v" in vpp_unit.lower():
            unit = "Vpp"  # Default to Vpp when only 'v' is present.
        else:
            unit = ""

        parse_curr = f"{vpp_val} {ini}{unit}"
        vpp.set(parse_curr)

    # ----------------------------- Generic: normalize prefix only -----------------------------
    @staticmethod
    def general_out_focus(var: tk.StringVar, *args):
        """
        Generic normalization that only harmonizes the prefix (no unit label).
        Result format: "<val> <prefix>".
        """
        var_match = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]*)", var.get().replace(" ", ""))

        val = var_match.group(1)
        unit = var_match.group(2)

        prefix = unit[0] if unit != "" else ""

        if prefix in ('G', 'g'):
            unit = "G"
        elif prefix == 'M':
            unit = "M"
        elif prefix in ('k', 'K'):
            unit = "k"
        elif prefix == 'm':
            unit = "m"
        elif prefix in ('u', 'µ', 'μ'):
            unit = "µ"
        elif prefix in ('n', 'N'):
            unit = "N"
        elif prefix in ('p', 'P'):
            unit = "P"
        else:
            unit = ""

        parse_curr = f"{val} {unit}"
        var.set(parse_curr)

    # ----------------------------- Constraint: force positive (>0) -----------------------------
    @staticmethod
    def force_positive_out_focus(var: tk.StringVar, *args):
        """
        Enforce a positive value:
        - Parse the numeric portion (scientific notation allowed).
        - Clear the field when parsing fails or the value <= 0.
        """
        try:
            val = re.search(r"[+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?", var.get().replace(" ", ""))
            if val and float(val.group()) > 0:
                return
            var.set("")
        except (tk.TclError, ValueError):
            var.set("")

    # ----------------------------- Constraint: round to integer (after scaling) -----------------------------
    @staticmethod
    def force_int_out_focus(var: tk.StringVar, *args):
        """
        Enforce integers:
        - Parse the numeric part and prefix to determine the scale factor.
        - Convert to the base unit, round, then convert back.
        - If no unit is present, cast directly to int.
        - Clear the field on failure.
        """
        try:
            var_match = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]*)", var.get().replace(" ", ""))

            val = var_match.group(1)
            unit = var_match.group(2)

            if not unit:
                var.set(f"{int(float(val))}")
                return

            unit_val = CvtTools.convert_general_unit(unit=unit)  # e.g., "k" -> 1e3, "M" -> 1e6

            # Scale to the base magnitude, round, then scale back.
            val = int(float(val) * unit_val) / unit_val
            var.set(f"{val} {unit}")
        except:
            var.set("")

    # ----------------------------- IP octet validation (0-255) -----------------------------
    @staticmethod
    def ip_out_focus(var: tk.StringVar, *args):
        """
        Ensure the IP octet is an integer between 0 and 255; clear otherwise.
        """
        try:
            ip_val = int(var.get())
            if ip_val < 0 or ip_val > 255:
                var.set("")
        except (tk.TclError, ValueError):
            var.set("")
