# SMLPY - monitor your power meter

## What is it?
smlpy enables reading of smart meter language (sml) data from a smart power meter ("Stromzähler").
This library is intended for newer smart meters which support publishing data through an IR sender. 
Older power meters are not supported.

You need a working IR-reading device for this, e.g. https://shop.weidmann-elektronik.de/index.php?page=product&info=24
which must be connected to a USB port.

Please note that this library only supports a small part of the SML-spec,
especially the sending part is intentionally omitted

## How to use it?

```
pip install smlpy
```

From the shell:
go to the folder containing smlpy and modify data_reader.dump to account for your baudrate etc.

This should dump the readings to the shell:
```shell
python data_reader.py 
```

programmatic usage:

This dumps the results to the console:
```python
from smlpy import data_reader
import asyncio
loop = asyncio.get_event_loop()
try:
    loop.run_until_complete(data_reader.dump_results()) # todo set baud rate etc!
finally:
    # see: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.shutdown_asyncgens
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
```

If you need programmatic access to the data, use 
```python
from smlpy import data_reader
import asyncio
import serial
loop = asyncio.get_event_loop()
try:
    default_port_settings = data_reader.PortSettings(port='/dev/ttyUSB0',
                                         baudrate=9600,
                                         bytesize=serial.EIGHTBITS,
                                         parity=serial.PARITY_NONE,
                                         stopbits=serial.STOPBITS_ONE,
                                         wait_time=data_reader.WAIT_TIME)
    async for result in data_reader.main(default_port_settings):
        print(result.dump_to_json())
        # e.g. save to DB
finally:
    # see: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.shutdown_asyncgens
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
```

## Tests
1. clone this project
1. install pytest
1. pytest test
1. Optional: 
    1. Please clone [libsml-testing](https://github.com/devZer0/libsml-testing) into a folder next to the smlpy folder
    1. Remove the `@pytest.mark.skip("manual only")`flag and run also the test against other power meter data. A lot of the data is broken though
    
If you have additional data please add a test case and submit a PR

## Device compatibility

I have test this library with data from these devices:

- EMH EHZ-K (eHZ Generation K)
- EMH EHZ-361L5R
- EMH EHZ-HW8E2A5LOEK2P
- EMH EHZ-GW8E2A500AK2
- ITRON Openway 3
- ISKRA MT175 EHZ
- ISKRA MT691 EHZ

Does not work: 
- HOLLEY DTZ541 ZDBA
