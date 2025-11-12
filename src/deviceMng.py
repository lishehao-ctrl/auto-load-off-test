from __future__ import annotations
from equips import InstrumentBase
from channel import ChannelBase, AWG_Channel, OSC_Channel
from typing import List, Union
import tkinter as tk
from mapping import Mapping
import equips

class DeviceManager:

    class device_info:
        """Single-device metadata: name/address, channel collection, and linkage helpers."""
    
        def __init__(self, device_index: int, freq_unit: tk.StringVar):
            """Key attributes: device index, UI frequency unit, channel count, and max channels."""
            self.device_index: int = device_index
            self.freq_unit = freq_unit
            self.var_chan_num = tk.IntVar(value=1)
            self.max_chan_num = tk.IntVar(value=1)

            # Instrument configuration: low-level instance, VISA address, device type/name.
            self.instrument: InstrumentBase = None
            self.visa_address: str = ""
            self.var_device_type = tk.StringVar(value="")
            self.var_device_name = tk.StringVar(value="")
            self.var_device_name.trace_add("write", self.track_device_name)  # Rebuild instrument when the model name changes.

            # Channel collection, keyed by channel number.
            self.channel_dict: dict[int, ChannelBase] = {}

            # VISA address inputs: auto/manual (LAN) modes trigger address rebuilds.
            self.var_switch_auto_lan = tk.StringVar(value="")
            self.var_switch_auto_lan.trace_add("write", self.trace_visa_address)
            self.var_auto_visa_address = tk.StringVar(value="")
            self.var_auto_visa_address.trace_add("write", self.trace_visa_address)

            # LAN IPv4 octets.
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
            """When the device model changes, rebuild the instrument and update all channels."""
            from ui import UI
            inst = equips.inst_mapping[self.var_device_name.get()]
            self.max_chan_num.set(inst.chan_num)

            self.instrument = equips.inst_mapping[self.var_device_name.get()](name=self.var_device_name.get(), visa_address=self.visa_address)
            for channel in self.channel_dict.values():
                channel.VisaAddress = self.visa_address
                channel.set_inst(self.instrument)

        def create_chan(self):
            """Create any missing channels for the current device type without duplicating entries."""
            if self.var_device_type.get() == Mapping.label_for_device_type_awg:
                for channel_tag in range(1, self.var_chan_num.get()+1):
                    if channel_tag not in self.channel_dict:
                        self.channel_dict[channel_tag] = AWG_Channel(chan_index=channel_tag, freq_unit=self.freq_unit)

            elif self.var_device_type.get() == Mapping.label_for_device_type_osc:
                for channel_tag in range(1, self.var_chan_num.get()+1):
                    if channel_tag not in self.channel_dict:
                        self.channel_dict[channel_tag] = OSC_Channel(chan_index=channel_tag, freq_unit=self.freq_unit)
        
        def find_channel(self, chan_index: int = None, chan_tag: int=None) -> Union[AWG_Channel, OSC_Channel]:
            """Look up a channel by chan_index or dictionary key; raise if not found."""
            if chan_index is not None:
                for chan in self.channel_dict.values():
                    if chan.chan_index.get() == chan_index: 
                        return chan
                raise ValueError(f"Device {self.device_index} does not have channel {chan_index}")
            
            if chan_tag is not None:
                try:
                    return self.channel_dict[chan_tag]
                except KeyError as e:
                    raise KeyError (f"Device {self.device_index} does not have channel tag {chan_tag}") from e

        def trace_visa_address(self, *args):
            """Rebuild the VISA address per auto/LAN mode and propagate it to the instrument and channels."""
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

            # Conditions: LAN mode requires all four octets; AUTO mode requires the auto address field.
            lan_visa_address_typed = (self.var_lan_ip_list[0].get().rstrip('\n') and
                                            self.var_lan_ip_list[1].get().rstrip('\n') and
                                            self.var_lan_ip_list[2].get().rstrip('\n') and
                                            self.var_lan_ip_list[3].get().rstrip('\n') and
                                            lan_selected)
            auto_visa_address_typed = var_auto and auto_selected

            # Construct the VISA address (LAN -> TCPIP form; AUTO -> raw input).
            if lan_visa_address_typed or auto_visa_address_typed:
                self.visa_address = f"TCPIP0::{var_lan}::INSTR" if lan_selected else var_auto

            # Rebuild the instrument and update channels whenever the address changes.
            self.instrument = equips.inst_mapping[self.var_device_name.get()](name=self.var_device_name.get(), visa_address=self.visa_address)
            for channel in self.channel_dict.values():
                channel.VisaAddress = self.visa_address
                channel.set_inst(self.instrument)
    
    def __init__(self):
        """Manage a list of devices (container for multiple instruments)."""
        self.device_list: List[DeviceManager.device_info] = []

    def create_devices(self, device_num: int, freq_unit: tk.StringVar):
        """Create or trim device instances to match device_num, reusing the same freq_unit."""
        while len(self.device_list) < device_num:
            self.device_list.append(DeviceManager.device_info(device_index=(len(self.device_list) + 1), freq_unit=freq_unit))
        while len(self.device_list) > device_num:
            self.device_list.pop()

    def find_device(self, device_index: int) -> DeviceManager.device_info:
        """Find a device object by its index."""
        for device in self.device_list:
            if device.device_index == device_index:
                return device

    def get_devices(self) -> List[DeviceManager.device_info]:
        """Return the list of device objects."""
        return self.device_list
