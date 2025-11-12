from __future__ import annotations

class Mapping:
    # ========================= messages =========================
    label_for_input_ui                 = "Input Control Panel"
    label_for_file_menu                = "File"
    label_for_config_menu              = "Device Manager"
    label_for_device_configure_window  = "Advanced Settings"
    label_for_exit                     = "Exit"

    # ========================= connection =========================
    label_for_auto_lan                 = "Connection Mode"
    label_for_visa_address             = "VISA address"
    label_for_ip_address               = "IP address"
    label_for_auto                     = "Auto"
    label_for_lan                      = "LAN"

    # ========================= channel =========================
    label_for_chan_index               = "Channel"
    label_for_test_chan                = "Test Channel"
    label_for_ref_chan                 = "Reference Channel"
    label_for_trig_chan                = "Trigger Channel"

    # ========================= awg/osc setting =========================
    label_for_set_start_frequency      = "Start Freq"
    label_for_set_stop_frequency       = "Stop Freq"
    label_for_set_step_freq            = "Freq Step"
    label_for_set_step_num             = "Step Count"
    label_for_set_center_frequency     = "Center Freq"
    label_for_set_interval_frequency   = "Span"
    label_for_log                      = "Log"
    label_for_freq_unit                = "Unit"
    label_for_points                   = "Max Samples"
    label_for_freq                     = "Frequency"
    label_for_set_amp                  = "Amplitude"
    label_for_set_imp                  = "Impedance"
    label_for_imp_r50                  = "R50"
    label_for_imp_inf                  = "High-Z"
    label_for_coup                     = "Coupling Mode"
    label_for_yoffset                  = "Center Voltage"
    label_for_range                    = "Full-Scale Voltage"
    label_for_auto_range               = "Auto"

    # ========================= correct/reference =========================
    label_for_single_chan_correct      = "Single Channel"
    label_for_duo_chan_correct         = "Dual Channel"
    label_for_no_correct               = "No Calibration"
    label_for_set_ref                  = "Set As Reference"
    label_for_load_ref                 = "Load Reference"
    label_for_enable_ref               = "Enable Calibration"

    # ========================= figure =========================
    label_for_figure_gain              = "Gain"
    label_for_figure_gain_db           = "dB"
    label_for_figure_phase             = "Phase (deg)"
    label_for_figure_gain_freq         = f"{label_for_figure_gain}_vs_{label_for_freq}"
    label_for_figure_gaindb_freq       = f"{label_for_figure_gain_db}_vs_{label_for_freq}"

    # ========================= load/save data =========================
    label_for_load_file_to_show        = "Load data file for display"
    label_for_load_file_to_ref         = "Load data file as reference"
    label_for_load_config              = "Load config file"
    label_for_save_file                = "Save data"
    label_for_save_config              = "Save config"
    label_for_file_is_saved            = "File saved"
    label_for_sub_folder_data          = "__data__"

    # ========================= errors & titles =========================
    error_file_not_save                = "Failed to save data!!!"
    error_fail_auto_save               = "Automatic save failed!!!"
    title_alert                        = "Warning"

    # ========================= mappings / options =========================
    mapping_auto_detect                = "Auto Detect"
    label_for_device_type_awg          = "Arbitrary Waveform Generator"
    label_for_device_type_osc          = "Oscilloscope"

    mapping_DSG_4102                   = "DSG4102"
    mapping_DSG_836                    = "DSG836"
    mapping_MDO_34                     = "MDO34"
    mapping_MDO_3024                   = "MDO3024"
    mapping_DHO_1202                   = "DHO1202"
    mapping_DHO_1204                   = "DHO1204"

    mapping_hz                         = "Hz"
    mapping_khz                        = "KHz"
    mapping_mhz                        = "MHz"
    mapping_ghz                        = "GHz"

    mapping_imp_r50                    = "50"
    mapping_imp_high_z                 = "INF"

    mapping_vpp                        = "Vpp"
    mapping_vpk                        = "Vpk"
    mapping_vrms                       = "Vrms"

    mapping_file_ext_mat               = ".mat"
    mapping_file_ext_csv               = ".csv"
    mapping_file_ext_txt               = ".txt"
    mapping_file_ext_png               = ".png"

    mapping_coup_ac                    = "AC"
    mapping_coup_dc                    = "DC"

    mapping_state_on                   = "ON"
    mapping_state_off                  = "OFF"

    # ========================= combobox values =========================
    values_awg = [
        mapping_DSG_4102,
        mapping_DSG_836,
    ]
    values_osc = [
        mapping_MDO_34,
        mapping_MDO_3024,
        mapping_DHO_1202,
        mapping_DHO_1204,
    ]
    values_device_type = [
        label_for_device_type_awg,
        label_for_device_type_osc,
    ]
    values_freq_unit = [
        mapping_hz,
        mapping_khz,
        mapping_mhz,
        mapping_ghz,
    ]
    values_device_num_list             = [1, 2, 3, 4]
    values_test_load_off_figure = [
        label_for_figure_gain_freq,
        label_for_figure_gaindb_freq,
    ]
    values_correct_modes = [
        label_for_no_correct,
        label_for_single_chan_correct,
        label_for_duo_chan_correct,
    ]
    values_coup = [
        mapping_coup_ac,
        mapping_coup_dc,
    ]

    # ========================= data keys =========================
    mapping_freq                       = "freq"
    mapping_gain_raw                   = "gain_raw"
    mapping_gain_db_raw                = "gain_db_raw"
    mapping_phase_deg                  = "phase"
    mapping_gain_corr                  = "gain_corr"
    mapping_gain_db_corr               = "gain_db_corr"
    mapping_phase_deg_corr             = "phase_corr"
    mapping_gain_complex               = "gain_complex"

    # ========================= trigger modes =========================
    label_for_free_run                 = "free run"
    label_for_triggered                = "triggered"
    values_trig_mode                   = [label_for_free_run, label_for_triggered]

    # ========================= colors =========================
    mapping_color_for_phase_line       = "tab:red"

    # ========================= plot options =========================
    label_for_mag                      = "Magnitude"
    label_for_phase                    = "Phase"
    label_for_mag_and_phase            = "Magnitude + Phase"
    values_mag_or_phase                = [label_for_mag, label_for_phase, label_for_mag_and_phase]

    # ========================= defaults (UI/fonts/theme) =========================
    default_data_fn                    = "Test_File"
    default_show_selection_font        = ("Microsoft YaHei", 18)
    default_text_font                  = ("Microsoft YaHei", 10)
    default_terminal_bg                = "black"
    default_terminal_fg                = "white"

    # ========================= defaults (general sweep) =========================
    default_start_freq                 = "1.0"
    default_stop_freq                  = "100.0"
    default_step_freq                  = "1.0"
    default_step_num                   = "100"
    default_is_log_freq_enabled        = mapping_state_off
    default_freq_unit                  = mapping_mhz
    default_samp_pts                   = "10000"

    # ========================= defaults (AWG/OSC settings) =========================
    default_awg_amp                    = "1.0"
    default_awg_imp                    = "50"
    default_yoffset                    = "0.0"
    default_range                      = "1.0"
    default_osc_imp                    = "50"
    default_osc_coup                   = mapping_coup_dc

    # ========================= defaults (modes/switches) =========================
    default_is_auto_range              = mapping_state_on
    default_correct_mode               = label_for_no_correct
    default_is_correct_enabled         = mapping_state_off
    default_trig_mode                  = label_for_free_run
    default_is_auto_save               = mapping_state_on
    default_is_auto_reset              = mapping_state_on

    # ========================= defaults (device names) =========================
    default_awg_name                   = mapping_DSG_4102
    default_osc_name                   = mapping_MDO_34

    # ========================= defaults (channel indices) =========================
    default_awg_chan_index             = "1"
    default_osc_test_chan_index        = "1"
    default_osc_trig_chan_index        = "2"
    default_osc_ref_chan_index         = "2"

    # ========================= defaults (connection) =========================
    default_awg_connect_mode           = label_for_auto
    default_osc_connect_mode           = label_for_auto
    default_awg_visa                   = ""
    default_osc_visa                   = ""
    default_awg_ip                     = "0.0.0.0"
    default_osc_ip                     = "0.0.0.0"
