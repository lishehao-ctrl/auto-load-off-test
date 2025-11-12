from typing import List, Tuple
import tkinter as tk
import numpy as np
from cvtTools import CvtTools
from mapping import Mapping
from equips import InstrumentBase, instAWG, instOSC

class ChannelBase(InstrumentBase):
    """Channel base class: binds an instrument instance, tracks channel index/occupancy, and provides reset helpers."""

    def __init__(self, chan_index: int, freq_unit: tk.StringVar, instrument: InstrumentBase = None):
        """Initialize channel parameters."""
        super().__init__()
        self.instrument: InstrumentBase = instrument
        self.chan_index = tk.IntVar(value=chan_index)
        self.freq_unit = freq_unit
        self.occupied = False
        self.frame_channel = tk.Frame()

    def copy_from(self, other: "ChannelBase"):
        """Copy occupancy state from another channel, raising if the type mismatches."""
        if not isinstance(other, ChannelBase):
            raise TypeError("other must be a channel")
        self.occupied = other.occupied
        return self

    def set_inst(self, inst: InstrumentBase):
        """Bind the instrument instance for this channel."""
        self.instrument = inst

    def set_is_occupied(self):
        """Mark the channel as occupied."""
        self.occupied = True

    def set_is_free(self):
        """Mark the channel as free."""
        self.occupied = False

    def rst(self):
        """Reset the currently bound instrument."""
        inst = self.instrument
        inst.rst()
            
