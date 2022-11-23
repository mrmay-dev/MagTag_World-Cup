
#

# built-in modules
import gc
import time as atime
import alarm
import random
import rtc
import json
import supervisor
import board
import busio
from digitalio import DigitalInOut, Direction, Pull, DriveMode
from analogio import AnalogIn
import displayio
import terminalio
import ssl
import wifi
import socketpool
import ipaddress

# External Modules
# Time
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import bitmap_label as label
from adafruit_display_shapes.rect import Rect
# import adafruit_ntp
from adafruit_datetime import datetime, date, time, timedelta
# Network
import adafruit_requests as aio_requests
from adafruit_io.adafruit_io import IO_HTTP
# import adafruit_minimqtt.adafruit_minimqtt as MQTT
# from adafruit_io.adafruit_io import IO_MQTT
from secrets import secrets
# Hardware
import adafruit_lis3dh
import neopixel

# Change these to meet your location
TIME_ZONE_NAME = 'PST'
TIME_ZONE_OFFSET = -8

# For future, change to timezone of cup host
HOST_TIME = 3


# I2C Devices
i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)

# Turn things off
NP_POWER = DigitalInOut(board.NEOPIXEL_POWER)
NP_POWER.switch_to_output(True)  # OFF = True, ON = False

# set up hardware
lis = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x19)
voltage_pin = AnalogIn(board.VOLTAGE_MONITOR)
pixels = neopixel.NeoPixel(board.NEOPIXEL, 4, brightness=1, auto_write=True)


# Useful functions
def np_signal(color=0x220000, flashes=3, interval=.15, time_off=1):
    NP_POWER.switch_to_output(False)
    for i in range(flashes):
        atime.sleep(interval * time_off)
        pixels.fill(color)
        atime.sleep(interval)
        pixels.fill(0)


# Time Functions ------------------

# Adafruit delivers time based on user's IP.
# This function helps move time between time zones.
def local_time(hours = 0, minutes = 0, seconds = 0):    
    dt_current_time = datetime.fromtimestamp(atime.time()) # update the datetime object
    show_date = dt_current_time + timedelta(hours = hours, minutes = minutes, seconds = seconds) 
    times = {
        'ts' : atime.time(),
        'iso' : show_date.isoformat(),
        'ctime' : show_date.ctime(),
        'date' : show_date.date(),
        'time' : show_date.time()
        }    
    return(times)

# POSIX / Unix Timestamp, always GMT.
# Uses TIME_ZONE_OFFSET to get GMT/UTC/Zulu time.
def ts():  
    now_time = local_time(hours = (-1 * TIME_ZONE_OFFSET), minutes = 0, seconds = 0)
    return(now_time['ts'])


# Network Functions ------------------
# See sample secrets.py file for details.
ssid = [secrets["ssid"], secrets["ssid_2"], secrets["ssid_3"]]
password = [secrets["password"], secrets["password_2"], secrets["password_3"]]

def wifi_connect(choice=0):
    # Connect to local network
    print("\nAvailable WiFi networks:")

    for network in wifi.radio.start_scanning_networks():
        print("  {:>18}   RSSI: {:<4}  Channel: {:<2}".format(
            str(network.ssid, "utf-8"), network.rssi, network.channel ))
    wifi.radio.stop_scanning_networks()

    while not wifi.radio.ipv4_address:
        try:
            print("\nConnecting to {}".format(ssid[choice]))
            wifi.radio.connect(secrets["ssid"], secrets["password"])
        except ConnectionError as e:
            print("Connection Error: {}".format(e))
            print("Retrying in 10 seconds")
    print("Connected!\n")
    np_signal(color=0x000100, flashes=3, interval=0.15, time_off=0.3)
    atime.sleep(10)
    gc.collect()


# MQTT Functions -----------

# Define callback functions which will be called when certain events happen.
# pylint: disable=unused-argument
def connected(client):
    print("Connected to AIO, listening for feed updates ...")
    # https://io.adafruit.com/api/docs/mqtt.html#time-seconds
    # io.subscribe_to_time("hours")
    io.subscribe_to_time("seconds")
    # io.subscribe_to_time("iso")

def subscribe(client, userdata, topic, granted_qos):
    # This method is called when the client subscribes to a new feed.
    print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))


def unsubscribe(client, userdata, topic, pid):
    # This method is called when the client unsubscribes from a feed.
    print("Unsubscribed from {0} with PID {1}".format(topic, pid))


# pylint: disable=unused-argument
def disconnected(client):
    # Disconnected function will be called when the client disconnects.
    print("Disconnected from Adafruit IO!")


