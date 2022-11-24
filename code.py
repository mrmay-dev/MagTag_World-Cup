
#TODO use the 'id' url to grab live stats.
# https://worldcupjson.net/matches/11

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
# Hardware
import adafruit_lis3dh
import neopixel


# User Settings -----------

# See sample secrets.py file for details.
from secrets import secrets
# WiFi Credentials
SSID = secrets["ssid"]
PASSWORD = secrets["password"]

# Change these to meet your location
TIME_ZONE_NAME = 'PST'
TIME_ZONE_OFFSET = -8

# Refresh times
GAME_ON_REFRESH = 60  # in seconds
GAME_OFF_REFRESH = (10 * 60)  # in seconds

# For future, change to timezone of cup host
HOST_TIME = 3


# Configurations ------

# I2C Devices
i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)

# Turn things off
NP_POWER = DigitalInOut(board.NEOPIXEL_POWER)
NP_POWER.switch_to_output(True)  # OFF = True, ON = False

# set up hardware
lis = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x19)
voltage_pin = AnalogIn(board.VOLTAGE_MONITOR)
pixels = neopixel.NeoPixel(board.NEOPIXEL, 4, brightness=1, auto_write=True)


# Useful functions ---------
# flashing LEDs routine
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

def wifi_connect(choice=0):
    # Connect to local network
    print("\nAvailable WiFi networks:")

    for network in wifi.radio.start_scanning_networks():
        print("  {:>18}   RSSI: {:<4}  Channel: {:<2}".format(
            str(network.ssid, "utf-8"), network.rssi, network.channel ))
    wifi.radio.stop_scanning_networks()

    while not wifi.radio.ipv4_address:
        try:
            print("\nConnecting to {}".format(SSID))
            wifi.radio.connect(SSID, PASSWORD)
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


# Data Update -------------------
# These lines activate board components.
# Be sure to load modules/drivers first.
def update_data():
    # Turn things off
    NP_POWER.switch_to_output(False)

    # Light Sensor
    # light = light_sensor.value
    # light = (((light_sensor.value - 0) / 65535.0) * 3.3 * 2) * 10000

    # Battery Voltage
    # battery = voltage_pin.value
    battery = ((voltage_pin.value / 65535.0) * 3.3 * 2) * 1
    
    # On-board accelerometer
    x, y, z = lis.acceleration
    
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


# This function parses information on the current match.
def match_stats(current_match):
    try:
        home_team = current_match[0]['home_team_country']
        away_team = current_match[0]['away_team_country']
        match_time = current_match[0]['time']
        
        home_team_goals = current_match[0]['home_team']['goals']
        away_team_goals = current_match[0]['away_team']['goals']
        
        match_title = ('{} vs. {} - [{}]'.format(
            home_team, away_team, match_time))
        match_title = ('{:^37}'.format(match_title))
        match_score = ('{!s:>3} - {!s:<3}'.format(
                        current_match[0]['home_team']['goals'],
                        current_match[0]['away_team']['goals']                
                       ))
        match_score = ('{:^14}'.format(match_score))
    
    except:
        match_title = '{:^39}'.format('No Game')
        match_score = ('{!s:>3} {!s:<3}'.format('-', '-'))
        match_score = ('{:^16}'.format(match_score))
      
    return(match_title, match_score)


# This function GETs today's schedule (in GMT times).
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


# Function GETs current game stats.
def wc_current():    
    # pool = socketpool.SocketPool(wifi.radio)
    # requests = aio_requests.Session(pool, ssl.create_default_context())
    
    WORLD_CUP = 'https://worldcupjson.net/'
    
    # Fetching World Cup Today
    json_header = {"Accept": "application/json"}
    
    print("{}matches/current\n".format(WORLD_CUP))
    current_match = requests.get("{}matches/current".format(WORLD_CUP), headers = json_header)
    
    match_title, match_score = match_stats(current_match.json())
    
    return(match_title, match_score)


# Test Data Functions ------

# This function uses an API dump from a running game for test.
def wc_current_test():
    try:
        with open("wc_current_match.json", "r") as fp:
            x = fp.read()
            # parse x:
            current_match = json.loads(x)
            
    except OSError as e:
        raise Exception("Could not read text file.")
    
    match_title, match_score = match_stats(current_match)

    return(match_title, match_score)

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
    refresh_time = GAME_ON_REFRESH  # seconds
else:
    game_on = False  # Display schedule
    DISPLAY_ROTATION = 270
    #TODO refresh just before the next match
    refresh_time = GAME_OFF_REFRESH  # seconds


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
        match_title, match_score = wc_current_test() 
    print('Using test data.\n')