class AWG_Channel(ChannelBase):
    """AWG channel: manages sweep parameters/units, wraps the AWG read/write APIs, and links trace callbacks to UI fields."""


    def __init__(self, chan_index: int, freq_unit: tk.StringVar, instrument: instAWG = None):
        """Initialize channel state and UI variables."""
        super().__init__(chan_index=chan_index, freq_unit=freq_unit, instrument=instrument)
        self.default_imp = Mapping.mapping_imp_r50

        self.instrument: instAWG
        self.frame_awg_channel = tk.Frame()
        self.start_freq = tk.StringVar(value="")
        self.stop_freq = tk.StringVar(value="")
        self.step_freq = tk.StringVar(value="")
        self.center_freq = tk.StringVar(value="")
        self.interval_freq = tk.StringVar(value="")

        self.step_num = tk.StringVar(value="")
        self.is_log_freq_enabled = tk.BooleanVar(value=False)

        self.freq_unit = freq_unit
        self.freq_unit.trace_add("write", self.change_on_freq_unit)  # Keep unit changes in sync

        self.amp = tk.StringVar(value="")
        self.imp = tk.StringVar(value="")

        # Frequency input traces keep center/interval in sync
        self.set_trace_start_freq()
        self.set_trace_stop_freq()
        self.set_trace_center_freq()
        self.set_trace_interval_freq()

    def set_inst(self, inst: instAWG):
        """Bind the AWG instrument instance."""
        super().set_inst(inst=inst)

    def set_freq(self, freq: float, ch: int = None) -> int:
        """
        Set the AWG output frequency
        - freq: target frequency (Hz)
        - ch: channel index, defaults to chan_index
        """
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        if freq:
            inst.set_freq(freq=freq, ch=ch)

    def get_freq(self, ch: int = None) -> float:
        """
        Read the AWG output frequency
        - ch: channel index, defaults to chan_index
        """
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        freq = inst.get_freq(ch=ch)
        return freq

    def get_sweep_freq_points(self, start_freq: str = None, stop_freq: str = None, step_freq: str = None, step_num: str = None, is_log_freq_enabled: str=None) -> List[float]:
        """
        Generate sweep frequency points (linear or logarithmic)
        - start_freq/stop_freq/step_freq/step_num: string inputs (with units); use UI values when omitted
        - is_log_freq_enabled: whether to use logarithmic sweep
        Return: numpy array of frequency points (Hz)
        """
        # Read provided arguments or fall back to UI values
        start = start_freq if start_freq is not None else self.start_freq.get()
        stop = stop_freq if stop_freq is not None else self.stop_freq.get()
        step = step_freq if step_freq is not None else self.step_freq.get()
        step_num = step_num if step_num is not None else self.step_num.get()
        is_log_freq_enabled = is_log_freq_enabled if is_log_freq_enabled is not None else self.is_log_freq_enabled.get()

        # Parse text inputs into Hz; clamp the minimum to avoid log10 errors
        start_freq = max(CvtTools.parse_to_hz(freq=start, default_unit=self.freq_unit.get()), 1e-12)
        stop_freq = max(CvtTools.parse_to_hz(freq=stop, default_unit=self.freq_unit.get()), 1e-12)

        if self.is_log_freq_enabled.get():
            # Log sweep: step_num must be an integer
            try:
                num_steps = int(max(1, round(CvtTools.parse_general_val(step_num))))
            except Exception:
                num_steps = 1
            # Skip the first point when the start is effectively zero
            if start_freq == 1e-12:
                freq_points = np.logspace(np.log10(start_freq), np.log10(stop_freq), num_steps + 1)
                freq_points = freq_points[1:]
            else:
                freq_points = np.logspace(np.log10(start_freq), np.log10(stop_freq), num_steps)
        else:
            # Linear sweep: generate points by step size including the endpoint
            step_freq = CvtTools.parse_to_hz(freq=step, default_unit=self.freq_unit.get())

            start_freq = start_freq if start_freq != 1e-12 else step_freq

            # Return a single point when start equals stop
            if start_freq == stop_freq:
                freq_points = np.array([start_freq])
            else:
                curr_freq = start_freq
                freq_points = []
                while stop_freq - curr_freq >= -1e-6:
                    freq_points.append(curr_freq)
                    curr_freq += step_freq


        return freq_points
            
    def set_amp(self, amp: str = None, ch: int = None):
        """
        Set the output amplitude (always converted to Vpp)
        - amp: textual input such as "1 Vpp"/"500 mVpp"
        - ch: channel index, defaults to chan_index
        """
        inst = self.instrument
        amp_val = float(CvtTools.parse_to_Vpp(amp if amp is not None else self.amp.get()))
        ch = ch if ch is not None else self.chan_index.get()
        if amp_val:
            inst.set_amp(amp=amp_val, ch=ch)

    def get_amp(self, ch: int=None):
        """
        Read the output amplitude
        - ch: channel index, defaults to chan_index
        """
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        amp = inst.get_amp(ch=ch)
        return amp

    def set_imp(self, imp: str=None, ch: int=None):
        """
        Set the output impedance
        - imp: textual input such as "50" or "INF"
        - ch: channel index, defaults to chan_index
        """
        inst = self.instrument
        imp_val = imp if imp is not None else self.imp.get()
        ch = ch if ch is not None else self.chan_index.get()
        inst.set_imp(imp=imp_val, ch=ch)

    def set_on(self, ch:int=None):
        """
        Enable channel output
        - ch: channel index, defaults to chan_index
        """
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        inst.set_on(ch=ch)

    def rst(self):
        """""Reset the underlying instrument."""
        super().rst()

    def set_trace_start_freq(self):
        """""Attach a trace callback to start_freq."""
        self.trace_start_id = self.start_freq.trace_add("write", self.change_on_start_freq)

    def set_trace_stop_freq(self):
        """""Attach a trace callback to stop_freq."""
        self.trace_stop_id = self.stop_freq.trace_add("write", self.change_on_stop_freq)

    def set_trace_center_freq(self):
        """""Attach a trace callback to center_freq."""
        self.trace_center_id = self.center_freq.trace_add("write", self.change_on_center_freq)

    def set_trace_interval_freq(self):        
        """""Attach a trace callback to interval_freq."""
        self.trace_interval_id = self.interval_freq.trace_add("write", self.change_on_interval_freq)

    def change_on_start_freq(self, *args):
        """""When start_freq changes, recompute center/interval and repopulate while temporarily removing traces to avoid recursion."""
        try:
            start_val_hz = CvtTools.parse_to_hz(self.start_freq.get(), self.freq_unit.get())
            stop_val_hz  = CvtTools.parse_to_hz(self.stop_freq.get(),  self.freq_unit.get())
            factor = CvtTools.convert_general_unit(unit=self.freq_unit.get())
            center   = str(round(((start_val_hz + stop_val_hz) / 2.0) / factor, 2))
            interval = str(round(abs(start_val_hz - stop_val_hz) / factor, 2))
        except (tk.TclError, ValueError, TypeError):
            center = ""
            interval = ""

        # Temporarily remove related traces to avoid recursive triggers
        try:    
            self.center_freq.trace_remove("write", self.trace_center_id)
            self.interval_freq.trace_remove("write", self.trace_interval_id)
        except tk.TclError:
            pass

        # Write back center and interval
        self.center_freq.set(center)
        self.interval_freq.set(interval)

        # Restore the trace bindings
        self.set_trace_center_freq()
        self.set_trace_interval_freq()

    def change_on_stop_freq(self, *args):
        """""When stop_freq changes, recompute center/interval and repopulate while temporarily removing traces to avoid recursion."""
        try:
            start_val_hz = CvtTools.parse_to_hz(self.start_freq.get(), self.freq_unit.get())
            stop_val_hz  = CvtTools.parse_to_hz(self.stop_freq.get(),  self.freq_unit.get())
            factor = CvtTools.convert_general_unit(unit=self.freq_unit.get())
            center   = str(round(((start_val_hz + stop_val_hz) / 2.0) / factor, 2))
            interval = str(round(abs(start_val_hz - stop_val_hz) / factor, 2))
        except (tk.TclError, ValueError, TypeError):
            center = ""
            interval = ""

        # Temporarily remove related traces to avoid recursive triggers
        try:
            self.center_freq.trace_remove("write", self.trace_center_id)
            self.interval_freq.trace_remove("write", self.trace_interval_id)
        except tk.TclError:
            pass

        # Write back center and interval
        self.center_freq.set(center)
        self.interval_freq.set(interval)

        # Restore the trace bindings
        self.set_trace_center_freq()
        self.set_trace_interval_freq()

    def change_on_center_freq(self, *args):
        """
        When center_freq changes, adjust interval and start/stop; clamp when values exceed the valid range.
        """
        try:
            factor = CvtTools.convert_general_unit(unit=self.freq_unit.get())
            center_val_hz = CvtTools.parse_to_hz(self.center_freq.get(), self.freq_unit.get())
            if center_val_hz == 0: raise ValueError
            interval_val_hz = CvtTools.parse_to_hz(self.interval_freq.get(), self.freq_unit.get())

            # Cap interval at its maximum allowed value
            if interval_val_hz > center_val_hz*2:
                interval_val_hz = center_val_hz*2
                interval = str(interval_val_hz / factor)
                self.interval_freq.set(value=interval)

            start_val_hz = CvtTools.parse_to_hz(self.start_freq.get(), self.freq_unit.get()) 
            stop_val_hz  = CvtTools.parse_to_hz(self.stop_freq.get(),  self.freq_unit.get())

            if start_val_hz <= stop_val_hz:
                start = str(round((center_val_hz - (interval_val_hz/2.0)) / factor, 2))
                stop = str(round((center_val_hz + (interval_val_hz/2.0)) / factor, 2))
            else:
                start = str(round((center_val_hz + (interval_val_hz/2.0)) / factor, 2))
                stop = str(round((center_val_hz - (interval_val_hz/2.0)) / factor, 2))
        except (tk.TclError, ValueError, TypeError):
            start = ""
            stop = ""

        # Temporarily remove related traces to avoid recursive triggers
        try:
            self.start_freq.trace_remove("write", self.trace_start_id)
            self.stop_freq.trace_remove("write", self.trace_stop_id)
            self.interval_freq.trace_remove("write", self.trace_interval_id)
        except tk.TclError:
            pass

        # Write back start and stop
        self.start_freq.set(value=start)
        self.stop_freq.set(value=stop)

        # Restore the trace bindings
        self.set_trace_start_freq()
        self.set_trace_stop_freq()
        self.set_trace_interval_freq()

    def change_on_interval_freq(self, *args):
        """""When interval_freq changes, adjust center/start/stop and ensure it is not less than half of the center value."""
        try:
            factor = CvtTools.convert_general_unit(unit=self.freq_unit.get())
            center_val_hz = CvtTools.parse_to_hz(self.center_freq.get(), self.freq_unit.get())
            if center_val_hz == 0: raise ValueError
            interval_val_hz = CvtTools.parse_to_hz(self.interval_freq.get(), self.freq_unit.get())

            # Lift the center limit when it falls below half the interval
            if center_val_hz < interval_val_hz/2.0:
                center_val_hz = interval_val_hz/2.0
                center = str(center_val_hz / factor)
                self.center_freq.set(value=center)

            start_val_hz = CvtTools.parse_to_hz(self.start_freq.get(), self.freq_unit.get())
            stop_val_hz  = CvtTools.parse_to_hz(self.stop_freq.get(),  self.freq_unit.get())

            if start_val_hz <= stop_val_hz:
                start = str(round((center_val_hz - (interval_val_hz/2.0)) / factor, 2))
                stop = str(round((center_val_hz + (interval_val_hz/2.0)) / factor, 2))
            else:
                start = str(round((center_val_hz + (interval_val_hz/2.0)) / factor, 2))
                stop = str(round((center_val_hz - (interval_val_hz/2.0)) / factor, 2))
        except (tk.TclError, ValueError, TypeError):
            start = ""
            stop = ""

        # Temporarily remove related traces to avoid recursive triggers
        try:
            self.start_freq.trace_remove("write", self.trace_start_id)
            self.stop_freq.trace_remove("write", self.trace_stop_id)
            self.center_freq.trace_remove("write", self.trace_center_id)
        except tk.TclError:
            pass

        # Write back start and stop
        self.start_freq.set(value=start)
        self.stop_freq.set(value=stop)

        # Restore the trace bindings
        self.set_trace_start_freq()
        self.set_trace_stop_freq()
        self.set_trace_center_freq()

    def change_on_freq_unit(self, *args):
        """
        When the frequency unit changes, recompute start/stop/step/center/interval in the new unit and repopulate the UI.
        - Suspend traces first to avoid cyclic updates, then restore them.
        """
        def suspend_traces():
            """""Remove all related traces to prevent recursive triggers."""
            try:
                self.start_freq.trace_remove("write", self.trace_start_id)
            except Exception:
                pass
            try:
                self.stop_freq.trace_remove("write", self.trace_stop_id)
            except Exception:
                pass
            try:
                self.center_freq.trace_remove("write", self.trace_center_id)
            except Exception:
                pass
            try:
                self.interval_freq.trace_remove("write", self.trace_interval_id)
            except Exception:
                pass

        def resume_traces():
            """""Restore the trace bindings."""
            self.set_trace_start_freq()
            self.set_trace_stop_freq()
            self.set_trace_center_freq()
            self.set_trace_interval_freq()
            
        old_unit = getattr(self, "last_freq_unit", self.freq_unit.get())
        new_unit = self.freq_unit.get()

        try:
            # First parse using the previous unit to obtain Hz
            start_hz = CvtTools.parse_to_hz(self.start_freq.get(),   old_unit)
            stop_hz  = CvtTools.parse_to_hz(self.stop_freq.get(),    old_unit)
            step_hz  = CvtTools.parse_to_hz(self.step_freq.get(),    old_unit)
            center_hz   = (start_hz + stop_hz) / 2.0
            interval_hz = abs(start_hz - stop_hz)

            # Then convert back to display values using the new unit
            factor = CvtTools.convert_general_unit(new_unit) 
            start   = str(round(start_hz   / factor, 2))
            stop    = str(round(stop_hz    / factor, 2))
            step    = str(round(step_hz    / factor, 2))
            center  = str(round(center_hz  / factor, 2))
            interval= str(round(interval_hz/ factor, 2))
        except Exception:
            return  

        # Temporarily remove related traces to avoid recursive triggers
        suspend_traces()
        # Write the recomputed values back
        try:
            self.start_freq.set(start)
            self.stop_freq.set(stop)
            self.step_freq.set(step)
            self.center_freq.set(center)
            self.interval_freq.set(interval)
        except:
            pass
        # Restore the trace bindings
        finally:
            resume_traces()

        self.last_freq_unit = new_unit
     
