from typing import List, Tuple
import tkinter as tk
import numpy as np
from cvtTools import CvtTools
from mapping import Mapping
from equips import InstrumentBase, instAWG, instOSC

class ChannelBase(InstrumentBase):
    """通道基类：绑定设备实例，管理通道索引、占用状态，支持复位等基础操作。"""

    def __init__(self, chan_index: int, freq_unit: tk.StringVar, instrument: InstrumentBase = None):
        """初始化通道参数"""
        super().__init__()
        self.instrument: InstrumentBase = instrument
        self.chan_index = tk.IntVar(value=chan_index)
        self.freq_unit = freq_unit
        self.occupied = False
        self.frame_channel = tk.Frame()

    def copy_from(self, other: "ChannelBase"):
        """从另一通道复制占用状态，类型错误则抛异常"""
        if not isinstance(other, ChannelBase):
            raise TypeError("other must be a channel")
        self.occupied = other.occupied
        return self

    def set_inst(self, inst: InstrumentBase):
        """设置通道绑定的仪器实例"""
        self.instrument = inst

    def set_is_occupied(self):
        """标记通道为占用"""
        self.occupied = True

    def set_is_free(self):
        """标记通道为空闲"""
        self.occupied = False

    def rst(self):
        """复位当前绑定的仪器"""
        inst = self.instrument
        inst.rst()
            
