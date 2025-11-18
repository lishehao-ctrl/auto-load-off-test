import sys
import re
import time
from datetime import datetime
import os
import pyvisa as visa
import csv
import numpy as np
from scipy.interpolate import make_interp_spline
from scipy.io import loadmat
import tkinter as tk
import threading
from threading import Event
import queue
from tkinter import ttk, filedialog, messagebox, font
from equips import *
from deviceMng import DeviceManager
from test import TestLoadOff
from configMgr import ConfigMgr
from cvtTools import CvtTools
from traceVal import TraceVal
from mapping import Mapping

class UI(tk.Tk):

    def __init__(self):
        super().__init__()  # Call tkinter initialization to create the main window
        self.change_font()  # Set default font

        # Set window title
        self.title(Mapping.label_for_input_ui)

        # Bind the callback function for closing the window
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initialize and display the UI
        self.generat_ui()


    def on_closing(self, *args):
        """Callback function before closing the window: save the configuration first, then destroy the window"""
        self.auto_save_config()
        self.destroy()


    def change_font(self):
        """Modify UI default font"""
        self.default_font = font.nametofont("TkDefaultFont")
        self.default_font.configure(
            family=Mapping.default_text_font[0], size=Mapping.default_text_font[1]
        )

        self.text_font = font.nametofont("TkTextFont")
        self.text_font.configure(
            family=Mapping.default_text_font[0], size=Mapping.default_text_font[1]
        )


    def generat_ui(self):
        """Generate main interface layout"""
        # Create main Frame
        self.frame_main = tk.Frame(self)
        self.frame_main.pack(anchor=tk.W, pady=5, fill=tk.BOTH, expand=True)

        # Create a test control area Frame
        self.frame_test = tk.Frame(self.frame_main)
        self.frame_test.pack(anchor=tk.W, fill=tk.BOTH, expand=True)

        # Initialize I/O, device control and test control
        self.initialize_io()
        self.generate_device_control()
        self.show_test_control()

        # Automatically load configuration files
        self.auto_load_config()

        # Create menu bar
        self.menu_bar = tk.Menu(self)

        # File menu
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_menu.add_command(
            label=Mapping.label_for_load_file_to_show,
            command=self.load_data_to_shown
        )
        file_menu.add_command(
            label=Mapping.label_for_load_file_to_ref,
            command=self.load_ref_file
        )
        file_menu.add_command(
            label=Mapping.label_for_load_config,
            command=self.load_config
        )
        file_menu.add_command(
            label=Mapping.label_for_save_file,
            command=self.save_file
        )
        file_menu.add_command(
            label=Mapping.label_for_save_config,
            command=self.save_config
        )
        file_menu.add_separator()
        file_menu.add_command(
            label=Mapping.label_for_exit,
            command=sys.exit
        )

        # Configuration menu
        config_menu = tk.Menu(self.menu_bar, tearoff=0)
        config_menu.add_command(
            label=Mapping.label_for_device_configure_window,
            command=self.device_control_window.deiconify
        )

        # Add menu to menu bar
        self.menu_bar.add_cascade(
            label=Mapping.label_for_file_menu, 
            menu=file_menu
        )
        self.menu_bar.add_cascade(
            label=Mapping.label_for_config_menu, 
            menu=config_menu
        )

        # Set the window's menu bar
        self.config(menu=self.menu_bar)

        # Device control window hidden by default
        self.device_control_window.withdraw()

    def initialize_io(self):
        """Initialize I/O related variables, devices and channels"""

        # Automatically save configuration switch
        self.auto_save = tk.BooleanVar()

        # Frequency unit (e.g. Hz/kHz/MHz)
        self.freq_unit = tk.StringVar(value="")

        # Test object, bound frequency unit
        self.test = TestLoadOff(freq_unit=self.freq_unit)
        # Synchronize frequency unit tags when frequency units change
        self.freq_unit.trace_add("write", self.test.refresh_plot)

        # configuration manager
        self.cfgMgr = ConfigMgr()

        # Create device manager
        self.var_device_num = tk.IntVar(value=self.test.device_num)
        self.device_manager = DeviceManager()
        self.device_manager.create_devices(
            device_num=self.var_device_num.get(),
            freq_unit=self.test.freq_unit
        )

        # ========== AWG signal source equipment ==========
        self.awg_device = self.device_manager.get_devices()[0]  # Get the first device as AWG
        self.awg_device.var_device_type.set(Mapping.label_for_device_type_awg)  # Set device type to AWG

        # AWG channel settings
        self.awg_device.var_chan_num.set(1)      # 1 channel
        self.awg_device.create_chan()            # Create channel
        self.test.awg = self.awg_device.find_channel(chan_tag=1)  # Bind the AWG channel of the test object

        # ========== Oscilloscope Equipment ==========
        self.osc_device = self.device_manager.get_devices()[1]  # The second device is an oscilloscope
        self.osc_device.var_device_type.set(Mapping.label_for_device_type_osc)  # Set the device type to oscilloscope

        # Oscilloscope channel settings
        self.osc_device.var_chan_num.set(3)      # 3 channels
        self.osc_device.create_chan()            # Create channel

        # Main test channel
        self.test.osc_test = self.osc_device.find_channel(chan_tag=1)
        # Reference channel, copy autonomous test channel configuration
        self.test.osc_ref = (self.osc_device.find_channel(chan_tag=2)
                             .copy_from(self.test.osc_test))
        # Trigger channel, copy autonomous test channel configuration
        self.test.osc_trig = (self.osc_device.find_channel(chan_tag=3)
                              .copy_from(self.test.osc_test))
        self.test.osc_trig.chan_index.set(value=2)  # Set trigger channel index to 2
        self.test.trace_trig_chan_index()           # Update triggers channel index callback

    def set_ui_from_config(self):
        """Read parameters from the configuration file and backfill them into UI variables; only do value acquisition and formatting, without changing the business logic"""

        # frequency unit
        freq_unit = self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_freq_unit,
            fallback=Mapping.mapping_mhz
        ).replace(" ", "").lower()

        # Inclusion judgment is used here: 'g'->GHz, 'm'->MHz, 'k'->kHz; otherwise the default is Hz
        if "g" in freq_unit:
            freq_unit = Mapping.mapping_ghz
        elif "m" in freq_unit:
            freq_unit = Mapping.mapping_mhz
        elif "k" in freq_unit:
            freq_unit = Mapping.mapping_khz
        else:
            freq_unit = Mapping.mapping_hz

        # ========= AWG/OSC basic parameters (use cvtTools for unit analysis and formatting) =========
        # Frequency scan: start/stop/step/unit
        self.test.awg.start_freq.set(str(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_start_freq, fallback=Mapping.default_start_freq
        )))
        self.test.awg.stop_freq.set(str(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_stop_freq, fallback=Mapping.default_stop_freq
        )))
        self.test.awg.step_freq.set(str(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_step_freq, fallback=Mapping.default_step_freq
        )))
        self.test.awg.step_num.set(str(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_step_num, fallback=Mapping.default_step_num
        )))
        self.test.awg.is_log_freq_enabled.set(self.cfgMgr.cfg.getboolean(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_is_log_freq_enabled, fallback=False
        ))
        self.test.freq_unit.set(freq_unit)

        # AWG amplitude: converted to Vpp text; output impedance
        self.test.awg.amp.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_awg_amp, fallback=Mapping.default_awg_amp
        ))
        self.test.awg.imp.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_awg_imp, fallback=Mapping.default_awg_imp
        ))

        # OSC vertical offset/range (converted to V text), input impedance, coupling, number of sampling points
        self.test.osc_test.yoffset.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_yoffset, fallback=Mapping.default_yoffset
        ))
        self.test.osc_test.range.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_range, fallback=Mapping.default_range
        ))
        self.test.osc_test.imp.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_osc_imp, fallback=Mapping.default_osc_imp
        ))
        self.test.osc_test.coupling.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_osc_coup, fallback=Mapping.default_osc_coup
        ))
        self.test.osc_test.points.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_samp_pts, fallback=Mapping.default_samp_pts
        ))

        # ========= Mode area: range linkage/calibration mode/trigger mode/auto save/auto reset =========
        self.test.is_auto_osc_range.set(self.cfgMgr.cfg.getboolean(
            self.cfgMgr.mapping_mode, self.cfgMgr.mapping_is_auto_range, fallback=Mapping.default_is_auto_range
        ))
        self.test.var_correct_mode.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_mode, self.cfgMgr.mapping_correct_mode, fallback=Mapping.default_correct_mode
        ))
        self.test.is_correct_enabled.set(self.cfgMgr.cfg.getboolean(
            self.cfgMgr.mapping_mode, self.cfgMgr.mapping_is_correct_enabled, fallback=Mapping.default_is_correct_enabled
        ))

        # Trigger mode: free run / triggered (ignore spaces and case)
        trig_mode = self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_mode, self.cfgMgr.mapping_trig_mode, fallback=Mapping.default_trig_mode
        ).replace(" ", "")
        if trig_mode.lower() == Mapping.label_for_free_run.lower().replace(" ", ""):
            trig_mode = Mapping.label_for_free_run
        elif trig_mode.lower() == Mapping.label_for_triggered.lower().replace(" ", ""):
            trig_mode = Mapping.label_for_triggered
        else:
            trig_mode = Mapping.label_for_free_run
        self.test.trig_mode.set(trig_mode)

        # Auto save and auto reset
        self.auto_save.set(self.cfgMgr.cfg.getboolean(
            self.cfgMgr.mapping_mode, self.cfgMgr.mapping_is_auto_save, fallback=Mapping.default_is_auto_save
        ))
        self.test.auto_reset.set(self.cfgMgr.cfg.getboolean(
            self.cfgMgr.mapping_mode, self.cfgMgr.mapping_is_auto_reset, fallback=Mapping.default_is_auto_reset
        ))

        # ========= Device name (default: AWG=DSG4102, OSC=MDO34) =========
        self.awg_device.var_device_name.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_device, self.cfgMgr.mapping_awg_name, fallback=Mapping.default_awg_name
        ))
        self.osc_device.var_device_name.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_device, self.cfgMgr.mapping_osc_name, fallback=Mapping.default_osc_name
        ))

        # ========= Channel index mapping (restored from configuration) =========
        self.test.awg.chan_index.set(self.cfgMgr.cfg.getint(
            self.cfgMgr.mapping_chan, self.cfgMgr.mapping_awg_chan_index, fallback=Mapping.default_awg_chan_index
        ))
        self.test.osc_test.chan_index.set(self.cfgMgr.cfg.getint(
            self.cfgMgr.mapping_chan, self.cfgMgr.mapping_osc_test_chan_index, fallback=Mapping.default_osc_test_chan_index
        ))
        self.test.osc_trig.chan_index.set(self.cfgMgr.cfg.getint(
            self.cfgMgr.mapping_chan, self.cfgMgr.mapping_osc_trig_chan_index, fallback=Mapping.default_osc_trig_chan_index
        ))
        self.test.osc_ref.chan_index.set(self.cfgMgr.cfg.getint(
            self.cfgMgr.mapping_chan, self.cfgMgr.mapping_osc_ref_chan_index, fallback=Mapping.default_osc_ref_chan_index
        ))

        # ========= Connection parameters: AWG =========
        auto_lan = self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_connection, self.cfgMgr.mapping_awg_connect_mode, fallback=Mapping.default_awg_connect_mode
        )
        auto_lan = "".join(ch for ch in auto_lan if ch.isalpha())
        if auto_lan.lower() == Mapping.label_for_auto.lower():
            auto_lan = Mapping.label_for_auto
        elif auto_lan.lower() == Mapping.label_for_lan.lower():
            auto_lan = Mapping.label_for_lan
        else:
            auto_lan = Mapping.label_for_auto
        self.awg_device.var_switch_auto_lan.set(auto_lan)

        auto_visa = self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_connection, self.cfgMgr.mapping_awg_visa, fallback=Mapping.default_awg_visa
        ).strip()
        self.awg_device.var_auto_visa_address.set(auto_visa)

        ip = self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_connection, self.cfgMgr.mapping_awg_ip, fallback=Mapping.default_awg_ip
        ).replace(" ", "")
        ip = re.search(r"(\d{1,3})\.?(\d{1,3})\.?(\d{1,3})\.?(\d{1,3})", ip)
        try:
            self.awg_device.var_lan_ip_list[0].set(ip.group(1))
            self.awg_device.var_lan_ip_list[1].set(ip.group(2))
            self.awg_device.var_lan_ip_list[2].set(ip.group(3))
            self.awg_device.var_lan_ip_list[3].set(ip.group(4))
        except:
            self.awg_device.var_lan_ip_list[0].set("0")
            self.awg_device.var_lan_ip_list[1].set("0")
            self.awg_device.var_lan_ip_list[2].set("0")
            self.awg_device.var_lan_ip_list[3].set("0")

        # ========= Connection parameters: OSC =========
        auto_lan = self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_connection, self.cfgMgr.mapping_osc_connect_mode, fallback=Mapping.default_osc_connect_mode
        )
        auto_lan = "".join(ch for ch in auto_lan if ch.isalpha())
        if auto_lan.lower() == Mapping.label_for_auto.lower():
            auto_lan = Mapping.label_for_auto
        elif auto_lan.lower() == Mapping.label_for_lan.lower():
            auto_lan = Mapping.label_for_lan
        else:
            auto_lan = Mapping.label_for_auto
        self.osc_device.var_switch_auto_lan.set(auto_lan)

        auto_visa = self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_connection, self.cfgMgr.mapping_osc_visa, fallback=Mapping.default_osc_visa
        ).strip()
        self.osc_device.var_auto_visa_address.set(auto_visa)

        ip = self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_connection, self.cfgMgr.mapping_osc_ip, fallback=Mapping.default_osc_ip
        ).replace(" ", "")
        ip = re.search(r"(\d{1,3})\.?(\d{1,3})\.?(\d{1,3})\.?(\d{1,3})", ip)
        try:
            self.osc_device.var_lan_ip_list[0].set(ip.group(1))
            self.osc_device.var_lan_ip_list[1].set(ip.group(2))
            self.osc_device.var_lan_ip_list[2].set(ip.group(3))
            self.osc_device.var_lan_ip_list[3].set(ip.group(4))
        except:
            self.osc_device.var_lan_ip_list[0].set("0")
            self.osc_device.var_lan_ip_list[1].set("0")
            self.osc_device.var_lan_ip_list[2].set("0")
            self.osc_device.var_lan_ip_list[3].set("0")


    def set_config_from_ui(self):
        """Write the parameters in the current UI back to the configuration."""

        # ========= General (general parameters: frequency sweep/unit/AWG amplitude/OSC range, etc.) =========
        # Frequency scan: uniformly stored as a string
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_general, self.cfgMgr.mapping_start_freq, str(self.test.awg.start_freq.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_general, self.cfgMgr.mapping_stop_freq,  str(self.test.awg.stop_freq.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_general, self.cfgMgr.mapping_step_freq,  str(self.test.awg.step_freq.get()))

        # Number of steps (parse_general_val is error-tolerant if non-integer input is allowed in the UI; still ultimately written as str)
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_step_num,
            str(CvtTools.parse_general_val(self.test.awg.step_num.get()))
        )

        # Logarithmic scan switch: saved as "on"/"off"
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_is_log_freq_enabled,
            "on" if bool(self.test.awg.is_log_freq_enabled.get()) else "off"
        )

        # Frequency unit: save UI text directly
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_freq_unit,
            str(self.test.freq_unit.get())
        )

        # AWG amplitude: save UI text directly
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_awg_amp,
            str(self.test.awg.amp.get())
        )
        # AWG output impedance: save current selection directly
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_awg_imp,
            str(self.test.awg.imp.get())
        )

        # OSC vertical offset/range: save UI text directly
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_yoffset,
            str(self.test.osc_test.yoffset.get())
        )
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_range,
            str(self.test.osc_test.range.get())
        )

        # OSC input impedance/coupling/number of sampling points, directly save UI text
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_general, self.cfgMgr.mapping_osc_imp,  str(self.test.osc_test.imp.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_general, self.cfgMgr.mapping_osc_coup, str(self.test.osc_test.coupling.get()))
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_samp_pts,
            str(self.test.osc_test.points.get())
        )
        # NOTE: If points are allowed to be set to a very small number, it is recommended to perform lower limit protection at the UI layer or before writing (such as >= 2 or >= 128)

        # ========= Mode (Mode: Auto range/Calibrate/Trigger/Auto save/Auto reset) =========
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_mode,
            self.cfgMgr.mapping_is_auto_range,
            Mapping.mapping_state_on if bool(self.test.is_auto_osc_range.get()) else Mapping.mapping_state_off
        )
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_mode,
            self.cfgMgr.mapping_correct_mode,
            str(self.test.var_correct_mode.get())
        )
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_mode,
            self.cfgMgr.mapping_is_correct_enabled,
            Mapping.mapping_state_on if bool(self.test.is_correct_enabled.get()) else Mapping.mapping_state_off
        )
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_mode,
            self.cfgMgr.mapping_trig_mode,
            str(self.test.trig_mode.get())
        )
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_mode,
            self.cfgMgr.mapping_is_auto_save,
            Mapping.mapping_state_on if bool(self.auto_save.get()) else Mapping.mapping_state_off
        )
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_mode,
            self.cfgMgr.mapping_is_auto_reset,
            Mapping.mapping_state_on if bool(self.test.auto_reset.get()) else Mapping.mapping_state_off
        )

        # ========= Device (device name: AWG/OSC) =========
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_device, self.cfgMgr.mapping_awg_name, str(self.awg_device.var_device_name.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_device, self.cfgMgr.mapping_osc_name, str(self.osc_device.var_device_name.get()))

        # ========= Channel (channel map: index) =========
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_chan, self.cfgMgr.mapping_awg_chan_index,         str(self.test.awg.chan_index.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_chan, self.cfgMgr.mapping_osc_test_chan_index,    str(self.test.osc_test.chan_index.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_chan, self.cfgMgr.mapping_osc_trig_chan_index,    str(self.test.osc_trig.chan_index.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_chan, self.cfgMgr.mapping_osc_ref_chan_index,     str(self.test.osc_ref.chan_index.get()))

        # ========= Connection (Connection: Mode/VISA/IP) =========
        # Connected mode: save UI text directly
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_connection,
            self.cfgMgr.mapping_awg_connect_mode,
            str(self.awg_device.var_switch_auto_lan.get())
        )
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_connection,
            self.cfgMgr.mapping_awg_visa,
            str(self.awg_device.var_auto_visa_address.get())
        )
        # IP: The four-segment input box is spliced ​​into x.x.x.x; no numerical verification is performed here (relaxed analysis and disclosure have been done during loading)
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_connection,
            self.cfgMgr.mapping_awg_ip,
            ".".join(str(v.get()) for v in self.awg_device.var_lan_ip_list[:4])
        )

        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_connection,
            self.cfgMgr.mapping_osc_connect_mode,
            str(self.osc_device.var_switch_auto_lan.get())
        )
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_connection,
            self.cfgMgr.mapping_osc_visa,
            str(self.osc_device.var_auto_visa_address.get())
        )
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_connection,
            self.cfgMgr.mapping_osc_ip,
            ".".join(str(v.get()) for v in self.osc_device.var_lan_ip_list[:4])
        )


    def save_config(self):
        """Manual save: first write the UI back to the configuration, then save it to disk and trigger an automatic save."""
        self.set_config_from_ui()
        self.cfgMgr.save()
        self.cfgMgr.auto_save()


    def auto_save_config(self):
        """Autosave: just write the UI back to the configuration and call auto_save"""
        self.set_config_from_ui()
        self.cfgMgr.auto_save()

    def show_test_control(self):
        """Build and mount the behavior of the test control area (enable/disable controls, run tests, progress queue polling, etc.)"""

        # ========== Utility function: recursively enable/disable all child controls ==========
        def activate_all_widgets(parent=self):
            """Recursively enable all child controls under parent (ignore on failure)"""
            for child in parent.winfo_children():
                try:
                    child.config(state=tk.NORMAL)
                except Exception:
                    pass
                activate_all_widgets(child)

        def disable_all_widgets(parent=self):
            """Recursively disable all child controls under parent (ignore on failure)"""
            for child in parent.winfo_children():
                try:
                    child.config(state=tk.DISABLED)
                except Exception:
                    pass
                disable_all_widgets(child)

        # ========== Tool function: uniformly control the status of a group of "calibration-related controls" according to the calibration mode ==========
        def set_corr_controls_state(state=tk.NORMAL):
            """According to the current calibration mode, unified start and stop calibration related controls"""
            if self.test.var_correct_mode.get() == Mapping.label_for_no_correct:
                # No Calibration: Does not enable any calibration controls
                return
            # Single Channel / Dual Channel: All three are enabled
            try:
                self.set_as_ref.config(state=state)
                self.btn_load_ref.config(state=state)
                self.btn_enable_corr.config(state=state)
            except Exception:
                pass
            # Dual channels only: Amplitude and phase switching pull-down enable/disable
            if self.test.var_correct_mode.get() == Mapping.label_for_duo_chan_correct:
                try:
                    self.cmb_mag_or_phase.config(state=state)
                except Exception:
                    pass

        # ========== UI state management during testing ==========
        def activate_during_test():
            """After the test starts: Turn on necessary controls"""
            try:
                self.btn_stop_test.config(state=tk.NORMAL)
                self.btn_save_data.config(state=tk.NORMAL)
                self.lb_status.config(state=tk.NORMAL)
                self.cmb_figure_switch.config(state=tk.NORMAL)
            except Exception:
                pass
            set_corr_controls_state(state=tk.NORMAL)

        def disable_during_set():
            """The test has not started or is being cleaned: close some controls"""
            try:
                self.btn_stop_test.config(state=tk.DISABLED)
            except Exception:
                pass

        # ========== Start testing ==========
        def start_test():
            """The main process after clicking "Start Test": the background thread runs the collection; the main thread polls the queue regularly and refreshes the UI"""

            def test_func():
                """Background thread: perform blocking actions (connection verification, frequency sweep acquisition, etc.).Direct manipulation of Tk controls is prohibited."""
                try:
                    # 1) Disable everything first to prevent users from accidentally touching it during the preparation stage; and reset the event flag
                    disable_all_widgets()
                    
                    self.test.stop_event.clear()
                    self.pause_refresh_insts.clear()
                except Exception as e:
                    # Prepare to fail: restore UI and prompt
                    messagebox.showwarning(Mapping.title_alert, f"Not ready: {e}")
                    activate_all_widgets()
                    disable_during_set()
                    self.pause_refresh_insts.set()
                    return

                try:
                    # 2) Activating "during testing" requires available controls
                    activate_during_test()

                    # 3) Device connection/collection
                    self.test.start_swep_test()

                    self.lb_status.config(text="Started testing") 

                except Exception as e:
                    # Error occurred during collection, automatically saved
                    messagebox.showwarning(Mapping.title_alert, f"Test failed: {e}")
                    self.lb_status.config(text="")

                    if self.auto_save.get():
                        self.auto_save_file()

                    activate_all_widgets()
                    disable_during_set()

                    # Close device connection
                    try:
                        self.test.awg.inst_close()
                    except Exception:
                        pass
                    for _osc in (self.test.osc_test, self.test.osc_ref, self.test.osc_trig):
                        try:
                            _osc.inst_close()
                        except Exception:
                            pass

                    self.pause_refresh_insts.set()
                    return

            def process_queue():
                """The main thread polls the queue regularly and refreshes the image and status bar.
- item: current frequency point
- None: end signal"""
                finished = False
                try:
                    self.test.refresh_plot()
                    while True:
                        item = self.test.data_queue.get_nowait()
                        if item is None:
                            # End: update status and call stop_test
                            self.lb_status.config(
                                text="Done" if not self.test.stop_event.is_set() else "Stopped"
                            )
                            stop_test() 
                            finished = True
                            return

                        # Refresh graph
                        self.test.refresh_plot()

                        # Update status line: display frequency points in current units
                        unit = self.test.freq_unit.get()

                        scale = CvtTools.convert_general_unit(unit)
                        self.lb_status.config(text=f"Freq: {item/scale:.2f} {unit}")


                except queue.Empty:
                    pass
                finally:
                    if not finished:
                        # Poll every 100 ms
                        self.after(100, process_queue)

            # Start background collection thread
            threading.Thread(target=test_func, daemon=True).start()

            # Start queue polling (main thread)
            self.after(100, process_queue)

        def stop_test():
            """Stop testing:
- Send stop event
- Optional auto-save data
- Automatically save configuration
- Close device connection
- Restore UI"""
            self.test.stop_event.set()

            # Automatically save data (configurable)
            if self.auto_save.get():
                try:
                    self.auto_save_file()
                except Exception as e:
                    messagebox.showwarning(Mapping.title_alert, f"Failed to auto-save data: {e}")

            # Automatically save configuration
            try:
                self.auto_save_config()
            except Exception as e:
                messagebox.showwarning(Mapping.title_alert, f"Failed to auto-save config: {e}")

            # Turn off the device
            for inst in (getattr(self.test, "awg", None),
                         getattr(self.test, "osc_test", None),
                         getattr(self.test, "osc_ref", None),
                         getattr(self.test, "osc_trig", None)):
                try:
                    if inst is not None:
                        inst.inst_close()
                except Exception:
                    pass

            # Allow the background to automatically monitor device connections and resume operations
            self.pause_refresh_insts.set()

            # Restore UI
            activate_all_widgets()
            disable_during_set()  


        step_widgets = []
        step_row_index = 2

        def show_step_control(*args):
            """Display step settings according to the "Log Sweep Switch":
- Logarithm: Display [number of steps]
- Linear: Display [step size]"""
            nonlocal step_widgets
            # Empty the previous row before rebuilding it
            for widget in step_widgets:
                widget.destroy()
            step_widgets = []

            if self.test.awg.is_log_freq_enabled.get():
                lb_text = f"{Mapping.label_for_set_step_num}: "
                entry_var = self.test.awg.step_num

                # Normalization: positive numbers, common format, integers
                def _norm_step_num(_e=None):
                    TraceVal.general_out_focus(var=self.test.awg.step_num)
                    TraceVal.force_int_out_focus(var=self.test.awg.step_num)
                    TraceVal.force_positive_out_focus(var=self.test.awg.step_num)

                norm_callback = _norm_step_num

            else:
                lb_text = f"{Mapping.label_for_set_step_freq}: "
                entry_var = self.test.awg.step_freq

                # Normalization: positive numbers, frequency units
                def _norm_step_freq(_e=None):
                    TraceVal.force_positive_out_focus(var=self.test.awg.step_freq)
                    TraceVal.freq_out_focus(freq=self.test.awg.step_freq)

                norm_callback = _norm_step_freq

            lb_step = tk.Label(frame_awg_start_stop_freq, text=lb_text)
            lb_step.grid(row=step_row_index, column=0, sticky=tk.E, padx=5, pady=2)

            etr = tk.Entry(frame_awg_start_stop_freq, textvariable=entry_var, width=10)
            etr.grid(row=step_row_index, column=1, sticky=tk.W, padx=5, pady=2)

            etr.bind("<FocusOut>", norm_callback)
            etr.bind("<Return>",   norm_callback)

            step_widgets = [lb_step, etr]

        def show_correct_modes_control(*args):
            """Generate corresponding controls according to the calibration mode:
            - No calibration: only display trigger mode
            - Single channel: trigger + set as reference/read reference/calibration enable
            - Dual channel: trigger + set as reference/read reference/calibration enable"""
            # Empty container
            for child in frame_correct_modes.winfo_children():
                child.destroy()

            # Calibration mode switch
            ttk.Combobox(frame_correct_modes,
                         textvariable=self.test.var_correct_mode,
                         values=Mapping.values_correct_modes,
                         width=10).pack(side=tk.LEFT, padx=5)

            # Trigger mode (required for all modes)
            ttk.Combobox(frame_correct_modes,
                         textvariable=self.test.trig_mode,
                         values=Mapping.values_trig_mode,
                         width=10).pack(side=tk.LEFT, padx=5)

            if self.test.var_correct_mode.get() == Mapping.label_for_no_correct:
                self.test.is_correct_enabled.set(False)  # Forced shutdown when not calibrating
                return 

            # Three modes are shared: set as reference/read reference/calibration enable
            def set_as_ref(*args):
                try:
                    res = self.test.results
                    self.test.href_at = self.build_bspline_holdout_interp(
                        ref_freq=res[Mapping.mapping_freq],
                        gain_db=res[Mapping.mapping_gain_db_raw],
                        phase=res[Mapping.mapping_phase_deg]
                    )
                    self.test.refresh_plot() 
                except Exception as e:
                    messagebox.showwarning(Mapping.title_alert, f"Failed to set calibration: {e}")

            self.set_as_ref = tk.Button(frame_correct_modes, text=Mapping.label_for_set_ref, command=set_as_ref)
            self.set_as_ref.pack(side=tk.LEFT, padx=5)

            self.btn_load_ref = tk.Button(frame_correct_modes, text=Mapping.label_for_load_ref, command=self.load_ref_file)
            self.btn_load_ref.pack(side=tk.LEFT, padx=5)

            self.btn_enable_corr = tk.Checkbutton(frame_correct_modes, text=Mapping.label_for_enable_ref, variable=self.test.is_correct_enabled)
            self.btn_enable_corr.pack(side=tk.LEFT, padx=5)

        def show_mag_or_phase(*args):
            """The [Amplitude/Phase] pull-down is displayed when "Dual Channel Calibration" or "Trigger Mode=Triggered";
Otherwise, "magnitude" is forced to be displayed."""
            for child in frame_mag_or_phase.winfo_children():
                child.destroy()

            need_switch = (
                self.test.var_correct_mode.get() == Mapping.label_for_duo_chan_correct
                or self.test.trig_mode.get() == Mapping.label_for_triggered
            )

            if need_switch:
                self.cmb_mag_or_phase = ttk.Combobox(
                    frame_mag_or_phase,
                    textvariable=self.test.var_mag_or_phase,
                    values=Mapping.values_mag_or_phase,
                    width=10
                )
                self.cmb_mag_or_phase.pack(side=tk.RIGHT, padx=5)
            else:
                # Default falls back to "amplitude"
                self.test.var_mag_or_phase.set(value=Mapping.label_for_mag)


        def connection_check(*args):
            """Background connection detection:
- Create two background threads to detect the connection status of AWG and OSC devices respectively
- Try turning the device on + off every 0.5 seconds to determine if it can be connected
- Pass the status to the UI main thread through the queue, and the main thread is responsible for refreshing the "indicator light" color"""

            connection_status_queue = queue.Queue()  # Thread-safe queue, used to store connection status

            def awg_connection_worker():
                """AWG device active thread"""
                awg_rm = visa.ResourceManager()
                while True:
                    self.pause_refresh_insts.wait()  # Waiting for event set, no detection during blocking
                    awg_ready = False

                    try:
                        visas = awg_rm.list_resources()
                        if self.test.awg.VisaAddress in visas:
                            awg_ready = True
                    except:
                        awg_rm = visa.ResourceManager()
                        visas = awg_rm.list_resources()
                        if self.test.awg.VisaAddress in visas:
                            awg_ready = True

                    # Put the status into the queue and update the UI from the main thread
                    connection_status_queue.put((Mapping.label_for_device_type_awg, awg_ready))
                    time.sleep(0.5)  # Detect once every 0.5 seconds

            def osc_connection_worker():
                """OSC device active thread"""
                osc_rm = visa.ResourceManager()
                while True:
                    self.pause_refresh_insts.wait()  # Execute after waiting for event set
                    osc_ready = False

                    try:
                        visas = osc_rm.list_resources()
                        if self.test.osc_test.VisaAddress in visas:
                            osc_ready = True
                    except:
                        osc_rm = visa.ResourceManager()
                        visas = osc_rm.list_resources()
                        if self.test.osc_test.VisaAddress in visas:
                            osc_ready = True

                    connection_status_queue.put((Mapping.label_for_device_type_osc, osc_ready))
                    time.sleep(0.5)

            def update_connection_status():
                """Main thread UI update function:
- Poll all connection status to be updated in the queue
- Update "light" color based on ready status: green = connected, red = not connected"""
                try:
                    while True:
                        device_type, ready = connection_status_queue.get_nowait()
                        if device_type == Mapping.label_for_device_type_awg:
                            c_awg_connection_status.itemconfig(awg_light, fill="green" if ready else "red")
                        elif device_type == Mapping.label_for_device_type_osc:
                            c_osc_connection_status.itemconfig(osc_light, fill="green" if ready else "red")
                except queue.Empty:
                    pass  # Queue is empty -> no processing
                finally:
                    # Call itself again every 100 ms to implement periodic updates of the UI
                    self.after(100, update_connection_status)

            # Start the background detection thread (daemon mode)
            threading.Thread(target=awg_connection_worker, daemon=True).start()
            threading.Thread(target=osc_connection_worker, daemon=True).start()

            # Start UI scheduled refresh
            update_connection_status()


        # ========================= Left: Equipment and sweep parameters =========================
        frame_load_off_test = tk.Frame(self.frame_test)
        frame_load_off_test.pack(anchor=tk.W, fill=tk.BOTH, expand=True)

        frame_left = tk.Frame(frame_load_off_test)
        frame_left.pack(side=tk.LEFT, anchor=tk.N, fill=tk.Y)

        # Device Configuration Area (AWG/OSC)
        frame_device_config = tk.Frame(frame_left)
        frame_device_config.pack(anchor=tk.W)

        # Bottom test control (Start/Stop, online status, status bar)
        frame_test_control = tk.Frame(frame_left)
        frame_test_control.pack(side=tk.BOTTOM)

        # ------------------ AWG: Sweep parameters ------------------
        frame_awg = tk.Frame(frame_device_config)
        frame_awg.pack(anchor=tk.W)

        frame_awg_freq = tk.Frame(frame_awg)
        frame_awg_freq.pack(anchor=tk.W)

        # Start/stop/step setting container
        frame_awg_start_stop_freq = tk.Frame(frame_awg_freq)
        frame_awg_start_stop_freq.pack(side=tk.LEFT, padx=5)
        frame_awg_start_stop_freq.grid_columnconfigure(1, weight=1)

        # starting frequency
        lb_set_start_freq = tk.Label(frame_awg_start_stop_freq, text=f"{Mapping.label_for_set_start_frequency}: ")
        lb_set_start_freq.grid(row=0, column=0, sticky=tk.E, padx=5, pady=2)

        etr_set_start_freq = tk.Entry(frame_awg_start_stop_freq, textvariable=self.test.awg.start_freq, width=10)
        etr_set_start_freq.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        # Normalization: number + frequency string
        etr_set_start_freq.bind("<FocusOut>", lambda e: TraceVal.freq_out_focus(freq=self.test.awg.start_freq))
        etr_set_start_freq.bind("<Return>",   lambda e: TraceVal.freq_out_focus(freq=self.test.awg.start_freq))

        # Termination frequency
        lb_set_stop_freq = tk.Label(frame_awg_start_stop_freq, text=f"{Mapping.label_for_set_stop_frequency}: ")
        lb_set_stop_freq.grid(row=1, column=0, sticky=tk.E, padx=5, pady=2)

        etr_set_stop_freq = tk.Entry(frame_awg_start_stop_freq, textvariable=self.test.awg.stop_freq, width=10)
        etr_set_stop_freq.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        # Normalization: positive number + frequency string
        etr_set_stop_freq.bind("<FocusOut>", lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.stop_freq),
                                                        TraceVal.freq_out_focus(freq=self.test.awg.stop_freq)))
        etr_set_stop_freq.bind("<Return>",   lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.stop_freq),
                                                        TraceVal.freq_out_focus(freq=self.test.awg.stop_freq)))

        # Step setting (log = number of steps; linear = step size)
        show_step_control()

        # Center/scan width/unit selection container
        frame_awg_center_freq = tk.Frame(frame_awg_freq)
        frame_awg_center_freq.pack(side=tk.LEFT, padx=5)

        # center frequency
        frame_set_freq_center = tk.Frame(frame_awg_center_freq)
        frame_set_freq_center.pack(anchor=tk.W)
        frame_set_freq_center.grid_columnconfigure(1, weight=1)

        lb_set_center_freq = tk.Label(frame_set_freq_center, text=f"{Mapping.label_for_set_center_frequency}: ")
        lb_set_center_freq.grid(row=0, column=0, sticky=tk.E, padx=5, pady=2)

        etr_set_center_freq = tk.Entry(frame_set_freq_center, textvariable=self.test.awg.center_freq, width=10)
        etr_set_center_freq.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        # Normalization: positive number + frequency string
        etr_set_center_freq.bind("<FocusOut>", lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.center_freq),
                                                        TraceVal.freq_out_focus(freq=self.test.awg.center_freq)))
        etr_set_center_freq.bind("<Return>",   lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.center_freq),
                                                        TraceVal.freq_out_focus(freq=self.test.awg.center_freq)))

        # scan width
        frame_awg_interval_freq = tk.Frame(frame_awg_center_freq)
        frame_awg_interval_freq.pack(anchor=tk.W)
        frame_awg_interval_freq.grid_columnconfigure(1, weight=1)

        lb_set_interval_freq = tk.Label(frame_awg_interval_freq, text=f"{Mapping.label_for_set_interval_frequency}: ")
        lb_set_interval_freq.grid(row=0, column=0, sticky=tk.E, padx=5, pady=2)

        etr_set_interval_freq = tk.Entry(frame_awg_interval_freq, textvariable=self.test.awg.interval_freq, width=10)
        etr_set_interval_freq.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        # normalization: frequency string
        etr_set_interval_freq.bind("<FocusOut>", lambda e: TraceVal.freq_out_focus(freq=self.test.awg.interval_freq))
        etr_set_interval_freq.bind("<Return>",   lambda e: TraceVal.freq_out_focus(freq=self.test.awg.interval_freq))

        # Unit and Logarithmic Switches
        frame_set_freq_unit = tk.Frame(frame_awg_center_freq)
        frame_set_freq_unit.pack(anchor=tk.W)

        btn_log_freq = tk.Checkbutton(frame_set_freq_unit, text=Mapping.label_for_log, variable=self.test.awg.is_log_freq_enabled)
        btn_log_freq.pack(side=tk.LEFT, padx=5)
        # Refresh "Step Settings" control when switching log/linear
        self.test.awg.is_log_freq_enabled.trace_add("write", show_step_control)

        lb_set_freq_unit = tk.Label(frame_set_freq_unit, text=f"{Mapping.label_for_freq_unit}")
        lb_set_freq_unit.pack(side=tk.LEFT, padx=2)

        cmb_set_freq_unit = ttk.Combobox(frame_set_freq_unit, width=5,
                                        textvariable=self.test.freq_unit,
                                        values=Mapping.values_freq_unit)
        cmb_set_freq_unit.pack(side=tk.LEFT)

        # AWG amplitude
        frame_awg_amplitude = tk.Frame(frame_awg)
        frame_awg_amplitude.pack(anchor=tk.W, padx=5)

        frame_awg_amplitude_control = tk.Frame(frame_awg_amplitude)
        frame_awg_amplitude_control.pack(anchor=tk.W)
        frame_awg_amplitude_control.grid_columnconfigure(1, weight=1)

        lb_awg_amplitude = tk.Label(frame_awg_amplitude_control, text=f"{Mapping.label_for_set_amp}: ")
        lb_awg_amplitude.grid(row=0, column=0, sticky=tk.E, padx=5, pady=2)

        etr_awg_amplitude = tk.Entry(frame_awg_amplitude_control, textvariable=self.test.awg.amp, width=10)
        etr_awg_amplitude.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        # Normalization: positive number + amplitude unit
        etr_awg_amplitude.bind("<FocusOut>", lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.amp),
                                                        TraceVal.vpp_out_focus(vpp=self.test.awg.amp)))
        etr_awg_amplitude.bind("<Return>",   lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.amp),
                                                        TraceVal.vpp_out_focus(vpp=self.test.awg.amp)))

        # ------------------ OSC: Measuring range, etc. ------------------
        frame_osc = tk.Frame(frame_device_config)
        frame_osc.pack(anchor=tk.W, pady=10)

        frame_osc_range = tk.Frame(frame_osc)
        frame_osc_range.pack(anchor=tk.W, padx=5)
        frame_osc_range.grid_columnconfigure(1, weight=1)

        lb_osc_range = tk.Label(frame_osc_range, text=f"{Mapping.label_for_range}: ")
        lb_osc_range.grid(row=0, column=0, sticky=tk.E, padx=5, pady=2)

        etr_osc_range = tk.Entry(frame_osc_range, textvariable=self.test.osc_test.range, width=10)
        etr_osc_range.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        # Normalization: positive number + amplitude unit
        etr_osc_range.bind("<FocusOut>", lambda e: (TraceVal.force_positive_out_focus(var=self.test.osc_test.range),
                                                    TraceVal.volts_out_focus(curr=self.test.osc_test.range)))
        etr_osc_range.bind("<Return>",   lambda e: (TraceVal.force_positive_out_focus(var=self.test.osc_test.range),
                                                    TraceVal.volts_out_focus(curr=self.test.osc_test.range)))

        btn_osc_range_auto_switch = tk.Checkbutton(
            frame_osc_range,
            text=Mapping.label_for_auto_range,
            variable=self.test.is_auto_osc_range
        )
        btn_osc_range_auto_switch.grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)

        # ========================= Right: Figures and Patterns =========================
        frame_right = tk.Frame(frame_load_off_test)
        frame_right.pack(side=tk.LEFT, anchor=tk.N, fill=tk.BOTH, expand=True)

        frame_test_config = tk.Frame(frame_right)
        frame_test_config.pack(anchor=tk.W, padx=10, fill=tk.BOTH, expand=True)

        frame_test_config_control = tk.Frame(frame_test_config)
        # The right area uses grid: the upper part is the control bar (not enlarged with the form), and the lower part is the image (can be enlarged)
        frame_test_config.grid_rowconfigure(0, weight=0)
        frame_test_config.grid_rowconfigure(1, weight=1)
        frame_test_config.grid_columnconfigure(0, weight=1)
        # The inner grid of the control bar: the controls at both ends are on the left and right, leaving a scalable blank column in the middle
        frame_test_config_control.grid(row=0, column=0, sticky="ew")
        frame_test_config_control.grid_columnconfigure(0, weight=0)
        frame_test_config_control.grid_columnconfigure(1, weight=0)
        frame_test_config_control.grid_columnconfigure(2, weight=1)
        frame_test_config_control.grid_columnconfigure(3, weight=0)
        frame_test_config_control.grid_columnconfigure(4, weight=0)

        # Figure area
        frame_figure = tk.Frame(frame_test_config)
        frame_figure.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.test.setup_plots(frame_figure)

        # save data button
        self.btn_save_data = tk.Button(frame_test_config_control, text=Mapping.label_for_save_file, command=self.save_file)
        self.btn_save_data.grid(row=0, column=0, padx=5, sticky="w")

        # Calibration mode area
        frame_correct_modes = tk.Frame(frame_test_config_control)
        frame_correct_modes.grid(row=0, column=1, sticky="w")

        # These attributes are used for subsequent enable/disable; declare them in advance for type hinting
        self.btn_load_ref: tk.Button
        self.btn_enable_corr: tk.Button
        self.set_as_ref: tk.Button

        # Generate controls in the current mode and rebuild them when the mode changes
        show_correct_modes_control()
        self.test.var_correct_mode.trace_add("write", show_correct_modes_control)

        # Display image selection (Gain vs Freq / dB vs Freq)
        self.cmb_figure_switch = ttk.Combobox(
            frame_test_config_control,
            textvariable=self.test.figure_mode,
            values=Mapping.values_test_load_off_figure,
            width=20
        )
        self.cmb_figure_switch.grid(row=0, column=4, padx=5, sticky="e")

        # "Amplitude/Phase" selection (dual channel/trigger mode display only)
        frame_mag_or_phase = tk.Frame(frame_test_config_control)
        frame_mag_or_phase.grid(row=0, column=3, padx=5, sticky="e")

        self.cmb_mag_or_phase: ttk.Combobox
        show_mag_or_phase()
        self.test.var_correct_mode.trace_add("write", show_mag_or_phase)
        self.test.trig_mode.trace_add("write", show_mag_or_phase)

        # ========================= Bottom test control =========================
        frame_test_control_button = tk.Frame(frame_test_control)
        frame_test_control_button.pack()

        self.btn_start_test = tk.Button(frame_test_control_button, text="start", command=start_test, state=tk.NORMAL, width=15, height=2)
        self.btn_start_test.pack(side=tk.LEFT, padx=5)

        self.btn_stop_test = tk.Button(frame_test_control_button, text="stop", command=stop_test, state=tk.DISABLED, width=15, height=2)
        self.btn_stop_test.pack(side=tk.LEFT, padx=5)

        # Connection status prompt (little red/green light)
        frame_connection_status = tk.Frame(frame_test_control_button)
        frame_connection_status.pack(side=tk.LEFT, padx=5)

        lb_awg_connection_status = tk.Label(frame_connection_status, text=f"{Mapping.label_for_device_type_awg}")
        lb_awg_connection_status.grid(row=0, column=0, sticky=tk.W)

        c_awg_connection_status = tk.Canvas(frame_connection_status, width=10, height=10)
        c_awg_connection_status.grid(row=0, column=1, sticky=tk.W)
        awg_light = c_awg_connection_status.create_oval(2, 2, 9, 9, fill="red")

        lb_osc_connection_status = tk.Label(frame_connection_status, text=f"{Mapping.label_for_device_type_osc}")
        lb_osc_connection_status.grid(row=1, column=0, sticky=tk.W)

        c_osc_connection_status = tk.Canvas(frame_connection_status, width=10, height=10)
        c_osc_connection_status.grid(row=1, column=1, sticky=tk.W)
        osc_light = c_osc_connection_status.create_oval(2, 2, 9, 9, fill="red")

        # Start life exploration instructions
        connection_check()

        # Status bar (frequency point, running status, etc.)
        self.lb_status = tk.Label(frame_test_control_button)
        self.lb_status.pack(side=tk.LEFT, padx=10)


    def generate_device_control(self):
        """Equipment control area:
- OSC channel selection (dynamically displays Test/Ref/Trig according to calibration/trigger mode)
- VISA resource refresh (background thread detection -> main thread update drop-down)
- Device name change callback: restrict channel and impedance options according to model"""

        # ========================= Dynamic: OSC channel selection =========================
        def show_test_osc_sel(*args):
            """Rebuild OSC channel selection control based on current calibration/trigger mode"""
            # Empty the container to avoid overlapping
            for child in frame_test_device_osc.winfo_children():
                child.destroy()

            # —— Title (OSC name) —— #
            lb_test_device_osc = tk.Label(
                frame_test_device_osc,
                text=f"{Mapping.label_for_device_type_osc}: " 
            )
            lb_test_device_osc.pack(side=tk.LEFT, padx=5)

            # —— Tested channel (Test) —— #
            # Note: The drop-down value range is dynamically generated based on the maximum channel of the current OSC
            values_osc_chan = list(range(1, self.osc_device.max_chan_num.get() + 1))
            cmb_test_osc_chan_test_index = ttk.Combobox(
                frame_test_device_osc,
                textvariable=self.test.osc_test.chan_index,
                values=values_osc_chan,
                width=5
            )
            cmb_test_osc_chan_test_index.pack(side=tk.LEFT, padx=5)
            tk.Label(frame_test_device_osc, text=Mapping.label_for_test_chan).pack(side=tk.LEFT)

            # ——Reference channel (Ref): only displayed when "dual channel calibration" —— #
            if self.test.var_correct_mode.get() == Mapping.label_for_duo_chan_correct:
                ttk.Combobox(
                    frame_test_device_osc,
                    textvariable=self.test.osc_ref.chan_index,
                    values=values_osc_chan,
                    width=5
                ).pack(side=tk.LEFT, padx=(5, 0))
                tk.Label(frame_test_device_osc, text=Mapping.label_for_ref_chan).pack(side=tk.LEFT)

            # —— Trigger channel (Trig): only displayed when "Triggered" —— #
            if self.test.trig_mode.get() == Mapping.label_for_triggered:
                ttk.Combobox(
                    frame_test_device_osc,
                    textvariable=self.test.osc_trig.chan_index,
                    values=values_osc_chan,
                    width=5
                ).pack(side=tk.LEFT, padx=(5, 0))
                tk.Label(frame_test_device_osc, text=Mapping.label_for_trig_chan).pack(side=tk.LEFT)

        # ========================= Backstage: VISA resource refresh =========================
        def refresh_insts(*args):
            """Periodically refresh the VISA resource list:
- Background thread list_resources() -> enqueue
- The main thread takes out the queue and updates the drop-down box values
- Automatically select the first resource for AWG/OSC when there is no value for the first time (optional)
- Anti-reentrancy to avoid repeatedly starting threads"""
            if not hasattr(self, "_insts_refresh_started"):
                self._insts_refresh_started = False
            if self._insts_refresh_started:
                return
            self._insts_refresh_started = True

            inst_queue = queue.Queue()

            def refresh_worker():
                """Background thread: cycle list_resources(), enqueue the results; do not touch Tk directly"""
                rm = None
                while True:
                    try:
                        if rm is None:
                            rm = visa.ResourceManager()
                        values = rm.list_resources()
                        inst_queue.put(values)
                    except Exception:
                        # Rebuild the resource manager when it is abnormal; give the UI an empty list to prevent it from getting stuck.
                        rm = None
                        inst_queue.put(tuple())
                    finally:
                        time.sleep(0.5)  # Throttle and avoid too frequent

            def update_insts():
                """Main thread: drain the queue -> update the values of the two Comboboxes;
If the variable is currently empty, automatically select the first one (optional logic)"""
                try:
                    while True:
                        values_auto_visa_address = inst_queue.get_nowait()
                        try:
                            cmb_awg_auto_visa_address['values'] = values_auto_visa_address
                            cmb_osc_auto_visa_address['values'] = values_auto_visa_address
                        except Exception:
                            # If the drop-down box has not been created yet, try again later
                            pass

                except queue.Empty:
                    pass
                finally:
                    # Continue polling after 100 ms (non-blocking)
                    self.after(100, update_insts)

            threading.Thread(target=refresh_worker, daemon=True).start()
            update_insts()

        # ========================= Callback: AWG name change =========================
        def trace_awg_name(*args):
            """When the AWG model name changes:
- Update "Tag: type + name"
- DSG836: Force selection of RFO (index=1), and force 50Ω, disable "high impedance" radio selection
- Other models: Restore selectable channel range and high impedance available"""
            try:
                lb_frame_awg_channel_tag.config(
                    text=f"{self.awg_device.var_device_type.get()} : {self.awg_device.var_device_name.get()}"
                )
            except Exception:
                pass

            if self.awg_device.var_device_name.get() == Mapping.mapping_DSG_836:
                # Fixed single channel
                self.test.awg.chan_index.set("1")
                try:
                    cmb_awg_channel_index.config(values=["1"])
                    cmb_test_awg_chan_index.config(values=["1"])
                except Exception:
                    pass

                # Impedance: Fixed 50Ω, "High Impedance" disabled
                try:
                    self.test.awg.imp.set(Mapping.mapping_imp_r50)
                    rb_btn_set_awg_imp_inf.config(state=tk.DISABLED)
                except Exception:
                    pass
            else:
                # Restore multi-channel
                try:
                    self.test.awg.chan_index.set(1)
                    values_awg_chan = list(range(1, self.awg_device.max_chan_num.get() + 1))
                    cmb_awg_channel_index.config(values=values_awg_chan)
                    cmb_test_awg_chan_index.config(values=values_awg_chan)
                    rb_btn_set_awg_imp_inf.config(state=tk.NORMAL)
                except Exception:
                    pass

        # ========================= Callback: OSC name change =========================
        def trace_osc_name(*args):
            """Update "Tag: Type + Name" when OSC model name changes"""
            try:
                lb_frame_osc_channel_tag.config(
                    text=f"{self.osc_device.var_device_type.get()}: {self.osc_device.var_device_name.get()}"
                )
            except Exception:
                pass

            # Optional channel range limited by model
            if self.osc_device.var_device_name.get() == Mapping.mapping_DHO_1202:
                chan_values = list(range(1, instOSC_DHO1202.chan_num + 1))
                if self.test.osc_test.chan_index.get() not in chan_values:
                    self.test.osc_test.chan_index.set(1)

                # Impedance: Fixed ‘High Impedance’, disabled 50Ω
                try:
                    self.test.osc_test.imp.set(Mapping.mapping_imp_high_z)
                    rb_btn_set_osc_imp_r50.config(state=tk.DISABLED)
                except Exception:
                    pass
            elif self.osc_device.var_device_name.get() == Mapping.mapping_DHO_1204:
                # Limit the channel range to 1..4; if it exceeds the limit, it will fall back to 1
                chan_values = list(range(1, instOSC_DHO1204.chan_num + 1))
                if self.test.osc_test.chan_index.get() not in chan_values:
                    self.test.osc_test.chan_index.set(1)

                # Impedance: Fixed ‘High Impedance’, disabled 50Ω
                try:
                    self.test.osc_test.imp.set(Mapping.mapping_imp_high_z)
                    rb_btn_set_osc_imp_r50.config(state=tk.DISABLED)
                except Exception:
                    pass
            else:
                # Restoration impedance options
                try:
                    rb_btn_set_osc_imp_r50.config(state=tk.NORMAL)
                except Exception:
                    pass


        # Define the function first, then bind/call it!
        def trace_log_freq(*_):
            """Rebuild the 'Step Settings' area based on the log/linear switch."""
            nonlocal trace_step_widgets
            for widget in trace_step_widgets:
                widget.destroy()
            trace_step_widgets = []

            if self.test.awg.is_log_freq_enabled.get():
                # —— Logarithm: number of steps —— #
                lb_text = f"{Mapping.label_for_set_step_num}: "
                entry_var = self.test.awg.step_num

                # Normalization: positive integer + unit
                def _norm_step_num(_e=None):
                    TraceVal.general_out_focus(var=self.test.awg.step_num)
                    TraceVal.force_int_out_focus(var=self.test.awg.step_num)
                    TraceVal.force_positive_out_focus(var=self.test.awg.step_num)

                norm_callback = _norm_step_num

            else:
                # —— Linear: step size —— #
                lb_text = f"{Mapping.label_for_set_step_freq}: "
                entry_var = self.test.awg.step_freq

                def _norm_step_freq(_e=None):
                    TraceVal.force_positive_out_focus(var=self.test.awg.step_freq)
                    TraceVal.freq_out_focus(freq=self.test.awg.step_freq)

                norm_callback = _norm_step_freq

            lb_step = tk.Label(frame_awg_param_grid, text=lb_text)
            lb_step.grid(row=awg_step_row, column=0, sticky=tk.W, padx=5, pady=2)

            etr = tk.Entry(frame_awg_param_grid, textvariable=entry_var, width=10)
            etr.grid(row=awg_step_row, column=1, sticky=tk.W, padx=5, pady=2)

            etr.bind("<FocusOut>", norm_callback)
            etr.bind("<Return>",   norm_callback)

            trace_step_widgets = [lb_step, etr]

        def trace_osc_chan_num(*args):
            cmb_osc_channel_index.config(values=list(range(1, self.osc_device.max_chan_num.get() + 1)))

        def trace_awg_chan_num(*args):
            cmb_awg_channel_index.config(values=list(range(1, self.awg_device.max_chan_num.get() + 1)))

        # ======================= Device management (pop-up window) and device parameter area =======================
        self.device_control_window = tk.Toplevel()
        # The window is not destroyed when the close button is clicked, only hidden so that it can be opened again
        self.device_control_window.protocol("WM_DELETE_WINDOW", self.device_control_window.withdraw)

        # Overall container on the left
        frame_config = tk.Frame(self.device_control_window)
        frame_config.pack(side=tk.LEFT, anchor=tk.N)

        # Device selection area (channel/model)
        frame_test_device_sel = tk.Frame(frame_config)
        frame_test_device_sel.pack(anchor=tk.W)

        # VISA Address Setting Group (AWG/OSC)
        frame_visa_address_groups = tk.Frame(frame_config)
        frame_visa_address_groups.pack(anchor=tk.W)

        # Equipment detailed control area (AWG parameter settings, etc.)
        frame_control = tk.Frame(frame_config)
        frame_control.pack(anchor=tk.W)

        # Latch event of active thread: allow background exploration when set(); pause when clear() (during testing)
        self.pause_refresh_insts = threading.Event()
        self.pause_refresh_insts.set()

        # ----------------------- Device selection: AWG/OSC channel -----------------------
        frame_device_selection = tk.Frame(frame_test_device_sel)
        frame_device_selection.pack(anchor=tk.W, pady=10)

        # AWG channel selection
        frame_test_device_awg = tk.Frame(frame_device_selection)
        frame_test_device_awg.pack(anchor=tk.W)

        lb_test_device_awg = tk.Label(frame_test_device_awg, text=f"{Mapping.label_for_device_type_awg}: ")
        lb_test_device_awg.pack(side=tk.LEFT, padx=5)

        cmb_test_awg_chan_index = ttk.Combobox(
            frame_test_device_awg,
            textvariable=self.test.awg.chan_index,
            values=list(range(1, self.awg_device.max_chan_num.get() + 1)),
            width=5
        )
        cmb_test_awg_chan_index.pack(side=tk.LEFT, padx=5)

        lb_test_awg_chan_index = tk.Label(frame_test_device_awg, text=Mapping.label_for_chan_index)
        lb_test_awg_chan_index.pack(side=tk.LEFT)

        # OSC channel selection (dynamically refreshed based on calibration/trigger mode)
        frame_test_device_osc = tk.Frame(frame_device_selection)
        frame_test_device_osc.pack(anchor=tk.W)

        show_test_osc_sel()  # Initialize once
        # Rebuild selection control when mode/number of channels changes
        self.test.var_correct_mode.trace_add("write", show_test_osc_sel)
        self.test.trig_mode.trace_add("write", show_test_osc_sel)
        self.awg_device.max_chan_num.trace_add("write", show_test_osc_sel)
        self.osc_device.max_chan_num.trace_add("write", show_test_osc_sel)

        # ----------------------- AWG VISA Settings -----------------------
        frame_awg_visa_address = tk.Frame(frame_visa_address_groups)
        frame_awg_visa_address.pack(anchor=tk.W)

        frame_awg_name = tk.Frame(frame_awg_visa_address)
        frame_awg_name.pack(anchor=tk.W)

        lb_awg_visa_address = tk.Label(frame_awg_name, text=f"#{self.awg_device.device_index}: {Mapping.label_for_device_type_awg}")
        lb_awg_visa_address.pack(side=tk.LEFT, padx=5)

        cmb_awg_device_name = ttk.Combobox(
            frame_awg_name,
            textvariable=self.awg_device.var_device_name,
            values=Mapping.values_awg,
            width=10
        )
        cmb_awg_device_name.pack(side=tk.LEFT, padx=5)

        # Auto/LAN switch + address
        frame_awg_auto_lan = tk.Frame(frame_awg_visa_address)
        frame_awg_auto_lan.pack(anchor=tk.W, pady=5)

        rb_btn_awg_auto = tk.Radiobutton(
            frame_awg_auto_lan, text=Mapping.mapping_auto_detect,
            variable=self.awg_device.var_switch_auto_lan, value=Mapping.label_for_auto
        )
        rb_btn_awg_auto.grid(row=0, column=0, sticky=tk.W)

        lb_awg_auto_visa_address = tk.Label(frame_awg_auto_lan, text=Mapping.label_for_visa_address)
        lb_awg_auto_visa_address.grid(row=0, column=1, sticky=tk.W)

        cmb_awg_auto_visa_address = ttk.Combobox(
            frame_awg_auto_lan, textvariable=self.awg_device.var_auto_visa_address, width=42
        )
        cmb_awg_auto_visa_address.grid(row=0, column=2, sticky=tk.W, padx=10)

        rb_awg_btn_lan = tk.Radiobutton(
            frame_awg_auto_lan, text=Mapping.label_for_lan,
            variable=self.awg_device.var_switch_auto_lan, value=Mapping.label_for_lan
        )
        rb_awg_btn_lan.grid(row=1, column=0, sticky=tk.W)

        lb_awg_lan_visa_address = tk.Label(frame_awg_auto_lan, text=Mapping.label_for_ip_address)
        lb_awg_lan_visa_address.grid(row=1, column=1, sticky=tk.W)

        # LAN IPv4 four-segment input
        frame_awg_lan = tk.Frame(frame_awg_auto_lan)
        frame_awg_lan.grid(row=1, column=2, sticky=tk.W, padx=10)

        etr_awg_lan_visa_address_1 = tk.Entry(frame_awg_lan, textvariable=self.awg_device.var_lan_ip_list[0], width=10)
        etr_awg_lan_visa_address_1.grid(row=0, column=0, sticky=tk.W)
        tk.Label(frame_awg_lan, text=".").grid(row=0, column=1, padx=2)
        etr_awg_lan_visa_address_2 = tk.Entry(frame_awg_lan, textvariable=self.awg_device.var_lan_ip_list[1], width=10)
        etr_awg_lan_visa_address_2.grid(row=0, column=2, sticky=tk.W)
        tk.Label(frame_awg_lan, text=".").grid(row=0, column=3, padx=2)
        etr_awg_lan_visa_address_3 = tk.Entry(frame_awg_lan, textvariable=self.awg_device.var_lan_ip_list[2], width=10)
        etr_awg_lan_visa_address_3.grid(row=0, column=4, sticky=tk.W)
        tk.Label(frame_awg_lan, text=".").grid(row=0, column=5, padx=2)
        etr_awg_lan_visa_address_4 = tk.Entry(frame_awg_lan, textvariable=self.awg_device.var_lan_ip_list[3], width=10)
        etr_awg_lan_visa_address_4.grid(row=0, column=6, sticky=tk.W)

        # Normalization: Force integer + range 0~255 for each segment
        etr_awg_lan_visa_address_1.bind("<FocusOut>", lambda e: (TraceVal.force_int_out_focus(var=self.awg_device.var_lan_ip_list[0]), 
                                                                 TraceVal.ip_out_focus(var=self.awg_device.var_lan_ip_list[0])))
        etr_awg_lan_visa_address_1.bind("<Return>", lambda e: (TraceVal.force_int_out_focus(var=self.awg_device.var_lan_ip_list[0]), 
                                                               TraceVal.ip_out_focus(var=self.awg_device.var_lan_ip_list[0])))
        etr_awg_lan_visa_address_2.bind("<FocusOut>", lambda e: (TraceVal.force_int_out_focus(var=self.awg_device.var_lan_ip_list[1]), 
                                                                 TraceVal.ip_out_focus(var=self.awg_device.var_lan_ip_list[1])))
        etr_awg_lan_visa_address_2.bind("<Return>", lambda e: (TraceVal.force_int_out_focus(var=self.awg_device.var_lan_ip_list[1]),
                                                               TraceVal.ip_out_focus(var=self.awg_device.var_lan_ip_list[1])))
        etr_awg_lan_visa_address_3.bind("<FocusOut>", lambda e: (TraceVal.force_int_out_focus(var=self.awg_device.var_lan_ip_list[2]),
                                                                 TraceVal.ip_out_focus(var=self.awg_device.var_lan_ip_list[2])))
        etr_awg_lan_visa_address_3.bind("<Return>", lambda e: (TraceVal.force_int_out_focus(var=self.awg_device.var_lan_ip_list[2]),
                                                               TraceVal.ip_out_focus(var=self.awg_device.var_lan_ip_list[2])))
        etr_awg_lan_visa_address_4.bind("<FocusOut>", lambda e: (TraceVal.force_int_out_focus(var=self.awg_device.var_lan_ip_list[3]),
                                                                 TraceVal.ip_out_focus(var=self.awg_device.var_lan_ip_list[3])))
        etr_awg_lan_visa_address_4.bind("<Return>", lambda e: (TraceVal.force_int_out_focus(var=self.awg_device.var_lan_ip_list[3]),
                                                               TraceVal.ip_out_focus(var=self.awg_device.var_lan_ip_list[3])))

        # ----------------------- OSC VISA Settings -----------------------
        frame_osc_visa_address = tk.Frame(frame_visa_address_groups)
        frame_osc_visa_address.pack(anchor=tk.W)

        # Create device name row
        frame_osc_name = tk.Frame(frame_osc_visa_address)
        frame_osc_name.pack(anchor=tk.W)

        lb_osc_visa_address = tk.Label(frame_osc_name, text=f"#{self.osc_device.device_index}: {Mapping.label_for_device_type_osc}")
        lb_osc_visa_address.pack(side=tk.LEFT, padx=5)

        cmb_osc_device_name = ttk.Combobox(
            frame_osc_name,
            textvariable=self.osc_device.var_device_name,
            values=Mapping.values_osc,
            width=10
        )
        cmb_osc_device_name.pack(side=tk.LEFT, padx=5)

        frame_osc_auto_lan = tk.Frame(frame_osc_visa_address)
        frame_osc_auto_lan.pack(anchor=tk.W, pady=5)

        # Auto detect mode radio button
        rb_osc_btn_auto = tk.Radiobutton(
            frame_osc_auto_lan, text=Mapping.mapping_auto_detect,
            variable=self.osc_device.var_switch_auto_lan, value=Mapping.label_for_auto
        )
        rb_osc_btn_auto.grid(row=0, column=0, sticky=tk.W)

        # Automatically detect address drop-down box
        lb_osc_auto_visa_address = tk.Label(frame_osc_auto_lan, text=Mapping.label_for_visa_address)
        lb_osc_auto_visa_address.grid(row=0, column=1, sticky=tk.W)

        cmb_osc_auto_visa_address = ttk.Combobox(
            frame_osc_auto_lan, textvariable=self.osc_device.var_auto_visa_address, width=42
        )
        cmb_osc_auto_visa_address.grid(row=0, column=2, sticky=tk.W, padx=10)

        # Auto/LAN switch + address
        rb_osc_btn_lan = tk.Radiobutton(
            frame_osc_auto_lan, text=Mapping.label_for_lan,
            variable=self.osc_device.var_switch_auto_lan, value=Mapping.label_for_lan
        )
        rb_osc_btn_lan.grid(row=1, column=0, sticky=tk.W)

        lb_osc_lan_visa_address = tk.Label(frame_osc_auto_lan, text=Mapping.label_for_ip_address)
        lb_osc_lan_visa_address.grid(row=1, column=1, sticky=tk.W)

        # LAN IPv4 four-segment input
        frame_osc_lan = tk.Frame(frame_osc_auto_lan)
        frame_osc_lan.grid(row=1, column=2, sticky=tk.W, padx=10)

        etr_osc_lan_visa_address_1 = tk.Entry(frame_osc_lan, textvariable=self.osc_device.var_lan_ip_list[0], width=10)
        etr_osc_lan_visa_address_1.grid(row=0, column=0, sticky=tk.W)
        tk.Label(frame_osc_lan, text=".").grid(row=0, column=1, padx=2)
        etr_osc_lan_visa_address_2 = tk.Entry(frame_osc_lan, textvariable=self.osc_device.var_lan_ip_list[1], width=10)
        etr_osc_lan_visa_address_2.grid(row=0, column=2, sticky=tk.W)
        tk.Label(frame_osc_lan, text=".").grid(row=0, column=3, padx=2)
        etr_osc_lan_visa_address_3 = tk.Entry(frame_osc_lan, textvariable=self.osc_device.var_lan_ip_list[2], width=10)
        etr_osc_lan_visa_address_3.grid(row=0, column=4, sticky=tk.W)
        tk.Label(frame_osc_lan, text=".").grid(row=0, column=5, padx=2)
        etr_osc_lan_visa_address_4 = tk.Entry(frame_osc_lan, textvariable=self.osc_device.var_lan_ip_list[3], width=10)
        etr_osc_lan_visa_address_4.grid(row=0, column=6, sticky=tk.W)

        # Normalization: Force integer + range 0~255 for each segment
        etr_osc_lan_visa_address_1.bind("<FocusOut>", lambda e: (TraceVal.force_int_out_focus(var=self.osc_device.var_lan_ip_list[0]), 
                                                                 TraceVal.ip_out_focus(var=self.osc_device.var_lan_ip_list[0])))
        etr_osc_lan_visa_address_1.bind("<Return>", lambda e: (TraceVal.force_int_out_focus(var=self.osc_device.var_lan_ip_list[0]), 
                                                               TraceVal.ip_out_focus(var=self.osc_device.var_lan_ip_list[0])))
        etr_osc_lan_visa_address_2.bind("<FocusOut>", lambda e: (TraceVal.force_int_out_focus(var=self.osc_device.var_lan_ip_list[1]), 
                                                                 TraceVal.ip_out_focus(var=self.osc_device.var_lan_ip_list[1])))
        etr_osc_lan_visa_address_2.bind("<Return>", lambda e: (TraceVal.force_int_out_focus(var=self.osc_device.var_lan_ip_list[1]),
                                                               TraceVal.ip_out_focus(var=self.osc_device.var_lan_ip_list[1])))
        etr_osc_lan_visa_address_3.bind("<FocusOut>", lambda e: (TraceVal.force_int_out_focus(var=self.osc_device.var_lan_ip_list[2]), 
                                                                 TraceVal.ip_out_focus(var=self.osc_device.var_lan_ip_list[2])))
        etr_osc_lan_visa_address_3.bind("<Return>", lambda e: (TraceVal.force_int_out_focus(var=self.osc_device.var_lan_ip_list[2]),
                                                               TraceVal.ip_out_focus(var=self.osc_device.var_lan_ip_list[2])))
        etr_osc_lan_visa_address_4.bind("<FocusOut>", lambda e: (TraceVal.force_int_out_focus(var=self.osc_device.var_lan_ip_list[3]), 
                                                                 TraceVal.ip_out_focus(var=self.osc_device.var_lan_ip_list[3])))
        etr_osc_lan_visa_address_4.bind("<Return>", lambda e: (TraceVal.force_int_out_focus(var=self.osc_device.var_lan_ip_list[3]),
                                                               TraceVal.ip_out_focus(var=self.osc_device.var_lan_ip_list[3])))


        # Refresh VISA resource drop-down in the background
        refresh_insts()

        # ----------------------- AWG detailed settings (channel/frequency/amplitude/impedance) -----------------------
        frame_awg_setting = tk.Frame(frame_control)
        frame_awg_setting.pack(side=tk.LEFT, anchor=tk.N, padx=10)

        # Title: Device type + name (updated simultaneously when the model changes)
        lb_frame_awg_channel_tag = tk.Label(
            frame_awg_setting,
            text=f"{self.awg_device.var_device_type.get()} : {self.awg_device.var_device_name.get()}"
        )
        lb_frame_awg_channel_tag.pack(anchor=tk.W)
        self.awg_device.var_device_name.trace_add("write", trace_awg_name)

        frame_awg_param_grid = tk.Frame(frame_awg_setting)
        frame_awg_param_grid.pack(anchor=tk.W, fill=tk.X)
        frame_awg_param_grid.grid_columnconfigure(1, weight=1)

        awg_param_row = 0

        # Channel selection
        lb_awg_channel_index = tk.Label(frame_awg_param_grid, text=Mapping.label_for_chan_index)
        lb_awg_channel_index.grid(row=awg_param_row, column=0, sticky=tk.W, padx=5, pady=2)

        cmb_awg_channel_index = ttk.Combobox(
            frame_awg_param_grid,
            textvariable=self.test.awg.chan_index,
            values=list(range(1, self.awg_device.max_chan_num.get() + 1)),
            width=5
        )
        cmb_awg_channel_index.grid(row=awg_param_row, column=1, sticky=tk.W, padx=5, pady=2)
        self.awg_device.max_chan_num.trace_add("write", trace_awg_chan_num)
        awg_param_row += 1

        # starting frequency
        lb_set_start_freq = tk.Label(frame_awg_param_grid, text=f"{Mapping.label_for_set_start_frequency}: ")
        lb_set_start_freq.grid(row=awg_param_row, column=0, sticky=tk.W, padx=5, pady=2)

        etr_set_start_freq = tk.Entry(frame_awg_param_grid, textvariable=self.test.awg.start_freq, width=10)
        etr_set_start_freq.grid(row=awg_param_row, column=1, sticky=tk.W, padx=5, pady=2)
        etr_set_start_freq.bind("<FocusOut>", lambda e: TraceVal.freq_out_focus(freq=self.test.awg.start_freq))
        etr_set_start_freq.bind("<Return>",   lambda e: TraceVal.freq_out_focus(freq=self.test.awg.start_freq))
        awg_param_row += 1

        # Termination frequency
        lb_set_stop_freq = tk.Label(frame_awg_param_grid, text=f"{Mapping.label_for_set_stop_frequency}: ")
        lb_set_stop_freq.grid(row=awg_param_row, column=0, sticky=tk.W, padx=5, pady=2)

        etr_set_stop_freq = tk.Entry(frame_awg_param_grid, textvariable=self.test.awg.stop_freq, width=10)
        etr_set_stop_freq.grid(row=awg_param_row, column=1, sticky=tk.W, padx=5, pady=2)
        etr_set_stop_freq.bind("<FocusOut>", lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.stop_freq),
                                                        TraceVal.freq_out_focus(freq=self.test.awg.stop_freq)))
        etr_set_stop_freq.bind("<Return>",   lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.stop_freq),
                                                        TraceVal.freq_out_focus(freq=self.test.awg.stop_freq)))
        awg_param_row += 1

        # step size
        awg_step_row = awg_param_row
        awg_param_row += 1
        trace_step_widgets = []
        self.test.awg.is_log_freq_enabled.trace_add("write", trace_log_freq)
        # first render
        trace_log_freq()

        # Amplitude
        lb_set_amp = tk.Label(frame_awg_param_grid, text=f"{Mapping.label_for_set_amp}: ")
        lb_set_amp.grid(row=awg_param_row, column=0, sticky=tk.W, padx=5, pady=2)

        etr_set_amp = tk.Entry(frame_awg_param_grid, textvariable=self.test.awg.amp, width=10)
        etr_set_amp.grid(row=awg_param_row, column=1, sticky=tk.W, padx=5, pady=2)
        etr_set_amp.bind("<FocusOut>", lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.amp),
                                                TraceVal.vpp_out_focus(vpp=self.test.awg.amp)))
        etr_set_amp.bind("<Return>",   lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.amp),
                                                TraceVal.vpp_out_focus(vpp=self.test.awg.amp)))
        awg_param_row += 1

        # Output impedance (R50 / high impedance)
        lb_set_awg_imp = tk.Label(frame_awg_param_grid, text=f"{Mapping.label_for_set_imp}: ")
        lb_set_awg_imp.grid(row=awg_param_row, column=0, sticky=tk.W, padx=5, pady=2)

        frame_set_awg_imp = tk.Frame(frame_awg_param_grid)
        frame_set_awg_imp.grid(row=awg_param_row, column=1, sticky=tk.W, padx=5, pady=2)

        rb_btn_set_awg_imp_r50 = tk.Radiobutton(
            frame_set_awg_imp, text=Mapping.label_for_imp_r50, variable=self.test.awg.imp, value=Mapping.mapping_imp_r50
        )
        rb_btn_set_awg_imp_r50.pack(side=tk.LEFT, padx=(0, 5))

        rb_btn_set_awg_imp_inf = tk.Radiobutton(
            frame_set_awg_imp, text=Mapping.label_for_imp_inf, variable=self.test.awg.imp, value=Mapping.mapping_imp_high_z
        )
        rb_btn_set_awg_imp_inf.pack(side=tk.LEFT)


        # ======================= OSC (oscilloscope) setting area =======================
        frame_osc_setting = tk.Frame(frame_control)
        frame_osc_setting.pack(side=tk.LEFT, anchor=tk.N, padx=10)

        # Title: Device type + name (updated simultaneously when the model changes)
        lb_frame_osc_channel_tag = tk.Label(
            frame_osc_setting,
            text=f"{self.osc_device.var_device_type.get()}: {self.osc_device.var_device_name.get()}"
        )
        lb_frame_osc_channel_tag.pack(anchor=tk.W)
        self.osc_device.var_device_name.trace_add("write", trace_osc_name)

        frame_osc_param_grid = tk.Frame(frame_osc_setting)
        frame_osc_param_grid.pack(anchor=tk.W, fill=tk.X)
        frame_osc_param_grid.grid_columnconfigure(1, weight=1)

        osc_param_row = 0

        # —— Channel index —— #
        lb_osc_channel_index = tk.Label(frame_osc_param_grid, text=f"{Mapping.label_for_chan_index}: ")
        lb_osc_channel_index.grid(row=osc_param_row, column=0, sticky=tk.W, padx=5, pady=2)

        cmb_osc_channel_index = ttk.Combobox(
            frame_osc_param_grid,
            textvariable=self.test.osc_test.chan_index,
            values=list(range(1, self.osc_device.max_chan_num.get() + 1)),
            width=5
        )
        cmb_osc_channel_index.grid(row=osc_param_row, column=1, sticky=tk.W, padx=5, pady=2)
        self.osc_device.max_chan_num.trace_add("write", trace_osc_chan_num)
        osc_param_row += 1

        # ——Coupling method (AC/DC, etc.)—— #
        lb_osc_coup = tk.Label(frame_osc_param_grid, text=f"{Mapping.label_for_coup}: ")
        lb_osc_coup.grid(row=osc_param_row, column=0, sticky=tk.W, padx=5, pady=2)

        cmb_osc_coup = ttk.Combobox(
            frame_osc_param_grid,
            textvariable=self.test.osc_test.coupling,
            values=Mapping.values_coup,
            width=5
        )
        cmb_osc_coup.grid(row=osc_param_row, column=1, sticky=tk.W, padx=5, pady=2)
        osc_param_row += 1

        # —— Full scale —— #
        lb_osc_range = tk.Label(frame_osc_param_grid, text=f"{Mapping.label_for_range}: ")
        lb_osc_range.grid(row=osc_param_row, column=0, sticky=tk.W, padx=5, pady=2)

        etr_osc_range = tk.Entry(frame_osc_param_grid, textvariable=self.test.osc_test.range, width=10)
        etr_osc_range.grid(row=osc_param_row, column=1, sticky=tk.W, padx=5, pady=2)
        # Normalization: Range should be a positive number
        etr_osc_range.bind(
            "<FocusOut>",
            lambda e: (TraceVal.force_positive_out_focus(var=self.test.osc_test.range),
                    TraceVal.volts_out_focus(curr=self.test.osc_test.range)) 
        )
        etr_osc_range.bind(
            "<Return>",
            lambda e: (TraceVal.force_positive_out_focus(var=self.test.osc_test.range),
                    TraceVal.volts_out_focus(curr=self.test.osc_test.range))  
        )
        osc_param_row += 1

        # —— Center display voltage —— #
        lb_osc_yoffset = tk.Label(frame_osc_param_grid, text=f"{Mapping.label_for_yoffset}: ")
        lb_osc_yoffset.grid(row=osc_param_row, column=0, sticky=tk.W, padx=5, pady=2)

        etr_osc_yoffset = tk.Entry(frame_osc_param_grid, textvariable=self.test.osc_test.yoffset, width=10)
        etr_osc_yoffset.grid(row=osc_param_row, column=1, sticky=tk.W, padx=5, pady=2)
        # Normalization: Positive numbers are not enforced here (negative values ​​are allowed for bias)
        etr_osc_yoffset.bind("<FocusOut>", lambda e: TraceVal.volts_out_focus(curr=self.test.osc_test.yoffset)) 
        etr_osc_yoffset.bind("<Return>",   lambda e: TraceVal.volts_out_focus(curr=self.test.osc_test.yoffset))
        osc_param_row += 1

        # —— Number of sampling points —— #
        lb_osc_points = tk.Label(frame_osc_param_grid, text=f"{Mapping.label_for_points}: ")
        lb_osc_points.grid(row=osc_param_row, column=0, sticky=tk.W, padx=5, pady=2)

        etr_osc_points = tk.Entry(frame_osc_param_grid, textvariable=self.test.osc_test.points, width=10)
        etr_osc_points.grid(row=osc_param_row, column=1, sticky=tk.W, padx=5, pady=2)
        # Normalization: positive integers, common numeric format

        etr_osc_points.bind(
            "<FocusOut>",
            lambda e: (
                TraceVal.general_out_focus(var=self.test.osc_test.points),
                TraceVal.force_int_out_focus(var=self.test.osc_test.points),
                TraceVal.force_positive_out_focus(var=self.test.osc_test.points)
            )
        )
        etr_osc_points.bind(
            "<Return>",
            lambda e: (
                TraceVal.general_out_focus(var=self.test.osc_test.points),
                TraceVal.force_int_out_focus(var=self.test.osc_test.points),
                TraceVal.force_positive_out_focus(var=self.test.osc_test.points)
            )
        )
        osc_param_row += 1

        # ——Input impedance (R50 / high impedance)—— #
        lb_set_osc_imp = tk.Label(frame_osc_param_grid, text=f"{Mapping.label_for_set_imp}: ")
        lb_set_osc_imp.grid(row=osc_param_row, column=0, sticky=tk.W, padx=5, pady=2)

        frame_set_osc_imp = tk.Frame(frame_osc_param_grid)
        frame_set_osc_imp.grid(row=osc_param_row, column=1, sticky=tk.W, padx=5, pady=2)

        rb_btn_set_osc_imp_r50 = tk.Radiobutton(
            frame_set_osc_imp,
            text=Mapping.label_for_imp_r50,
            variable=self.test.osc_test.imp,
            value=Mapping.mapping_imp_r50
        )
        rb_btn_set_osc_imp_r50.pack(side=tk.LEFT, padx=(0, 5))

        rb_btn_set_osc_imp_inf = tk.Radiobutton(
            frame_set_osc_imp,
            text=Mapping.label_for_imp_inf,
            variable=self.test.osc_test.imp,
            value=Mapping.mapping_imp_high_z
        )
        rb_btn_set_osc_imp_inf.pack(side=tk.LEFT)
        osc_param_row += 1


    def auto_load_config(self):
        """Automatically load configuration (from default location) and sync to UI"""
        self.cfgMgr.auto_load()
        self.set_ui_from_config()


    def load_config(self):
        """Select and load a profile, then sync to the UI"""
        self.cfgMgr.load()
        self.set_ui_from_config()


    def generate_file_path_for_files(self, fp_data, time_stamp: str = ""):
        """Based on the incoming "basic file path" and optional timestamp, file names such as mat/txt/csv/png are derived and placed on disk.
Note:
- fp_data is only used as the source of "base name + directory"; extensions in different formats are uniformly generated by this function.
- Will save: mat, txt, csv, two pictures (gain/freq and dB/freq)
- Text/CSV column set changes with "Calibration switch/Calibration mode/Trigger mode"
"""

        # ============ 1) Prepare the data to be saved (convert to 1D vectors, length aligned) ============
        mat_freq       = np.round(self.test.results[Mapping.mapping_freq],            4)
        mat_gain_db    = np.round(self.test.results[Mapping.mapping_gain_db_raw],     4)
        mat_gain_db_c  = np.round(self.test.results[Mapping.mapping_gain_db_corr],    4)
        mat_phase      = np.round(self.test.results[Mapping.mapping_phase_deg],       4)
        mat_phase_c    = np.round(self.test.results[Mapping.mapping_phase_deg_corr],  4)

        # Configuration snapshot
        mat_config = {
            "AWG_Start_freq": f"{CvtTools.parse_to_hz(self.test.awg.start_freq.get(), self.test.freq_unit.get())} Hz",
            "AWG_Stop_freq": f"{CvtTools.parse_to_hz(self.test.awg.stop_freq.get(), self.test.freq_unit.get())} Hz",
            ("AWG_Step_Freq" if not self.test.awg.is_log_freq_enabled.get() else "AWG_Steps_Num"):
                (f"{CvtTools.parse_to_hz(self.test.awg.step_freq.get(), self.test.freq_unit.get())} Hz"
                if not self.test.awg.is_log_freq_enabled.get()
                else f"{CvtTools.parse_general_val(self.test.awg.step_num.get())} Steps"),
            "AWG_Amp": f"{CvtTools.parse_to_Vpp(self.test.awg.amp.get())} Vpp",
            "AWG_Impedance": f"{self.test.awg.imp.get()}",
            "OSC_Coupling": f"{self.test.osc_test.coupling.get()}", 
            "OSC_Range": f"{CvtTools.parse_to_V(self.test.osc_test.range.get())} V",
            "OSC_yOffset": f"{CvtTools.parse_to_V(self.test.osc_test.yoffset.get())} V",
            "OSC_Impedance": f"{self.test.osc_test.imp.get()}",
            "OSC_Sampling_Points": f"{CvtTools.parse_general_val(self.test.osc_test.points.get())}",
            "Test_Correct_Mode": f"{self.test.var_correct_mode.get()}",
            "Test_Trig_Mode": f"{self.test.trig_mode.get()}",
        }

        # ============ 2) Generate various target file paths (with optional timestamp prefix) ============

        dir_path = os.path.dirname(fp_data)
        os.makedirs(dir_path, exist_ok=True)

        base_name = os.path.basename(fp_data)
        base_file_name, _ext = os.path.splitext(base_name)

        ts = (time_stamp or "")

        new_file_name_mat           = f"{ts}{base_file_name}{Mapping.mapping_file_ext_mat}"
        new_file_name_csv           = f"{ts}{base_file_name}{Mapping.mapping_file_ext_csv}"
        new_file_name_txt           = f"{ts}{base_file_name}{Mapping.mapping_file_ext_txt}"
        new_file_name_gain_freq_png = f"{ts}{base_file_name}_{Mapping.label_for_figure_gain_freq}{Mapping.mapping_file_ext_png}"
        new_file_name_gaindb_png    = f"{ts}{base_file_name}_{Mapping.label_for_figure_gaindb_freq}{Mapping.mapping_file_ext_png}"

        file_path_mat          = os.path.join(dir_path, new_file_name_mat)
        file_path_csv          = os.path.join(dir_path, new_file_name_csv)
        file_path_txt          = os.path.join(dir_path, new_file_name_txt)
        file_path_gain_png     = os.path.join(dir_path, new_file_name_gain_freq_png)
        file_path_gaindb_png   = os.path.join(dir_path, new_file_name_gaindb_png)

        # ============ 3) Define the saving sub-function of each format ============
        def save_mat_file():
            """Save mat: freq must be saved; gain/phase is selected by mode and calibration switch; comes with config."""
            data_to_save = {Mapping.mapping_freq: mat_freq}
            # gain column
            if self.test.is_correct_enabled.get():
                data_to_save[Mapping.mapping_gain_db_corr] = mat_gain_db_c
            else:
                data_to_save[Mapping.mapping_gain_db_raw] = mat_gain_db
            # Phase column (saved only in dual channel or trigger mode)
            if (self.test.var_correct_mode.get() == Mapping.label_for_duo_chan_correct or
                self.test.trig_mode.get() == Mapping.label_for_triggered):
                if self.test.is_correct_enabled.get():
                    data_to_save[Mapping.mapping_phase_deg_corr] = mat_phase_c
                else:
                    data_to_save[Mapping.mapping_phase_deg] = mat_phase
            # Configuration
            data_to_save["config"] = mat_config

            bATEinst_base.save_matfile(self, fn=file_path_mat, mm=data_to_save)

        def save_txt_file():
            """Save txt (tab-delimited, with headers, no comment prefix); column set consistent with .mat."""
            header = [f"{Mapping.mapping_freq}"]
            cols = [mat_freq]

            # gain column
            if self.test.is_correct_enabled.get():
                header.append(f"{Mapping.mapping_gain_db_corr}")
                cols.append(mat_gain_db_c)
            else:
                header.append(f"{Mapping.mapping_gain_db_raw}")
                cols.append(mat_gain_db)

            # phase sequence
            if (self.test.var_correct_mode.get() == Mapping.label_for_duo_chan_correct or
                self.test.trig_mode.get() == Mapping.label_for_triggered):
                if self.test.is_correct_enabled.get():
                    header.append(f"{Mapping.mapping_phase_deg_corr}")
                    cols.append(mat_phase_c)
                else:
                    header.append(f"{Mapping.mapping_phase_deg}")
                    cols.append(mat_phase)

            np.savetxt(
                file_path_txt,
                np.column_stack(cols),
                header="\t".join(header),
                delimiter="\t",
                comments="" 
            )

        def save_csv_file():
            """Save csv (comma separated, first column units shown in Hz); column set consistent with mat."""
            header = [f"{Mapping.mapping_freq}({Mapping.mapping_hz})"]
            cols = [mat_freq]

            if self.test.is_correct_enabled.get():
                header.append(f"{Mapping.mapping_gain_db_corr}")
                cols.append(mat_gain_db_c)
            else:
                header.append(f"{Mapping.mapping_gain_db_raw}")
                cols.append(mat_gain_db)

            if (self.test.var_correct_mode.get() == Mapping.label_for_duo_chan_correct or
                self.test.trig_mode.get() == Mapping.label_for_triggered):
                if self.test.is_correct_enabled.get():
                    header.append(f"{Mapping.mapping_phase_deg_corr}")
                    cols.append(mat_phase_c)
                else:
                    header.append(f"{Mapping.mapping_phase_deg}")
                    cols.append(mat_phase)

            # Write data line by line
            with open(file_path_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                for row in zip(*cols):
                    writer.writerow(row)

        def save_plot():
            """Save two graphs: Gain vs Freq / dB vs Freq"""
            # This assumes that setup_plots has created fig_gain/fig_db
            try:
                self.test.fig_gain.savefig(file_path_gain_png, dpi=300)
            except Exception:
                pass
            try:
                self.test.fig_db.savefig(file_path_gaindb_png, dpi=300)
            except Exception:
                pass

        # ============ 4) Actual save ============
        save_mat_file()
        save_txt_file()
        save_csv_file()
        save_plot()


    def save_file(self, *args):
        """Manual save: Select "Basic file name" in the pop-up box, then derive each format file and save it."""
        try:
            fp_data = filedialog.asksaveasfilename(
                filetypes=[("All files", "*.*")],
                initialfile="Test_File",
                initialdir=bATEinst_base.fn_relative(),
                title="Save data file",
            )
            if not fp_data:
                # User cancels save
                return

            self.generate_file_path_for_files(fp_data=fp_data)
            self.lb_status.config(text=Mapping.label_for_file_is_saved)

        except Exception as e:
            messagebox.showwarning(Mapping.title_alert, f"{Mapping.error_file_not_save}: {e}")


    def auto_save_file(self, *args):
        """Auto-save: Use the default relative directory + data subdirectory + timestamp prefix to avoid overwriting."""
        try:
            fp_data = bATEinst_base.fn_relative(fn=Mapping.default_data_fn, sub_folder=Mapping.label_for_sub_folder_data)
            time_stamp = datetime.now().strftime("%Y%m%d_%H_%M_%S") + "_"
            self.generate_file_path_for_files(fp_data=fp_data, time_stamp=time_stamp)
        except Exception as e:
            messagebox.showwarning(Mapping.title_alert, f"{Mapping.error_fail_auto_save}: {e}")


    def load_ref_file(self, *args):
        """Read the reference (calibration) file (mat), build the reference interpolation function self.test.href_at, and refresh the plot.
Mat is required to contain at least:
- Frequency: self.test.mapping_freq
- Gain (dB): Choose one of raw or corr
- Phase (optional): Choose one of raw or corr (only used in dual channel/trigger mode)"""
        default_fp = bATEinst_base.fn_relative(sub_folder=Mapping.label_for_sub_folder_data)

        ref_file_path = filedialog.askopenfilename(
            title="Select reference document",
            initialdir=default_fp,
            filetypes=[("MAT files", "*.mat"), ("All files", "*.*")]
        )
        # User cancels
        if not ref_file_path:
            return

        try:
            mat_data = loadmat(ref_file_path)

            # Take raw first, if not, take corr.
            freq  = mat_data.get(Mapping.mapping_freq, None)
            gdb   = mat_data.get(Mapping.mapping_gain_db_raw, None)
            if not isinstance(gdb, np.ndarray):
                gdb = mat_data.get(Mapping.mapping_gain_db_corr, None)

            ph    = mat_data.get(Mapping.mapping_phase_deg, None)
            if not isinstance(ph, np.ndarray):
                ph = mat_data.get(Mapping.mapping_phase_deg_corr, None)

            if isinstance(freq, np.ndarray) and isinstance(gdb, np.ndarray):
                # Build reference interpolation (phase can be null)
                self.test.href_at = self.build_bspline_holdout_interp(
                    ref_freq=freq, gain_db=gdb, phase=ph
                )
                # Refresh on main thread
                self.test.refresh_plot()
            else:
                messagebox.showwarning(Mapping.title_alert, "Missing reference (frequency or gain column does not exist)")

        except Exception as e:
            messagebox.showwarning(Mapping.title_alert, f"Failed to load MAT file: {e}")


    def build_bspline_holdout_interp(self,
                                     ref_freq: np.ndarray,
                                     gain_db: np.ndarray,
                                     phase: np.ndarray | None):
        """Construct the "Frequency -> Complex/Amplitude" reference interpolation function:
- Deduplication and sorting of frequencies
- Spline order k = min(3, n-1) at n points
- If the phase is given, return the complex interpolation; otherwise only return the amplitude interpolation
- Phase unit degree"""
        # normalized shape
        freq  = np.asarray(ref_freq, dtype=np.float64).squeeze()
        gdb   = np.asarray(gain_db,  dtype=np.float64).squeeze()

        phase = (
            None if (not isinstance(phase, np.ndarray)) or (phase.size == 0) 
            else np.asarray(phase).squeeze()
        ) 
        # Note: The unit of phase is degree, which needs to be converted to radian before constructing the complex reference.
        if phase is None:
            href = 10 ** (gdb / 20)
        else:
            phi = np.deg2rad(phase)
            href = 10 ** (gdb / 20) * (np.cos(phi) + 1j * np.sin(phi))

        # Sort + remove duplicates
        order = np.argsort(freq)
        freq, href = freq[order], href[order]
        freq, unique_idx = np.unique(freq, return_index=True)
        href = href[unique_idx]

        n = freq.size
        if n == 0:
            raise ValueError("ref_freq is empty")

        if n == 1:
            # There is only one point: the identity function
            h0 = href[0]
            if np.iscomplexobj(href):
                def href_at(x):
                    x = np.asarray(x, dtype=np.float64)
                    y = np.empty_like(x, dtype=np.complex128)
                    y[...] = h0
                    return y
            else:
                mag0 = float(np.abs(h0))
                def href_at(x):
                    x = np.asarray(x, dtype=np.float64)
                    y = np.empty_like(x, dtype=np.float64)
                    y[...] = mag0
                    return y
            return href_at

        # spline order
        k = int(min(3, n - 1))

        if np.iscomplexobj(href):
            spl_r = make_interp_spline(freq, href.real, k=k)
            spl_i = make_interp_spline(freq, href.imag, k=k)

            def href_at(x):
                x = np.asarray(x, dtype=np.float64)
                y = np.empty_like(x, dtype=np.complex128)

                lo = x < freq[0]
                hi = x > freq[-1]
                mid = ~(lo | hi)

                if np.any(mid):
                    y[mid] = spl_r(x[mid]) + 1j * spl_i(x[mid])
                if np.any(lo):
                    y[lo] = href[0]
                if np.any(hi):
                    y[hi] = href[-1]
                return y
        else:
            mag = np.abs(href)
            spl_mag = make_interp_spline(freq, mag, k=k)

            def href_at(x):
                x = np.asarray(x, dtype=np.float64)
                y = np.empty(x.shape, dtype=np.float64)
                lo = x < freq[0]
                hi = x > freq[-1]
                mid = ~(lo | hi)
                if np.any(mid):
                    y[mid] = spl_mag(x[mid])
                if np.any(lo):
                    y[lo] = mag[0]
                if np.any(hi):
                    y[hi] = mag[-1]
                return y

        return href_at


    def load_data_to_shown(self):
        """Loads data from an external MAT file for displaying frequency, gain, and phase curves in the UI.
Supports standard key names or sequential reading."""

        def import_data(ref_freq: np.ndarray, gain_db: np.ndarray, phase: np.ndarray | None):
            """Internal function: write the read data into self.test.results,
And automatically calculate the linear gain value."""
            freq = np.asarray(ref_freq, dtype=np.float64).squeeze()   # frequency array
            gain_db = np.asarray(gain_db).squeeze()                   # Gain (dB) array
            gain = 10 ** (gain_db / 20)                               # dB to linear amplitude

            # Set to None if phase is invalid
            phase = None if (not isinstance(phase, np.ndarray)) or (phase.size == 0) else np.asarray(phase).squeeze()

            # Store data in the test.results dictionary
            self.test.results[Mapping.mapping_freq] = freq
            self.test.results[Mapping.mapping_gain_raw] = gain
            self.test.results[Mapping.mapping_gain_db_raw] = gain_db
            if phase is not None:
                self.test.results[Mapping.mapping_phase_deg] = phase
                phi = np.deg2rad(phase)
                self.test.results[Mapping.mapping_gain_complex] = gain * (np.cos(phi) + 1j * np.sin(phi))

        # Set default path
        default_fp = bATEinst_base.fn_relative(sub_folder=Mapping.label_for_sub_folder_data)

        # Pop up file selection dialog box
        data_file_path = filedialog.askopenfilename(
            title="Select display file",
            initialdir=default_fp,
            filetypes=[("MAT files", "*.mat"), ("All files", "*.*")]
        )

        try:
            # Read MAT file
            mat_data = loadmat(data_file_path)

            # Case 1: Standard key name, read directly
            if ((Mapping.mapping_gain_db_raw in mat_data or Mapping.mapping_gain_db_corr in mat_data) and
                Mapping.mapping_freq in mat_data):

                import_data(
                    ref_freq=mat_data.get(Mapping.mapping_freq, None),
                    gain_db=mat_data.get(Mapping.mapping_gain_db_raw, None) if isinstance(mat_data.get(Mapping.mapping_gain_db_raw, None), np.ndarray)
                            else mat_data.get(Mapping.mapping_gain_db_corr, None),
                    phase=mat_data.get(Mapping.mapping_phase_deg, None) if isinstance(mat_data.get(Mapping.mapping_phase_deg, None), np.ndarray)
                        else mat_data.get(Mapping.mapping_phase_deg_corr, None)
                )
                self.test.refresh_plot()

            # Case 2: Don’t worry, take keys[3], keys[4], keys[5] as freq, gain_db, phase
            elif len(mat_data) >= 5:
                ref_freq = mat_data.get(list(mat_data.keys())[3], None)
                gain_db = mat_data.get(list(mat_data.keys())[4], None)
                phase = None

                # Determine whether there is a phase column based on the number of keys
                if len(mat_data) == 5:
                    len_data = min(ref_freq.size, gain_db.size)
                else:
                    phase = mat_data.get(list(mat_data.keys())[5], None)
                    len_data = min(ref_freq.size, gain_db.size, phase.size)

                import_data(
                    ref_freq=ref_freq[:len_data],
                    gain_db=gain_db[:len_data],
                    phase=phase[:len_data] if phase is not None else None
                )
                self.test.refresh_plot()

            # Situation 3: Insufficient data, pop-up window prompt
            else:
                messagebox.showwarning(Mapping.title_alert, "Missing data")

        except Exception as e:
            messagebox.showwarning(Mapping.title_alert, f"Failed to load MAT file: {e}")