# pylint: disable=unused-argument
def message(client, feed_id, payload):
    # Message function will be called when a subscribed feed has a new value.
    # The feed_id parameter identifies the feed, and the payload parameter has
    # the new value.
    ts = payload
    print("Feed {0} received new value: {1}".format(feed_id, payload))
    return(ts)

# ------------------------
def update_data():
    # Turn things off
    NP_POWER.switch_to_output(False)

    # Light Sensor
    # light = light_sensor.value
    # light = (((light_sensor.value - 0) / 65535.0) * 3.3 * 2) * 10000

    # Battery Voltage
    # battery = voltage_pin.value
    battery = ((voltage_pin.value / 65535.0) * 3.3 * 2) * 1

    x, y, z = lis.acceleration
    
    # NP_POWER.switch_to_output(True)
    return(x, y, z, battery)


# World Cup functions
# Function to build schedule text for MagTag display
def wc_schedule(matches_today):
    # JSON times are Zulu/UTC/GMT
    # Device is set to local time
    
    title_date = ((local_time())['ctime'])[0:10]
    
    the_schedule = ''
    page_title = ('{}\n'.format(title_date))
    for i in matches_today:
        game_time = (i['datetime'])
        game_time = (game_time[0:19])
        game_time = (datetime.fromisoformat(game_time) +  # Game time as local time.
               timedelta(hours = TIME_ZONE_OFFSET))
        
        the_schedule = the_schedule + ('    {:<5}   {:>3} ({}) v. {:<3} ({})\n'.format(
            str(game_time.time())[0:5],
            i['home_team']['country'],
            i['home_team']['goals'],
            i['away_team']['country'],
            i['away_team']['goals'],
            ))
    
    return(the_schedule, page_title)

def wc_test_data():
    # This is simply the output from the API for testing.
    # https://worldcupjson.net/matches/today
    
    try:
        with open("wc_test_data.json", "r") as fp:
            x = fp.read()
            # parse x:
            matches_today = json.loads(x)
            
    except OSError as e:
        raise Exception("Could not read text file.")
    
    the_schedule, page_title = wc_schedule(matches_today)

    return(the_schedule, page_title)

# This function GETs today's schedule (in GMT times).
# print('yesterday: {}'.format((local_time(hours=-24))['date']))
# print('today: {}'.format((local_time(hours=0))['date']))
# print('tomorrow: {}'.format((local_time(hours=24))['date']))
# ?start_date=2022-11-22&end_date=2022-11-22
def world_cup():
    TODAY = ((local_time(hours=0))['date'])
    WORLD_CUP = 'https://worldcupjson.net/'
    API_PARAMETERS = 'start_date={0}&end_date={0}'.format(TODAY)
    
    # Fetching World Cup Today
    json_header = {"Accept": "application/json"}
    
    print("{}matches?{}".format(WORLD_CUP, API_PARAMETERS))
    matches_today = requests.get("{}matches?{}".format(WORLD_CUP, API_PARAMETERS), headers = json_header)
    # matches_today.close()
    matches_today = matches_today.json()

    the_schedule = wc_schedule(matches_today)
    return(the_schedule)

# This function GETs information on the current match.
def match_now(current_match):
    try:
        home_team = current_match[0]['home_team_country']
        away_team = current_match[0]['away_team_country']
        match_time = current_match[0]['time']
        
        home_team_goals = current_match[0]['home_team']['goals']
        away_team_goals = current_match[0]['away_team']['goals']
        
        match_title = ('({}){} vs. {}({}) - [{}]'.format(
            home_team_goals, home_team, away_team, away_team_goals, match_time))
        match_score = ('{:>11}:   {!s:^6} {!s:^6}\n{:>11}:   {!s:^6} {!s:^6}\n{:>11}:   {!s:^6} {!s:^6}\n{:>11}:   {!s:^6} {!s:^6}\n{:>11}:   {!s:^6} {!s:^6}'.format(
                        'On Target',
                        current_match[0]['home_team_statistics']['on_target'],
                        current_match[0]['away_team_statistics']['on_target'],
                        'Off Target',
                        current_match[0]['home_team_statistics']['off_target'],                      
                        current_match[0]['away_team_statistics']['off_target'],
                        'Possession',
                        current_match[0]['home_team_statistics']['ball_possession'],
                        current_match[0]['away_team_statistics']['ball_possession'],
                        'Accuracy',
                        current_match[0]['home_team_statistics']['pass_accuracy'],
                        current_match[0]['away_team_statistics']['pass_accuracy'],
                        'Fouls',
                        current_match[0]['home_team_statistics']['fouls_committed'],
                        current_match[0]['away_team_statistics']['fouls_committed']
                       ))
    
    except:
        match_title = '\n{:^36}'.format('No Game')
        match_score = ' '
    return(match_title, match_score)

