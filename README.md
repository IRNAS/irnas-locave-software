# Irnas LoCave software

LoCave is a communication system designed for communication in caves and mines, that can be used to
send short text messages. In addition to text communication, there is additional information
available on base, such as weather data from Ruuvi beacons, topology information and list of nearby
BLE devices detected on each node.

This Python implementation of Locave base software contains everything we need to setup a new base
unit on Raspberry Pi:

- simple web server for browser based user interface
- Telegram bot for Telegram integration
- implementation of LoCave serial communication protocol, for communication with first node in
  network

## Scope of operation

LoCave solution is designed to operate in cave and mine type scenarios, where we assume a large
number of nodes needs to be deployed, in an ideal scenario all of them in a single line, such that
one device has exactly two neighbors. All units together form a line of communication between point
A and B, and nodes can be added when needed. It may be the case however, that due to RF propagation
there may be a multi-node scenario with them in range.

Nodes switch between optical and RF communication automatically, be operating in one of the
following modes:

- FIBER_ONLY: both optical links active, RF inactive
- FIBER_CAVE_RF, FIBER_EXIT_RF: one optical link active, RF active (send data from RF to optical and
  vice-versa)
- RF_ONLY no optical links active, RF active (send/receive via RF only)

## Setting up for development

```bash
git clone https://github.com/IRNAS/irnas-locave-software
```

Create python venv and install dependencies:

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

Build web interface:

```bash
npm build --prefix flash-ui
```

Run protocol-serial-bridge (adjust port as needed):

```bash
python protocol-serial-bridge.py --port /dev/tty.usbserial-0001
```

## LoCave user manual

### Getting started

#### 1. Setting up LoCave base

1. Connect LoCave base to power source with USB-C power adapter and wait for device to turn on
2. Connect the ethernet cable for internet access (required for Telegram integration, software
   updates and remote technical support)
3. Turn on the base node by pressing the button **once**.
4. after a brief delay we should see a full screen web interface on touchscreen and node interface
   on base node LED displays
5. Turn on 1 non base node and try sending a message (from base to node and from node to base), to
   verify everything is working as expected

#### 2. Connecting to Telegram

LoCave base software includes a Telegram bot for Telegram group chat integration. To access
information about the bot, click on `Bot Control` button in web interface. It contains all necessary
information for adding the bot to our group chat and some simple controls.

- status (online, offline): tells us if the bot is connected to Telegram
- username, name: name and username used to add LoCave telegram bot to our group
- OTP Code: a one time use code generated on bot startup, used to verify and pair the bot with a
  group chat
- Restart Bot: try to restart the bot
- Update Bot Token: update bot api access token - we can get this token by creating a bot with
  `@BotFather` on Telegram. Usually the bot token will be preconfigured on the device, but you can
  update it here to use your own Telegram bot created with `@BotFather`

##### Step by step instructions

1. add bot to Telegram group
2. the bot should ask you for one time password (OTP Code)
3. **The next message sent** to this group should be the OTP code found in bot control page:
   - If the password is incorrect or bot receives any other message it will immediately leave the
     group, to prevent unwanted access.
   - If the password is correct the bot will inform you that it is successfully paired with the
     group
4. After successful connection to group chat all messages between LoCave system and Telegram group
   will be forwarded (every message from group chat will be forwarded to LoCave and every text
   message from LoCave will be sent to group chat).

#### 3. Deploying nodes and setting up the LoCave network

