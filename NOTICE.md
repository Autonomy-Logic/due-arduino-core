# NOTICE

This repository builds the `autonomylogic:sam` Arduino platform for the
Arduino Due. It does not vendor the upstream sources:
`tools/ci/build-release.py` downloads them at the version and SHA-256 digest
pinned in `tools/ci/upstream.json` and patches `platform.txt`.

## Upstream sources

| Component | Version | Source | Licence |
| --- | --- | --- | --- |
| ArduinoCore-sam (Arduino SAM Boards) | 1.6.12 | https://github.com/arduino/ArduinoCore-sam | Per-file headers (LGPL-2.1 for the Arduino core; Atmel and Arm parts under their own terms) |
| arm-none-eabi-gcc | 7-2017q4 | Arduino board manager index | GPL with the GCC runtime exception |
| bossac | 1.6.1-arduino | Arduino board manager index | BSD-3-Clause |

The toolchain and bossac are referenced from Arduino's board manager index at
their original URLs and are not redistributed here. Upstream files keep their
original copyright and licence headers.

## Changes made by this repository

- `platform.txt`: the compiler path names arm-none-eabi-gcc 7-2017q4, C++ is
  compiled with `-std=gnu++14 -fno-sized-deallocation`, and the platform name
  and version identify this build.