# This function uses an API dump from a running game for test.
def wc_now_test():
    try:
        with open("wc_current_match.json", "r") as fp:
            x = fp.read()
            # parse x:
            current_match = json.loads(x)
            
    except OSError as e:
        raise Exception("Could not read text file.")
    
    match_title, match_score = match_now(current_match)

    return(match_title, match_score)

# Function GETs current game stats.
def wc_now():    
    # pool = socketpool.SocketPool(wifi.radio)
    # requests = aio_requests.Session(pool, ssl.create_default_context())
    
    WORLD_CUP = 'https://worldcupjson.net/'
    
    # Fetching World Cup Today
    json_header = {"Accept": "application/json"}
    
    print("{}matches/current\n".format(WORLD_CUP))
    current_match = requests.get("{}matches/current".format(WORLD_CUP), headers = json_header)
    # matches_today.close()
    
    current_match = current_match.json()

    match_title, match_score = match_now(current_match)
    
    return(match_title, match_score)


# ------ Main Program ------

def main_program():
    return

# Comment out for test mode and use cached JSON files.
# choice= option to choose what SSID to connect with.
wifi_connect(choice=0)

x, y, z, battery = update_data()

# Rotation determines what screen to display and refresh_time
#TODO a vertical orientation to display favorite team details.
if y < 0:
    game_on = True  # Display live score
    DISPLAY_ROTATION = 90
    #TODO refresh every 2 minutes for current match.
    refresh_time = 120  # seconds
else:
    game_on = False  # Display schedule
    DISPLAY_ROTATION = 270
    #TODO refresh just before the next match
    refresh_time = 10 * 60  # seconds


print('Game is on: {}'.format(game_on))
print('Refresh: {}s\n'.format(refresh_time))

print("My gateway is {}".format(wifi.radio.ipv4_gateway))
print("My IP address is {}\n".format(wifi.radio.ipv4_address))

print('Battery: {}'.format(battery))
print('x:{} y:{} z:{}\n'.format(x, y, z))


# WiFi Setup ------------------
# Use test data 
if wifi.radio.ipv4_gateway is None:
    
    now_time = (local_time())['iso']
    next_update_ts = ts() + refresh_time
    next_update = str((datetime.fromtimestamp(next_update_ts)).time())[0:5]
    print('The current datetime is: {}, ({})'.format(now_time, ts()))
    print('The next update will be: {}, ({})\n'.format(next_update, next_update_ts))
           
    import os
    if not game_on:
        the_schedule, page_title = wc_test_data()
    if game_on:    
        match_title, match_score = wc_now_test() 
    print('Using test data.\n')

else:  # use live data
    
    pool = socketpool.SocketPool(wifi.radio)
    requests = aio_requests.Session(pool, ssl.create_default_context())
    
    #For using NTP instead of AdafruitIO
    '''
    # set RTC clock
    ntp = adafruit_ntp.NTP(pool, tz_offset=TIME_ZONE_OFFSET)
    rtc.RTC().datetime = ntp.datetime
    r = rtc.RTC()
    now_time = local_time()
    print('The current datetime is: {}, ({})'.format(now_time['iso'], ts()))
    '''
    
    # For storing data on AdafruitIO
    '''
    # Initialize a new MQTT Client object
    mqtt_client = MQTT.MQTT(
        broker = "io.adafruit.com",
        port = 1883,
        username = secrets["aio_username"],
        password = secrets["aio_key"],
        socket_pool = pool,
        ssl_context = ssl.create_default_context(),
    )
    
    # Initialize an Adafruit IO MQTT Client
    io = IO_MQTT(mqtt_client)

    # Connect the callback methods defined above to Adafruit IO
    io.on_connect = connected
    io.on_disconnect = disconnected
    io.on_subscribe = subscribe
    io.on_unsubscribe = unsubscribe
    io.on_message = message

    # Connect to Adafruit IO
    io.connect()
    print('\nConnected to Adafruit IO via MQTT')
    
    the_schedule = world_cup()
    io.loop()
    ts = message()
    ts = datetime.fromtimestamp(ts)
    
    rtc.RTC().datetime = ts.datetime
    r = rtc.RTC()
    now_time = local_time()
    print('The current datetime is: {}, ({})'.format(now_time['iso'], ts()))
    '''
    
    # AIO Time
    # Initialize an Adafruit IO HTTP API object
    io = IO_HTTP(secrets["aio_username"], secrets["aio_key"], requests)
    # io = IO_HTTP(aio_username, aio_key, requests)
    
    print("Fetching time from Adafruit IO...\n")
    
    rtc.RTC().datetime = io.receive_time()
    now_time = (local_time())['iso']
    next_update_ts = ts() + refresh_time
    next_update = str((datetime.fromtimestamp(next_update_ts)).time())[0:5]
    print('The current datetime is: {}, ({})'.format(now_time, ts()))
    print('The next update will be: {}, ({})\n'.format(next_update, next_update_ts))

    if not game_on:    
        the_schedule, page_title = world_cup()
    if game_on:    
        match_title, match_score = wc_now() 