class OSC_Channel(ChannelBase):
    """""Oscilloscope channel: manages vertical/horizontal settings, triggering, waveform reads, and impedance/coupling along with required UI traces."""

    def __init__(self, chan_index: int, freq_unit: tk.StringVar, instrument: instOSC = None):
        """
        Initialize channel and UI variables
        - chan_index: channel index
        - freq_unit: frequency unit variable (for interface consistency)
        - instrument: oscilloscope instrument instance
        """
        super().__init__(chan_index=chan_index, freq_unit=freq_unit, instrument=instrument)
        self.instrument: instOSC  
        self.frame_channel = tk.Frame()
        self.range = tk.StringVar(value="")     # Vertical full-scale span (peak-to-peak)
        self.yoffset = tk.StringVar(value="")   # Center voltage
        self.points = tk.StringVar(value="")    # Sample points
        self.imp = tk.StringVar(value="")       # Input impedance (e.g., 50-ohm/high-Z)
        self.coupling = tk.StringVar(value="")  # Coupling mode (AC/DC)
        self.xscale = None                     
        self.xoffset = None                    

        # Impedance/coupling guard: AC is disallowed when impedance is 50-ohm; auto-adjust on conflict
        self.imp.trace_add("write", self.trace_on_imp)
        self.coupling.trace_add("write", self.trace_on_coup)

    def trace_on_imp(self, *args):
        """""If impedance switches to 50-ohm while coupling is AC, fall back to DC coupling automatically."""
        if self.imp.get() == Mapping.mapping_imp_r50 and self.coupling.get() == Mapping.mapping_coup_ac:
            self.coupling.set(Mapping.mapping_coup_dc)

    def trace_on_coup(self, *args):
        """""If coupling switches to AC while impedance is 50-ohm, fall back to high impedance automatically."""
        if self.imp.get() == Mapping.mapping_imp_r50 and self.coupling.get() == Mapping.mapping_coup_ac:
            self.imp.set(Mapping.mapping_imp_high_z)

    def copy_from(self, other: "OSC_Channel"):
        """""Copy base state from another oscilloscope channel; raise when the type mismatches."""
        super().copy_from(other)
        if not isinstance(other, OSC_Channel):
            raise TypeError("other must be OSC_Channel")

        self.range = other.range
        self.yoffset = other.yoffset
        self.points = other.points
        self.xscale = other.xscale
        self.xoffset = other.xoffset
        return self

    def set_x(self, xscale: float=None, xoffset: float=None):
        """
        Configure horizontal scale and offset
        - xscale: full-screen time, internally converted to time per division (divide by 10)
        - xoffset: horizontal offset
        """
        inst = self.instrument
        xscale = xscale/10.0 if xscale is not None else self.xscale/10.0
        xoffset = xoffset if xoffset is not None else self.xoffset
        inst.set_x(xscale=xscale, xoffset=xoffset)

    def set_y(self, yscale: str=None, yoffset: str=None, ch: int=None):
        """
        Configure vertical scale and offset
        - yscale: UI span (full-scale Vpp), internally converted to volts per division (Vpp/8)
        - yoffset: vertical offset
        - ch: channel index
        """
        inst = self.instrument
        yscale = CvtTools.parse_to_V(yscale if yscale is not None else self.range.get()) / 8.0
        yoffset = CvtTools.parse_to_V(yoffset if yoffset is not None else self.yoffset.get())
        ch = ch if ch is not None else self.chan_index.get()
        inst.set_y(ch=ch, yscale=yscale, yoffset=yoffset)

    def get_y(self, ch: int=None):
        """
        Read the vertical settings
        Return: (full-scale Vpp, offset)
        """
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        yscale, yoffs = inst.get_y(ch=ch)
        return yscale * 8.0, yoffs  # Convert V/div back to full-scale Vpp

    def get_sample_rate(self, ch: int=None) -> int:
        """""Read the sampling rate."""
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        sample_rate = inst.get_sample_rate()
        return sample_rate

    def quick_measure(self):
        """""Run a quick acquisition once."""
        inst = self.instrument
        inst.quick_measure() 
    
    def trig_measure(self):
        """""Perform a triggered acquisition once."""
        inst = self.instrument
        inst.trig_measure()

    def read_raw_waveform(self, points: str=None, ch: int=None) -> Tuple[np.array]:
        """
        Read the raw waveform
        - points: textual sample count converted to int
        - ch: channel index
        Return: (times, volts) or the raw data structure defined by the instrument
        """
        inst =  self.instrument
        raw_points = CvtTools.parse_general_val(points if points is not None else self.points.get())
        # Safely convert the requested points to int; pass None to use the instrument default when invalid or zero
        try:
            points_val = int(round(raw_points)) if raw_points and raw_points > 0 else None
        except Exception:
            points_val = None
        ch = ch if ch is not None else self.chan_index.get()
        raw_data = inst.read_raw_waveform(ch=ch, points=points_val)
        return raw_data

    def set_trig_rise(self, ch: int=None, level: float=None):
        """
        Configure rising-edge trigger
        - ch: channel index
        - level: trigger level, defaults to 0.0
        """
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        level = level if level is not None else 0.0
        inst.set_trig_rise(ch=ch, level=level)

    def set_free_run(self):
        """""Set free-run mode."""
        inst =  self.instrument
        inst.set_free_run()
    
    def set_on(self, ch: int=None):
        """""Enable the channel display/input."""
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        inst.set_on(ch=ch)

    def set_imp(self, imp: str=None, ch: int=None):
        """
        Configure input impedance
        - imp: e.g., "50" or "HiZ"
        - ch: channel index
        """
        inst = self.instrument
        imp = imp if imp is not None else self.imp.get()
        ch = ch if ch is not None else self.chan_index.get()
        inst.set_imp(imp=imp, ch=ch)

    def set_coup(self, coup: str=None, ch: int=None):
        """
        Configure coupling mode
        - coup: "AC"/"DC", etc.
        - ch: channel index
        """
        inst = self.instrument
        coup = coup if coup is not None else self.coupling.get()
        ch = ch if ch is not None else self.chan_index.get()
        inst.set_coup(coup=coup, ch=ch)

    def rst(self):
        """""Reset the underlying instrument."""
        super().rst()

