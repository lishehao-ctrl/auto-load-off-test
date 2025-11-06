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
        super().__init__()  # 调用tkinter初始化，创建主窗口
        self.change_font()  # 设置默认字体

        # 设置窗口标题
        self.title(Mapping.label_for_input_ui)

        # 绑定关闭窗口的回调函数
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 初始化并显示UI
        self.generat_ui()


    def on_closing(self, *args):
        """关闭窗口前的回调函数：先保存配置，再销毁窗口"""
        self.auto_save_config()
        self.destroy()


    def change_font(self):
        """修改UI默认字体"""
        self.default_font = font.nametofont("TkDefaultFont")
        self.default_font.configure(
            family=Mapping.default_text_font[0], size=Mapping.default_text_font[1]
        )

        self.text_font = font.nametofont("TkTextFont")
        self.text_font.configure(
            family=Mapping.default_text_font[0], size=Mapping.default_text_font[1]
        )


    def generat_ui(self):
        """生成主界面布局"""
        # 创建主Frame
        self.frame_main = tk.Frame(self)
        self.frame_main.pack(anchor=tk.W, pady=5, fill=tk.BOTH, expand=True)

        # 创建测试控制区域Frame
        self.frame_test = tk.Frame(self.frame_main)
        self.frame_test.pack(anchor=tk.W, fill=tk.BOTH, expand=True)

        # 初始化I/O，设备控制和测试控制
        self.initialize_io()
        self.generate_device_control()
        self.show_test_control()

        # 自动加载配置文件
        self.auto_load_config()

        # 创建菜单栏
        self.menu_bar = tk.Menu(self)

        # 文件菜单
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

        # 配置菜单
        config_menu = tk.Menu(self.menu_bar, tearoff=0)
        config_menu.add_command(
            label=Mapping.label_for_device_configure_window,
            command=self.device_control_window.deiconify
        )

        # 将菜单加入菜单栏
        self.menu_bar.add_cascade(
            label=Mapping.label_for_file_menu, 
            menu=file_menu
        )
        self.menu_bar.add_cascade(
            label=Mapping.label_for_config_menu, 
            menu=config_menu
        )

        # 设置窗口的菜单栏
        self.config(menu=self.menu_bar)

        # 默认隐藏设备控制窗口
        self.device_control_window.withdraw()

    def initialize_io(self):
        """初始化 I/O 相关的变量、设备和通道"""

        # 自动保存配置开关
        self.auto_save = tk.BooleanVar()

        # 频率单位（例如 Hz/kHz/MHz）
        self.freq_unit = tk.StringVar(value="")

        # 测试对象，绑定频率单位
        self.test = TestLoadOff(freq_unit=self.freq_unit)
        # 当频率单位发生变化时，同步频率单位标签
        self.freq_unit.trace_add("write", self.test.refresh_plot)

        # 配置管理器
        self.cfgMgr = ConfigMgr()

        # 创建设备管理器
        self.var_device_num = tk.IntVar(value=self.test.device_num)
        self.device_manager = DeviceManager()
        self.device_manager.create_devices(
            device_num=self.var_device_num.get(),
            freq_unit=self.test.freq_unit
        )

        # ========== AWG 信号源设备 ==========
        self.awg_device = self.device_manager.get_devices()[0]  # 获取第一个设备作为 AWG
        self.awg_device.var_device_type.set(Mapping.label_for_device_type_awg)  # 设置设备类型为 AWG

        # AWG 通道设置
        self.awg_device.var_chan_num.set(1)      # 1 个通道
        self.awg_device.create_chan()            # 创建通道
        self.test.awg = self.awg_device.find_channel(chan_tag=1)  # 绑定测试对象的 AWG 通道

        # ========== 示波器设备 ==========
        self.osc_device = self.device_manager.get_devices()[1]  # 第二个设备为示波器
        self.osc_device.var_device_type.set(Mapping.label_for_device_type_osc)  # 设置设备类型为示波器

        # 示波器通道设置
        self.osc_device.var_chan_num.set(3)      # 3 个通道
        self.osc_device.create_chan()            # 创建通道

        # 主测试通道
        self.test.osc_test = self.osc_device.find_channel(chan_tag=1)
        # 参考通道，复制自主测试通道配置
        self.test.osc_ref = (self.osc_device.find_channel(chan_tag=2)
                             .copy_from(self.test.osc_test))
        # 触发通道，复制自主测试通道配置
        self.test.osc_trig = (self.osc_device.find_channel(chan_tag=3)
                              .copy_from(self.test.osc_test))
        self.test.osc_trig.chan_index.set(value=2)  # 设置触发通道索引为 2
        self.test.trace_trig_chan_index()           # 更新触发通道索引回调

    def set_ui_from_config(self):
        """从配置文件读取参数并回填到 UI 变量；只做取值与格式化，不改变业务逻辑"""

        # 频率单位
        freq_unit = self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_freq_unit,
            fallback=Mapping.mapping_mhz
        ).replace(" ", "").lower()

        # 这里用包含判断：'g'->GHz, 'm'->MHz, 'k'->kHz；否则默认 Hz
        if "g" in freq_unit:
            freq_unit = Mapping.mapping_ghz
        elif "m" in freq_unit:
            freq_unit = Mapping.mapping_mhz
        elif "k" in freq_unit:
            freq_unit = Mapping.mapping_khz
        else:
            freq_unit = Mapping.mapping_hz

        # ========= AWG/OSC 基本参数（统一用 cvtTools 做单位解析与格式化） =========
        # 频率扫描：起/止/步长/单位
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

        # AWG 幅度：转成 Vpp 文本；输出阻抗
        self.test.awg.amp.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_awg_amp, fallback=Mapping.default_awg_amp
        ))
        self.test.awg.imp.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_general, self.cfgMgr.mapping_awg_imp, fallback=Mapping.default_awg_imp
        ))

        # OSC 垂直偏置/量程（转为 V 文本）、输入阻抗、耦合、采样点数
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

        # ========= 模式区：量程联动/校准模式/触发模式/自动保存/自动复位 =========
        self.test.is_auto_osc_range.set(self.cfgMgr.cfg.getboolean(
            self.cfgMgr.mapping_mode, self.cfgMgr.mapping_is_auto_range, fallback=Mapping.default_is_auto_range
        ))
        self.test.var_correct_mode.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_mode, self.cfgMgr.mapping_correct_mode, fallback=Mapping.default_correct_mode
        ))
        self.test.is_correct_enabled.set(self.cfgMgr.cfg.getboolean(
            self.cfgMgr.mapping_mode, self.cfgMgr.mapping_is_correct_enabled, fallback=Mapping.default_is_correct_enabled
        ))

        # 触发模式：free run / triggered（忽略空格与大小写）
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

        # 自动保存与自动复位
        self.auto_save.set(self.cfgMgr.cfg.getboolean(
            self.cfgMgr.mapping_mode, self.cfgMgr.mapping_is_auto_save, fallback=Mapping.default_is_auto_save
        ))
        self.test.auto_reset.set(self.cfgMgr.cfg.getboolean(
            self.cfgMgr.mapping_mode, self.cfgMgr.mapping_is_auto_reset, fallback=Mapping.default_is_auto_reset
        ))

        # ========= 设备名（默认：AWG=DSG4102，OSC=MDO34） =========
        self.awg_device.var_device_name.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_device, self.cfgMgr.mapping_awg_name, fallback=Mapping.default_awg_name
        ))
        self.osc_device.var_device_name.set(self.cfgMgr.cfg.get(
            self.cfgMgr.mapping_device, self.cfgMgr.mapping_osc_name, fallback=Mapping.default_osc_name
        ))

        # ========= 通道索引映射（从配置恢复） =========
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

        # ========= 连接参数：AWG =========
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

        # ========= 连接参数：OSC =========
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
        """将当前 UI 中的参数写回配置。"""

        # ========= General（通用参数：频率扫描 / 单位 / AWG 幅度 / OSC 量程等） =========
        # 频率扫描：统一存为字符串
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_general, self.cfgMgr.mapping_start_freq, str(self.test.awg.start_freq.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_general, self.cfgMgr.mapping_stop_freq,  str(self.test.awg.stop_freq.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_general, self.cfgMgr.mapping_step_freq,  str(self.test.awg.step_freq.get()))

        # 步数（若 UI 中允许非整数输入，parse_general_val 可容错；最终仍以 str 写入）
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_step_num,
            str(CvtTools.parse_general_val(self.test.awg.step_num.get()))
        )

        # 对数扫描开关：保存为 "on"/"off"
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_is_log_freq_enabled,
            "on" if bool(self.test.awg.is_log_freq_enabled.get()) else "off"
        )

        # 频率单位：直接保存 UI 文本
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_freq_unit,
            str(self.test.freq_unit.get())
        )

        # AWG 幅度：直接保存 UI 文本
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_awg_amp,
            str(self.test.awg.amp.get())
        )
        # AWG 输出阻抗：直接保存当前选择
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_awg_imp,
            str(self.test.awg.imp.get())
        )

        # OSC 垂直偏置 / 量程：直接保存 UI 文本
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

        # OSC 输入阻抗 / 耦合 / 采样点数，直接保存 UI 文本
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_general, self.cfgMgr.mapping_osc_imp,  str(self.test.osc_test.imp.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_general, self.cfgMgr.mapping_osc_coup, str(self.test.osc_test.coupling.get()))
        self.cfgMgr.cfg.set(
            self.cfgMgr.mapping_general,
            self.cfgMgr.mapping_samp_pts,
            str(self.test.osc_test.points.get())
        )
        # NOTE: 如果 points 允许被设置为很小的数，建议在 UI 层或写入前做下限保护（如 >= 2 或 >= 128）

        # ========= Mode（模式：自动量程 / 校准 / 触发 / 自动保存 / 自动复位） =========
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

        # ========= Device（设备名：AWG / OSC） =========
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_device, self.cfgMgr.mapping_awg_name, str(self.awg_device.var_device_name.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_device, self.cfgMgr.mapping_osc_name, str(self.osc_device.var_device_name.get()))

        # ========= Channel（通道映射：索引） =========
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_chan, self.cfgMgr.mapping_awg_chan_index,         str(self.test.awg.chan_index.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_chan, self.cfgMgr.mapping_osc_test_chan_index,    str(self.test.osc_test.chan_index.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_chan, self.cfgMgr.mapping_osc_trig_chan_index,    str(self.test.osc_trig.chan_index.get()))
        self.cfgMgr.cfg.set(self.cfgMgr.mapping_chan, self.cfgMgr.mapping_osc_ref_chan_index,     str(self.test.osc_ref.chan_index.get()))

        # ========= Connection（连接：模式 / VISA / IP） =========
        # 连接模式：直接保存 UI 文本
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
        # IP：四段输入框拼接为 x.x.x.x；此处不做数值校验（加载时已做宽松解析与兜底）
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
        """手动保存：先把 UI 写回配置，再保存到磁盘，并触发一次自动保存"""
        self.set_config_from_ui()
        self.cfgMgr.save()
        self.cfgMgr.auto_save()


    def auto_save_config(self):
        """自动保存：仅把 UI 写回配置并调用 auto_save"""
        self.set_config_from_ui()
        self.cfgMgr.auto_save()

    def show_test_control(self):
        """构建并挂载测试控制区的行为（启用/禁用控件、运行测试、进度队列轮询等）"""

        # ========== 工具函数：递归启用/禁用所有子控件 ==========
        def activate_all_widgets(parent=self):
            """递归启用 parent 下的所有子控件（失败则忽略）"""
            for child in parent.winfo_children():
                try:
                    child.config(state=tk.NORMAL)
                except Exception:
                    pass
                activate_all_widgets(child)

        def disable_all_widgets(parent=self):
            """递归禁用 parent 下的所有子控件（失败则忽略）"""
            for child in parent.winfo_children():
                try:
                    child.config(state=tk.DISABLED)
                except Exception:
                    pass
                disable_all_widgets(child)

        # ========== 工具函数：按校准模式统一控制一组“校准相关控件”的状态 ==========
        def set_corr_controls_state(state=tk.NORMAL):
            """根据当前校准模式，统一启停校准相关控件"""
            if self.test.var_correct_mode.get() == Mapping.label_for_no_correct:
                # 不校准：不启用任何校准控件
                return
            # 单通道 / 双通道：这三项都启用
            try:
                self.set_as_ref.config(state=state)
                self.btn_load_ref.config(state=state)
                self.btn_enable_corr.config(state=state)
            except Exception:
                pass
            # 仅双通道：幅相切换下拉启/禁
            if self.test.var_correct_mode.get() == Mapping.label_for_duo_chan_correct:
                try:
                    self.cmb_mag_or_phase.config(state=state)
                except Exception:
                    pass

        # ========== 测试过程中的 UI 状态管理 ==========
        def activate_during_test():
            """测试开始后：开启必要控件"""
            try:
                self.btn_stop_test.config(state=tk.NORMAL)
                self.btn_save_data.config(state=tk.NORMAL)
                self.lb_status.config(state=tk.NORMAL)
                self.cmb_figure_switch.config(state=tk.NORMAL)
            except Exception:
                pass
            set_corr_controls_state(state=tk.NORMAL)

        def disable_during_set():
            """测试未开始或清理中：关闭部分控件"""
            try:
                self.btn_stop_test.config(state=tk.DISABLED)
            except Exception:
                pass

        # ========== 启动测试 ==========
        def start_test():
            """点击“开始测试”后的主流程：后台线程跑采集；主线程定时轮询队列并刷新 UI"""

            def test_func():
                """后台线程：做阻塞性动作（连接校验、扫频采集等）。禁止直接操作 Tk 控件。"""
                try:
                    # 1) 先全禁用，避免用户在准备阶段误触；并重置事件标志
                    disable_all_widgets()
                    
                    self.test.stop_event.clear()
                    self.pause_refresh_insts.clear()
                except Exception as e:
                    # 准备失败：恢复 UI 并提示
                    messagebox.showwarning(Mapping.title_alert, f"未准备就绪：{e}")
                    activate_all_widgets()
                    disable_during_set()
                    self.pause_refresh_insts.set()
                    return

                try:
                    # 2) 激活“测试期间”需要可用的控件
                    activate_during_test()

                    # 3) 设备连接/采集
                    self.test.start_swep_test()

                    self.lb_status.config(text="开始测试了") 

                except Exception as e:
                    # 采集中出错,自动保存
                    messagebox.showwarning(Mapping.title_alert, f"测试出错: {e}")
                    self.lb_status.config(text="")

                    if self.auto_save.get():
                        self.auto_save_file()

                    activate_all_widgets()
                    disable_during_set()

                    # 关闭设备连接
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
                """
                主线程定时轮询队列，刷新图像和状态栏。
                - item: 当前频点
                - None: 结束信号
                """
                finished = False
                try:
                    self.test.refresh_plot()
                    while True:
                        item = self.test.data_queue.get_nowait()
                        if item is None:
                            # 结束：更新状态并调用 stop_test
                            self.lb_status.config(
                                text="Done" if not self.test.stop_event.is_set() else "Stopped"
                            )
                            stop_test() 
                            finished = True
                            return

                        # 刷新图
                        self.test.refresh_plot()

                        # 更新状态行：按当前单位显示频点
                        unit = self.test.freq_unit.get()

                        scale = CvtTools.convert_general_unit(unit)
                        self.lb_status.config(text=f"Freq: {item/scale:.2f} {unit}")


                except queue.Empty:
                    pass
                finally:
                    if not finished:
                        # 100 ms 轮询一次
                        self.after(100, process_queue)

            # 启动后台采集线程
            threading.Thread(target=test_func, daemon=True).start()

            # 启动队列轮询（主线程）
            self.after(100, process_queue)

        def stop_test():
            """
            停止测试：
            - 发停止事件
            - 可选自动保存数据 
            - 自动保存配置
            - 关闭设备连接
            - 恢复UI
            """
            self.test.stop_event.set()

            # 自动保存数据（可配）
            if self.auto_save.get():
                try:
                    self.auto_save_file()
                except Exception as e:
                    messagebox.showwarning(Mapping.title_alert, f"自动保存数据失败：{e}")

            # 自动保存配置
            try:
                self.auto_save_config()
            except Exception as e:
                messagebox.showwarning(Mapping.title_alert, f"自动保存配置失败：{e}")

            # 关闭设备
            for inst in (getattr(self.test, "awg", None),
                         getattr(self.test, "osc_test", None),
                         getattr(self.test, "osc_ref", None),
                         getattr(self.test, "osc_trig", None)):
                try:
                    if inst is not None:
                        inst.inst_close()
                except Exception:
                    pass

            # 允许后台自动监测设备连接恢复运行
            self.pause_refresh_insts.set()

            # 恢复 UI
            activate_all_widgets()
            disable_during_set()  


        def show_step_control(*args):
            """
            根据“对数扫描开关”展示步进设置：
            - 对数：显示【步数】
            - 线性：显示【步长】
            """
            # 先清空容器
            for child in frame_set_step_freq.winfo_children():
                child.destroy()

            if self.test.awg.is_log_freq_enabled.get():
                # —— 对数：步数 —— #
                tk.Label(frame_set_step_freq, text=f"{Mapping.label_for_set_step_num}: ").pack(side=tk.LEFT, padx=5)
                etr = tk.Entry(frame_set_step_freq, textvariable=self.test.awg.step_num, width=10)
                etr.pack(side=tk.LEFT, padx=5)

                # 规范化：正数、通用格式、整数
                def _norm_step_num(_e=None):
                    TraceVal.general_out_focus(var=self.test.awg.step_num)
                    TraceVal.force_int_out_focus(var=self.test.awg.step_num)
                    TraceVal.force_positive_out_focus(var=self.test.awg.step_num)

                etr.bind("<FocusOut>", _norm_step_num)
                etr.bind("<Return>",   _norm_step_num)

            else:
                # —— 线性：步长 —— #
                tk.Label(frame_set_step_freq, text=f"{Mapping.label_for_set_step_freq}: ").pack(side=tk.LEFT, padx=5)
                etr = tk.Entry(frame_set_step_freq, textvariable=self.test.awg.step_freq, width=10)
                etr.pack(side=tk.LEFT, padx=5)

                # 规范化：正数、频率单位
                def _norm_step_freq(_e=None):
                    TraceVal.force_positive_out_focus(var=self.test.awg.step_freq)
                    TraceVal.freq_out_focus(freq=self.test.awg.step_freq)

                etr.bind("<FocusOut>", _norm_step_freq)
                etr.bind("<Return>",   _norm_step_freq)


        def show_correct_modes_control(*args):
            """
            根据校准模式生成对应控件：
            - 不校准：只显示触发模式
            - 单通道：触发 + 设为参考 / 读参考 / 校准使能
            - 双通道：触发 + 设为参考 / 读参考 / 校准使能
            """
            # 清空容器
            for child in frame_correct_modes.winfo_children():
                child.destroy()

            # 校准模式切换
            ttk.Combobox(frame_correct_modes,
                         textvariable=self.test.var_correct_mode,
                         values=Mapping.values_correct_modes,
                         width=5).pack(side=tk.LEFT, padx=5)

            # 触发模式（各模式都需要）
            ttk.Combobox(frame_correct_modes,
                         textvariable=self.test.trig_mode,
                         values=Mapping.values_trig_mode,
                         width=10).pack(side=tk.LEFT, padx=5)

            if self.test.var_correct_mode.get() == Mapping.label_for_no_correct:
                self.test.is_correct_enabled.set(False)  # 不校准时强制关闭
                return 

            # 三种模式共享：设为参考 / 读参考 / 校准使能
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
                    messagebox.showwarning(Mapping.title_alert, f"设为校准出错: {e}")

            self.set_as_ref = tk.Button(frame_correct_modes, text=Mapping.label_for_set_ref, command=set_as_ref)
            self.set_as_ref.pack(side=tk.LEFT, padx=5)

            self.btn_load_ref = tk.Button(frame_correct_modes, text=Mapping.label_for_load_ref, command=self.load_ref_file)
            self.btn_load_ref.pack(side=tk.LEFT, padx=5)

            self.btn_enable_corr = tk.Checkbutton(frame_correct_modes, text=Mapping.label_for_enable_ref, variable=self.test.is_correct_enabled)
            self.btn_enable_corr.pack(side=tk.LEFT, padx=5)

        def show_mag_or_phase(*args):
            """
            在“双通道校准”或“触发模式=Triggered”时显示【幅度/相位】下拉；
            否则强制显示“幅度”。
            """
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
                # 默认回退到“幅度”
                self.test.var_mag_or_phase.set(value=Mapping.label_for_mag)


        def connection_check(*args):
            """
            后台连接检测：
            - 创建两个后台线程分别检测 AWG 和 OSC 设备连接状态
            - 每隔 0.5 秒尝试打开+关闭一次设备，以判断是否可连接
            - 通过队列传递状态到 UI 主线程，主线程负责刷新“指示灯”颜色
            """

            connection_status_queue = queue.Queue()  # 线程安全队列，用于存放连接状态

            def awg_connection_worker():
                """AWG 设备探活线程"""
                awg_rm = visa.ResourceManager()
                while True:
                    self.pause_refresh_insts.wait()  # 等待事件 set，阻塞期间不检测
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

                    # 将状态放入队列，由主线程更新 UI
                    connection_status_queue.put((Mapping.label_for_device_type_awg, awg_ready))
                    time.sleep(0.5)  # 0.5 秒检测一次

            def osc_connection_worker():
                """OSC 设备探活线程"""
                osc_rm = visa.ResourceManager()
                while True:
                    self.pause_refresh_insts.wait()  # 等待事件 set 后执行
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
                """
                主线程 UI 更新函数：
                - 轮询队列中所有待更新的连接状态
                - 根据 ready 状态更新“指示灯”颜色：绿=已连接，红=未连接
                """
                try:
                    while True:
                        device_type, ready = connection_status_queue.get_nowait()
                        if device_type == Mapping.label_for_device_type_awg:
                            c_awg_connection_status.itemconfig(awg_light, fill="green" if ready else "red")
                        elif device_type == Mapping.label_for_device_type_osc:
                            c_osc_connection_status.itemconfig(osc_light, fill="green" if ready else "red")
                except queue.Empty:
                    pass  # 队列为空 -> 不做处理
                finally:
                    # 每 100 ms 再次调用自身，实现 UI 的周期更新
                    self.after(100, update_connection_status)

            # 启动后台探活线程（守护模式）
            threading.Thread(target=awg_connection_worker, daemon=True).start()
            threading.Thread(target=osc_connection_worker, daemon=True).start()

            # 启动 UI 定时刷新
            update_connection_status()


        # ========================= 左侧：设备与扫频参数 =========================
        frame_load_off_test = tk.Frame(self.frame_test)
        frame_load_off_test.pack(anchor=tk.W, fill=tk.BOTH, expand=True)

        frame_left = tk.Frame(frame_load_off_test)
        frame_left.pack(side=tk.LEFT, anchor=tk.N, fill=tk.Y)

        # 设备配置区域（AWG / OSC）
        frame_device_config = tk.Frame(frame_left)
        frame_device_config.pack(anchor=tk.W)

        # 底部测试控制（Start/Stop、联机状态、状态栏）
        frame_test_control = tk.Frame(frame_left)
        frame_test_control.pack(side=tk.BOTTOM)

        # ----------------- AWG：扫频参数 -----------------
        frame_awg = tk.Frame(frame_device_config)
        frame_awg.pack(anchor=tk.W)

        frame_awg_freq = tk.Frame(frame_awg)
        frame_awg_freq.pack(anchor=tk.W)

        # 起/止/步设置容器
        frame_awg_start_stop_freq = tk.Frame(frame_awg_freq)
        frame_awg_start_stop_freq.pack(side=tk.LEFT, padx=5)

        # 起始频率
        frame_set_freq_start = tk.Frame(frame_awg_start_stop_freq)
        frame_set_freq_start.pack(anchor=tk.W)

        lb_set_start_freq = tk.Label(frame_set_freq_start, text=f"{Mapping.label_for_set_start_frequency}: ")
        lb_set_start_freq.pack(side=tk.LEFT, padx=5)

        etr_set_start_freq = tk.Entry(frame_set_freq_start, textvariable=self.test.awg.start_freq, width=10)
        etr_set_start_freq.pack(side=tk.LEFT, padx=5)
        # 规范化: 数字 + 频率字符串
        etr_set_start_freq.bind("<FocusOut>", lambda e: TraceVal.freq_out_focus(freq=self.test.awg.start_freq))
        etr_set_start_freq.bind("<Return>",   lambda e: TraceVal.freq_out_focus(freq=self.test.awg.start_freq))

        # 终止频率
        frame_set_freq_end = tk.Frame(frame_awg_start_stop_freq)
        frame_set_freq_end.pack(anchor=tk.W)

        lb_set_stop_freq = tk.Label(frame_set_freq_end, text=f"{Mapping.label_for_set_stop_frequency}: ")
        lb_set_stop_freq.pack(side=tk.LEFT, padx=5)

        etr_set_stop_freq = tk.Entry(frame_set_freq_end, textvariable=self.test.awg.stop_freq, width=10)
        etr_set_stop_freq.pack(side=tk.LEFT, padx=5)
        # 规范化：正数 + 频率字符串
        etr_set_stop_freq.bind("<FocusOut>", lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.stop_freq),
                                                        TraceVal.freq_out_focus(freq=self.test.awg.stop_freq)))
        etr_set_stop_freq.bind("<Return>",   lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.stop_freq),
                                                        TraceVal.freq_out_focus(freq=self.test.awg.stop_freq)))

        # 步进设置（对数=步数；线性=步长）
        frame_set_step_freq = tk.Frame(frame_awg_start_stop_freq)
        frame_set_step_freq.pack(anchor=tk.W)

        # 根据是否开启对数步长展示不同控件
        show_step_control()

        # 中心/扫描宽度/单位选择容器
        frame_awg_center_freq = tk.Frame(frame_awg_freq)
        frame_awg_center_freq.pack(side=tk.LEFT, padx=5)

        # 中心频率
        frame_set_freq_center = tk.Frame(frame_awg_center_freq)
        frame_set_freq_center.pack(anchor=tk.W)

        lb_set_center_freq = tk.Label(frame_set_freq_center, text=f"{Mapping.label_for_set_center_frequency}: ")
        lb_set_center_freq.pack(side=tk.LEFT, padx=5)

        etr_set_center_freq = tk.Entry(frame_set_freq_center, textvariable=self.test.awg.center_freq, width=10)
        etr_set_center_freq.pack(side=tk.LEFT, padx=5)
        # 规范化：正数 + 频率字符串
        etr_set_center_freq.bind("<FocusOut>", lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.center_freq),
                                                        TraceVal.freq_out_focus(freq=self.test.awg.center_freq)))
        etr_set_center_freq.bind("<Return>",   lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.center_freq),
                                                        TraceVal.freq_out_focus(freq=self.test.awg.center_freq)))

        # 扫描宽度
        frame_awg_interval_freq = tk.Frame(frame_awg_center_freq)
        frame_awg_interval_freq.pack(anchor=tk.W)

        lb_set_interval_freq = tk.Label(frame_awg_interval_freq, text=f"{Mapping.label_for_set_interval_frequency}: ")
        lb_set_interval_freq.pack(side=tk.LEFT, padx=5)

        etr_set_interval_freq = tk.Entry(frame_awg_interval_freq, textvariable=self.test.awg.interval_freq, width=10)
        etr_set_interval_freq.pack(side=tk.LEFT, padx=5)
        # 规范化：频率字符串
        etr_set_interval_freq.bind("<FocusOut>", lambda e: TraceVal.freq_out_focus(freq=self.test.awg.interval_freq))
        etr_set_interval_freq.bind("<Return>",   lambda e: TraceVal.freq_out_focus(freq=self.test.awg.interval_freq))

        # 单位与对数开关
        frame_set_freq_unit = tk.Frame(frame_awg_center_freq)
        frame_set_freq_unit.pack(anchor=tk.W)

        btn_log_freq = tk.Checkbutton(frame_set_freq_unit, text=Mapping.label_for_log, variable=self.test.awg.is_log_freq_enabled)
        btn_log_freq.pack(side=tk.LEFT, padx=5)
        # 切换对数/线性时刷新“步进设置”控件
        self.test.awg.is_log_freq_enabled.trace_add("write", show_step_control)

        lb_set_freq_unit = tk.Label(frame_set_freq_unit, text=f"{Mapping.label_for_freq_unit}")
        lb_set_freq_unit.pack(side=tk.LEFT, padx=2)

        cmb_set_freq_unit = ttk.Combobox(frame_set_freq_unit, width=5,
                                        textvariable=self.test.freq_unit,
                                        values=Mapping.values_freq_unit)
        cmb_set_freq_unit.pack(side=tk.LEFT)

        # AWG 幅度
        frame_awg_amplitude = tk.Frame(frame_awg)
        frame_awg_amplitude.pack(anchor=tk.W, padx=5)

        frame_awg_amplitude_control = tk.Frame(frame_awg_amplitude)
        frame_awg_amplitude_control.pack(side=tk.LEFT)

        lb_awg_amplitude = tk.Label(frame_awg_amplitude_control, text=f"{Mapping.label_for_set_amp}: ")
        lb_awg_amplitude.pack(side=tk.LEFT, padx=5)

        etr_awg_amplitude = tk.Entry(frame_awg_amplitude_control, textvariable=self.test.awg.amp, width=10)
        etr_awg_amplitude.pack(side=tk.LEFT, padx=5)
        # 规范化：正数 + 幅度单位
        etr_awg_amplitude.bind("<FocusOut>", lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.amp),
                                                        TraceVal.vpp_out_focus(vpp=self.test.awg.amp)))
        etr_awg_amplitude.bind("<Return>",   lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.amp),
                                                        TraceVal.vpp_out_focus(vpp=self.test.awg.amp)))

        # ----------------- OSC：量程等 -----------------
        frame_osc = tk.Frame(frame_device_config)
        frame_osc.pack(anchor=tk.W, pady=10)

        frame_osc_range = tk.Frame(frame_osc)
        frame_osc_range.pack(anchor=tk.W, padx=5)

        lb_osc_range = tk.Label(frame_osc_range, text=f"{Mapping.label_for_range}: ")
        lb_osc_range.pack(side=tk.LEFT, padx=5)

        etr_osc_range = tk.Entry(frame_osc_range, textvariable=self.test.osc_test.range, width=10)
        etr_osc_range.pack(side=tk.LEFT)
        # 规范化：正数 + 幅度单位
        etr_osc_range.bind("<FocusOut>", lambda e: (TraceVal.force_positive_out_focus(var=self.test.osc_test.range),
                                                    TraceVal.volts_out_focus(curr=self.test.osc_test.range)))
        etr_osc_range.bind("<Return>",   lambda e: (TraceVal.force_positive_out_focus(var=self.test.osc_test.range),
                                                    TraceVal.volts_out_focus(curr=self.test.osc_test.range)))

        btn_osc_range_auto_switch = tk.Checkbutton(frame_osc_range, text=Mapping.label_for_auto_range, variable=self.test.is_auto_osc_range)
        btn_osc_range_auto_switch.pack(side=tk.LEFT, padx=5)

        # ========================= 右侧：图与模式 =========================
        frame_right = tk.Frame(frame_load_off_test)
        frame_right.pack(side=tk.LEFT, anchor=tk.N, fill=tk.BOTH, expand=True)

        frame_test_config = tk.Frame(frame_right)
        frame_test_config.pack(anchor=tk.W, padx=10, fill=tk.BOTH, expand=True)

        frame_test_config_control = tk.Frame(frame_test_config)
        # 右侧区域采用 grid：上方为控制条（不随窗体放大），下方为图像（可放大）
        frame_test_config.grid_rowconfigure(0, weight=0)
        frame_test_config.grid_rowconfigure(1, weight=1)
        frame_test_config.grid_columnconfigure(0, weight=1)
        # 控制条内部 grid：两端控件靠左右，中间留可伸缩空白列
        frame_test_config_control.grid(row=0, column=0, sticky="ew")
        frame_test_config_control.grid_columnconfigure(0, weight=0)
        frame_test_config_control.grid_columnconfigure(1, weight=0)
        frame_test_config_control.grid_columnconfigure(2, weight=1)
        frame_test_config_control.grid_columnconfigure(3, weight=0)
        frame_test_config_control.grid_columnconfigure(4, weight=0)

        # 图区域
        frame_figure = tk.Frame(frame_test_config)
        frame_figure.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.test.setup_plots(frame_figure)

        # 保存数据按钮
        self.btn_save_data = tk.Button(frame_test_config_control, text=Mapping.label_for_save_file, command=self.save_file)
        self.btn_save_data.grid(row=0, column=0, padx=5, sticky="w")

        # 校准模式区域
        frame_correct_modes = tk.Frame(frame_test_config_control)
        frame_correct_modes.grid(row=0, column=1, sticky="w")

        # 这些属性用于后续 enable/disable；提前声明以便类型提示
        self.btn_load_ref: tk.Button
        self.btn_enable_corr: tk.Button
        self.set_as_ref: tk.Button

        # 按当前模式生成控件，并在模式变更时重建
        show_correct_modes_control()
        self.test.var_correct_mode.trace_add("write", show_correct_modes_control)

        # 显示图像选择（Gain vs Freq / dB vs Freq）
        self.cmb_figure_switch = ttk.Combobox(
            frame_test_config_control,
            textvariable=self.test.figure_mode,
            values=Mapping.values_test_load_off_figure,
            width=20
        )
        self.cmb_figure_switch.grid(row=0, column=4, padx=5, sticky="e")

        # “幅度/相位”选择（仅双通道/触发模式显示）
        frame_mag_or_phase = tk.Frame(frame_test_config_control)
        frame_mag_or_phase.grid(row=0, column=3, padx=5, sticky="e")

        self.cmb_mag_or_phase: ttk.Combobox
        show_mag_or_phase()
        self.test.var_correct_mode.trace_add("write", show_mag_or_phase)
        self.test.trig_mode.trace_add("write", show_mag_or_phase)

        # ========================= 底部测试控制 =========================
        frame_test_control_button = tk.Frame(frame_test_control)
        frame_test_control_button.pack()

        self.btn_start_test = tk.Button(frame_test_control_button, text="start", command=start_test, state=tk.NORMAL, width=15, height=2)
        self.btn_start_test.pack(side=tk.LEFT, padx=5)

        self.btn_stop_test = tk.Button(frame_test_control_button, text="stop", command=stop_test, state=tk.DISABLED, width=15, height=2)
        self.btn_stop_test.pack(side=tk.LEFT, padx=5)

        # 连接状态提示（小红/绿灯）
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

        # 启动探活指示
        connection_check()

        # 状态栏（频点、运行状态等）
        self.lb_status = tk.Label(frame_test_control_button)
        self.lb_status.pack(side=tk.LEFT, padx=10)


    def generate_device_control(self):
        """
        设备控制区：
        - OSC 通道选择（根据校准/触发模式动态展示 Test/Ref/Trig)
        - VISA 资源刷新（后台线程探测 -> 主线程更新下拉）
        - 设备名变化回调：根据机型限制通道与阻抗选项
        """

        # ========================= 动态：OSC 通道选择 =========================
        def show_test_osc_sel(*args):
            """
            根据当前校准/触发模式，重建 OSC 通道选择控件
            """
            # 清空容器，避免叠加
            for child in frame_test_device_osc.winfo_children():
                child.destroy()

            # —— 标题（OSC 名称） —— #
            lb_test_device_osc = tk.Label(
                frame_test_device_osc,
                text=f"{Mapping.label_for_device_type_osc}: " 
            )
            lb_test_device_osc.pack(side=tk.LEFT, padx=5)

            # —— 被测通道（Test） —— #
            # 注意：下拉值范围根据当前 OSC 的最大通道动态生成
            values_osc_chan = list(range(1, self.osc_device.max_chan_num.get() + 1))
            cmb_test_osc_chan_test_index = ttk.Combobox(
                frame_test_device_osc,
                textvariable=self.test.osc_test.chan_index,
                values=values_osc_chan,
                width=5
            )
            cmb_test_osc_chan_test_index.pack(side=tk.LEFT, padx=5)
            tk.Label(frame_test_device_osc, text=Mapping.label_for_test_chan).pack(side=tk.LEFT)

            # —— 参考通道（Ref）：仅“双通道校准”时显示 —— #
            if self.test.var_correct_mode.get() == Mapping.label_for_duo_chan_correct:
                ttk.Combobox(
                    frame_test_device_osc,
                    textvariable=self.test.osc_ref.chan_index,
                    values=values_osc_chan,
                    width=5
                ).pack(side=tk.LEFT, padx=(5, 0))
                tk.Label(frame_test_device_osc, text=Mapping.label_for_ref_chan).pack(side=tk.LEFT)

            # —— 触发通道（Trig）：仅“Triggered”时显示 —— #
            if self.test.trig_mode.get() == Mapping.label_for_triggered:
                ttk.Combobox(
                    frame_test_device_osc,
                    textvariable=self.test.osc_trig.chan_index,
                    values=values_osc_chan,
                    width=5
                ).pack(side=tk.LEFT, padx=(5, 0))
                tk.Label(frame_test_device_osc, text=Mapping.label_for_trig_chan).pack(side=tk.LEFT)

        # ========================= 后台：VISA 资源刷新 =========================
        def refresh_insts(*args):
            """
            周期性刷新 VISA 资源列表：
            - 后台线程 list_resources() -> 入队
            - 主线程从队列取出并更新下拉框 values
            - 首次无值时，给 AWG/OSC 自动选择第一个资源（可选）
            - 防重入，避免重复启动线程
            """
            if not hasattr(self, "_insts_refresh_started"):
                self._insts_refresh_started = False
            if self._insts_refresh_started:
                return
            self._insts_refresh_started = True

            inst_queue = queue.Queue()

            def refresh_worker():
                """
                后台线程：周期 list_resources()，将结果入队；不直接触碰 Tk
                """
                rm = None
                while True:
                    try:
                        if rm is None:
                            rm = visa.ResourceManager()
                        values = rm.list_resources()
                        inst_queue.put(values)
                    except Exception:
                        # 资源管理器异常时重建；给 UI 一次空列表防止卡住
                        rm = None
                        inst_queue.put(tuple())
                    finally:
                        time.sleep(0.5)  # 节流，避免过于频繁

            def update_insts():
                """
                主线程：抽干队列 -> 更新两个 Combobox 的 values；
                若变量当前为空，自动选第一个（可选逻辑）
                """
                try:
                    while True:
                        values_auto_visa_address = inst_queue.get_nowait()
                        try:
                            cmb_awg_auto_visa_address['values'] = values_auto_visa_address
                            cmb_osc_auto_visa_address['values'] = values_auto_visa_address
                        except Exception:
                            # 如果下拉框尚未创建完毕，稍后重试
                            pass

                except queue.Empty:
                    pass
                finally:
                    # 100 ms 后继续轮询（非阻塞）
                    self.after(100, update_insts)

            threading.Thread(target=refresh_worker, daemon=True).start()
            update_insts()

        # ========================= 回调：AWG 名称变化 =========================
        def trace_awg_name(*args):
            """
            当 AWG 机型名称变化时：
            - 更新“标签：类型 + 名称”
            - DSG836: 强制选择RFO (index=1), 并强制 50Ω, 禁用“高阻”单选
            - 其它机型：恢复可选通道范围与高阻可用
            """
            try:
                lb_frame_awg_channel_tag.config(
                    text=f"{self.awg_device.var_device_type.get()} : {self.awg_device.var_device_name.get()}"
                )
            except Exception:
                pass

            if self.awg_device.var_device_name.get() == Mapping.mapping_DSG_836:
                # 固定单通道
                self.test.awg.chan_index.set("1")
                try:
                    cmb_awg_channel_index.config(values=["1"])
                    cmb_test_awg_chan_index.config(values=["1"])
                except Exception:
                    pass

                # 阻抗：固定 50Ω，禁用“高阻”
                try:
                    self.test.awg.imp.set(Mapping.mapping_imp_r50)
                    rb_btn_set_awg_imp_inf.config(state=tk.DISABLED)
                except Exception:
                    pass
            else:
                # 恢复多通道
                try:
                    self.test.awg.chan_index.set(1)
                    values_awg_chan = list(range(1, self.awg_device.max_chan_num.get() + 1))
                    cmb_awg_channel_index.config(values=values_awg_chan)
                    cmb_test_awg_chan_index.config(values=values_awg_chan)
                    rb_btn_set_awg_imp_inf.config(state=tk.NORMAL)
                except Exception:
                    pass

        # ========================= 回调：OSC 名称变化 =========================
        def trace_osc_name(*args):
            """当 OSC 机型名称变化时，更新“标签：类型 + 名称”"""
            try:
                lb_frame_osc_channel_tag.config(
                    text=f"{self.osc_device.var_device_type.get()}: {self.osc_device.var_device_name.get()}"
                )
            except Exception:
                pass

            # 根据机型限制可选通道范围
            if self.osc_device.var_device_name.get() == Mapping.mapping_DHO_1202:
                chan_values = list(range(1, instOSC_DHO1202.chan_num + 1))
                if self.test.osc_test.chan_index.get() not in chan_values:
                    self.test.osc_test.chan_index.set(1)

                # 阻抗：固定‘高阻’，禁用50Ω
                try:
                    self.test.osc_test.imp.set(Mapping.mapping_imp_high_z)
                    rb_btn_set_osc_imp_r50.config(state=tk.DISABLED)
                except Exception:
                    pass
            elif self.osc_device.var_device_name.get() == Mapping.mapping_DHO_1204:
                # 限制通道范围到 1..4；若越界则回落到 1
                chan_values = list(range(1, instOSC_DHO1204.chan_num + 1))
                if self.test.osc_test.chan_index.get() not in chan_values:
                    self.test.osc_test.chan_index.set(1)

                # 阻抗：固定‘高阻’，禁用50Ω
                try:
                    self.test.osc_test.imp.set(Mapping.mapping_imp_high_z)
                    rb_btn_set_osc_imp_r50.config(state=tk.DISABLED)
                except Exception:
                    pass
            else:
                # 恢复阻抗选项
                try:
                    rb_btn_set_osc_imp_r50.config(state=tk.NORMAL)
                except Exception:
                    pass


        # 先定义函数，再绑定/调用！
        def trace_log_freq(*_):
            """根据对数/线性开关重建‘步进设置’区域。"""
            # 清空旧控件
            for child in frame_set_step_freq.winfo_children():
                child.destroy()

            if self.test.awg.is_log_freq_enabled.get():
                # —— 对数：步数 —— #
                tk.Label(frame_set_step_freq, text=f"{Mapping.label_for_set_step_num}: ").pack(side=tk.LEFT, padx=5)

                etr = tk.Entry(frame_set_step_freq, textvariable=self.test.awg.step_num, width=10)
                etr.pack(side=tk.LEFT, padx=5)

                # 规范化：正整数 + 单位
                def _norm_step_num(_e=None):
                    TraceVal.general_out_focus(var=self.test.awg.step_num)
                    TraceVal.force_int_out_focus(var=self.test.awg.step_num)
                    TraceVal.force_positive_out_focus(var=self.test.awg.step_num)

                etr.bind("<FocusOut>", _norm_step_num)
                etr.bind("<Return>",   _norm_step_num)

            else:
                # —— 线性：步长 —— #
                tk.Label(frame_set_step_freq, text=f"{Mapping.label_for_set_step_freq}: ").pack(side=tk.LEFT, padx=5)

                etr = tk.Entry(frame_set_step_freq, textvariable=self.test.awg.step_freq, width=10)
                etr.pack(side=tk.LEFT, padx=5)

                def _norm_step_freq(_e=None):
                    TraceVal.force_positive_out_focus(var=self.test.awg.step_freq)
                    TraceVal.freq_out_focus(freq=self.test.awg.step_freq)

                etr.bind("<FocusOut>", _norm_step_freq)
                etr.bind("<Return>",   _norm_step_freq)

        def trace_osc_chan_num(*args):
            cmb_osc_channel_index.config(values=list(range(1, self.osc_device.max_chan_num.get() + 1)))

        def trace_awg_chan_num(*args):
            cmb_awg_channel_index.config(values=list(range(1, self.awg_device.max_chan_num.get() + 1)))

        # ======================= 设备管理（弹窗）与设备参数区 =======================
        self.device_control_window = tk.Toplevel()
        # 点击关闭按钮时不销毁窗口，只隐藏，便于再次打开
        self.device_control_window.protocol("WM_DELETE_WINDOW", self.device_control_window.withdraw)

        # 左侧总体容器
        frame_config = tk.Frame(self.device_control_window)
        frame_config.pack(side=tk.LEFT, anchor=tk.N)

        # 设备选择区（通道/机型）
        frame_test_device_sel = tk.Frame(frame_config)
        frame_test_device_sel.pack(anchor=tk.W)

        # VISA 地址设置组（AWG / OSC）
        frame_visa_address_groups = tk.Frame(frame_config)
        frame_visa_address_groups.pack(anchor=tk.W)

        # 设备细项控制区（AWG 参数设置等）
        frame_control = tk.Frame(frame_config)
        frame_control.pack(anchor=tk.W)

        # 探活线程的门闩事件：set() 时允许后台探活；clear() 时暂停（测试期间）
        self.pause_refresh_insts = threading.Event()
        self.pause_refresh_insts.set()

        # ----------------------- 设备选择：AWG/OSC 通道 -----------------------
        frame_device_selection = tk.Frame(frame_test_device_sel)
        frame_device_selection.pack(anchor=tk.W, pady=10)

        # AWG 通道选择
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

        # OSC 通道选择（根据校准/触发模式动态刷新）
        frame_test_device_osc = tk.Frame(frame_device_selection)
        frame_test_device_osc.pack(anchor=tk.W)

        show_test_osc_sel()  # 初始化一次
        # 模式/通道数变化时重建选择控件
        self.test.var_correct_mode.trace_add("write", show_test_osc_sel)
        self.test.trig_mode.trace_add("write", show_test_osc_sel)
        self.awg_device.max_chan_num.trace_add("write", show_test_osc_sel)
        self.osc_device.max_chan_num.trace_add("write", show_test_osc_sel)

        # ----------------------- AWG VISA 设置 -----------------------
        frame_awg_visa_address = tk.Frame(frame_visa_address_groups)
        frame_awg_visa_address.pack(anchor=tk.W)

        frame_awg_name = tk.Frame(frame_awg_visa_address)
        frame_awg_name.pack(anchor=tk.W)

        lb_awg_visa_address = tk.Label(frame_awg_name, text=f"#{Mapping.label_for_device_type_awg}")
        lb_awg_visa_address.pack(side=tk.LEFT, padx=5)

        cmb_awg_device_name = ttk.Combobox(
            frame_awg_name,
            textvariable=self.awg_device.var_device_name,
            values=Mapping.values_awg,
            width=10
        )
        cmb_awg_device_name.pack(side=tk.LEFT, padx=5)

        # Auto/LAN 切换 + 地址
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

        # LAN IPv4 四段输入
        frame_awg_lan = tk.Frame(frame_awg_auto_lan)
        frame_awg_lan.grid(row=1, column=2, sticky=tk.W, padx=10)

        etr_awg_lan_visa_address_1 = tk.Entry(frame_awg_lan, textvariable=self.awg_device.var_lan_ip_list[0], width=10)
        etr_awg_lan_visa_address_1.pack(side=tk.LEFT)
        tk.Label(frame_awg_lan, text=".").pack(side=tk.LEFT)
        etr_awg_lan_visa_address_2 = tk.Entry(frame_awg_lan, textvariable=self.awg_device.var_lan_ip_list[1], width=10)
        etr_awg_lan_visa_address_2.pack(side=tk.LEFT)
        tk.Label(frame_awg_lan, text=".").pack(side=tk.LEFT)
        etr_awg_lan_visa_address_3 = tk.Entry(frame_awg_lan, textvariable=self.awg_device.var_lan_ip_list[2], width=10)
        etr_awg_lan_visa_address_3.pack(side=tk.LEFT)
        tk.Label(frame_awg_lan, text=".").pack(side=tk.LEFT)
        etr_awg_lan_visa_address_4 = tk.Entry(frame_awg_lan, textvariable=self.awg_device.var_lan_ip_list[3], width=10)
        etr_awg_lan_visa_address_4.pack(side=tk.LEFT)

        # 规范化：每段强制整数 + 范围 0~255
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

        # ----------------------- OSC VISA 设置 -----------------------
        frame_osc_visa_address = tk.Frame(frame_visa_address_groups)
        frame_osc_visa_address.pack(anchor=tk.W)

        # 创建设备名称行
        frame_osc_name = tk.Frame(frame_osc_visa_address)
        frame_osc_name.pack(anchor=tk.W)

        lb_osc_visa_address = tk.Label(frame_osc_name, text=f"#{self.osc_device.device_index}: {Mapping.label_for_auto_lan}")
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

        # 自动检测模式单选按钮
        rb_osc_btn_auto = tk.Radiobutton(
            frame_osc_auto_lan, text=Mapping.mapping_auto_detect,
            variable=self.osc_device.var_switch_auto_lan, value=Mapping.label_for_auto
        )
        rb_osc_btn_auto.grid(row=0, column=0, sticky=tk.W)

        # 自动检测地址下拉框
        lb_osc_auto_visa_address = tk.Label(frame_osc_auto_lan, text=Mapping.label_for_visa_address)
        lb_osc_auto_visa_address.grid(row=0, column=1, sticky=tk.W)

        cmb_osc_auto_visa_address = ttk.Combobox(
            frame_osc_auto_lan, textvariable=self.osc_device.var_auto_visa_address, width=42
        )
        cmb_osc_auto_visa_address.grid(row=0, column=2, sticky=tk.W, padx=10)

        # Auto/LAN 切换 + 地址
        rb_osc_btn_lan = tk.Radiobutton(
            frame_osc_auto_lan, text=Mapping.label_for_lan,
            variable=self.osc_device.var_switch_auto_lan, value=Mapping.label_for_lan
        )
        rb_osc_btn_lan.grid(row=1, column=0, sticky=tk.W)

        lb_osc_lan_visa_address = tk.Label(frame_osc_auto_lan, text=Mapping.label_for_ip_address)
        lb_osc_lan_visa_address.grid(row=1, column=1, sticky=tk.W)

        # LAN IPv4 四段输入
        frame_osc_lan = tk.Frame(frame_osc_auto_lan)
        frame_osc_lan.grid(row=1, column=2, sticky=tk.W, padx=10)

        etr_osc_lan_visa_address_1 = tk.Entry(frame_osc_lan, textvariable=self.osc_device.var_lan_ip_list[0], width=10)
        etr_osc_lan_visa_address_1.pack(side=tk.LEFT)
        tk.Label(frame_osc_lan, text=".").pack(side=tk.LEFT)
        etr_osc_lan_visa_address_2 = tk.Entry(frame_osc_lan, textvariable=self.osc_device.var_lan_ip_list[1], width=10)
        etr_osc_lan_visa_address_2.pack(side=tk.LEFT)
        tk.Label(frame_osc_lan, text=".").pack(side=tk.LEFT)
        etr_osc_lan_visa_address_3 = tk.Entry(frame_osc_lan, textvariable=self.osc_device.var_lan_ip_list[2], width=10)
        etr_osc_lan_visa_address_3.pack(side=tk.LEFT)
        tk.Label(frame_osc_lan, text=".").pack(side=tk.LEFT)
        etr_osc_lan_visa_address_4 = tk.Entry(frame_osc_lan, textvariable=self.osc_device.var_lan_ip_list[3], width=10)
        etr_osc_lan_visa_address_4.pack(side=tk.LEFT)

        # 规范化：每段强制整数 + 范围 0~255
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


        # 后台刷新 VISA 资源下拉
        refresh_insts()

        # ----------------------- AWG 细项设置（通道/频率/幅度/阻抗） -----------------------
        frame_awg_setting = tk.Frame(frame_control)
        frame_awg_setting.pack(side=tk.LEFT, anchor=tk.N, padx=10)

        # 标题：设备类型 + 名称（机型变化时同步更新）
        lb_frame_awg_channel_tag = tk.Label(
            frame_awg_setting,
            text=f"{self.awg_device.var_device_type.get()} : {self.awg_device.var_device_name.get()}"
        )
        lb_frame_awg_channel_tag.pack(anchor=tk.W)
        self.awg_device.var_device_name.trace_add("write", trace_awg_name)

        # 通道选择
        frame_awg_channel_index = tk.Frame(frame_awg_setting)
        frame_awg_channel_index.pack(anchor=tk.W)

        cmb_awg_channel_index = ttk.Combobox(
            frame_awg_channel_index,
            textvariable=self.test.awg.chan_index,
            values=list(range(1, self.awg_device.max_chan_num.get() + 1)),
            width=5
        )
        cmb_awg_channel_index.pack(side=tk.LEFT, padx=5)
        self.awg_device.max_chan_num.trace_add("write", trace_awg_chan_num)

        lb_awg_channel_index = tk.Label(frame_awg_channel_index, text=Mapping.label_for_chan_index)
        lb_awg_channel_index.pack(side=tk.LEFT)

        # 起始频率
        frame_set_freq_start = tk.Frame(frame_awg_setting)
        frame_set_freq_start.pack(anchor=tk.W)

        lb_set_start_freq = tk.Label(frame_set_freq_start, text=f"{Mapping.label_for_set_start_frequency}: ")
        lb_set_start_freq.pack(side=tk.LEFT, padx=5)

        etr_set_start_freq = tk.Entry(frame_set_freq_start, textvariable=self.test.awg.start_freq, width=10)
        etr_set_start_freq.pack(side=tk.LEFT, padx=5)
        etr_set_start_freq.bind("<FocusOut>", lambda e: TraceVal.freq_out_focus(freq=self.test.awg.start_freq))
        etr_set_start_freq.bind("<Return>",   lambda e: TraceVal.freq_out_focus(freq=self.test.awg.start_freq))

        # 终止频率
        frame_set_freq_end = tk.Frame(frame_awg_setting)
        frame_set_freq_end.pack(anchor=tk.W)

        lb_set_stop_freq = tk.Label(frame_set_freq_end, text=f"{Mapping.label_for_set_stop_frequency}: ")
        lb_set_stop_freq.pack(side=tk.LEFT, padx=5)

        etr_set_stop_freq = tk.Entry(frame_set_freq_end, textvariable=self.test.awg.stop_freq, width=10)
        etr_set_stop_freq.pack(side=tk.LEFT, padx=5)
        etr_set_stop_freq.bind("<FocusOut>", lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.stop_freq),
                                                        TraceVal.freq_out_focus(freq=self.test.awg.stop_freq)))
        etr_set_stop_freq.bind("<Return>",   lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.stop_freq),
                                                        TraceVal.freq_out_focus(freq=self.test.awg.stop_freq)))

        # 步长
        frame_set_step_freq = tk.Frame(frame_awg_setting)
        frame_set_step_freq.pack(anchor=tk.W)
        self.test.awg.is_log_freq_enabled.trace_add("write", trace_log_freq)
        # 初次渲染
        trace_log_freq()

        # 幅度
        frame_set_amp = tk.Frame(frame_awg_setting)
        frame_set_amp.pack(anchor=tk.W)

        lb_set_amp = tk.Label(frame_set_amp, text=f"{Mapping.label_for_set_amp}: ")
        lb_set_amp.pack(side=tk.LEFT, padx=5)

        etr_set_amp = tk.Entry(frame_set_amp, textvariable=self.test.awg.amp, width=10)
        etr_set_amp.pack(side=tk.LEFT, padx=5)
        etr_set_amp.bind("<FocusOut>", lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.amp),
                                                TraceVal.vpp_out_focus(vpp=self.test.awg.amp)))
        etr_set_amp.bind("<Return>",   lambda e: (TraceVal.force_positive_out_focus(var=self.test.awg.amp),
                                                TraceVal.vpp_out_focus(vpp=self.test.awg.amp)))

        # 输出阻抗（R50 / 高阻）
        frame_set_awg_imp = tk.Frame(frame_awg_setting)
        frame_set_awg_imp.pack(anchor=tk.W)

        lb_set_awg_imp = tk.Label(frame_set_awg_imp, text=f"{Mapping.label_for_set_imp}: ")
        lb_set_awg_imp.pack(side=tk.LEFT, padx=5)

        rb_btn_set_awg_imp_r50 = tk.Radiobutton(
            frame_set_awg_imp, text=Mapping.label_for_imp_r50, variable=self.test.awg.imp, value=Mapping.mapping_imp_r50
        )
        rb_btn_set_awg_imp_r50.pack(side=tk.LEFT, padx=5)

        rb_btn_set_awg_imp_inf = tk.Radiobutton(
            frame_set_awg_imp, text=Mapping.label_for_imp_inf, variable=self.test.awg.imp, value=Mapping.mapping_imp_high_z
        )
        rb_btn_set_awg_imp_inf.pack(side=tk.LEFT, padx=5)


        # ======================= OSC（示波器）设置区 =======================
        frame_osc_setting = tk.Frame(frame_control)
        frame_osc_setting.pack(side=tk.LEFT, anchor=tk.N, padx=10)

        # 标题：设备类型 + 名称（机型变化时同步更新）
        lb_frame_osc_channel_tag = tk.Label(
            frame_osc_setting,
            text=f"{self.osc_device.var_device_type.get()}: {self.osc_device.var_device_name.get()}"
        )
        lb_frame_osc_channel_tag.pack(anchor=tk.W)
        self.osc_device.var_device_name.trace_add("write", trace_osc_name)

        # —— 通道索引 —— #
        frame_osc_channel_index = tk.Frame(frame_osc_setting)
        frame_osc_channel_index.pack(anchor=tk.W)

        cmb_osc_channel_index = ttk.Combobox(
            frame_osc_channel_index,
            textvariable=self.test.osc_test.chan_index,
            values=list(range(1, self.osc_device.max_chan_num.get() + 1)),
            width=5
        )
        cmb_osc_channel_index.pack(side=tk.LEFT, padx=5)
        self.osc_device.max_chan_num.trace_add("write", trace_osc_chan_num)

        lb_osc_channel_index = tk.Label(frame_osc_channel_index, text=Mapping.label_for_chan_index)
        lb_osc_channel_index.pack(side=tk.LEFT)

        # —— 耦合方式（AC/DC 等）—— #
        frame_osc_coup = tk.Frame(frame_osc_setting)
        frame_osc_coup.pack(anchor=tk.W)

        lb_osc_coup = tk.Label(frame_osc_coup, text=f"{Mapping.label_for_coup}: ")
        lb_osc_coup.pack(side=tk.LEFT, padx=5)

        cmb_osc_coup = ttk.Combobox(
            frame_osc_coup,
            textvariable=self.test.osc_test.coupling,
            values=Mapping.values_coup,
            width=5
        )
        cmb_osc_coup.pack(side=tk.LEFT, padx=5)

        # —— 满幅量程 —— #
        frame_osc_range = tk.Frame(frame_osc_setting)
        frame_osc_range.pack(anchor=tk.W)

        lb_osc_range = tk.Label(frame_osc_range, text=Mapping.label_for_range)
        lb_osc_range.pack(side=tk.LEFT, padx=5)

        etr_osc_range = tk.Entry(frame_osc_range, textvariable=self.test.osc_test.range, width=10)
        etr_osc_range.pack(side=tk.LEFT, padx=5)
        # 规范化：量程应为正数
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

        # —— 中心显示电压 —— #
        frame_osc_yoffset = tk.Frame(frame_osc_setting)
        frame_osc_yoffset.pack(anchor=tk.W)

        lb_osc_yoffset = tk.Label(frame_osc_yoffset, text=Mapping.label_for_yoffset)
        lb_osc_yoffset.pack(side=tk.LEFT, padx=5)

        etr_osc_yoffset = tk.Entry(frame_osc_yoffset, textvariable=self.test.osc_test.yoffset, width=10)
        etr_osc_yoffset.pack(side=tk.LEFT, padx=5)
        # 规范化：这里不强制正数（偏置允许负值）
        etr_osc_yoffset.bind("<FocusOut>", lambda e: TraceVal.volts_out_focus(curr=self.test.osc_test.yoffset)) 
        etr_osc_yoffset.bind("<Return>",   lambda e: TraceVal.volts_out_focus(curr=self.test.osc_test.yoffset))

        # —— 采样点数 —— #
        frame_osc_points = tk.Frame(frame_osc_setting)
        frame_osc_points.pack(anchor=tk.W)

        lb_osc_points = tk.Label(frame_osc_points, text=Mapping.label_for_points)
        lb_osc_points.pack(side=tk.LEFT, padx=5)

        etr_osc_points = tk.Entry(frame_osc_points, textvariable=self.test.osc_test.points, width=10)
        etr_osc_points.pack(side=tk.LEFT, padx=5)
        # 规范化：正整数，通用数值格式

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

        # —— 输入阻抗（R50 / 高阻）—— #
        frame_set_osc_imp = tk.Frame(frame_osc_setting)
        frame_set_osc_imp.pack(anchor=tk.W)

        lb_set_osc_imp = tk.Label(frame_set_osc_imp, text=f"{Mapping.label_for_set_imp}: ")
        lb_set_osc_imp.pack(side=tk.LEFT, padx=5)

        rb_btn_set_osc_imp_r50 = tk.Radiobutton(
            frame_set_osc_imp,
            text=Mapping.label_for_imp_r50,
            variable=self.test.osc_test.imp,
            value=Mapping.mapping_imp_r50
        )
        rb_btn_set_osc_imp_r50.pack(side=tk.LEFT, padx=5)

        rb_btn_set_osc_imp_inf = tk.Radiobutton(
            frame_set_osc_imp,
            text=Mapping.label_for_imp_inf,
            variable=self.test.osc_test.imp,
            value=Mapping.mapping_imp_high_z
        )
        rb_btn_set_osc_imp_inf.pack(side=tk.LEFT, padx=5)


    def auto_load_config(self):
        """
        自动加载配置（从默认位置）并同步到 UI
        """
        self.cfgMgr.auto_load()
        self.set_ui_from_config()


    def load_config(self):
        """
        选择并加载配置文件，然后同步到 UI
        """
        self.cfgMgr.load()
        self.set_ui_from_config()


    def generate_file_path_for_files(self, fp_data, time_stamp: str = ""):
        """
        依据传入的“基础文件路径”与可选时间戳，派生出 mat/txt/csv/png 等文件名并落盘。
        注意：
        - fp_data 只用作“基名 + 目录”的来源；不同格式的扩展名由本函数统一生成。
        - 将会保存: mat、txt、csv、两张图 (gain/freq 与 dB/freq)
        - 文本/CSV 列集合随“校准开关/校准模式/触发模式”而变
        """

        # ============ 1) 准备待保存的数据（统一转成 1D 向量，长度对齐） ============
        mat_freq       = np.round(self.test.results[Mapping.mapping_freq],            4)
        mat_gain_db    = np.round(self.test.results[Mapping.mapping_gain_db_raw],     4)
        mat_gain_db_c  = np.round(self.test.results[Mapping.mapping_gain_db_corr],    4)
        mat_phase      = np.round(self.test.results[Mapping.mapping_phase_deg],       4)
        mat_phase_c    = np.round(self.test.results[Mapping.mapping_phase_deg_corr],  4)

        # 配置快照
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

        # ============ 2) 生成各类目标文件路径（带可选时间戳前缀） ============

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

        # ============ 3) 定义各格式的保存子函数 ============
        def save_mat_file():
            """
            保存 mat: freq 必存；增益/相位按模式与校准开关选择；附带 config。
            """
            data_to_save = {Mapping.mapping_freq: mat_freq}
            # 增益列
            if self.test.is_correct_enabled.get():
                data_to_save[Mapping.mapping_gain_db_corr] = mat_gain_db_c
            else:
                data_to_save[Mapping.mapping_gain_db_raw] = mat_gain_db
            # 相位列（双通道 或 触发 模式时才保存）
            if (self.test.var_correct_mode.get() == Mapping.label_for_duo_chan_correct or
                self.test.trig_mode.get() == Mapping.label_for_triggered):
                if self.test.is_correct_enabled.get():
                    data_to_save[Mapping.mapping_phase_deg_corr] = mat_phase_c
                else:
                    data_to_save[Mapping.mapping_phase_deg] = mat_phase
            # 配置
            data_to_save["config"] = mat_config

            bATEinst_base.save_matfile(self, fn=file_path_mat, mm=data_to_save)

        def save_txt_file():
            """
            保存 txt (制表符分隔，带表头，无注释前缀)；列集合与 .mat 保持一致。
            """
            header = [f"{Mapping.mapping_freq}"]
            cols = [mat_freq]

            # 增益列
            if self.test.is_correct_enabled.get():
                header.append(f"{Mapping.mapping_gain_db_corr}")
                cols.append(mat_gain_db_c)
            else:
                header.append(f"{Mapping.mapping_gain_db_raw}")
                cols.append(mat_gain_db)

            # 相位列
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
            """
            保存 csv (逗号分隔，第一列单位显示为 Hz); 列集合与 mat 保持一致。
            """
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

            # 逐行写入data
            with open(file_path_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                for row in zip(*cols):
                    writer.writerow(row)

        def save_plot():
            """
            保存两张图: Gain vs Freq / dB vs Freq
            """
            # 这里假设 setup_plots 已创建 fig_gain / fig_db
            try:
                self.test.fig_gain.savefig(file_path_gain_png, dpi=300)
            except Exception:
                pass
            try:
                self.test.fig_db.savefig(file_path_gaindb_png, dpi=300)
            except Exception:
                pass

        # ============ 4) 真正执行保存 ============
        save_mat_file()
        save_txt_file()
        save_csv_file()
        save_plot()


    def save_file(self, *args):
        """
        手动保存：弹框选择“基础文件名”，随后派生出各格式文件并保存。
        """
        try:
            fp_data = filedialog.asksaveasfilename(
                filetypes=[("All files", "*.*")],
                initialfile="Test_File",
                initialdir=bATEinst_base.fn_relative(),
                title="保存数据文件",
            )
            if not fp_data:
                # 用户取消保存
                return

            self.generate_file_path_for_files(fp_data=fp_data)
            self.lb_status.config(text=Mapping.label_for_file_is_saved)

        except Exception as e:
            messagebox.showwarning(Mapping.title_alert, f"{Mapping.error_file_not_save}: {e}")


    def auto_save_file(self, *args):
        """
        自动保存：使用默认相对目录 + data 子目录 + 时间戳前缀，避免覆盖。
        """
        try:
            fp_data = bATEinst_base.fn_relative(fn=Mapping.default_data_fn, sub_folder=Mapping.label_for_sub_folder_data)
            time_stamp = datetime.now().strftime("%Y%m%d_%H_%M_%S") + "_"
            self.generate_file_path_for_files(fp_data=fp_data, time_stamp=time_stamp)
        except Exception as e:
            messagebox.showwarning(Mapping.title_alert, f"{Mapping.error_fail_auto_save}: {e}")


    def load_ref_file(self, *args):
        """
        读取参考 (校准) 文件 (mat), 构建参考插值函数 self.test.href_at, 并刷新图。
        要求 mat 至少包含：
        - 频率: self.test.mapping_freq
        - 增益(dB): raw 或 corr 二选一
        - 相位(可选): raw 或 corr 二选一（仅双通道/触发模式会用到）
        """
        default_fp = bATEinst_base.fn_relative(sub_folder=Mapping.label_for_sub_folder_data)

        ref_file_path = filedialog.askopenfilename(
            title="选择参考文件",
            initialdir=default_fp,
            filetypes=[("MAT files", "*.mat"), ("All files", "*.*")]
        )
        # 用户取消
        if not ref_file_path:
            return

        try:
            mat_data = loadmat(ref_file_path)

            # 优先取 raw，没有就取 corr
            freq  = mat_data.get(Mapping.mapping_freq, None)
            gdb   = mat_data.get(Mapping.mapping_gain_db_raw, None)
            if not isinstance(gdb, np.ndarray):
                gdb = mat_data.get(Mapping.mapping_gain_db_corr, None)

            ph    = mat_data.get(Mapping.mapping_phase_deg, None)
            if not isinstance(ph, np.ndarray):
                ph = mat_data.get(Mapping.mapping_phase_deg_corr, None)

            if isinstance(freq, np.ndarray) and isinstance(gdb, np.ndarray):
                # 构建参考插值（相位可为空）
                self.test.href_at = self.build_bspline_holdout_interp(
                    ref_freq=freq, gain_db=gdb, phase=ph
                )
                # 在主线程刷新
                self.test.refresh_plot()
            else:
                messagebox.showwarning(Mapping.title_alert, "缺少参考（频率或增益列不存在）")

        except Exception as e:
            messagebox.showwarning(Mapping.title_alert, f"加载 MAT 文件出错: {e}")


    def build_bspline_holdout_interp(self,
                                     ref_freq: np.ndarray,
                                     gain_db: np.ndarray,
                                     phase: np.ndarray | None):
        """
        构建“频率 -> 复数/幅度”参考插值函数：
        - 对频率去重、排序
        - n 点时样条阶数 k = min(3, n-1)
        - 若给了相位则返回复数插值；否则只返回幅度插值
        - 相位单位degree
        """
        # 归一化形状
        freq  = np.asarray(ref_freq, dtype=np.float64).squeeze()
        gdb   = np.asarray(gain_db,  dtype=np.float64).squeeze()

        phase = (
            None if (not isinstance(phase, np.ndarray)) or (phase.size == 0) 
            else np.asarray(phase).squeeze()
        ) 
        # 注意：phase 单位为 degree，需要先转换为 radian 再构造复数参考
        if phase is None:
            href = 10 ** (gdb / 20)
        else:
            phi = np.deg2rad(phase)
            href = 10 ** (gdb / 20) * (np.cos(phi) + 1j * np.sin(phi))

        # 排序 + 去重
        order = np.argsort(freq)
        freq, href = freq[order], href[order]
        freq, unique_idx = np.unique(freq, return_index=True)
        href = href[unique_idx]

        n = freq.size
        if n == 0:
            raise ValueError("ref_freq 为空")

        if n == 1:
            # 只有一个点：恒等函数
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

        # 样条阶数
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
        """
        加载外部 MAT 文件中的数据，用于在 UI 中显示频率、增益和相位曲线。
        支持标准键名或兜底按顺序读取。
        """

        def import_data(ref_freq: np.ndarray, gain_db: np.ndarray, phase: np.ndarray | None):
            """
            内部函数：将读取的数据写入 self.test.results 中，
            并自动计算线性增益值。
            """
            freq = np.asarray(ref_freq, dtype=np.float64).squeeze()   # 频率数组
            gain_db = np.asarray(gain_db).squeeze()                   # 增益(dB)数组
            gain = 10 ** (gain_db / 20)                               # dB 转线性幅值

            # 如果 phase 无效，则设为 None
            phase = None if (not isinstance(phase, np.ndarray)) or (phase.size == 0) else np.asarray(phase).squeeze()

            # 将数据存入 test.results 字典
            self.test.results[Mapping.mapping_freq] = freq
            self.test.results[Mapping.mapping_gain_raw] = gain
            self.test.results[Mapping.mapping_gain_db_raw] = gain_db
            if phase is not None:
                self.test.results[Mapping.mapping_phase_deg] = phase
                phi = np.deg2rad(phase)
                self.test.results[Mapping.mapping_gain_complex] = gain * (np.cos(phi) + 1j * np.sin(phi))

        # 设置默认路径
        default_fp = bATEinst_base.fn_relative(sub_folder=Mapping.label_for_sub_folder_data)

        # 弹出文件选择对话框
        data_file_path = filedialog.askopenfilename(
            title="选择显示文件",
            initialdir=default_fp,
            filetypes=[("MAT files", "*.mat"), ("All files", "*.*")]
        )

        try:
            # 读取 MAT 文件
            mat_data = loadmat(data_file_path)

            # 情况1：标准键名，直接读取
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

            # 情况2：兜底，取 keys[3], keys[4], keys[5] 作为 freq, gain_db, phase
            elif len(mat_data) >= 5:
                ref_freq = mat_data.get(list(mat_data.keys())[3], None)
                gain_db = mat_data.get(list(mat_data.keys())[4], None)
                phase = None

                # 根据 key 数量决定是否有相位列
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

            # 情况3：数据不够，弹窗提示
            else:
                messagebox.showwarning(Mapping.title_alert, f"缺少数据")

        except Exception as e:
            messagebox.showwarning(Mapping.title_alert, f"加载 MAT 文件出错: {e}")
