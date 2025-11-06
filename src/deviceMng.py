from __future__ import annotations
from equips import InstrumentBase
from channel import ChannelBase, AWG_Channel, OSC_Channel
from typing import List, Union
import tkinter as tk
from mapping import Mapping
import equips

class DeviceManager:

    class device_info:
        """功能：单台设备的信息与通道管理（名称/地址/通道集合/联动）"""
    
        def __init__(self, device_index: int, freq_unit: tk.StringVar):
            """关键属性: 设备序号、UI 频率单位、通道数量与上限"""
            self.device_index: int = device_index
            self.freq_unit = freq_unit
            self.var_chan_num = tk.IntVar(value=1)
            self.max_chan_num = tk.IntVar(value=1)

            # 配置：底层仪器实例、VISA 地址、设备类型/名称（
            self.instrument: InstrumentBase = None
            self.visa_address: str = ""
            self.var_device_type = tk.StringVar(value="")
            self.var_device_name = tk.StringVar(value="")
            self.var_device_name.trace_add("write", self.track_device_name)  # 名称变更→重建实例并更新通道

            # 通道集合：按通道号索引
            self.channel_dict: dict[int, ChannelBase] = {}

            # VISA 地址相关：自动/手动（LAN）两种模式，任一变化即尝试拼装/更新地址
            self.var_switch_auto_lan = tk.StringVar(value="")
            self.var_switch_auto_lan.trace_add("write", self.trace_visa_address)
            self.var_auto_visa_address = tk.StringVar(value="")
            self.var_auto_visa_address.trace_add("write", self.trace_visa_address)

            # LAN IP 四段输入
            lan_visa_address_1 = tk.StringVar(value="")
            lan_visa_address_1.trace_add("write", lambda *args: self.trace_visa_address())
            lan_visa_address_2 = tk.StringVar(value="")
            lan_visa_address_2.trace_add("write", lambda *args: self.trace_visa_address())
            lan_visa_address_3 = tk.StringVar(value="")
            lan_visa_address_3.trace_add("write", lambda *args: self.trace_visa_address())
            lan_visa_address_4 = tk.StringVar(value="")
            lan_visa_address_4.trace_add("write", lambda *args: self.trace_visa_address())
            self.var_lan_ip_list = [lan_visa_address_1, lan_visa_address_2,  lan_visa_address_3, lan_visa_address_4]

        def track_device_name(self, *args):
            """设备名称变更回调：重建底层实例并同步到所有通道"""
            from ui import UI
            inst = equips.inst_mapping[self.var_device_name.get()]
            self.max_chan_num.set(inst.chan_num)

            self.instrument = equips.inst_mapping[self.var_device_name.get()](name=self.var_device_name.get(), visa_address=self.visa_address)
            for channel in self.channel_dict.values():
                channel.VisaAddress = self.visa_address
                channel.set_inst(self.instrument)

        def create_chan(self):
            """功能：按当前设备类型与通道数，补齐缺失的通道对象（已存在的不重复创建）"""
            if self.var_device_type.get() == Mapping.label_for_device_type_awg:
                for channel_tag in range(1, self.var_chan_num.get()+1):
                    if channel_tag not in self.channel_dict:
                        self.channel_dict[channel_tag] = AWG_Channel(chan_index=channel_tag, freq_unit=self.freq_unit)

            elif self.var_device_type.get() == Mapping.label_for_device_type_osc:
                for channel_tag in range(1, self.var_chan_num.get()+1):
                    if channel_tag not in self.channel_dict:
                        self.channel_dict[channel_tag] = OSC_Channel(chan_index=channel_tag, freq_unit=self.freq_unit)
        
        def find_channel(self, chan_index: int = None, chan_tag: int=None) -> Union[AWG_Channel, OSC_Channel]:
            """功能: 按通道索引值 (chan_index) 或键 (chan_tag) 查找通道对象；未找到抛异常。"""
            if chan_index is not None:
                for chan in self.channel_dict.values():
                    if chan.chan_index.get() == chan_index: 
                        return chan
                raise ValueError(f"{self.device_index}未找到{chan_index}号通道")
            
            if chan_tag is not None:
                try:
                    return self.channel_dict[chan_tag]
                except KeyError as e:
                    raise KeyError (f"{self.device_index}未找到{chan_tag}号通道") from e

        def trace_visa_address(self, *args):
            """功能：根据自动/手动模式拼接 VISA 地址并更新仪器与通道绑定"""
            from ui import UI
            var_auto = self.var_auto_visa_address.get().replace(" ","")
            var_lan = (
                self.var_lan_ip_list[0].get().replace(" ", "").rstrip('\n') + "." + 
                self.var_lan_ip_list[1].get().replace(" ", "").rstrip('\n') + "." +
                self.var_lan_ip_list[2].get().replace(" ", "").rstrip('\n') + "." +
                self.var_lan_ip_list[3].get().replace(" ", "").rstrip('\n')
            )

            auto_selected = self.var_switch_auto_lan.get() == Mapping.label_for_auto
            lan_selected = self.var_switch_auto_lan.get() == Mapping.label_for_lan

            # 条件：四段 LAN IP 都非空且选择 LAN；或自动地址非空且选择 AUTO
            lan_visa_address_typed = (self.var_lan_ip_list[0].get().rstrip('\n') and
                                            self.var_lan_ip_list[1].get().rstrip('\n') and
                                            self.var_lan_ip_list[2].get().rstrip('\n') and
                                            self.var_lan_ip_list[3].get().rstrip('\n') and
                                            lan_selected)
            auto_visa_address_typed = var_auto and auto_selected

            # 生成 VISA 地址（LAN 优先用 TCPIP 规范；AUTO 直接使用输入）
            if lan_visa_address_typed or auto_visa_address_typed:
                self.visa_address = f"TCPIP0::{var_lan}::INSTR" if lan_selected else var_auto

            # 变更地址后重建底层实例并同步到所有通道
            self.instrument = equips.inst_mapping[self.var_device_name.get()](name=self.var_device_name.get(), visa_address=self.visa_address)
            for channel in self.channel_dict.values():
                channel.VisaAddress = self.visa_address
                channel.set_inst(self.instrument)
    
    def __init__(self):
        """功能：设备列表管理（多台设备的容器）"""
        self.device_list: List[DeviceManager.device_info] = []

    def create_devices(self, device_num: int, freq_unit: tk.StringVar):
        """功能：根据数量创建/裁剪设备实例；复用频率单位变量"""
        while len(self.device_list) < device_num:
            self.device_list.append(DeviceManager.device_info(device_index=(len(self.device_list) + 1), freq_unit=freq_unit))
        while len(self.device_list) > device_num:
            self.device_list.pop()

    def find_device(self, device_index: int) -> DeviceManager.device_info:
        """功能：按设备序号查找设备对象"""
        for device in self.device_list:
            if device.device_index == device_index:
                return device

    def get_devices(self) -> List[DeviceManager.device_info]:
        """功能：返回所有设备对象列表"""
        return self.device_list
