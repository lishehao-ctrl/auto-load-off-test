from __future__ import annotations

import tkinter as tk

from mapping import Mapping


class ViewModel:
    def __init__(self, root: tk.Misc) -> None:
        self.awg_model = tk.StringVar(root, value=Mapping.mapping_DSG_4102)
        self.osc_model = tk.StringVar(root, value=Mapping.mapping_MDO_34)

        self.awg_connect_mode = tk.StringVar(root, value="auto")
        self.osc_connect_mode = tk.StringVar(root, value="auto")
        self.awg_visa = tk.StringVar(root, value="")
        self.osc_visa = tk.StringVar(root, value="")
        self.awg_ip = tk.StringVar(root, value="0.0.0.0")
        self.osc_ip = tk.StringVar(root, value="0.0.0.0")

        self.freq_unit = tk.StringVar(root, value=Mapping.mapping_mhz)
        self.start_freq = tk.StringVar(root, value="1.0")
        self.stop_freq = tk.StringVar(root, value="100.0")
        self.step_freq = tk.StringVar(root, value="1.0")
        self.step_count = tk.StringVar(root, value="100")
        self.is_log = tk.BooleanVar(root, value=False)

        self.awg_amp = tk.StringVar(root, value="1.0")
        self.awg_imp = tk.StringVar(root, value=Mapping.mapping_imp_r50)

        self.osc_range = tk.StringVar(root, value="1.0")
        self.osc_offset = tk.StringVar(root, value="0.0")
        self.osc_points = tk.StringVar(root, value="10000")
        self.osc_imp = tk.StringVar(root, value=Mapping.mapping_imp_r50)
        self.osc_coupling = tk.StringVar(root, value=Mapping.mapping_coup_dc)

        self.awg_ch = tk.StringVar(root, value="1")
        self.osc_test_ch = tk.StringVar(root, value="1")
        self.osc_ref_ch = tk.StringVar(root, value="2")
        self.osc_trig_ch = tk.StringVar(root, value="2")

        self.correction_mode = tk.StringVar(root, value="none")
        self.trigger_mode = tk.StringVar(root, value="free_run")
        self.auto_range = tk.BooleanVar(root, value=True)
        self.auto_reset = tk.BooleanVar(root, value=True)
        self.calibration_enabled = tk.BooleanVar(root, value=False)
        self.auto_save_data = tk.BooleanVar(root, value=True)

        self.figure_mode = tk.StringVar(root, value="gain")
        self.magnitude_phase_mode = tk.StringVar(root, value="magnitude")

        self.status_text = tk.StringVar(root, value="Ready")
