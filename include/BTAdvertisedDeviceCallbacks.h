#ifndef BTADVERTISEDDEVICECALLBACKS_H
#define BTADVERTISEDDEVICECALLBACKS_H

#include <NimBLEDevice.h>

class BTAdvertisedDeviceCallbacks : public NimBLEScanCallbacks {
 public:
  void onResult(const NimBLEAdvertisedDevice* advertisedDevice) override;
  void onScanEnd(const NimBLEScanResults& scanResults, int reason) override;
};

#endif
