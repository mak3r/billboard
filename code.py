
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
    keys_index = 0
    display_types = ["img", "text", "stext"]
    scroll_rate = .1
    SCROLLING = False
    layers = {} # dictionary of content keys and display groups
    layer_list = [] # list of layers for navigating prev/next on display
    cur_layer = 0 # index into layer_list
    group = displayio.Group()
    medium_font = "fonts/IBMPlexMono-Medium-24_jep.bdf"

    def __init__(self, filename):
        display.auto_refresh = True
        with open(filename, 'r') as c:
            self.content = json.load(c)
        
        display_items = list(self.content.keys())
        print("display items len: ", len(display_items))
        for item in display_items:
            self.__add_layer__(item, self.content[item] )

        self.layer_list=list(self.layers.keys())
        print("Number of display items: ", len(self.layers))
        print("Content for display: ", self.content)
        print("List of layers: ", self.layer_list)

        # Initialize the next item to be visible (!group.hidden)
        print("next billboard: ", self.next())

    def __make_Label__(self, text="", bg=0x000000, fg=0x10BA08):
        label = Label(
            font=terminalio.FONT,
            text = text,
            color = fg,
            background_color = bg,
            line_spacing = .8,
            anchored_position = (display.width/2, display.height/2),
            anchor_point = (.5,.6)
        )
        return label

    def __make_TileGroup__(self, bmp):
        odb = displayio.OnDiskBitmap(bmp)
        tg = displayio.TileGrid(odb, pixel_shader=odb.pixel_shader)
        return tg

    # Create a group with layer 1 = layer
    def ____make_Group____(self, layer):
        g = displayio.Group()
        g.append(layer)
        g.hidden = False
        return g

    def next(self):
        if self.cur_layer < (len(self.layer_list) - 1):
            self.cur_layer += 1
        else:
            self.cur_layer = 0
        
        print("Cur layer id: ", self.cur_layer)
        self.clear()
        self.group.append(self.layers[self.layer_list[self.cur_layer]])
        print("Cur layer key: ", self.layer_list[self.cur_layer])
        return {self.layer_list[self.cur_layer]: self.content[self.layer_list[self.cur_layer]]}


    def prev(self):
        if self.cur_layer > 0: 
            self.cur_layer -= 1
        else:
            self.cur_layer = (len(self.layer_list) - 1)
        
        print("Cur layer id: ", self.cur_layer)
        self.clear()
        self.group.append(self.layers[self.layer_list[self.cur_layer]])
        print("Cur layer key: ", self.layer_list[self.cur_layer])
        return {self.layer_list[self.cur_layer]: self.content[self.layer_list[self.cur_layer]]}

    def clear(self):
        while len(self.group) > 0:
            del self.group[0]
        
    def __add_layer__(self, key, item):
        print("key {}, item: {}".format(key,item))
        self.SCROLLING = False
        layer = None 
        background = None
        for k in item.keys():
            if k in self.display_types:
                if k == "text":
                    background = self.make_background(item['bg'])
                    layer = self.__make_Label__(
                        item[k], 
                        fg=int(item['fg'],16), 
                        bg=None
                    )
                if k == "stext":
                    self.scroll_rate = float(item['rate'] if "rate" in item.keys() else .1)
                    background = self.make_background(item['bg'])
                    print("background: ", item['bg'])
                    layer = self.__make_Label__(
                        item[k], 
                        fg=int(item['fg'],16), 
                        bg=None
                    )
                    self.SCROLLING = True
                elif k == "img":
                    background = self.__make_TileGroup__(item[k])
                g = self.____make_Group____(background)
                if (layer is not None):
                    g.append(layer)
                self.layers[key] = g

    def make_background(self, color):
        if color.startswith("0x"):
            palette = displayio.Palette(1)
            palette[0] = int(color,16)
            bitmap = displayio.Bitmap(display.width, display.height, 1)
            tg = displayio.TileGrid(pixel_shader=palette, bitmap=bitmap)
            return tg
        elif color[-4:] == ".bmp":
            return self.__make_TileGroup__(color)

    def clear(self):
        while len(self.group) > 0:
            del self.group[0]


# Setup the billboard
billboard = Billboard('content.json')


def live_msg(text, fg, bg):  
    print("text received")
    return parse_content(text,fg,bg)

def next():
    return billboard.next()


def prev():
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
            print(billboard.next())

        if not down_btn.value:
            print(billboard.prev())

        # reset debounce clock
        cur_debounce = time.monotonic() + debounce_timeout

    display.show(billboard.group)


do_scroll = time.monotonic() + billboard.scroll_rate
while True:
    ble.start_advertising(advertisement)
    print("waiting to connect")
    while not ble.connected:
        display_change()
        pass
    print("connected: trying to read input")
    while ble.connected:
        # Returns b'' if nothing was read.
        one_byte = uart.read(1)
        if one_byte:
            print(one_byte)
            #uart.write(one_byte)
            if one_byte == b'n':
                uart.write(json.dumps(billboard.next()).encode('utf-8'))
            if one_byte == b'p':
                uart.write(json.dumps(billboard.prev()).encode('utf-8'))
        display_change()
    #FIXME: scrolling needs additional logic for functioning 
    # regardless of whether ble is connected or not
    if billboard.SCROLLING == True:
        if time.monotonic() > do_scroll:
            #scroll()
            do_scroll = time.monotonic() + billboard.scroll_rate
