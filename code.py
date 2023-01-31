
import time
import board
import json
import displayio
import terminalio
import digitalio
import rgbmatrix
import framebufferio

from adafruit_display_text.label import Label

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService
from adafruit_airlift.esp32 import ESP32

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# --- Display setup ---
displayio.release_displays()
matrix = rgbmatrix.RGBMatrix(
    width=64, bit_depth=4,
    rgb_pins=[
        board.MTX_R1,
        board.MTX_G1,
        board.MTX_B1,
        board.MTX_R2,
        board.MTX_G2,
        board.MTX_B2
    ],
    addr_pins=[
        board.MTX_ADDRA,
        board.MTX_ADDRB,
        board.MTX_ADDRC,
        board.MTX_ADDRD
    ],
    clock_pin=board.MTX_CLK,
    latch_pin=board.MTX_LAT,
    output_enable_pin=board.MTX_OE
)
display = framebufferio.FramebufferDisplay(matrix)


esp32 = ESP32()

adapter = esp32.start_bluetooth()

ble = BLERadio(adapter)
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

class Billboard:

    content = ""
    item = "NO ITEMS"
    keys_index = 0
    keys = []
    display_types = ["img", "text", "stext"]
    scroll_rate = .1
    SCROLLING = False
    cur = None
    group = displayio.Group()
    medium_font = "fonts/IBMPlexMono-Medium-24_jep.bdf"

    def __init__(self, filename):
        display.auto_refresh = True
        with open(filename, 'r') as c:
            self.content = json.load(c)
        
        for k in self.content.keys():
            self.keys.append(k)

        print("Content for display: ", self.content)

        #Show the first item
        self.next()

    def add_label(self, text="", bg=0x000000, fg=0x10BA08):
        label = Label(
            font=terminalio.FONT,
            text = text,
            color = fg,
            background_color = bg,
            line_spacing = .8,
            anchored_position = (display.width/2, display.height/2),
            anchor_point = (.5,.6)
        )
        self.group.append(label)

    def add_image(self, bmp):
        odb = displayio.OnDiskBitmap(bmp)
        tg = displayio.TileGrid(odb, pixel_shader=odb.pixel_shader)
        self.group.append(tg)

    def next(self):
        if len(self.keys) > 0:
            if self.keys_index < len(self.keys) - 1:
                self.keys_index += 1
            else:
                self.keys_index = 0
        self.cur = self.keys_index
        self.item = self.content[self.keys[self.keys_index]]
        self.__display__(self.keys[self.keys_index], self.item)
        return {self.keys[self.keys_index]: self.item}

    def prev(self):
        if len(self.keys) > 0:
            if self.keys_index == 0:
                self.keys_index = len(self.keys) - 1
            else:
                self.keys_index -= 1
        self.cur = self.keys_index
        self.item = self.content[self.keys[self.keys_index]]
        self.__display__(self.keys[self.keys_index], self.item)
        return {self.keys[self.keys_index]: self.item}
        
    def __display__(self, key, item):
        print("key {}, item: {}".format(key,item))
        self.SCROLLING = False
        # Clear the display
        self.clear()
        for k in item.keys():
            if k in self.display_types:
                if k == "text":
                    self.add_label(
                        item[k], 
                        fg=self.parse_color(item['fg']), 
                        bg=self.parse_color(item['bg'])
                    )
                if k == "stext":
                    self.scroll_rate = float(item['rate'] if "rate" in item.keys() else .1)
                    self.add_label(
                        item[k], 
                        fg=self.parse_color(item['fg']), 
                        bg=self.parse_color(item['bg'])
                    )
                    self.SCROLLING = True
                elif k == "img":
                    self.add_image(item[k])

    def parse_color(self, color):
        if color.startswith("0x"):
            return int(color,16)
        elif color[-4:] == ".bmp":
            return color
        else:
            return 0x000000

    def clear(self):
        while len(self.group) > 0:
            del self.group[0]


# Setup the billboard
billboard = Billboard('content.json')


def get_cur(): 
    c = {billboard.cur: billboard.content[billboard.keys[billboard.cur]]}
    return c

def live_msg(text, fg, bg):  
    print("text received")
    return parse_content(text,fg,bg)

def next():  
    print("next screen")
    return billboard.next()


def prev():  
    print("prev screen")
    return billboard.prev()

def parse_content(text=None,fg=None,bg=None,*):
    if text is None or fg is None or bg is None:
        content = "{}"#default_content
    content = (
        '{' + 
        '"text": "' + text + '", ' + 
        '"fg": "' +   fg + '", ' + 
        '"bg": "' +   bg + 
        '"}')
    return json.loads(content)


# Matrix Portal Button Responders
up_btn = digitalio.DigitalInOut(board.BUTTON_UP)
up_btn.direction = digitalio.Direction.INPUT
up_btn.pull = digitalio.Pull.UP

down_btn = digitalio.DigitalInOut(board.BUTTON_DOWN)
down_btn.direction = digitalio.Direction.INPUT
down_btn.pull = digitalio.Pull.UP

debounce_timeout =  .2
cur_debounce = time.monotonic() + debounce_timeout
def display_change():
    global cur_debounce
    global up_btn
    global down_btn
    global billboard
    global debounce_timeout
    if time.monotonic() > cur_debounce:
        if not up_btn.value:
            print("next ...")
            billboard.next()

        if not down_btn.value:
            print("prev ...")
            billboard.prev()

        # reset debounce clock
        cur_debounce = time.monotonic() + debounce_timeout

    display.show(billboard.group)


do_scroll = time.monotonic() + billboard.scroll_rate
while True:
    display_change()
    # ble.start_advertising(advertisement)
    # print("waiting to connect")
    # while not ble.connected:
    #     pass
    # print("connected: trying to read input")
    # while ble.connected:
    #     # Returns b'' if nothing was read.
    #     one_byte = uart.read(1)
    #     if one_byte:
    #         #print(one_byte)
    #         #uart.write(one_byte)
    #         if one_byte == 'n':
    #             print(next())
    #         if one_byte == 'p':
    #             print(prev())
    #         display_change()
    #FIXME: scrolling needs additional logic for functioning 
    # regardless of whether ble is connected or not
    if billboard.SCROLLING == True:
        if time.monotonic() > do_scroll:
            #scroll()
            do_scroll = time.monotonic() + billboard.scroll_rate
