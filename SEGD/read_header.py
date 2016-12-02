from struct import unpack
from datetime import datetime, timedelta

def pbcd2dec(pbcd):
    ''' Returns decimal number from packed Binary Coded Decimal'''
    
    decode = 0
    
    for n in pbcd:
        unpck   =   divmod(n,16)
        decode  =   (10*unpck[0]+unpck[1])+100*decode
    
    return decode

class SEGD_trace_header(object):

    def __init__(self,hdr_block):
        
        ch_set_hdr      =   unpack('>32B',hdr_block)
        
        self._ch_set    =   pbcd2dec(ch_set_hdr[1:2])
        self.start      =   (ch_set_hdr[2]*2**8+ch_set_hdr[3])*2
        self.stop       =   (ch_set_hdr[4]*2**8+ch_set_hdr[5])*2

        mp_factor  =   bin(ch_set_hdr[7])+bin(ch_set_hdr[6])[2:].zfill(8)
        

        # If the gain field is set to zero and the above field will only be 10 characters long
        if mp_factor=='0b000000000':
            mp_factor = '0b0000000000000000'
        
        channel_gain   =   0
        for idx, gain_step in enumerate(range(4,-11,-1)):
            channel_gain +=2**gain_step*eval(mp_factor[idx+3])

        if mp_factor[2]=='1':
            channel_gain *= -1


        self.mp_factor      =   2**channel_gain

        self.channels       =   pbcd2dec(ch_set_hdr[8:10])
        self.type           =   divmod(ch_set_hdr[10],16)[0]
        self.sample_per_channel =   2**divmod(ch_set_hdr[11],16)[0]
        self.alias_filter_freq  =   pbcd2dec(ch_set_hdr[12:14])
        self.alias_filter_slope =   divmod(ch_set_hdr[14],16)[0]*100+pbcd2dec(ch_set_hdr[15:16])
        self.hp_filter_freq     =   pbcd2dec(ch_set_hdr[16:18])
        self.hp_filter_slope    =   divmod(ch_set_hdr[18],16)[0]*100+pbcd2dec(ch_set_hdr[19:20])
        self.streamer_no    =   ch_set_hdr[30]
        self.array_forming  =   ch_set_hdr[31]

    def __str__(self):
        # Cahnnel set header information
        readable_output = 'Start of record: \t {0}ms\n'.format(self.start)
        readable_output += 'Stop of record: \t {0}ms\n'.format(self.stop)
        readable_output += 'MP factor: \t\t {0}\n'.format(self.mp_factor)
        readable_output += 'Channels: \t\t {0} \t(type {1}, samples per channel {2})\n'\
            .format(self.channels,self.type,self.sample_per_channel)
        readable_output += 'Alias filter freq: \t {0} \t(slope {1})\n'\
            .format(self.alias_filter_freq,self.alias_filter_slope)
        readable_output += 'Low cut filter freq: \t {0} \t(slope {1})\n'\
                    .format(self.hp_filter_freq,self.hp_filter_slope)
        readable_output += 'Streamer number: \t {0}\n'.format(self.streamer_no)
        readable_output += 'Array forming: \t\t {0}\n\n'.format(self.array_forming)

        return readable_output

class SEGD_header(object):

    def __init__(self,file_name = ''):
        self.file_name = file_name
    
        if self.file_name:
            self.populate_header()

    def populate_header(self):

        f = open(self.file_name,'rb')

        # General header block #1
        gen_hdr_1   =   unpack('>32B',f.read(32))
        # General header block #2
        gen_hdr_2   =   unpack('>32B',f.read(32))
        # General header block #3
        gen_hdr_3   =   unpack('>32B',f.read(32))
        
        
        # Header block #1
        
        self.file_number    =   pbcd2dec(gen_hdr_1[0:2])
        self.segd_format    =   pbcd2dec(gen_hdr_1[2:4])
        
        # Decode timestamp and place result in a datetime object
        year                =   pbcd2dec(gen_hdr_1[10:11])
        julian_day          =   divmod(gen_hdr_1[11],16)[1]*100+pbcd2dec(gen_hdr_1[12:13])
        hour                =   pbcd2dec(gen_hdr_1[13:14])
        minute              =   pbcd2dec(gen_hdr_1[13:14])
        second              =   pbcd2dec(gen_hdr_1[15:16])
        
        self.time_stamp     =   datetime(year,1,1,hour,minute,second)+timedelta(days=julian_day-1)
        
        self._additional_hdr_blocks =   divmod(gen_hdr_1[11],16)[0]

        self.dt             =   divmod(gen_hdr_1[22],16)[0]*1e-3 # skip fractions
        self.trace_length   =   (divmod(gen_hdr_1[25],16)[1]*10+pbcd2dec(gen_hdr_1[26:27])/10.)*1.024

        self.channel_sets   =   pbcd2dec(gen_hdr_1[28:29])
        self._skew_blocks   =   pbcd2dec(gen_hdr_1[29:30])

        self._extended_hdr_blocks   =   pbcd2dec(gen_hdr_1[30:31])
        self._external_hdr_blocks   =   pbcd2dec(gen_hdr_1[31:32])


        # Header block #2
        
        if self._extended_hdr_blocks  == 165:
            self._extended_hdr_blocks   =   gen_hdr_2[5]*256+gen_hdr_2[6]
                
        if self._external_hdr_blocks  == 165:
            self._external_hdr_blocks   =   gen_hdr_2[7]*256+gen_hdr_2[8]
    
        if self.trace_length == 170.496:
            self.trace_length   =   (gen_hdr_2[14]*2**16+gen_hdr_2[15]*2**8+gen_hdr_2[16])*1e-3
    
        self.segd_rev   =   pbcd2dec(gen_hdr_2[10:11])+pbcd2dec(gen_hdr_2[11:12])/10.
        self._extended_trace_length     =   gen_hdr_2[31]

        self.channel_set_headers = [SEGD_trace_header(f.read(32)) for _ in range(self.channel_sets)]

        # skip Host recording sys, Line ID for cables and Shot time/reel number
        f.seek(32*3,1)
    
        self.client_name    =   unpack('>32s',f.read(32))[0].split(b'\x00')[0]
        self.contractor     =   unpack('>32s',f.read(32))[0].split(b'\x00')[0]
        self.survey         =   unpack('>32s',f.read(32))[0].split(b'\x00')[0]
        self.project        =   unpack('>32s',f.read(32))[0].split(b'\x00')[0]

    def __str__(self):

        # Global header information
        readable_output = 'SEG-D file header:\n\n'
        readable_output += 'File name:   \t\t {0}\n'.format(self.file_name)
        readable_output += 'File number: \t\t {0}\n'.format(self.file_number)
        readable_output += 'File Format: \t\t {0} rev {1}\n'.format(self.segd_format,self.segd_rev)
        readable_output += 'Time stamp:  \t\t {0}\n'.format(self.time_stamp.ctime())
        readable_output += 'Trace length:\t\t {0}s\n'.format(self.trace_length)
        readable_output += 'Sample rate: \t\t {0}s\n\n'.format(self.dt)

        for idx,ch_set in enumerate(self.channel_set_headers):
            readable_output += 'Channel set {0}:\n'.format(idx)
            readable_output += ch_set.__str__()

        return readable_output


def read_header(file):

    '''Returns SEGD_header object'''

    header = SEGD_header(file)

    return header
