"""Script for discovery and batch updating firmware of LoCave devices.

Typical usage example:
    python update_all.py --firmware path/to/firmware --password "password"
"""

import argparse
import random
from concurrent.futures import ThreadPoolExecutor

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

from espota import serve

devices = []
failed_list = []

global prefix
prefix = "locave"


def update_device(device, password, firmware):
    """Function to update a single device."""
    name, ip, port = device
    print(f"Updating {name} at {ip}:{port}...")
    try:
        ret = serve(
            ip, "0.0.0.0", port, random.randint(10000, 60000), password, firmware
        )
        if ret == 0:
            print(f"\n\nUpdate for {name} completed.\n")
        else:
            print(f"\n\nUpdate of {name} failed with value {ret}\n")
            failed_list.append(name)
    except Exception as e:
        print(f"\n\nFailed to update {name}: {e}\n")


class MyListener(ServiceListener):
    """Listener for node discovery on local network."""

    def add_service(self, zc, type_, name):
        """Add service to listener."""
        info = zc.get_service_info(type_, name)
        if info:
            if name.startswith(prefix):
                devices.append(
                    (name.split(".")[0], info.parsed_addresses()[0], info.port)
                )
                print("found: ", devices[-1][0])
            else:
                print("found nonmatching hostname -", name)
            print("devices count: ", len(devices))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LoCave OTA firmware updater")
    parser.add_argument(
        "--host", default="locave", help="Hostname prefix of ESP32 devices"
    )
    parser.add_argument("--firmware", required=True, help="Path to the firmware binary")
    parser.add_argument("--password", help="OTA password for authentication")

    args = parser.parse_args()

    prefix = args.host

    zeroconf = Zeroconf()
    listener = MyListener()

    type_ = "_arduino._tcp.local."  # mDNS service type for ArduinoOTA
    print(f"Browsing for services of type {type_}...")
    browser = ServiceBrowser(zeroconf, type_, listener)

    try:
        input("Press Enter to stop scanning and continue...\n")
    finally:
        zeroconf.close()

    print(devices)
    print("Do you want to update the following devices?[y/N]")
    x = input()
    if x.lower() != "y":
        exit(0)

    # Adjust max_workers as needed
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(update_device, device, args.password, args.firmware)
            for device in devices
        ]

    if len(failed_list) != 0:
        print("Some updates failed:")
        for e in failed_list:
            print(e)
    else:
        print("All updates completed.")
