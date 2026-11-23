#ifndef SETTINGSMANAGER_H
#define SETTINGSMANAGER_H

// IoTWebConf configuration
// identifier for EEPROM storage
#define WIFI_CONFIG_VERSION "init2"
// when CONFIG_PIN is pulled to ground on startup, the device will use the initial password to build an AP
// status indicator pin, first it will light up (kept LOW), on Wifi connection it will blink, when connected to the Wifi it will turn off (kept HIGH)
#ifdef ARDUINO_WT32_ETH01
#define WIFI_CONFIG_PIN IO12
#define WIFI_STATUS_PIN IO14
#else
// IO12/IO14 are strapping pins on a generic ESP32; use safe GPIOs instead
#define WIFI_CONFIG_PIN 4
#define WIFI_STATUS_PIN 5
#endif

#include <Arduino.h>
#include <IotWebConf.h>
#include <IotWebConfUsing.h>
#include <map>

typedef enum VirtualShiftingMode {
  BASIC_RESISTANCE = 0,
  TARGET_POWER = 1,
  TRACK_RESISTANCE = 2
} virtualShiftingModeType;

class SettingsManager {
 public:
  static void initialize(IotWebConf* iotWebConf);
  static uint16_t getChainringTeeth();
  static uint16_t getSprocketTeeth();
  static uint16_t getDifficulty();
  static void setChainringTeeth(uint16_t chainringTeeth);
  static void setSprocketTeeth(uint16_t sprocketTeeth);
  static void setDifficulty(uint16_t difficulty);
  static bool isVirtualShiftingEnabled();
  static bool isGradeSmoothingEnabled();
  static VirtualShiftingMode getVirtualShiftingMode();
  static void setVirtualShiftingMode(VirtualShiftingMode virtualShiftingMode);
  static std::map<size_t, std::string> getVirtualShiftingModes();
  static void setVirtualShiftingEnabled(bool enabled);
  static void setGradeSmoothingEnabled(bool enabled);
  static std::string getTrainerDeviceName();
  static void setTrainerDeviceName(std::string trainerDevice);
  static IotWebConfParameterGroup* getIoTWebConfSettingsParameterGroup();
  static std::string getUsername();
  static std::string getAPPassword();
  static bool isFTMSEnabled();
  static void setFTMSEnabled(bool enabled);
  static bool isAppDrivenGearsEnabled();
  static void setAppDrivenGearsEnabled(bool enabled);

 private:
  static char iotWebConfChainringTeethParameterValue[];
  static char iotWebConfSprocketTeethParameterValue[];
  static char iotWebConfVirtualShiftingModeParameterValue[];
  static char iotWebConfVirtualShiftingParameterValue[];
  static char iotWebConfTrainerDeviceParameterValue[];
  static char iotWebConfVirtualShiftingModeValues[][24];
  static char iotWebConfVirtualShiftingModeNames[][24];
  static char iotWebConfGradeSmoothingParameterValue[];
  static char iotWebConfDifficultyParameterValue[];
  static char iotWebConfFTMSParameterValue[];
  static char iotWebConfAppDrivenGearsParameterValue[];
  static IotWebConfParameterGroup iotWebConfSettingsGroup;
  static IotWebConfNumberParameter iotWebConfChainringTeethParameter;
  static IotWebConfNumberParameter iotWebConfSprocketTeethParameter;
  static IotWebConfSelectParameter iotWebConfVirtualShiftingModeParameter;
  static IotWebConfCheckboxParameter iotWebConfVirtualShiftingParameter;
  static IotWebConfTextParameter iotWebConfTrainerDeviceParameter;
  static IotWebConfCheckboxParameter iotWebConfGradeSmoothingParameter;
  static IotWebConfNumberParameter iotWebConfDifficultyParameter;
  static IotWebConfCheckboxParameter iotWebConfFTMSParameter;
  static IotWebConfCheckboxParameter iotWebConfAppDrivenGearsParameter;
  static IotWebConf* iotWebConf;
};

#endif