class AWG_Channel(ChannelBase):
    """AWG通道类: 管理扫频参数与单位, 封装与AWG仪器的读写接口, 支持trace回调联动UI字段。"""


    def __init__(self, chan_index: int, freq_unit: tk.StringVar, instrument: instAWG = None):
        """初始化通道与UI变量"""
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
        self.freq_unit.trace_add("write", self.change_on_freq_unit)  # 单位变更联动

        self.amp = tk.StringVar(value="")
        self.imp = tk.StringVar(value="")

        # 频率输入相关trace，联动计算center/interval等
        self.set_trace_start_freq()
        self.set_trace_stop_freq()
        self.set_trace_center_freq()
        self.set_trace_interval_freq()

    def set_inst(self, inst: instAWG):
        """设置AWG仪器实例"""
        super().set_inst(inst=inst)

    def set_freq(self, freq: float, ch: int = None) -> int:
        """
        设置AWG输出频率
        - freq: 目标频率(Hz)
        - ch: 通道号, 默认取chan_index
        """
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        if freq:
            inst.set_freq(freq=freq, ch=ch)

    def get_freq(self, ch: int = None) -> float:
        """
        读取AWG当前频率
        - ch: 通道号, 默认取chan_index
        """
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        freq = inst.get_freq(ch=ch)
        return freq

    def get_sweep_freq_points(self, start_freq: str = None, stop_freq: str = None, step_freq: str = None, step_num: str = None, is_log_freq_enabled: str=None) -> List[float]:
        """
        生成扫频点序列（线性或对数）
        - start_freq/stop_freq/step_freq/step_num: 字符串输入 (带单位) 未传入则取UI变量
        - is_log_freq_enabled: 是否对数扫频
        返回: numpy数组, 频率点(Hz)
        """
        # 读取输入或UI值
        start = start_freq if start_freq is not None else self.start_freq.get()
        stop = stop_freq if stop_freq is not None else self.stop_freq.get()
        step = step_freq if step_freq is not None else self.step_freq.get()
        step_num = step_num if step_num is not None else self.step_num.get()
        is_log_freq_enabled = is_log_freq_enabled if is_log_freq_enabled is not None else self.is_log_freq_enabled.get()

        # 文本解析为Hz；保护最小值避免log10出错
        start_freq = max(CvtTools.parse_to_hz(freq=start, default_unit=self.freq_unit.get()), 1e-12)
        stop_freq = max(CvtTools.parse_to_hz(freq=stop, default_unit=self.freq_unit.get()), 1e-12)

        if self.is_log_freq_enabled.get():
            # 对数扫频：step_num 必须为整数
            try:
                num_steps = int(max(1, round(CvtTools.parse_general_val(step_num))))
            except Exception:
                num_steps = 1
            # 注意当start接近0时跳过第一个点
            if start_freq == 1e-12:
                freq_points = np.logspace(np.log10(start_freq), np.log10(stop_freq), num_steps + 1)
                freq_points = freq_points[1:]
            else:
                freq_points = np.logspace(np.log10(start_freq), np.log10(stop_freq), num_steps)
        else:
            # 线性扫频：按步长生成，含端点
            step_freq = CvtTools.parse_to_hz(freq=step, default_unit=self.freq_unit.get())

            start_freq = start_freq if start_freq != 1e-12 else step_freq

            # 起止相等时返回单点
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
        设置输出幅度 (统一转换为Vpp) 
        - amp: 文本输入，如"1 Vpp"/"500 mVpp"
        - ch: 通道号, 默认取chan_index
        """
        inst = self.instrument
        amp_val = float(CvtTools.parse_to_Vpp(amp if amp is not None else self.amp.get()))
        ch = ch if ch is not None else self.chan_index.get()
        if amp_val:
            inst.set_amp(amp=amp_val, ch=ch)

    def get_amp(self, ch: int=None):
        """
        读取输出幅度
        - ch: 通道号, 默认取chan_index
        """
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        amp = inst.get_amp(ch=ch)
        return amp

    def set_imp(self, imp: str=None, ch: int=None):
        """
        设置输出阻抗
        - imp: 文本输入，如"50"或"INF"
        - ch: 通道号, 默认取chan_index
        """
        inst = self.instrument
        imp_val = imp if imp is not None else self.imp.get()
        ch = ch if ch is not None else self.chan_index.get()
        inst.set_imp(imp=imp_val, ch=ch)

    def set_on(self, ch:int=None):
        """
        开启通道输出
        - ch: 通道号, 默认取chan_index
        """
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        inst.set_on(ch=ch)

    def rst(self):
        """复位底层仪器"""
        super().rst()

    def set_trace_start_freq(self):
        """为start_freq添加trace回调"""
        self.trace_start_id = self.start_freq.trace_add("write", self.change_on_start_freq)

    def set_trace_stop_freq(self):
        """为stop_freq添加trace回调"""
        self.trace_stop_id = self.stop_freq.trace_add("write", self.change_on_stop_freq)

    def set_trace_center_freq(self):
        """为center_freq添加trace回调"""
        self.trace_center_id = self.center_freq.trace_add("write", self.change_on_center_freq)

    def set_trace_interval_freq(self):        
        """为interval_freq添加trace回调"""
        self.trace_interval_id = self.interval_freq.trace_add("write", self.change_on_interval_freq)

    def change_on_start_freq(self, *args):
        """当start_freq变化时: 计算center与interval并回填; 避免递归触发先移除trace再恢复。"""
        try:
            start_val_hz = CvtTools.parse_to_hz(self.start_freq.get(), self.freq_unit.get())
            stop_val_hz  = CvtTools.parse_to_hz(self.stop_freq.get(),  self.freq_unit.get())
            factor = CvtTools.convert_general_unit(unit=self.freq_unit.get())
            center   = str(round(((start_val_hz + stop_val_hz) / 2.0) / factor, 2))
            interval = str(round(abs(start_val_hz - stop_val_hz) / factor, 2))
        except (tk.TclError, ValueError, TypeError):
            center = ""
            interval = ""

        # 暂停相关trace，防止循环触发
        try:    
            self.center_freq.trace_remove("write", self.trace_center_id)
            self.interval_freq.trace_remove("write", self.trace_interval_id)
        except tk.TclError:
            pass

        # 回填center与interval
        self.center_freq.set(center)
        self.interval_freq.set(interval)

        # 恢复trace绑定
        self.set_trace_center_freq()
        self.set_trace_interval_freq()

    def change_on_stop_freq(self, *args):
        """当stop_freq变化时: 计算center与interval并回填; 避免递归触发先移除trace再恢复。"""
        try:
            start_val_hz = CvtTools.parse_to_hz(self.start_freq.get(), self.freq_unit.get())
            stop_val_hz  = CvtTools.parse_to_hz(self.stop_freq.get(),  self.freq_unit.get())
            factor = CvtTools.convert_general_unit(unit=self.freq_unit.get())
            center   = str(round(((start_val_hz + stop_val_hz) / 2.0) / factor, 2))
            interval = str(round(abs(start_val_hz - stop_val_hz) / factor, 2))
        except (tk.TclError, ValueError, TypeError):
            center = ""
            interval = ""

        # 暂停相关trace，防止循环触发
        try:
            self.center_freq.trace_remove("write", self.trace_center_id)
            self.interval_freq.trace_remove("write", self.trace_interval_id)
        except tk.TclError:
            pass

        # 回填center与interval
        self.center_freq.set(center)
        self.interval_freq.set(interval)

        # 恢复trace绑定
        self.set_trace_center_freq()
        self.set_trace_interval_freq()

    def change_on_center_freq(self, *args):
        """
        当center_freq变化时: 校正interval与start/stop; 超过边界时进行裁剪与回填。
        """
        try:
            factor = CvtTools.convert_general_unit(unit=self.freq_unit.get())
            center_val_hz = CvtTools.parse_to_hz(self.center_freq.get(), self.freq_unit.get())
            if center_val_hz == 0: raise ValueError
            interval_val_hz = CvtTools.parse_to_hz(self.interval_freq.get(), self.freq_unit.get())

            # interval上限保护
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

        # 暂停相关trace，防止循环触发
        try:
            self.start_freq.trace_remove("write", self.trace_start_id)
            self.stop_freq.trace_remove("write", self.trace_stop_id)
            self.interval_freq.trace_remove("write", self.trace_interval_id)
        except tk.TclError:
            pass

        # 回填start与stop
        self.start_freq.set(value=start)
        self.stop_freq.set(value=stop)

        # 恢复trace绑定
        self.set_trace_start_freq()
        self.set_trace_stop_freq()
        self.set_trace_interval_freq()

    def change_on_interval_freq(self, *args):
        """当interval_freq变化时: 校正center与start/stop; 小于中心的一半时进行上拉保护。"""
        try:
            factor = CvtTools.convert_general_unit(unit=self.freq_unit.get())
            center_val_hz = CvtTools.parse_to_hz(self.center_freq.get(), self.freq_unit.get())
            if center_val_hz == 0: raise ValueError
            interval_val_hz = CvtTools.parse_to_hz(self.interval_freq.get(), self.freq_unit.get())

            # center下限保护
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

        # 暂停相关trace，防止循环触发
        try:
            self.start_freq.trace_remove("write", self.trace_start_id)
            self.stop_freq.trace_remove("write", self.trace_stop_id)
            self.center_freq.trace_remove("write", self.trace_center_id)
        except tk.TclError:
            pass

        # 回填start与stop
        self.start_freq.set(value=start)
        self.stop_freq.set(value=stop)

        # 恢复trace绑定
        self.set_trace_start_freq()
        self.set_trace_stop_freq()
        self.set_trace_center_freq()

    def change_on_freq_unit(self, *args):
        """
        当频率单位变更时: 将start/stop/step/center/interval按新单位重算并回填。
        - 内部先暂停trace避免循环更新, 完成后恢复。
        """
        def suspend_traces():
            """移除所有相关trace, 防止递归触发"""
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
            """恢复trace绑定"""
            self.set_trace_start_freq()
            self.set_trace_stop_freq()
            self.set_trace_center_freq()
            self.set_trace_interval_freq()
            
        old_unit = getattr(self, "last_freq_unit", self.freq_unit.get())
        new_unit = self.freq_unit.get()

        try:
            # 先按旧单位解析为Hz
            start_hz = CvtTools.parse_to_hz(self.start_freq.get(),   old_unit)
            stop_hz  = CvtTools.parse_to_hz(self.stop_freq.get(),    old_unit)
            step_hz  = CvtTools.parse_to_hz(self.step_freq.get(),    old_unit)
            center_hz   = (start_hz + stop_hz) / 2.0
            interval_hz = abs(start_hz - stop_hz)

            # 再按新单位换算回显示值
            factor = CvtTools.convert_general_unit(new_unit) 
            start   = str(round(start_hz   / factor, 2))
            stop    = str(round(stop_hz    / factor, 2))
            step    = str(round(step_hz    / factor, 2))
            center  = str(round(center_hz  / factor, 2))
            interval= str(round(interval_hz/ factor, 2))
        except Exception:
            return  

        # 暂停相关trace，防止循环触发
        suspend_traces()
        # 回填新值
        try:
            self.start_freq.set(start)
            self.stop_freq.set(stop)
            self.step_freq.set(step)
            self.center_freq.set(center)
            self.interval_freq.set(interval)
        except:
            pass
        # 恢复trace绑定
        finally:
            resume_traces()

        self.last_freq_unit = new_unit
     
class OSC_Channel(ChannelBase):
    """示波器通道类：管理垂直/水平设置、触发、读波形与阻抗/耦合, 含必要的UI联动(trace)。"""

    def __init__(self, chan_index: int, freq_unit: tk.StringVar, instrument: instOSC = None):
        """
        初始化通道与UI变量
        - chan_index: 通道索引
        - freq_unit: 频率单位变量（占位一致性）
        - instrument: OSC仪器实例
        """
        super().__init__(chan_index=chan_index, freq_unit=freq_unit, instrument=instrument)
        self.instrument: instOSC  
        self.frame_channel = tk.Frame()
        self.range = tk.StringVar(value="")     # 垂直满幅显示量程(peak-to-peak)
        self.yoffset = tk.StringVar(value="")   # 中心电压
        self.points = tk.StringVar(value="")    # 采样点数
        self.imp = tk.StringVar(value="")       # 输入阻抗（如50Ω/高阻）
        self.coupling = tk.StringVar(value="")  # 耦合方式（AC/DC）
        self.xscale = None                     
        self.xoffset = None                    

        # 阻抗/耦合联动保护：50Ω不允许AC，冲突时自动调整
        self.imp.trace_add("write", self.trace_on_imp)
        self.coupling.trace_add("write", self.trace_on_coup)

    def trace_on_imp(self, *args):
        """当输入阻抗改为50Ω且耦合为AC时，自动切回DC耦合"""
        if self.imp.get() == Mapping.mapping_imp_r50 and self.coupling.get() == Mapping.mapping_coup_ac:
            self.coupling.set(Mapping.mapping_coup_dc)

    def trace_on_coup(self, *args):
        """当耦合改为AC且阻抗为50Ω时，自动切回高阻"""
        if self.imp.get() == Mapping.mapping_imp_r50 and self.coupling.get() == Mapping.mapping_coup_ac:
            self.imp.set(Mapping.mapping_imp_high_z)

    def copy_from(self, other: "OSC_Channel"):
        """从另一示波器通道复制基础状态；类型错误则抛异常"""
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
        设置水平时基与偏移
        - xscale: 全屏时间, 内部换算为每格时间 (除以10)
        - xoffset: 水平偏置
        """
        inst = self.instrument
        xscale = xscale/10.0 if xscale is not None else self.xscale/10.0
        xoffset = xoffset if xoffset is not None else self.xoffset
        inst.set_x(xscale=xscale, xoffset=xoffset)

    def set_y(self, yscale: str=None, yoffset: str=None, ch: int=None):
        """
        设置垂直刻度与偏置
        - yscale: UI量程 (满幅Vpp), 内部换算为每格电压(V/div) = Vpp/8
        - yoffset: 垂直偏置
        - ch: 通道号
        """
        inst = self.instrument
        yscale = CvtTools.parse_to_V(yscale if yscale is not None else self.range.get()) / 8.0
        yoffset = CvtTools.parse_to_V(yoffset if yoffset is not None else self.yoffset.get())
        ch = ch if ch is not None else self.chan_index.get()
        inst.set_y(ch=ch, yscale=yscale, yoffset=yoffset)

    def get_y(self, ch: int=None):
        """
        读取垂直设置
        返回：(满幅Vpp, 偏置)
        """
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        yscale, yoffs = inst.get_y(ch=ch)
        return yscale * 8.0, yoffs  # 将V/div还原为满幅Vpp

    def get_sample_rate(self, ch: int=None) -> int:
        """读取采样率"""
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        sample_rate = inst.get_sample_rate()
        return sample_rate

    def quick_measure(self):
        """快速采集一次"""
        inst = self.instrument
        inst.quick_measure() 
    
    def trig_measure(self):
        """触发采集一次"""
        inst = self.instrument
        inst.trig_measure()

    def read_raw_waveform(self, points: str=None, ch: int=None) -> Tuple[np.array]:
        """
        读取原始波形
        - points: 采样点数字符串, 内部统一为int
        - ch: 通道号
        返回：(times, volts)或底层定义的原始数据结构
        """
        inst =  self.instrument
        raw_points = CvtTools.parse_general_val(points if points is not None else self.points.get())
        # 将采样点安全转换为整数；0 或无效则传 None 让底层使用设备默认
        try:
            points_val = int(round(raw_points)) if raw_points and raw_points > 0 else None
        except Exception:
            points_val = None
        ch = ch if ch is not None else self.chan_index.get()
        raw_data = inst.read_raw_waveform(ch=ch, points=points_val)
        return raw_data

    def set_trig_rise(self, ch: int=None, level: float=None):
        """
        设置上升沿触发
        - ch: 通道号
        - level: 触发电平, 默认0.0
        """
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        level = level if level is not None else 0.0
        inst.set_trig_rise(ch=ch, level=level)

    def set_free_run(self):
        """设置自由运行模式"""
        inst =  self.instrument
        inst.set_free_run()
    
    def set_on(self, ch: int=None):
        """打开通道显示或输入"""
        inst = self.instrument
        ch = ch if ch is not None else self.chan_index.get()
        inst.set_on(ch=ch)

    def set_imp(self, imp: str=None, ch: int=None):
        """
        设置输入阻抗
        - imp: 如"50"或"HiZ"
        - ch: 通道号
        """
        inst = self.instrument
        imp = imp if imp is not None else self.imp.get()
        ch = ch if ch is not None else self.chan_index.get()
        inst.set_imp(imp=imp, ch=ch)

    def set_coup(self, coup: str=None, ch: int=None):
        """
        设置耦合方式
        - coup: "AC"/"DC"等
        - ch: 通道号
        """
        inst = self.instrument
        coup = coup if coup is not None else self.coupling.get()
        ch = ch if ch is not None else self.chan_index.get()
        inst.set_coup(coup=coup, ch=ch)

    def rst(self):
        """复位底层仪器"""
        super().rst()

