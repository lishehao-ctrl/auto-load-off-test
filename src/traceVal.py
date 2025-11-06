import re
import tkinter as tk
from cvtTools import CvtTools

class TraceVal:
    """
    输入框“失焦”时的规范化工具:
    - 将字符串中的数值与单位解析出来
    - 统一单位前缀 (G/M/k/m/µ/n/p)
    - 根据类型（频率/电压/电流/幅度等）拼回规范化文本
    - 提供强制正数、强制整数、IP 段校验等通用校验
    """

    # ----------------------------- 频率 -----------------------------
    @staticmethod
    def freq_out_focus(freq: tk.StringVar, *args):
        """
        频率输入规范化：
        - 解析出数值与单位前缀（如 k、M、G)
        - 统一改写为“<val> <前缀>Hz”, 例如 "1.5k" -> "1.5 kHz"
        - 若未提供任何单位，则不处理（保留原值）
        """
        freq_match = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]*)", freq.get().replace(" ", ""))

        freq_val = freq_match.group(1)
        freq_unit = freq_match.group(2)

        # 无单位：不做改写
        if freq_unit == "":
            return

        prefix = freq_unit[0]
        unit = "Hz"   # 频率的单位后缀

        # 统一单位前缀（大小写兼容）
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
        elif prefix in ("h", "H"):       # 兼容用户输入 "Hz"
            ini = ""
        else:
            # 未知前缀：不附加单位（尽量保留原意）
            ini = ""
            unit = ""

        parse_freq = f"{freq_val} {ini}{unit}"
        freq.set(parse_freq)

    # ----------------------------- 电压/电流（通用“curr”命名，但 unit=V） -----------------------------
    @staticmethod
    def volts_out_focus(curr: tk.StringVar):
        """
        电量输入规范化 (当前实现以“V”为单位): 
        - 解析数值与单位前缀, 统一前缀 (G/M/k/m/µ/n/P)
        - 拼接为“<val> <前缀>V”
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

    # ----------------------------- 幅度（Vpp/Vpk/Vrms/V） -----------------------------
    @staticmethod
    def vpp_out_focus(vpp: tk.StringVar):
        """
        幅度输入规范化：
        - 解析数值与单位前缀, 统一前缀(G/M/k/m/µ/n/P)
        - 识别单位: Vpp / Vpk(原代码写 Vpl) / Vrms / V (按包含关系）
        - 未识别则不追加单位
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
        
        # 单位识别（忽略大小写）
        if "Vpp".lower() in vpp_unit.lower():
            unit = "Vpp"
        elif "Vpk".lower() in vpp_unit.lower():
            unit = "Vpk"
        elif "Vrms".lower() in vpp_unit.lower() or "vr" in vpp_unit.lower():
            unit = "Vrms"
        elif "v" in vpp_unit.lower():
            unit = "Vpp"  # 仅出现 'v' 时，默认按 Vpp 处理
        else:
            unit = ""

        parse_curr = f"{vpp_val} {ini}{unit}"
        vpp.set(parse_curr)

    # ----------------------------- 通用：仅保留前缀 -----------------------------
    @staticmethod
    def general_out_focus(var: tk.StringVar, *args):
        """
        通用规范化 (不关心物理量类型): 
        - 只统一单位前缀 (G/M/k/m/µ/n/P), 不附加具体单位名称
        - 结果格式：“<val> <前缀>”
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

    # ----------------------------- 约束：必须为正数（>0） -----------------------------
    @staticmethod
    def force_positive_out_focus(var: tk.StringVar, *args):
        """
        强制正数：
        - 匹配字符串中的数值（科学计数法）
        - 若解析失败或 <= 0, 则清空
        """
        try:
            val = re.search(r"[+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?", var.get().replace(" ", ""))
            if val and float(val.group()) > 0:
                return
            var.set("")
        except (tk.TclError, ValueError):
            var.set("")

    # ----------------------------- 约束：取整（按单位缩放后取整） -----------------------------
    @staticmethod
    def force_int_out_focus(var: tk.StringVar, *args):
        """
        强制整数：
        - 解析数值和单位前缀，借助 cvtTools.convert_general_unit 计算单位缩放
        - 先将值换算到“基本单位”上取整，再换回原单位文本
        - 若无单位则直接转 int
        - 失败时清空
        """
        try:
            var_match = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]*)", var.get().replace(" ", ""))

            val = var_match.group(1)
            unit = var_match.group(2)

            if not unit:
                var.set(f"{int(float(val))}")
                return

            unit_val = CvtTools.convert_general_unit(unit=unit)  # 例如 "k"->1e3, "M"->1e6

            # 乘上单位换算到“基准”量级，再整除回到原量级
            val = int(float(val) * unit_val) / unit_val
            var.set(f"{val} {unit}")
        except:
            var.set("")

    # ----------------------------- IP 段校验（0~255） -----------------------------
    @staticmethod
    def ip_out_focus(var: tk.StringVar, *args):
        """
        IP 段输入规范化：
        - 必须是整数 0~255 之间，否则清空
        """
        try:
            ip_val = int(var.get())
            if ip_val < 0 or ip_val > 255:
                var.set("")
        except (tk.TclError, ValueError):
            var.set("")
