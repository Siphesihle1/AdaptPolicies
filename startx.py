#!/usr/bin/env python

import subprocess
import sys
import pynvml
import platform
import tempfile
import os
import shlex


def nvidia_devices():
    devices = []
    pynvml.nvmlInit()
    device_count = pynvml.nvmlDeviceGetCount()

    for i in range(device_count):
        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
        pci_info = pynvml.nvmlDeviceGetPciInfo(handle)
        devices.append(
            pci_info.busId.decode()
            if hasattr(pci_info.busId, "decode")
            else pci_info.busId
        )

    return devices


# Converts NVML busId (domain:bus:device.function) to Xorg PCI BusID (PCI:bus:device:function)
def nvml_busid_to_xorg(busid):
    # Example input: '0000:65:00.0'
    _, bus, dev_func = busid.split(":")
    device, function = dev_func.split(".")
    # Remove leading zeros for bus, device, function
    return f"PCI:{int(bus)}:{int(device)}:{int(function)}"


def generate_xorg_conf(devices):
    xorg_conf = []
    device_section = """
Section "Device"
    Identifier     "Device{device_id}"
    Driver         "nvidia"
    VendorName     "NVIDIA Corporation"
    BusID          "{bus_id}"
EndSection
"""
    server_layout_section = """
Section "ServerLayout"
    Identifier     "Layout0"
    {screen_records}
EndSection
"""
    screen_section = """
Section "Screen"
    Identifier     "Screen{screen_id}"
    Device         "Device{device_id}"
    DefaultDepth    24
    Option         "AllowEmptyInitialConfiguration" "True"
    SubSection     "Display"
        Depth       24
    EndSubSection
EndSection
"""
    screen_records = []
    for i, bus_id in enumerate(devices):
        xorg_conf.append(
            device_section.format(device_id=i, bus_id=nvml_busid_to_xorg(bus_id))
        )
        xorg_conf.append(screen_section.format(device_id=i, screen_id=i))
        screen_records.append(
            'Screen {screen_id} "Screen{screen_id}" 0 0'.format(screen_id=i)
        )

    xorg_conf.append(
        server_layout_section.format(screen_records="\n    ".join(screen_records))
    )

    output = "\n".join(xorg_conf)
    print(output)
    return output


def startx(display):
    if platform.system() != "Linux":
        raise Exception("Can only run startx on linux")

    devices = nvidia_devices()

    if not devices:
        raise Exception("no nvidia cards found")

    try:
        rel_path = "alfred_xorg.conf"
        path = f"/etc/X11/{rel_path}"
        # with open(path, "w") as f:
        #     f.write(generate_xorg_conf(devices))
        command = shlex.split(
            "Xorg -noreset +extension GLX +extension RANDR +extension RENDER -config %s :%s"
            % (rel_path, display)
        )
        subprocess.call(command)
    finally:
        # os.unlink(path)
        pass


if __name__ == "__main__":
    display = 0
    if len(sys.argv) > 1:
        display = int(sys.argv[1])
    print("Starting X on DISPLAY :%s" % display)
    startx(display)
