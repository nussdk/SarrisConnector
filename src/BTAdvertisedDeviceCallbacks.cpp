#include <BTAdvertisedDeviceCallbacks.h>
#include <BTDeviceManager.h>
#include <NimBLEDevice.h>

void BTAdvertisedDeviceCallbacks::onResult(const NimBLEAdvertisedDevice* advertisedDevice) {
  bool addDevice = true;
  for (NimBLEUUID uuid : BTDeviceManager::remoteDeviceFilterUUIDs) {
    if (!advertisedDevice->isAdvertisingService(uuid)) {
      addDevice = false;
      break;
    }
    if (!addDevice) {
      break;
    }
  }
  if (addDevice) {
    log_d("Adding %s (%s) to device list", advertisedDevice->getAddress().toString().c_str(), advertisedDevice->getName().c_str());
    BTDeviceManager::scannedDevices.push_back(NimBLEAdvertisedDevice(*advertisedDevice));
    if (BTDeviceManager::getRemoteDevice() != nullptr) {
      BTDeviceManager::stopScan();
    }
  }
}

void BTAdvertisedDeviceCallbacks::onScanEnd(const NimBLEScanResults& scanResults, int reason) {
  BTDeviceManager::onScanEnd(scanResults, reason);
}
