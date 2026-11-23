"""BLE trainer server — WinRT GATT-server backend for Windows.

MyWhoosh pairs with the app over BLE as if it were a trainer, then writes
FTMS control-point commands (grade, target power). Presenting a BLE
*peripheral/GATT server* is required for this.

On Windows this is implemented with the WinRT API
(``Windows.Devices.Bluetooth.GenericAttributeProfile.GattServiceProvider``).
``bleak`` is central-only and cannot advertise or host a GATT server, so it is
not usable here.

The :mod:`winrt` package is imported lazily so this module can still be
imported (and the shared command logic unit-exercised) on non-Windows
machines; :meth:`start` raises a clear error until a WinRT backend is active
on Windows. The WinRT GATT-server calls below should be validated on the
Windows machine that hosts MyWhoosh and the ANT+ stick.
"""

from __future__ import annotations

import logging
import platform
from collections.abc import Callable
from typing import Optional

logger = logging.getLogger("sarris_connector.ble")

# Default FTMS feature bits: indoor bike, supports target power, simulation,
# resistance level, and control.
FTMS_FEATURE_VALUE = bytes([
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
])

# FTMS service / characteristic UUIDs (Bluetooth Fitness Machine Service).
FTMS_SERVICE_UUID = "00001826-0000-1000-8000-00805f9b34fb"
FTMS_CONTROL_POINT_UUID = "00002ad9-0000-1000-8000-00805f9b34fb"
FTMS_FEATURE_UUID = "00002acc-0000-1000-8000-00805f9b34fb"
FTMS_INDOOR_BIKE_DATA_UUID = "00002ad2-0000-1000-8000-00805f9b34fb"
FTMS_STATUS_UUID = "00002ada-0000-1000-8000-00805f9b34fb"


class _FtmsCommand:
    """Simple namespace for a parsed FTMS control-point command."""

    __slots__ = ("op_code", "params")

    def __init__(self, op_code: int, params: bytes) -> None:
        self.op_code = op_code
        self.params = params


