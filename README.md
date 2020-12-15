# SMLPY - monitor your power meter

## What is it?
smlpy enables reading of smart meter language (sml) data from a smart power meter ("Stromzähler").
This library is intended for newer smart meters which support publishing data through an IR sender. 
Older power meters are not supported.

You need a working IR-reading device for this, e.g. https://shop.weidmann-elektronik.de/index.php?page=product&info=24
which must be connected to an USB port.

Please note that this library only supports a small part of the SML-spec,
especially the sending part is intentionally omitted

## How to use it?

Usage is simple:



### Example data
This is from my EHZ-K power meter:

#### Unformatted

```1b1b1b1b01010101760700110bf402df620062007263010176010107001103c500f50b0901454d4800007514c401016375f300760700110bf402e0620062007263070177010b0901454d4800007514c4070100620affff7262016503c5853c7a77078181c78203ff0101010104454d480177070100000009ff010101010b0901454d4800007514c40177070100010800ff6401018201621e52ff5600051bdfde0177070100020800ff6401018201621e52ff5600000006070177070100010801ff0101621e52ff5600051bdfde0177070100020801ff0101621e52ff5600000006070177070100010802ff0101621e52ff5600000000000177070100020802ff0101621e52ff5600000000000177070100100700ff0101621b52ff55000014f40177078181c78205ff010101018302957c486aaf8c92a257ec681e215fddeff32a2dbf2c8a88721777f5f01e5ed5ccaa694dd48c14dc5589d28e0c5b9ce88e01010163b4c800760700110bf402e362006200726302017101634e85001b1b1b1b1a000337```

#### Formatted
```
1b1b1b1b01010101
    76
        07  00  11  0b  f4  02  df
        62  00
        62  00
        72  
            63  01  01
            76
                01
                01
                07  00  11  03  c5  00  f5  
                0b  09  01  45  4d  48  00  00  75  14  c4  
                01
                01
            63  75  f3
            00
        76
            07  00  11  0b  f4  02  e0  
            62  00  
            62  00
            72  
                63  07
                01  
            77 
                01
                0b  09  01  45  4d  48  00  00  75  14  c4  
                07  01  00  62  0a  ff  ff  
                72  
                    62  01  
                    65  03  c5  85  3c
                7a
                    77 #0
                        07  81  81  c7  82  03  ff  
                        01
                        01
                        01
                        01
                        04  45  4d  48  
                        01  
                    77 #1 
                        07  01  00  00  00  09  ff 
                        01
                        01
                        01
                        01
                        0b  09  01  45  4d  48  00  00  75  14  c4  
                        01  
                    77  #2
                        07  01  00  01  08  00  ff
                        64  01  01  82  
                        01
                        62  1e  
                        52  ff
                        56  00  05  1b  df  de  
                        01
                    77 #3
                        07  01  00  02  08  00  ff  
                        64  01  01  82  
                        01
                        62  1e
                        52  ff
                        56  00  00  00  06  07  
                        01
                    77 #4
                        07  01  00  01  08  01  ff
                        01
                        01
                        62  1e
                        52  ff
                        56  00  05  1b  df  de
                        01
                    77  #5
                        07  01  00  02  08  01  ff
                        01
                        01
                        62  1e
                        52  ff  
                        56  00  00  00  06  07
                        01
                    77 #6
                        07  01  00  01  08  02  ff
                        01
                        01
                        62  1e
                        52  ff
                        56  00  00  00  00  00  
                        01
                    77 #7
                        07  01  00  02  08  02  ff  
                        01
                        01
                        62  1e
                        52  ff  
                        56  00  00  00  00  00
                        01
                    77  #8
                        07  01  00  10  07  00  ff
                        01
                        01
                        62  1b
                        52  ff  
                        55  00  00  14  f4  
                        01  
                    77  #9
                        07  81  81  c7  82  05  ff
                        01
                        01
                        01
                        01
                        83  02957c486aaf8c92a257ec681e215fddeff32a2dbf2c8a88721777f5f01e5ed5ccaa694dd48c14dc5589d28e0c5b9ce88e
                        01
                01
                01
            63b4c8
            00
        76
            07  00110bf402e36200620072630201
        71  
            01
        63  4e85001b1b1b1b1a000337
```
