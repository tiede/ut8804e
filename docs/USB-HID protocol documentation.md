# UT8804e desktop meter USB HID interface

## Measurements and corresponding usb HID data
19.538 VDC: abcd 21 00 02 08 01 10 31 02 d3 4d 9c 41 30 56 44 43 0000 0000 00 d4 95 9c 415644430000000000 9c 06
19.540 VDC: abcd 21 00 02 08 01 10 31 02 ec 51 9c 41 30 56 44 43 0000 0000 00 d4 95 9c 415644430000000000 b9 06
18.540 VDC: abcd 21 00 02 08 01 10 31 02 ec 51 94 41 30 56 44 43 0000 0000 00 a2 98 94 415644430000000000 7a 06
19.540 VDC: abcd 21 00 02 08 01 10 31 02 ec 51 9c 41 30 56 44 43 0000 0000 00 d4 95 9c 415644430000000000 b9 06


## Trying to decode
                                    -- Value --                      -- Value -- 
       0001 02 03 04 05 06 07 08 09 10 11 12 13 14 15161718 19202122 23 24 25 26 272829 3031323334 34 35 36
                                                    V D C                         V D C
19.538 abcd 21 00 02 08 01 10 31 02 d3 4d 9c 41 30 56444300 00000000 d4 95 9c 41 56444300 00000000 9c 06
19.540 abcd 21 00 02 08 01 10 31 02 ec 51 9c 41 30 56444300 00000000 d4 95 9c 41 56444300 00000000 b9 06
18.540 abcd 21 00 02 08 01 10 31 02 ec 51 94 41 30 56444300 00000000 a2 98 94 41 56444300 00000000 7a 06
18.500 abcd 21 00 02 08 01 10 31 02 00 00 94 41 30 56444300 00000000 1c cc 93 41 56444300 00000000 ea 04
                                                    ~ 0 0                         ~ 0 0
       abcd 21 00 02 08 01 10 51 01 71 3d a0 41 20 7e000000 00000000 86 c6 9f 41 7e000000 00000000 65 05 
                                                    m V D C
       abcd 21 00 02 08 01 10 41 02 8f 82 d7 43 20 6d564443 00000000 55 02 d8 43 6d564443 00000000 d0 06


package[0:2]         start header oxab 0xcd
package[3]           length of the following data excluding checksum
package[10-13]       float value - corresponds with the display
package[15-18]       measurement type
package[14]          mode? range?
package[8]           mode? range?
package[9]           mode? range?

package[23-26]       float value 2
package[27-30]       measurement type 2


00000000 00000010 00001000 00000001 00010000 00110001 00000010

Connect package
08 ab cd 04 00 05 01 0a 00

Disconnect package
08 ab cd 04 00 05 00 09 00