else:  # use live data
    
    pool = socketpool.SocketPool(wifi.radio)
    requests = aio_requests.Session(pool, ssl.create_default_context())
    
    # For using NTP instead of AdafruitIO
    '''
    # set RTC clock
    ntp = adafruit_ntp.NTP(pool, tz_offset=TIME_ZONE_OFFSET)
    rtc.RTC().datetime = ntp.datetime
    r = rtc.RTC()
    now_time = local_time()
    print('The current datetime is: {}, ({})'.format(now_time['iso'], ts()))
    '''
    
    # For storing data on AdafruitIO via MQTT
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
    # Get time from Adafruit public time server. Time can fetched as a regular GET
    # request. This eliminates need for dedicated NTP library.
    AIO_TIME = 'https://io.adafruit.com/api/v2/time/seconds'  # POSIX/Unix timestamp
    text_header = {"Accept": "application/text"}
    
    print("Fetching time from Adafruit IO...\n")
    # Get time from io.adafruit.com
    time_from_aio = requests.get('{}'.format(AIO_TIME), headers = text_header)
    # Convert timestamp to datetime object
    time_from_aio = (datetime.fromtimestamp(int(time_from_aio.text)))
    # Adjust to local time
    time_from_aio = time_from_aio + timedelta(hours = TIME_ZONE_OFFSET)
    # Set device clock
    rtc.RTC().datetime = time_from_aio.timetuple()
    
    # Get current time
    now_time = (local_time())['time']
    # Get time of next update as timestamp
    next_update_ts = ts() + refresh_time
    
    next_update = str((datetime.fromtimestamp(next_update_ts)).time())[0:5]
    print('The current time is: {}, ({})'.format(now_time, ts()))
    print('The next update will be: {}, ({})\n'.format(next_update, next_update_ts))
    
    if not game_on:    
        the_schedule, page_title = world_cup()
    if game_on:    
        match_title, match_score = wc_current() 

page_footer = 'Bat: {:0.1f}v - Next: {}'.format(
    battery, next_update)

if not game_on:
    print(page_title)
    print(the_schedule)
if game_on:
    print(match_title)
    print(match_score)
print(page_footer)


# Display Setup

def disiplay_setup():
    return

def try_refresh():
    try:
        board.DISPLAY.refresh()
    except RuntimeError as too_soon_error:
        # catch refresh too soon
        print(too_soon_error)
        print("waiting before retry refresh()")
        time.sleep(10)
        board.DISPLAY.refresh()


# Display object
display = board.DISPLAY
display.rotation = DISPLAY_ROTATION
main_group = displayio.Group()
display.show(main_group)


# Font definitions
SPARTAN_BOLD_16 = bitmap_font.load_font("fonts/LeagueSpartan-Bold-16.bdf")
HELVETICA_BOLD_16 = bitmap_font.load_font("fonts/Helvetica-Bold-16.bdf")
JUNCTION_24 = bitmap_font.load_font("fonts/Junction-regular-24.bdf")
TERMINAL_FONT = terminalio.FONT

# Make the background white
rect = Rect(0, 0, 296, 128, fill=0xFFFFFF, outline=0xFFFFFF)
main_group.append(rect)


# Create labels
# https://docs.circuitpython.org/projects/display_text/en/latest/api.html#adafruit-display-text
# https://github.com/adafruit/Adafruit_CircuitPython_Bitmap_Font/tree/main/examples/fonts
if not game_on:
    page_title = label.Label(
        SPARTAN_BOLD_16,
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
        SPARTAN_BOLD_16,
        text=match_title,
        bg_color=0xFFFFFF,
        color=0x000000,
        x=2,
        y=23,
        base_alignment=True,
    )

    page_body = label.Label(
        JUNCTION_24,
        scale = 2,
        text=match_score,
        bg_color=0xFFFFFF,
        color=0x000000,
        x=10,
        y=85,
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


# Blink LEDs to signal that screen has been updated
colors = [0x110900, 0x001111, 0x110011]
flashes = 1
interval = 0.5
time_off = 0.1
for i in range(len(colors)):
    np_signal(color=colors[i], flashes=flashes,
              interval=interval, time_off=time_off)

print('\nscreen refreshed\ngoing to sleep for {:0.0f} minutes.'.format(refresh_time/60))


# Create a an alarm 
time_alarm = alarm.time.TimeAlarm(monotonic_time=atime.monotonic() + refresh_time)
# Exit the program, and then deep sleep until the alarm wakes us.
alarm.exit_and_deep_sleep_until_alarms(time_alarm)
# Does not return, so we never get here.

