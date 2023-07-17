#!/usr/bin/env python3
import subprocess
import re

from lvcontrol_hp import *
from tpot_lv_util import *

#######################
def get_down_channels():
    # get FEE link status from ebdc39
    result = subprocess.run( ['ssh', 'ebdc39', '-x', '~/hpereira/tpot_daq_interface/get_rx_ready.py'], stdout=subprocess.PIPE)
    output = result.stdout.decode('utf8');
    rx_ready = re.findall( "(0|1)", output )

    # these are TPOT links
    fee_list = [0, 1, 5, 6, 7, 8, 9, 11, 12, 14, 15, 18, 19, 23, 24, 25]

    # check which links are down (rx_ready = 0)
    down_channels = []
    for i, row in enumerate(rx_ready):
        if i in fee_list and not eval(row):
            down_channels.append(str(i))

    return down_channels

#######################
def initialize_channels( down_channels_all ):
    if not down_channels_all:
        print( 'initialize_channels - noting to do' )
        return

    fee_init_base_command = '/opt/venvs/sphenix-pytpc/bin/fee_init sampa --pre-samples 90 --samples 100 --shape-gain 6'

    for channel in  down_channels_all:
        fee_init_command = fee_init_base_command + ' --fee ' + channel
        print( 'fee_init_command: ', fee_init_command )
    
        # try at most 5 times
        for i in range(0,5):
            result = subprocess.run( ['ssh', 'ebdc39', '-x', fee_init_command], stdout=subprocess.PIPE)
            output = result.stdout.decode('utf8');
            print( output )

            # parse output for errors and break if none found
            error = (
                re.match( 'SAMPA \d: Can\'t set time window', output ) or
                re.match( 'SAMPA \d: Can\'t set pre trigger', output ) or
                re.match( 'SAMPA \d: WARNING: Unexpected pre trigger length', output )
            )
            if not error:
                break

#####################
def main():
    down_channels_all = []

    ### make three attempts at recovering all links
    for i in range(0,3):
        down_channels = get_down_channels()
        if not down_channels:
            print( 'recover_channels - nothing to do' )
            break
        else:
            print( 'down channels: ', down_channels )

        # find matching lv channels
        channel_dict = parse_arguments( down_channels )
        for crate in sorted(channel_dict.keys()):
            digital_slots = sorted(channel_dict[crate]['digital_slots'])
            analog_slots = sorted(channel_dict[crate]['analog_slots'])
            channels = sorted(channel_dict[crate]['channels'])

            # print crate, slots, channels, controller
            print('crate: ',crate,
                  ' digital slots: ',digital_slots,
                  ' analog slots: ', analog_slots,
                  ' channels: ',channels)
            controller = ip[crate]
            print('controller: ',controller)

            # turn OFF
            print( 'turning off LV' )
            tn = lv_connect(controller)
            for slot in analog_slots+digital_slots:
                lv_disable_channels(tn,slot,channels)
                time.sleep(1)

            time.sleep(1)

            # update down_channels
            # this is because every time one turn off a channel, two FEEs loose link
            # one need to keep track of all the FEEs that loose link in the process 
            # to reinitialize them properly
            down_channels_all = down_channels_all+get_down_channels()

            # turn ON
            print( 'turning back on' )
            for slot in digital_slots:
                lv_enable_channels(tn,slot,channels)
                time.sleep(1)
            
            time.sleep(10)
            for slot in analog_slots:
                lv_enable_channels(tn,slot,channels)
                time.sleep(1)
    
    # get list of channels that could not be recovered
    # down_channels = get_down_channels()
    # print( 'Not all channels could be recovered: ', down_channels

    # make sure channels are sorted and unique
    # and re-initialize
    down_channels_all = list( set( down_channels_all ) )
    initialize_channels( down_channels_all )
    

if __name__ == '__main__':
  main()
