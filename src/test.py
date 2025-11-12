from typing import Callable
import numpy as np
import tkinter as tk
from tkinter import messagebox
import threading
import queue
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import mplcursors
import time
from channel import AWG_Channel, OSC_Channel
from cvtTools import CvtTools
from mapping import Mapping

class testBase:
    """Test base class that owns the queue, stop event, and result storage."""

    device_num: int  

    def __init__(self):
        """Create the base queue, stop event, and empty result dictionary."""
        self.data_queue = queue.Queue()      
        self.stop_event = threading.Event()   
        self.results = {}                     

    def connection_check(self):
        """Hook for subclasses to validate instrument connections."""
        pass
  
class TestLoadOff(testBase):
    """Offline load-off test: manages AWG/OSC devices and stores frequency/magnitude/phase data."""

    # Device count
    device_num = 2

    def __init__(self, freq_unit: tk.StringVar):
        """Create AWG/OSC channels, control variables, and default data structures."""
        super().__init__()

        # Channel references
        self.awg: AWG_Channel
        self.osc_test: OSC_Channel
        self.osc_ref: OSC_Channel
        self.osc_trig: OSC_Channel

        # Shared frequency unit
        self.freq_unit = freq_unit

        # Auto range control
        self.is_auto_osc_range = tk.BooleanVar()

        # Calibration mode and toggle, both hooked to trace callbacks
        self.var_correct_mode = tk.StringVar(value="")
        self.var_correct_mode.trace_add("write", self.trace_trig_chan_index)

        self.is_correct_enabled = tk.BooleanVar()
        self.is_correct_enabled.trace_add("write", self.refresh_plot)
        self.is_correct_enabled.set(False)

        # Reference file path plus interpolation handle
        self.ref_file_save_path: str = None
        self.href_at: Callable = None

        # Trigger mode
        self.trig_mode = tk.StringVar(value="")

        # Plot mode and visibility options with callbacks
        self.var_mag_or_phase = tk.StringVar(value="")
        self.var_mag_or_phase.trace_add("write", self.refresh_plot)
        self.var_mag_or_phase.set(Mapping.label_for_mag)

        self.figure_mode = tk.StringVar(value="")
        self.figure_mode.trace_add("write", self.show_plot)
        self.figure_mode.set(Mapping.label_for_figure_gain_freq)

        # Auto-reset toggle
        self.auto_reset = tk.BooleanVar()      

        # Result storage arrays
        self.results = {
            Mapping.mapping_freq            : np.array([]),
            Mapping.mapping_gain_raw        : np.array([]),
            Mapping.mapping_gain_db_raw     : np.array([]),
            Mapping.mapping_phase_deg       : np.array([]),
            Mapping.mapping_gain_corr       : np.array([]),
            Mapping.mapping_gain_db_corr    : np.array([]),
            Mapping.mapping_phase_deg_corr  : np.array([]),
            Mapping.mapping_gain_complex    : np.array([]),
        }


    def trace_trig_chan_index(self, *args):
        """Keep osc_trig.chan_index and osc_ref.chan_index synchronized in dual-channel calibration mode."""
        if self.var_correct_mode.get() == Mapping.label_for_duo_chan_correct:

            def trig_on_ref(*args):
                # ref -> trig: when the reference channel changes, mirror it to the trigger.
                # Skip if they already match to avoid redundant sets and trace loops.
                if self.osc_ref.chan_index.get() == self.osc_trig.chan_index.get():
                    return
                try:
                    self.osc_trig.chan_index.set(self.osc_ref.chan_index.get())
                except:
                    pass

            def ref_on_trig(*args):
                # trig -> ref: mirror trigger changes back to the reference channel.
                # Again, skip when they already match to avoid ping-pong updates.
                if self.osc_trig.chan_index.get() == self.osc_ref.chan_index.get():
                    return
                try:
                    self.osc_ref.chan_index.set(self.osc_trig.chan_index.get())
                except:
                    pass

            # Align once when entering the mode by copying ref -> trig.
            self.osc_trig.chan_index.set(self.osc_ref.chan_index.get())

            # Bind the traces; trace_add returns an id that must be reused for removal.
            self.ref_on_trig_id = self.osc_trig.chan_index.trace_add("write", ref_on_trig)
            self.trig_on_ref_id = self.osc_ref.chan_index.trace_add("write", trig_on_ref)

        else:
            # Outside dual-channel mode: remove traces to stop the linkage.
            try:
                self.osc_trig.chan_index.trace_remove("write", self.ref_on_trig_id)
                self.osc_ref.chan_index.trace_remove("write", self.trig_on_ref_id)
            except:
                pass

               
    def start_swep_test(self):

        def auto_osc_range_modifier(osc: OSC_Channel, volts: np.ndarray, force_auto: bool = False) -> bool:
            """
            Auto-adjust the oscilloscope range and offset based on the measured waveform.
            Return True if an adjustment was made (callers may re-measure), otherwise False.
            """
            if not (self.is_auto_osc_range.get() or force_auto):
                return False
            if volts is None or len(volts) == 0:
                return False

            # Basic stats: peak-to-peak and midpoint.
            vmax = float(np.max(volts))
            vmin = float(np.min(volts))            
            vpp  = vmax - vmin
            mid  = (vmax + vmin) / 2.0

            # Current full-scale range and offset.
            rng_cur, yofs_cur = osc.get_y()

            # Threshold parameters (empirical).
            HI_s, LO_s, TARGET_s = 0.8, 0.6, 0.7  # Keep vpp/range around ~0.7.

            ratio = vpp / rng_cur
            # Offset deviation relative to half the range.
            yofs_ratio = abs(mid - yofs_cur) / (rng_cur / 2.0)

            # Tolerances for comparing requested vs. readback values.
            RTOL_RANGE = 1e-2
            ATOL_RANGE = 1e-3
            RTOL_OFS   = 1e-2
            ATOL_OFS   = 1e-3  

            upper = yofs_cur + rng_cur * 0.95 / 2.0
            lower = yofs_cur - rng_cur * 0.95 / 2.0

            wave_find  = (lower < vmax < upper) or (upper > vmin > lower)   # Partial overlap with range.

            # First try recentring the offset when DC coupled and the trace is off-center.
            if wave_find and yofs_ratio > 0.2 and osc.coupling.get() == Mapping.mapping_coup_dc:
                yofs_needed =  mid
                osc.yoffset.set(str(yofs_needed))
                osc.set_y()

                # Lock to the readback value when it matches the requested offset.
                _, yofs_read = osc.get_y()
                if np.isclose(float(yofs_read), float(yofs_needed), rtol=RTOL_OFS, atol=ATOL_OFS):
                    osc.yoffset.set(str(yofs_read))
                    self.try_re_center = False
                    return True
                else:
                    # Otherwise keep the readback value and allow one retry before warning.
                    osc.yoffset.set(str(yofs_read))
                    if not self.try_re_center:
                        self.try_re_center = True
                        return True
                    else:
                        if not self.warning_reach_ofs_lim_shown:
                            messagebox.showwarning(
                                Mapping.title_alert,
                                f"Scope channel {osc.chan_index.get()} exceeded the offset limit\nAuto range set to: {yofs_read} V"
                            )
                            self.warning_reach_ofs_lim_shown = True

            if not wave_find:
                rng_needed = rng_cur * 3.0
                osc.range.set(str(rng_needed))
                osc.set_y()

                rng_read, _ = osc.get_y()

                # Lock to the readback value if it matches; otherwise retry once before warning.
                if np.isclose(float(rng_read), float(rng_needed), rtol=RTOL_RANGE, atol=ATOL_RANGE):
                    osc.range.set(str(rng_read))
                    self.try_get_target = False
                    return True
                else:
                    osc.range.set(str(rng_read))
                    if not self.try_get_target:
                        self.try_get_target = True
                        return True
                    else:
                        if not self.warning_lost_target_shown:
                            messagebox.showwarning(
                                Mapping.title_alert,
                                f"Scope channel {osc.chan_index.get()} could not locate the waveform\nAuto range set to: {rng_read} V"
                            )
                            self.warning_lost_target_shown = True

            # If the waveform fits, fine-tune the span toward ~0.7 of full scale.
            if (ratio > HI_s) or (ratio < LO_s):
                rng_needed = vpp / TARGET_s
                osc.range.set(str(rng_needed))
                osc.set_y()

                rng_read, _ = osc.get_y()
                if np.isclose(float(rng_read), float(rng_needed), rtol=RTOL_RANGE, atol=ATOL_RANGE):
                    osc.range.set(str(rng_read))
                    self.try_set_res = False
                    return True
                else:
                    osc.range.set(str(rng_read))
                    if not self.try_set_res:
                        self.try_set_res = True
                        return True
                    else:
                        if not self.warning_lack_res_shown:
                            messagebox.showwarning(
                                Mapping.title_alert,
                                f"Scope channel {osc.chan_index.get()} exceeded range limits\nAuto range set to: {rng_read} V"
                            )
                            self.warning_lack_res_shown = True

            return False
        
        def calc_vin_peak(vpp_panel, awg_imp, osc_imp):
            """Estimate the DUT peak voltage from the AWG panel Vpp and the impedance configuration."""
            RS = 50.0
            RL = 50.0 if osc_imp == Mapping.mapping_imp_r50 else 1e6

            # 50-ohm output means the panel Vpp assumes a matched load, so open-circuit voltage doubles.
            # Hi-Z output is already the open-circuit voltage.
            if awg_imp == Mapping.mapping_imp_r50: 
                voc = 2 * vpp_panel
            else:                             
                voc = vpp_panel

            # Divider to the load.
            vload = voc * RL / (RS + RL)

            # Convert Vpp to Vpeak.
            vpeak = 0.5 * vload
            return vpeak
            
        def append_result():
            """Append the current frequency point to the result arrays."""
            self.results[Mapping.mapping_freq]        = np.append(self.results[Mapping.mapping_freq], freq)
            self.results[Mapping.mapping_gain_raw]    = np.append(self.results[Mapping.mapping_gain_raw], gain_raw) 
            self.results[Mapping.mapping_gain_db_raw] = np.append(self.results[Mapping.mapping_gain_db_raw], gain_db_raw)
            if self.var_correct_mode.get() == Mapping.label_for_duo_chan_correct or self.trig_mode.get() == Mapping.label_for_triggered: 
                self.results[Mapping.mapping_gain_complex] = np.append(self.results[Mapping.mapping_gain_complex], gain_c)
                self.results[Mapping.mapping_phase_deg] = np.append(self.results[Mapping.mapping_phase_deg], phase)

        def initialize_devices():
            """Initialize on/imp/coup/trigger settings plus Y-scale based on the current mode."""
            if self.auto_reset.get(): 
                awg.rst()
                osc_test.rst()

            awg.set_on()
            awg.set_imp()

            osc_test.set_on()
            if self.var_correct_mode.get() == Mapping.label_for_duo_chan_correct:
                osc_ref.set_on()
                scale, offs = osc_ref.get_y()
                osc_ref.range = tk.StringVar(value=str(scale))
                osc_ref.yoffset = tk.StringVar(value=str(offs))

            if self.trig_mode.get() == Mapping.label_for_triggered: 
                osc_trig.set_on()
                scale, offs = osc_trig.get_y()
                osc_trig.range = tk.StringVar(value=str(scale))
                osc_trig.yoffset = tk.StringVar(value=str(offs))
                osc_trig.set_trig_rise()

            # Set coupling before impedance to avoid trace side effects.
            osc_test.set_coup()
            osc_test.set_imp()
            if self.trig_mode.get() == Mapping.label_for_free_run: 
                osc_test.set_free_run()

        def check_user_input():
            # Validate manual range/offset/amplitude values and fall back to readbacks if needed.
            rng_needed = CvtTools.parse_to_V(osc_test.range.get())
            yofs_needed = CvtTools.parse_to_V(osc_test.yoffset.get())
            osc_test.set_y()
            rng_read, yofs_read = osc_test.get_y()

            # Range validation.
            if np.isclose(rng_read, rng_needed, atol=1e-2, rtol=1e-2):
                osc_test.range.set(str(rng_read))
            else:
                osc_test.range.set(str(rng_read))
                messagebox.showwarning(
                    Mapping.title_alert, 
                    f"Scope channel {osc_test.chan_index.get()} exceeded the range limit\n{Mapping.label_for_range}: {rng_needed} V\nAdjusted to: {rng_read} V"
                )
                self.warning_lack_res_shown = True

            # Offset validation.
            if np.isclose(yofs_read, yofs_needed, rtol=1e-2, atol=1e-1):
                osc_test.yoffset.set(str(yofs_read))
            else:
                osc_test.yoffset.set(str(yofs_read))
                messagebox.showwarning(
                    Mapping.title_alert,
                    f"Scope channel {osc_test.chan_index.get()} exceeded the offset limit\n{Mapping.label_for_yoffset}: {yofs_needed} V\nAdjusted to: {yofs_read} V"
                )
                self.warning_reach_ofs_lim_shown = True

            # AWG amplitude validation.
            amp_needed = CvtTools.parse_to_Vpp(awg.amp.get())
            awg.set_amp()
            amp_read = awg.get_amp()

            if np.isclose(amp_read, amp_needed, rtol=1e-3, atol=1e-2):
                awg.amp.set(str(amp_read))
            else:
                awg.amp.set(str(amp_read))
                messagebox.showwarning(
                    Mapping.title_alert,
                    f"AWG channel {awg.chan_index.get()} exceeded the amplitude limit\n{Mapping.label_for_set_amp}: {amp_needed} Vpp\nAdjusted to: {amp_read} Vpp"
                )


        # --- Reset status flags ---
        self.warning_lack_res_shown = False
        self.warning_lost_target_shown = False
        self.warning_reach_ofs_lim_shown = False
        self.warning_freq_out_of_range_shown = False
        self.warning_amp_out_of_range_shown = False
        self.try_set_res = False
        self.try_get_target = False
        self.try_re_center = False

        awg: AWG_Channel = self.awg
        osc_test: OSC_Channel = self.osc_test
        osc_trig: OSC_Channel = self.osc_trig
        osc_ref: OSC_Channel = self.osc_ref

        # Frequency sweep points and iterator.
        freq_points = awg.get_sweep_freq_points()
        freq_index = 0
        # Program the initial frequency point.
        awg.set_freq(freq=freq_points[0])

        initialize_devices()
        check_user_input()

        # Let the equipment settle.
        time.sleep(0.5)

        self.results = {
                        Mapping.mapping_freq : np.array([]),
                        Mapping.mapping_gain_raw : np.array([]),
                        Mapping.mapping_gain_db_raw : np.array([]),
                        Mapping.mapping_phase_deg : np.array([]),
                        Mapping.mapping_gain_corr : np.array([]),
                        Mapping.mapping_gain_db_corr : np.array([]),
                        Mapping.mapping_phase_deg_corr : np.array([]),
                        Mapping.mapping_gain_complex : np.array([]),
        }

        self.refresh_plot()

        while freq_index < len(freq_points):
            freq = freq_points[freq_index]

            if self.stop_event.is_set(): 
                break

            if self.warning_freq_out_of_range_shown:
                break

            awg.set_freq(freq=freq)
            freq = awg.get_freq() 

            if not np.isclose(freq, freq_points[freq_index], atol=1e-3, rtol=5e-6):
                self.warning_freq_out_of_range_shown = True
                messagebox.showwarning(
                    Mapping.title_alert,
                    f"Failed to set frequency\nTarget: {freq_points[freq_index]} Hz\nActual: {freq} Hz\nTest aborted"
                )

                if freq in self.results[Mapping.mapping_freq]:
                    freq_index += 1
                    continue

            new_amp = awg.get_amp()
            if not np.isclose(new_amp, CvtTools.parse_to_Vpp(awg.amp.get()), atol=1e-2, rtol=1e-3):
                messagebox.showwarning(
                    Mapping.title_alert,
                    f"AWG channel {awg.chan_index.get()} exceeded the amplitude limit\n{Mapping.label_for_set_amp}: {CvtTools.parse_to_Vpp(awg.amp.get())} Vpp\nAdjusted to: {new_amp} Vpp"
                )
                awg.amp.set(str(awg.get_amp()))
                self.warning_amp_out_of_range_shown = True

            device_sampling_rate = osc_test.get_sample_rate()
            sampling_time = self.cal_sampling_time(
                freq=freq, 
                device_sr=device_sampling_rate,
                points=CvtTools.parse_general_val(osc_test.points.get())
            )

            # ------------------ No calibration branch ------------------
            if self.var_correct_mode.get() == Mapping.label_for_no_correct:
                # Configure oscilloscope X/Y axes
                osc_test.set_x(xscale=sampling_time)
                osc_test.set_y()

                # Acquire waveform according to the trigger mode
                if self.trig_mode.get() == Mapping.label_for_triggered: 
                    osc_test.trig_measure()
                elif self.trig_mode.get() == Mapping.label_for_free_run:
                    osc_test.quick_measure()

                # Read the waveform and rerun if auto-ranging changed settings
                times, volts = osc_test.read_raw_waveform()
                if auto_osc_range_modifier(osc=osc_test, volts=volts): 
                    continue

                # Remove the DC component
                volts_ac = volts - np.mean(volts)

                # FFT computation
                window = np.hanning(len(volts_ac))
                Vfft   = np.fft.rfft(window * volts_ac)
                freqs  = np.fft.rfftfreq(len(volts_ac), times[1]-times[0])
                k0     = np.argmin(np.abs(freqs - freq))
                lo     = max(0, k0 - 2)
                hi     = min(len(Vfft), k0 + 3)

                # Compute output/input peak values
                Vout_peak = (2/(np.sqrt(np.sum(window**2) * len(volts_ac)))) * np.sqrt(np.sum(abs(Vfft[lo:hi] ** 2)))
                Vin_peak = calc_vin_peak(
                    vpp_panel=CvtTools.parse_to_Vpp(awg.amp.get()), 
                    awg_imp=awg.imp.get(), 
                    osc_imp=osc_test.imp.get()
                ) 

                # Compute gain (linear and logarithmic)
                gain_raw    = Vout_peak / Vin_peak         
                gain_db_raw = 20.0 * np.log10(np.maximum(gain_raw, 1e-12)) 

                # Compute phase (only in triggered mode)
                if self.trig_mode.get() == Mapping.label_for_triggered:
                    mags = np.abs(Vfft)
                    if 1 <= k0 <= mags.size-2:
                        delta = CvtTools._parabolic_interp_delta(mags[k0-1], mags[k0], mags[k0+1])
                    else:
                        delta = 0.0
                    df = freqs[1] - freqs[0]
                    f_hat = freqs[k0] + delta * df

                    # When computing phase, prefer the interpolated frequency f_hat for the complex harmonic
                    X = CvtTools._complex_tone_at(times, volts_ac, f_hat, window)
                    if np.abs(X) < 1e-15:  
                        ang = np.angle(np.sum(Vfft[lo:hi]))
                    else:
                        ang = np.angle(X)

                    # Compute the complex gain and phase angle
                    Vout_phasor = Vout_peak * np.exp(1j * ang)
                    gain_c = Vout_phasor / Vin_peak
                    phase = np.degrees(np.angle(gain_c))

            # ------------------ Single-channel calibration branch ------------------
            elif self.var_correct_mode.get() == Mapping.label_for_single_chan_correct:
                # Configure oscilloscope X/Y axes
                osc_test.set_x(xscale=sampling_time)
                osc_test.set_y()

                # Acquire waveform according to the trigger mode
                if self.trig_mode.get() == Mapping.label_for_triggered: 
                    osc_test.trig_measure()
                elif self.trig_mode.get() == Mapping.label_for_free_run:
                    osc_test.quick_measure()

                # Read the waveform and rerun if auto-ranging changed settings
                times, volts = osc_test.read_raw_waveform()
                if auto_osc_range_modifier(osc=osc_test, volts=volts): 
                    continue  

                # Remove the DC component
                volts_ac = volts - np.mean(volts)

                # FFT computation
                window = np.hanning(len(volts_ac))
                Vfft   = np.fft.rfft(window * volts_ac)
                freqs  = np.fft.rfftfreq(len(volts_ac), times[1]-times[0])
                k0     = np.argmin(np.abs(freqs - freq))
                lo     = max(0, k0 - 2)
                hi     = min(len(Vfft), k0 + 3)

                # Compute output/input peak values
                Vout_peak = (2/(np.sqrt(np.sum(window**2) * len(volts_ac)))) * np.sqrt(np.sum(abs(Vfft[lo:hi] ** 2)))
                Vin_peak = calc_vin_peak(
                    vpp_panel=CvtTools.parse_to_Vpp(awg.amp.get()), 
                    awg_imp=awg.imp.get(), 
                    osc_imp=osc_test.imp.get()
                ) 

                # Compute gain (linear and logarithmic)
                gain_raw    = Vout_peak / Vin_peak         
                gain_db_raw = 20.0 * np.log10(np.maximum(gain_raw, 1e-12))

                # Compute phase (only in triggered mode)
                if self.trig_mode.get() == Mapping.label_for_triggered:
                    mags = np.abs(Vfft)
                    if 1 <= k0 <= mags.size-2:
                        delta = CvtTools._parabolic_interp_delta(mags[k0-1], mags[k0], mags[k0+1])
                    else:
                        delta = 0.0
                    df = freqs[1] - freqs[0]
                    f_hat = freqs[k0] + delta * df

                    # When computing phase, prefer the interpolated frequency f_hat for the complex harmonic
                    X = CvtTools._complex_tone_at(times, volts_ac, f_hat, window)
                    if np.abs(X) < 1e-15:
                        ang = np.angle(np.sum(Vfft[lo:hi]))
                    else:
                        ang = np.angle(X)

                    # Compute the complex gain and phase angle
                    Vout_phasor = Vout_peak * np.exp(1j * ang)
                    gain_c = Vout_phasor / Vin_peak
                    phase = np.degrees(np.angle(gain_c))

            # ------------------ Dual-channel calibration branch ------------------
            elif self.var_correct_mode.get() == Mapping.label_for_duo_chan_correct:
                # Configure oscilloscope X/Y axes
                osc_test.set_x(xscale=sampling_time)
                osc_test.set_y()
                osc_ref.set_x(xscale=sampling_time)
                osc_ref.set_y()

                # Acquire waveform according to the trigger mode
                if self.trig_mode.get() == Mapping.label_for_triggered: 
                    osc_test.trig_measure() 
                elif self.trig_mode.get() == Mapping.label_for_free_run:
                    osc_test.quick_measure()

                # Read the waveform and rerun if auto-ranging changed settings
                times_t, volts_t = osc_test.read_raw_waveform()
                if auto_osc_range_modifier(osc=osc_test, volts=volts_t): 
                    continue
                times_r, volts_r = osc_ref.read_raw_waveform()
                if auto_osc_range_modifier(osc=osc_ref, volts=volts_r, force_auto=True): 
                    continue

                # Remove the DC component
                volts_ac_t = volts_t - np.mean(volts_t)
                volts_ac_r = volts_r - np.mean(volts_r)

                # FFT computation
                window_t = np.hanning(len(volts_ac_t))
                window_r = np.hanning(len(volts_ac_r))

                Vfft_t = np.fft.rfft(window_t * volts_ac_t)
                Vfft_r = np.fft.rfft(window_r * volts_ac_r)

                freqs_t = np.fft.rfftfreq(len(volts_ac_t), times_t[1] - times_t[0])
                freqs_r = np.fft.rfftfreq(len(volts_ac_r), times_r[1] - times_r[0])

                k0_t = np.argmin(np.abs(freqs_t - freq))
                k0_r = np.argmin(np.abs(freqs_r - freq))

                lo_t = max(0, k0_t - 2)
                hi_t = min(len(Vfft_t), k0_t + 3)
                lo_r = max(0, k0_r - 2)
                hi_r = min(len(Vfft_r), k0_r + 3)

                mag_t = (2 / (np.sqrt(np.sum(window_t**2) * len(volts_ac_t)))) * np.sqrt(np.sum(abs(Vfft_t[lo_t:hi_t] ** 2)))
                mag_r = (2 / (np.sqrt(np.sum(window_r**2) * len(volts_ac_r)))) * np.sqrt(np.sum(abs(Vfft_r[lo_r:hi_r] ** 2)))

                Ph_t = np.angle(np.sum(Vfft_t[lo_t:hi_t]))
                Ph_r = np.angle(np.sum(Vfft_r[lo_r:hi_r]))

                mag_ratio = max(mag_t / max(mag_r, 1e-15), 1e-15)  
                dphi = Ph_t - Ph_r

                # Compute the complex gain and phase angle
                gain_c = mag_ratio * (np.cos(dphi) + 1j*np.sin(dphi))
                gain_raw    = np.abs(gain_c)
                gain_db_raw = 20.0 * np.log10(np.maximum(gain_raw, 1e-12))  

                mags_r = np.abs(Vfft_r)
                if 1 <= k0_r <= mags_r.size-2:
                    delta_r = CvtTools._parabolic_interp_delta(mags_r[k0_r-1], mags_r[k0_r], mags_r[k0_r+1])
                else:
                    delta_r = 0.0
                df_r = freqs_r[1] - freqs_r[0]
                f_hat = freqs_r[k0_r] + delta_r * df_r

                # When computing phase, prefer the interpolated frequency f_hat for the complex harmonic
                Xt = CvtTools._complex_tone_at(times_t, volts_ac_t, f_hat, window_t)
                Xr = CvtTools._complex_tone_at(times_r, volts_ac_r, f_hat, window_r)
                if (np.abs(Xt) < 1e-15) or (np.abs(Xr) < 1e-15):
                    # Fallback method
                    Ph_t = np.angle(np.sum(Vfft_t[lo_t:hi_t]))
                    Ph_r = np.angle(np.sum(Vfft_r[lo_r:hi_r]))
                    S_t = mag_t * np.exp(1j*Ph_t)
                    S_r = mag_r * np.exp(1j*Ph_r)
                    phase = np.degrees(np.angle(S_t / S_r))
                else:
                    Sxy = Xt * np.conj(Xr)
                    phase = np.degrees(np.angle(Sxy))  

            # Append the result
            append_result()

            self.data_queue.put(freq)
            freq_index += 1
        
        self.data_queue.put(None)


    def connection_check(self):
        """Verify instrument connectivity based on the current calibration/trigger mode."""
        # No calibration: only AWG and the DUT channel.
        if self.var_correct_mode.get() == Mapping.label_for_no_correct:
            self.awg.inst_open()
            self.awg.check_open()
            self.osc_test.inst_open()
            self.osc_test.check_open()
        # Single-channel calibration: still AWG + DUT channel.
        elif self.var_correct_mode.get() == Mapping.label_for_single_chan_correct:
            self.awg.inst_open()
            self.awg.check_open()
            self.osc_test.inst_open()
            self.osc_test.check_open()
        # Dual-channel calibration: AWG, DUT channel, and reference channel.
        elif self.var_correct_mode.get() == Mapping.label_for_duo_chan_correct:
            self.awg.inst_open()
            self.awg.check_open()
            self.osc_test.inst_open()
            self.osc_test.check_open()
            self.osc_ref.inst_open()
            self.osc_ref.check_open()

        # Triggered mode: also ensure the trigger channel is reachable.
        if self.trig_mode.get() == Mapping.label_for_triggered:
            self.osc_trig.inst_open()
            self.osc_trig.check_open()
        
    def cal_sampling_time(self, freq, device_sr, points, *, T_MIN=1e-6, N_CYC=10, PTS_MAX=1e7):
        """Compute the oscilloscope sampling window length in seconds."""
        f = max(float(freq), 1e-12)  # Avoid divide-by-zero.
        # Choose the longest of the candidates to ensure sufficient duration.
        T = max(points/device_sr, N_CYC/f, T_MIN)
        # Clamp if the device has a point-count limit.
        if PTS_MAX:
            T = min(T, PTS_MAX/device_sr)

        return T

    def setup_plots(self, frame: tk.Frame):
        """Build the gain/phase figures, axes, artists, and canvases in the provided frame."""

        self.frame_plot = tk.Frame(frame)
        self.frame_plot.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        freq_unit = self.freq_unit.get()

        # === Linear gain plot ===
        self.fig_gain = Figure(figsize=(8, 4))
        try:
            self.fig_gain.set_tight_layout(True)
        except Exception:
            pass
        self.ax_gain = self.fig_gain.add_subplot(111)
        self.ax_gain.set_xlabel(f"{Mapping.label_for_freq}({freq_unit})")
        self.ax_gain.set_ylabel(Mapping.label_for_figure_gain)
        (self.line_gain,) = self.ax_gain.plot([], [], linestyle='-')

        # Linear plot right axis: phase.
        self.ax_gain_right = self.ax_gain.twinx() 
        self.ax_gain_right.set_ylabel(Mapping.label_for_figure_phase) 
        (self.line_phase,) = self.ax_gain_right.plot([], [], linestyle=':', color=Mapping.mapping_color_for_phase_line)

        self.canvas_gain = FigureCanvasTkAgg(self.fig_gain, master=self.frame_plot)
        w = self.canvas_gain.get_tk_widget()
        w.bind("<FocusIn>", lambda e:'break') # Prevent matplotlib widgets from stealing Tk shortcuts.

        # === Log gain plot ===
        self.fig_db = Figure(figsize=(8, 4))
        try:
            self.fig_db.set_tight_layout(True)
        except Exception:
            pass
        self.ax_db = self.fig_db.add_subplot(111)
        self.ax_db.set_xlabel(f"{Mapping.label_for_freq}({freq_unit})")
        self.ax_db.set_ylabel(Mapping.label_for_figure_gain_db)
        (self.line_db,) = self.ax_db.plot([], [], linestyle='-')

        # Log plot right axis: phase.
        self.ax_db_right = self.ax_db.twinx() 
        self.ax_db_right.set_ylabel(Mapping.label_for_figure_phase) 
        (self.line_phase_db,) = self.ax_db_right.plot([], [], linestyle=':', color=Mapping.mapping_color_for_phase_line)

        self.canvas_db = FigureCanvasTkAgg(self.fig_db, master=self.frame_plot)
        w = self.canvas_db.get_tk_widget()
        w.bind("<FocusIn>", lambda e:'break') # Prevent matplotlib widgets from stealing Tk shortcuts.

        self.canvas_gain.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Cursor interactions
        mplcursors.cursor([self.line_gain, self.line_phase, self.line_db, self.line_phase_db], hover=True)

        # Initial render
        self.refresh_plot()

    def show_plot(self, *args):
        """Show the plot that matches the current figure_mode variable."""
        try:
            # Toggle visibility
            if self.figure_mode.get() == Mapping.label_for_figure_gain_freq:
                self.canvas_db.get_tk_widget().pack_forget()
                self.canvas_gain.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            elif self.figure_mode.get() == Mapping.label_for_figure_gaindb_freq:
                self.canvas_gain.get_tk_widget().pack_forget()
                self.canvas_db.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # Refresh plot contents
            self.refresh_plot()
        except:
            pass

    def refresh_plot(self, *args):
        """Refresh the figures based on the latest data and settings."""

        def get_gain_corr():
            """Compute calibrated gain/phase data and store them in results."""
            # Without calibration the corrected data equals the raw data.
            if not (self.is_correct_enabled.get() and hasattr(self, "href_at") and self.href_at):
                self.results[Mapping.mapping_gain_corr] = self.results[Mapping.mapping_gain_raw]
                self.results[Mapping.mapping_gain_db_corr] = self.results[Mapping.mapping_gain_db_raw]
                self.results[Mapping.mapping_phase_deg_corr] = self.results[Mapping.mapping_phase_deg]
                return

            href_vals = self.href_at(self.results[Mapping.mapping_freq])
            # Dual-channel calibration or triggered mode uses complex division; otherwise magnitude only.
            if self.var_correct_mode.get() == Mapping.label_for_duo_chan_correct or self.trig_mode.get() == Mapping.label_for_triggered:
                href_vals = np.array(href_vals, dtype=np.complex128)
                H_corr = self.results[Mapping.mapping_gain_complex] / href_vals
                self.results[Mapping.mapping_gain_corr] = np.abs(H_corr)
                self.results[Mapping.mapping_gain_db_corr] = np.round(20 * np.log10(np.abs(H_corr)), 6)
                self.results[Mapping.mapping_phase_deg_corr] = np.round(np.degrees(np.angle(H_corr)), 6)
            else:
                eps = 1e-12
                href_abs = np.maximum(np.abs(href_vals), eps)
                self.results[Mapping.mapping_gain_corr]    = np.round(self.results[Mapping.mapping_gain_raw]/href_abs, 6)
                self.results[Mapping.mapping_gain_db_corr] = np.round(20*np.log10(np.maximum(self.results[Mapping.mapping_gain_corr], eps)), 6)

        def switch_mag_phase():
            """Toggle which curves are visible according to figure_mag_or_phase."""
            # Gain + phase: show all four curves.
            if self.var_mag_or_phase.get() == Mapping.label_for_mag_and_phase:
                self.line_gain.set_visible(True)
                self.line_phase.set_visible(True)
                self.line_db.set_visible(True)
                self.line_phase_db.set_visible(True)
            # Gain only: hide both phase curves.
            elif self.var_mag_or_phase.get() == Mapping.label_for_mag:
                self.line_gain.set_visible(True)
                self.line_phase.set_visible(False)
                self.line_db.set_visible(True)
                self.line_phase_db.set_visible(False)
            # Phase only: hide both magnitude curves.
            elif self.var_mag_or_phase.get() == Mapping.label_for_phase:
                self.line_gain.set_visible(False)
                self.line_phase.set_visible(True)
                self.line_db.set_visible(False)
                self.line_phase_db.set_visible(True)

        # Update line data
        try:
            freq_unit = self.freq_unit.get()
            get_gain_corr()
            switch_mag_phase()

            # Update the linear gain data and axes.
            self.line_gain.set_data(
                self.results[Mapping.mapping_freq]/CvtTools.convert_general_unit(freq_unit),
                self.results[Mapping.mapping_gain_corr] if self.is_correct_enabled.get() else self.results[Mapping.mapping_gain_raw]
            )
            self.ax_gain.set_xlabel(f"{Mapping.label_for_freq}({freq_unit})")
            
            # Update the log gain data and axes.
            self.line_db.set_data(
                self.results[Mapping.mapping_freq]/CvtTools.convert_general_unit(freq_unit),
                self.results[Mapping.mapping_gain_db_corr] if self.is_correct_enabled.get() else self.results[Mapping.mapping_gain_db_raw]
            )
            self.ax_db.set_xlabel(f"{Mapping.label_for_freq}({freq_unit})")

            # Update phase traces when dual-channel/triggered data is available.
            if self.results[Mapping.mapping_phase_deg].size and (self.var_correct_mode.get() == Mapping.label_for_duo_chan_correct or self.trig_mode.get() == Mapping.label_for_triggered):
                self.line_phase.set_data(
                    self.results[Mapping.mapping_freq]/CvtTools.convert_general_unit(freq_unit),
                    self.results[Mapping.mapping_phase_deg_corr] if self.is_correct_enabled.get() else self.results[Mapping.mapping_phase_deg]
                )

                self.line_phase_db.set_data(
                    self.results[Mapping.mapping_freq]/CvtTools.convert_general_unit(freq_unit),
                    self.results[Mapping.mapping_phase_deg_corr] if self.is_correct_enabled.get() else self.results[Mapping.mapping_phase_deg]
                )
            else:
                self.line_phase.set_data([], [])
                self.line_phase_db.set_data([], [])

            self.ax_gain.relim(); self.ax_gain.autoscale_view()
            self.ax_db.relim(); self.ax_db.autoscale_view()
            self.ax_gain_right.relim(); self.ax_gain_right.autoscale_view()
            self.ax_db_right.relim(); self.ax_db_right.autoscale_view()

            # Redraw whichever canvas is currently visible.
            if self.figure_mode.get() == Mapping.label_for_figure_gain_freq:
                self.canvas_gain.draw_idle()
            elif self.figure_mode.get() == Mapping.label_for_figure_gaindb_freq:
                self.canvas_db.draw_idle()
        except:
            pass
