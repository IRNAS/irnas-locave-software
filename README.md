# Irnas LoCave software

LoCave is a communication system designed for communication in caves and mines, that can be used to send short text messages. In addition to text communication, there is additional information availible on base, such as weather data from Ruuvi beacons, topology information and list of nearby BLE devices detected on each node.

## Scope of operation

LoCave solution is designed to operate in cave and mine type scenarios, where we assume a large number of nodes needs to be deployed, in an ideal scenario all of them in a single line, such that one device has exactly two neighbors. All units together form a line of communication between point A and B, and nodes can be added when needed. It may be the case however, that due to RF propagation there may be a multi-node scenario with them in range.

Nodes switch between optical and RF communication automatically, be operating in one of the following modes:
- FIBER_ONLY: both optical links active, RF inactive
- FIBER_CAVE_RF, FIBER_EXIT_RF: one optical link active, RF active (send data from RF to optical and vice-versa)
- RF_ONLY no optical links active, RF active (send/receive via RF only)

Python implementation of Locave base software. It contains everything we need to setup a new base
unit on Raspberry Pi:

- simple web server for browser based user interface
- Telegram bot for Telegram integration
- implementation of LoCave serial communication protocol, for communication with first node in
  network