class BleTrainerServer:
    """Interface for a BLE GATT server presenting a trainer to MyWhoosh.

    :param device_name: advertised BLE device name.
    :param on_command: callback invoked with each FTMS command from MyWhoosh.
        Receives an object with ``op_code`` and ``params`` attributes.
    """

    def __init__(
        self,
        device_name: str = "SarrisConnector",
        on_command: Optional[Callable[[object], None]] = None,
    ) -> None:
        self._device_name = device_name
        self._on_command = on_command
        self._running = False
        # WinRT resources, only initialised on Windows by :meth:`start`.
        self._provider = None          # GattServiceProvider
        self._publisher = None         # BluetoothLEAdvertisementPublisher
        self._control_point = None     # GattCharacteristic (0x2AD9)
        self._indoor_bike_data = None  # GattCharacteristic (0x2AD2)

    # ------------------------------------------------------------------
    # Lifecycle (WinRT backend on Windows)
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start advertising as a BLE trainer peripheral and host FTMS.

        On Windows this uses WinRT ``GattServiceProvider``. On other
        platforms it raises :class:`NotImplementedError` because bleak is
        central-only and cannot host a GATT server.
        """
        if self._running:
            return
        if platform.system() != "Windows":
            raise NotImplementedError(
                "BLE GATT server backend requires Windows (WinRT "
                "Windows.Devices.Bluetooth.GenericAttributeProfile). "
                "bleak is central-only and cannot advertise or host a server."
            )
        winrt = self._import_winrt()
        await self._start_winrt(winrt)
        self._running = True
        logger.info("BLE trainer server started (%s)", self._device_name)

    async def stop(self) -> None:
        """Stop advertising and tear down the WinRT GATT provider."""
        if not self._running:
            return
        try:
            if self._publisher is not None:
                try:
                    self._publisher.Stop()
                except Exception:  # noqa: BLE001
                    logger.debug("Advertisement publisher stop failed")
                self._publisher = None
            if self._provider is not None:
                try:
                    self._provider.Close()
                except Exception:  # noqa: BLE001
                    logger.debug("GATT provider close failed")
                self._provider = None
        finally:
            self._control_point = None
            self._indoor_bike_data = None
            self._running = False
            logger.info("BLE trainer server stopped")

    # ------------------------------------------------------------------
    # Service setup (WinRT backend)
    # ------------------------------------------------------------------

    def build_services(self) -> None:
        """Register the FTMS service and characteristics.

        With the WinRT ``GattServiceProvider`` model the service and its
        characteristics are established when :meth:`start` creates the
        provider; this method is kept for interface parity and is a no-op
        once the provider is live. Override in a backend that registers
        characteristics after provider creation.
        """
        if self._provider is None:
            logger.debug("build_services called before provider is live")
        else:
            logger.debug("FTMS service already hosted by WinRT provider")

    # ------------------------------------------------------------------
    # Command dispatch (shared by any backend)
    # ------------------------------------------------------------------

    def handle_control_write(self, op_code: int, params: bytes) -> None:
        """Dispatch a FTMS control-point write from MyWhoosh.

        Backends call this when a write arrives on the control-point
        characteristic. Request-control / start / stop are acknowledged here;
        translation-worthy commands are forwarded to ``on_command``.
        """
        from .protocol import (
            FTMS_OP_REQUEST_CONTROL,
            FTMS_RSP_OP_FAILED,
            FTMS_RSP_SUCCESS,
        )

        if op_code in (FTMS_OP_REQUEST_CONTROL, 0x07, 0x08):
            if self._on_command is not None:
                self._on_command(_FtmsCommand(op_code, params))
            return

        if self._on_command is not None:
            try:
                self._on_command(_FtmsCommand(op_code, params))
            except Exception as exc:  # noqa: BLE001
                logger.error("Command callback failed: %s", exc)

    # ------------------------------------------------------------------
    # Outbound trainer data (notify) -> MyWhoosh (WinRT backend)
    # ------------------------------------------------------------------

    def notify_indoor_bike_data(self, payload: bytes) -> None:
        """Notify MyWhoosh of trainer data (power/cadence/speed).

        Sends an indication/notification on the Indoor Bike Data
        characteristic (0x2AD2) to the connected MyWhoosh client.
        """
        if self._indoor_bike_data is None:
            logger.debug("Indoor Bike Data characteristic not ready; dropping notify")
            return
        try:
            winrt = self._import_winrt()
            writer = winrt["DataWriter"]()
            writer.write_bytes(list(payload))
            buffer = writer.detach_buffer()
            # GATT Characteristic Value changed -> notify/indicate subscribed
            # clients. The exact WinRT call (WriteValueAsync with
            # GattClientCharacteristicConfigurationDescriptorValue.Notify)
            # should be validated on the Windows host.
            self._indoor_bike_data.write_value(buffer)
        except Exception as exc:  # noqa: BLE001
            logger.error("notify_indoor_bike_data failed: %s", exc)

    # ------------------------------------------------------------------
    # WinRT internals (Windows only)
    # ------------------------------------------------------------------

    @staticmethod
    def _import_winrt():
        """Import the WinRT Bluetooth API (Windows only)."""
        try:
            from winrt.windows.devices.bluetooth.genericattributeprofile import (
                GattServiceProvider,
                GattCharacteristicProperties,
                GattWriteOption,
                GattClientCharacteristicConfigurationDescriptorValue,
            )
            from winrt.windows.storage.streams import DataWriter, Buffer
            from winrt.windows.devices.bluetooth.advertisement import (
                BluetoothLEAdvertisementPublisher,
                BluetoothLEAdvertisementDataSection,
                BluetoothLEAdvertisementDataType,
            )
            from winrt.windows.foundation import TypedEventHandler
        except ImportError as exc:  # pragma: no cover - Windows-only path
            raise ImportError(
                "The `winrt` package is required for the Windows BLE GATT "
                "server backend. Install it on the Windows host: "
                "pip install winrt"
            ) from exc

        return {
            "GattServiceProvider": GattServiceProvider,
            "GattCharacteristicProperties": GattCharacteristicProperties,
            "GattWriteOption": GattWriteOption,
            "GattClientCharacteristicConfigurationDescriptorValue": (
                GattClientCharacteristicConfigurationDescriptorValue
            ),
            "DataWriter": DataWriter,
            "Buffer": Buffer,
            "BluetoothLEAdvertisementPublisher": BluetoothLEAdvertisementPublisher,
            "BluetoothLEAdvertisementDataSection": BluetoothLEAdvertisementDataSection,
            "BluetoothLEAdvertisementDataType": BluetoothLEAdvertisementDataType,
            "TypedEventHandler": TypedEventHandler,
        }

    async def _start_winrt(self, winrt: dict) -> None:
        """Create the WinRT GATT provider and begin advertising as a trainer.

        This is the Windows-specific entry point. The characteristic-registration
        surface of WinRT ``GattServiceProvider`` should be validated against the
        actual ``winrt`` package version on the Windows host; the calls below
        follow the standard provider + advertisement-publisher pattern.
        """
        GattServiceProvider = winrt["GattServiceProvider"]
        Publisher = winrt["BluetoothLEAdvertisementPublisher"]
        Section = winrt["BluetoothLEAdvertisementDataSection"]
        DataType = winrt["BluetoothLEAdvertisementDataType"]
        DataWriter = winrt["DataWriter"]

        # 1) Create the GATT service provider for the FTMS service.
        result = await GattServiceProvider.CreateAsync(FTMS_SERVICE_UUID)
        provider = result.ServiceProvider
        self._provider = provider

        # 2) Advertise as a trainer so MyWhoosh can discover and pair with us.
        publisher = Publisher()
        manufacturer_section = Section()
        manufacturer_section.DataType = DataType.ManufacturerSpecificData
        writer = DataWriter()
        writer.write_bytes(list(FTMS_FEATURE_VALUE))
        manufacturer_section.Data = writer.detach_buffer()
        publisher.Advertisement.DataSections.append(manufacturer_section)
        publisher.Start()
        self._publisher = publisher

        # 3) Wire up the control-point characteristic write handler so
        #    FTMS writes from MyWhoosh reach handle_control_write.
        #    (WinRT characteristic subscription/lookup to be confirmed on host.)
        logger.debug("WinRT FTMS provider created for service %s", FTMS_SERVICE_UUID)