page_footer = 'Bat: {:0.1f}v - Next: {}'.format(
    battery, next_update)

if not game_on:
    print(page_title)
    print(the_schedule)
if game_on:
    print('\n-- Match Now --\n')
    print(match_title)
    print(match_score)
print(page_footer)


def disiplay_setup():
    return

# Display Setup
# Creating Text Boxes
# Each terminalio letter is 6px wide on the MagTag
# 2px margin allows 49 characters per line.
# Arial-Bold-12.pcf fits 33 "x" characters across.

def try_refresh():
    """Attempt to refresh the display. Catch 'refresh too soon' error
       and retry after waiting 10 seconds.
    """
    try:
        board.DISPLAY.refresh()
    except RuntimeError as too_soon_error:
        # catch refresh too soon
        print(too_soon_error)
        print("waiting before retry refresh()")
        time.sleep(10)
        board.DISPLAY.refresh()


# Get the display object
display = board.DISPLAY
display.rotation = DISPLAY_ROTATION
main_group = displayio.Group()
display.show(main_group)

# Font definition. You can choose any two fonts available in your system
SPARTAN_BOLD = bitmap_font.load_font("fonts/LeagueSpartan-Bold-16.bdf")
TERMINAL_FONT = terminalio.FONT

rect = Rect(0, 0, 296, 128, fill=0xFFFFFF, outline=0xFFFFFF)
main_group.append(rect)

# Create labels
# https://docs.circuitpython.org/projects/display_text/en/latest/api.html#adafruit-display-text
# https://github.com/adafruit/Adafruit_CircuitPython_Bitmap_Font/tree/main/examples/fonts
if not game_on:
    page_title = label.Label(
        SPARTAN_BOLD,
        text=page_title,
        bg_color=0xFFFFFF,
        color=0x000000,
        x=10,
        y=23,
        base_alignment=True,
    )

    page_body = label.Label(
        TERMINAL_FONT,
        scale = 1,
        text=the_schedule,
        bg_color=0xFFFFFF,
        color=0x000000,
        x=20,
        y=47,
        base_alignment=True,
    )

if game_on:
    page_title = label.Label(
        SPARTAN_BOLD,
        text=match_title,
        bg_color=0xFFFFFF,
        color=0x000000,
        x=22,
        y=23,
        base_alignment=True,
    )

    page_body = label.Label(
        TERMINAL_FONT,
        scale = 1,
        text=match_score,
        bg_color=0xFFFFFF,
        color=0x000000,
        x=60,
        y=45,
        base_alignment=True,
    )

page_footer = label.Label(
    TERMINAL_FONT,
    text=page_footer,
    bg_color=0xFFFFFF,
    color=0x000000,
    x=80,
    y=126,
    base_alignment=True,
)

main_group.append(page_title)
main_group.append(page_body)
main_group.append(page_footer)

# show the group
display.show(main_group)

# refresh display
try_refresh()


# Signal that screen has been updated
colors = [0x110900, 0x001111, 0x110011]
flashes = 1
interval = 0.5
time_off = 0.1
for i in range(len(colors)):
    np_signal(color=colors[i], flashes=flashes,
              interval=interval, time_off=time_off)

print('\nscreen refreshed\ngoing to sleep for {:0.0f} minutes.'.format(refresh_time/60))

# Create a an alarm that will trigger 20 seconds from now.
time_alarm = alarm.time.TimeAlarm(monotonic_time=atime.monotonic() + refresh_time)
# Exit the program, and then deep sleep until the alarm wakes us.
alarm.exit_and_deep_sleep_until_alarms(time_alarm)
# Does not return, so we never get here.