After successful base setup we can begin to deploy LoCave nodes. When deploying nodes we should make
sure only one node is turned on at the time (see
[why](#1-why-can-only-one-device-be-turned-on-at-the-time-when-using-deploy-mode)).

##### Node user interface

We can turn the node on by pressing the button once. We can turn it off by holding the button until
the progress bar on right screen is full. The lights on device should light up LED screens should
light up. The right screen (cave side) shows the last message we received (only after receiving the
first message). The left screen shows:

- Node ID: the ID of this node
- current communication mode:
  - FIBER_ONLY: both sides of the node are connected with fiber cable
  - FIBER_CAVE_RF: cave side is connected with fiber, exit side is using LoRa
  - FIBER_EXIT_RF: exit side is connected with fiber, cave side is using LoRa
  - RF_ONLY: the device is communicating with LoRa only
- battery voltage
- charging status: `CHG` - charging, `DIS` - discharging
- time since last message (in seconds)
- neighbor info:
  - information about node neighbors, consisting of 3 integers (neighbor node ID, RSSI, time since
    last message in seconds)
  - if one of the neighbors has connection to the base, the neighbor with node ID 0 (0 means base)
    will be shown
  - in ideal situation, the device should show 3 neighbors (except the last device in linear
    network): - base - previous node in network - next node in network

|                            |                 |                         |
| -------------------------- | --------------- | ----------------------: |
| current communication mode |                 |           neighbor info |
| **Node ID**                |                 |                         |
| battery voltage            | charging status | time since last message |

##### How to start using deploy mode?

1. Turn on the node we want to deploy.
2. Shake it hard, to turn on deploy mode. When deploy mode is turned on, the word `DEPLOY` will be
   displayed on top of right LED screen. To keep the device in deploy mode, move it every few
   seconds (by walking or slightly shaking it).
3. Observe the right screen to see deploy connection quality, this is heuristic connection quality
   estimation, based on signal strength and current packet loss, displayed with percentage. We
   should aim to keep this above `50%`.
4. We can also use packet loss and signal strength directly to help us decide where to deploy the
   device: - Packet loss (`LOSS:`) is displayed in bottom left corner of the screen - it tells us
   what percentage of messages is lost. We should aim to keep this below `30%`. - Signal strength
   (`RSSI:`) is displayed in bottom right corner of the screen - it is a negative integer where
   higher number means stronger signal (**-30 is better than -80**). We should aim to have RSSI of
   -100 or higher
5. When the connection quality starts dropping (see 3. and 4.), put the device down and obseerve the
   right screen for a few seconds to make sure the connection is stable. The device will exit deploy
   mode after being stationary for 30 seconds.
6. Return to step 1 with the next device.

#### 4. Using LoCave nodes for communication

There are 2 ways to communicate using LoCave nodes: quick send mode and mobile web chat interface.
The messages always start with a sender node ID `[1-253]`. Sender ID 0 means base and ID 254 means
the message was forwarded from Telegram group.

##### Quick send mode

To enter quick send mode, press the device button once. The right screen (cave facing) will now
display `QUICK SEND` on top of the screen and the current selected option below that. To confirm
selection hold the button until progress bar is full. Selecting `(CANCEL)` (selected by default)
will quit quick send mode and display latest received message on the right screen. Messages sent
with quick send mode always start with `$`. Selecting any option other than `(CANCEL)`will send the
displayed message.

##### Mobile web chat interface

To send more complex messages and view message history, we can use mobile web chat interface that is
hosted on all devices. How to connect and use:

1. Connect to Wi-Fi access point named `LoCave_AP`.
2. Open web browser and visit `http://192.168.1.1/`
3. This should open up a very simple web chat interface. On top, we can see message history (newer
   messages first), and below message history there is a textbox for sending messages. Message
   length is limited to 120 characters. After sending a message, the bottom right corner of message
   will show if the message was successfully delivered to base with a green checkmark. If it shows a
   circular progress indicator, we are still waiting for confirmation. If we do not receive a
   confirmation in reasonable time, we can assume the message did not reach the base. In that case,
   red `X` will be displayed.

### Frequently asked questions

#### 1. Why can only one device be turned on at the time when using deploy mode?

Currently, deploy mode checks connection to **any** LoCave node. If we use deploy mode while
carrying another node that is turned on, the connection quality will always be nearly perfect,
because the second device will answer to deploy mode pings, even tho we might not be able to reach
the last deployed device in the network. If we want deploy mode to work correctly, we should make
sure the only nodes that will answer to deploy pings are the ones that are already connected to
LoCave network.

#### 2. How many mobile phones can connect to LoCave_AP at the same time?

Because of hardware limitations, a single node should support up to 10 simultaneous wifi clients.

#### 3. What happens to message history if base station loses power?

The message history is deleted on restart or in case of power loss.
