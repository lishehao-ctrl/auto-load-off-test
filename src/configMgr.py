import configparser
import sys
import os
from tkinter import filedialog
from mapping import Mapping

class ConfigMgr:

    # Default file name and subdirectory
    default_cfg_fn               = "config.ini"
    default_sub_folder           = "__config__"

    # Config section names
    mapping_general              = "general"
    mapping_mode                 = "mode"
    mapping_connection           = "connection"
    mapping_device               = "device"
    mapping_chan                 = "channel"

    # Keys inside the general section
    mapping_start_freq           = "start_freq"
    mapping_stop_freq            = "stop_freq"
    mapping_step_freq            = "step_freq"
    mapping_step_num             = "step_num"
    mapping_is_log_freq_enabled  = "is_log_freq_enabled"
    mapping_freq_unit            = "freq_unit"
    mapping_awg_amp              = "amp"
    mapping_awg_imp              = "awg_impedance"
    mapping_yoffset              = "yoffset"
    mapping_range                = "range"
    mapping_osc_imp              = "osc_impedance"
    mapping_osc_coup             = "osc_coupling"
    mapping_samp_pts             = "max_sampling_points"

    # Keys inside the mode section
    mapping_is_auto_range        = "auto_range"
    mapping_correct_mode         = "correct_mode"
    mapping_is_correct_enabled   = "is_correct_enabled"
    mapping_trig_mode            = "trig_mode"
    mapping_is_auto_save         = "auto_save"
    mapping_is_auto_reset        = "auto_reset"

    # Keys inside the device section
    mapping_awg_name             = "awg_model"
    mapping_osc_name             = "osc_model"

    # Keys inside the channel section
    mapping_awg_chan_index       = "awg_chan_index"
    mapping_osc_test_chan_index  = "osc_test_chan_index"
    mapping_osc_trig_chan_index  = "osc_trig_chan_index"
    mapping_osc_ref_chan_index   = "osc_ref_chan_index"

    # Keys inside the connection section
    mapping_awg_connect_mode     = "awg_connect_mode(Auto/Lan)"
    mapping_osc_connect_mode     = "osc_connect_mode(Auto/Lan)"
    mapping_awg_visa             = "awg_visa"
    mapping_osc_visa             = "osc_visa"
    mapping_awg_ip               = "awg_ip"
    mapping_osc_ip               = "osc_ip"

    # Default configuration values
    defaults = {
        mapping_general   : {
            mapping_start_freq          : Mapping.default_start_freq,
            mapping_stop_freq           : Mapping.default_stop_freq,
            mapping_step_freq           : Mapping.default_step_freq,
            mapping_step_num            : Mapping.default_step_num,
            mapping_is_log_freq_enabled : Mapping.default_is_log_freq_enabled,
            mapping_freq_unit           : Mapping.default_freq_unit,
            mapping_awg_amp             : Mapping.default_awg_amp,
            mapping_awg_imp             : Mapping.default_awg_imp,
            mapping_yoffset             : Mapping.default_yoffset,
            mapping_range               : Mapping.default_range,
            mapping_osc_imp             : Mapping.default_osc_imp,
            mapping_osc_coup            : Mapping.default_osc_coup,
            mapping_samp_pts            : Mapping.default_samp_pts,
        },

        mapping_mode      : {
            mapping_is_auto_range       : Mapping.default_is_auto_range,
            mapping_correct_mode        : Mapping.default_correct_mode,
            mapping_is_correct_enabled  : Mapping.default_is_correct_enabled,
            mapping_trig_mode           : Mapping.default_trig_mode,
            mapping_is_auto_save        : Mapping.default_is_auto_save,
            mapping_is_auto_reset       : Mapping.default_is_auto_reset,
        },

        mapping_device    : {
            mapping_awg_name            : Mapping.default_awg_name,
            mapping_osc_name            : Mapping.default_osc_name,
        },

        mapping_chan      : {
            mapping_awg_chan_index      : Mapping.default_awg_chan_index,
            mapping_osc_test_chan_index : Mapping.default_osc_test_chan_index,
            mapping_osc_trig_chan_index : Mapping.default_osc_trig_chan_index,
            mapping_osc_ref_chan_index  : Mapping.default_osc_ref_chan_index,
        },

        mapping_connection: {
            mapping_awg_connect_mode    : Mapping.default_awg_connect_mode,
            mapping_osc_connect_mode    : Mapping.default_osc_connect_mode,
            mapping_awg_visa            : Mapping.default_awg_visa,
            mapping_osc_visa            : Mapping.default_osc_visa,
            mapping_awg_ip              : Mapping.default_awg_ip,
            mapping_osc_ip              : Mapping.default_osc_ip,
        },
    }

    def __init__(self):
        # Initialize the config object with defaults
        self.save_fp = None
        self.cfg = configparser.ConfigParser()
        self.cfg.read_dict(self.defaults)

    @staticmethod
    def fn_relative(fn=None, sub_folder=None):
        # Resolve an absolute path for a file/folder and ensure the directory exists.
        if fn and os.path.isabs(fn):
            return fn
        else:
            if getattr(sys, 'frozen', False):
                hd = os.path.dirname(sys.executable)
            else:
                hd, _ = os.path.split(os.path.realpath(__file__))

            if sub_folder is None:
                path = hd if fn is None else os.path.join(hd, fn)
            else:
                folder = os.path.join(hd, sub_folder)
                path = folder if fn is None else os.path.join(folder, fn)

            path = os.path.realpath(path)

            # For files ensure the parent exists; for directories ensure the directory exists.
            if fn is None:
                os.makedirs(path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(path), exist_ok=True)

            return path
        
    def auto_load(self):
        # Load the default configuration file automatically.
        auto_fp = self.fn_relative(fn=self.default_cfg_fn, sub_folder=self.default_sub_folder)
        if os.path.exists(auto_fp):
            self.cfg.read(auto_fp, encoding="utf-8")
        return self.cfg

    def load(self):
        # Let the user choose a configuration file via a file dialog.
        default_fp = self.fn_relative(sub_folder=self.default_sub_folder)
        fp = filedialog.askopenfilename(
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
            initialdir=default_fp,
            title="Load configuration file"
        )
        self.cfg.read(fp, encoding="utf-8")
        return self.cfg

    def save(self):
        # Save configuration to a user-selected path.
        self.save_fp = filedialog.asksaveasfilename(
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
            initialfile=self.default_cfg_fn,
            initialdir=self.fn_relative(sub_folder=self.default_sub_folder),
            title="Save configuration file"
        )
        with open(self.save_fp, "w", encoding="utf-8") as f:
            self.cfg.write(f)

    def auto_save(self):
        # Save to the default path automatically.
        default_fp = self.fn_relative(fn=self.default_cfg_fn, sub_folder=self.default_sub_folder)
        with open(default_fp, "w", encoding="utf-8") as f:
            self.cfg.write(f)
