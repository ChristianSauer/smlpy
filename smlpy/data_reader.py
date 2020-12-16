"""
Functions to read sml files from a serial device, e.g. /dev/ttyUSB0
If you just want to dump some results to the console, adjust your configuration values in
dump_results default_portsettings (see pyserial for an explanation of the settings) and run this file,
e.g. python data_reader.py
For more advanced scenarios, call main, or even receive and read directly.
You can use dump_results as a template for this.
"""

import dataclasses
import asyncio
import codecs
from typing import Union

import serial
import serial_asyncio
import typing
from loguru import logger
from typing_extensions import Literal

from smlpy import sml_reader

WAIT_TIME = 5


@dataclasses.dataclass()
class PortSettings:
    port: str
    baudrate: int
    bytesize: Literal[5, 6, 7, 8]
    parity: Literal['N', 'E', 'O', 'M', 'S']
    stopbits: Union[int, float]
    wait_time: int = WAIT_TIME


async def receive(default_portsettings: PortSettings,
                  queue: asyncio.Queue, ):
    """
    Asynchronously receives data from the given port at the settings (for an explanation see pyserial) and puts them
    into the queue.
    wait_time is used to control the time given to accumulate data. it should be enough
    """
    reader, _ = await serial_asyncio.open_serial_connection(url=default_portsettings.port,
                                                            baudrate=default_portsettings.baudrate,
                                                            bytesize=default_portsettings.bytesize,
                                                            parity=default_portsettings.parity,
                                                            stopbits=default_portsettings.stopbits)
    return _read_from_port(reader, queue, default_portsettings.wait_time)


async def _read_from_port(reader: asyncio.StreamReader, queue: asyncio.Queue, wait_time):
    data = ""

    start = sml_reader.msg_start + sml_reader.msg_version_1
    end = sml_reader.msg_end + "1a"  # standard... I love sml!

    while True:
        msg = await reader.read(1000 * wait_time)

        # we need to find a start and an end in this mess.
        received_data = codecs.encode(msg, 'hex').decode('ascii')

        logger.info(f"msg length {len(msg)} msg {received_data}")

        data += received_data
        start_pos = data.find(start)
        end_pos = data.find(end)
        if start_pos != -1 and end_pos != -1:
            await queue.put(data[start_pos: end_pos + len(end) + 6])
            data = data[end_pos + 4:]
            logger.debug("full message received")
        elif start_pos != -1 and end_pos == -1:
            logger.debug("partial message received", data=received_data)
        else:
            logger.debug("end but no start")
            data = ""

        await asyncio.sleep(WAIT_TIME)


async def read(queue: asyncio.Queue):
    """Asynchronously reads data from the queue and tries to read them into an SmlFile"""
    while True:
        item = await queue.get()
        if item is None:
            # the producer emits None to indicate that it is done
            await asyncio.sleep(WAIT_TIME)
            continue
        else:
            logger.trace(item)

            reader = sml_reader.SmlReader(item)

            result = reader.read_sml_file()

            logger.trace(result.dump_to_json())

            yield result


async def main(port_settings: PortSettings) -> typing.AsyncIterator[sml_reader.SmlFile]:
    """
    Example main which dumps the received file as json to the console. This runs for an infinite time, quit with CTRL+C
    """

    queue = asyncio.Queue()
    receiver = await receive(port_settings, queue)
    asyncio.create_task(receiver)

    reader = read(queue)
    async for sml_file in reader:
        yield sml_file


async def dump_results():
    default_port_settings = PortSettings(port='/dev/ttyUSB0',
                                         baudrate=9600,
                                         bytesize=serial.EIGHTBITS,
                                         parity=serial.PARITY_NONE,
                                         stopbits=serial.STOPBITS_ONE,
                                         wait_time=WAIT_TIME)
    async for result in main(default_port_settings):
        logger.info(result.dump_to_json())


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(dump_results())
    finally:
        # see: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.shutdown_asyncgens
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
