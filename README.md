# Arduino Due core with C++14 (`autonomylogic:sam`)

Arduino's official SAM core for the Arduino Due, built with a newer Arm GCC so
sketches compile as C++14. The official `arduino:sam` core pins
arm-none-eabi-gcc 4.8.3 and builds as C++11, which cannot compile the C++14
code the OpenPLC Editor generates. The OpenPLC Editor installs this platform
through the `boardManagerUrl` of the `com.openplc.arduino` board package.

| | |
| --- | --- |
| Board manager URL | `https://raw.githubusercontent.com/Autonomy-Logic/due-arduino-core/main/package_autonomylogic_sam_index.json` |
| FQBN | `autonomylogic:sam:arduino_due_x` (Native USB Port), `autonomylogic:sam:arduino_due_x_dbg` (Programming Port) |
| Toolchain | arm-none-eabi-gcc `7-2017q4` and bossac `1.6.1-arduino`, from Arduino's own index |
| Licence | Build scripts GPL-3.0 (`LICENSE`); the core keeps its upstream licences (see `NOTICE.md`) |

## Install and use

```
URL=https://raw.githubusercontent.com/Autonomy-Logic/due-arduino-core/main/package_autonomylogic_sam_index.json
arduino-cli core update-index --additional-urls "$URL"
arduino-cli core install autonomylogic:sam --additional-urls "$URL"
arduino-cli compile -b autonomylogic:sam:arduino_due_x <sketch>
arduino-cli upload  -b autonomylogic:sam:arduino_due_x -p <serial port> <sketch>
```

The architecture stays `sam`, so `ARDUINO_ARCH_SAM` and libraries written for
the Due work unchanged.

## What differs from `arduino:sam`

Only `platform.txt`, patched by `tools/ci/build-release.py`:

- `compiler.path` uses arm-none-eabi-gcc `7-2017q4` (the toolchain of Arduino's
  SAMD core) instead of `4.8.3-2014q1`;
- C++ builds with `-std=gnu++14 -fno-sized-deallocation` instead of
  `-std=gnu++11` (the core links no C++ standard library, so sized `delete` is
  turned off);
- `name` and `version` name this platform.

## Layout

| Path | Purpose |
| --- | --- |
| `tools/ci/upstream.json` | pinned upstream core archive and the toolchain it depends on |
| `tools/ci/build-release.py` | builds the platform archive and the index |
| `tools/ci/localize-index.py` | points an index at a local server for pre-release tests |
| `tools/ci/verify-index.py` | checks every asset of a published index |
| `tools/ci/sketches/due_smoke/` | compile check for C++14 and linking |
| `package_autonomylogic_sam_index.json` | board manager index, written by the release workflow |

## Build a release locally

Needs Python 3.12+.

```
tools/ci/build-release.py --version 0.1.0 --out dist
```

`dist/` then holds `autonomylogic-sam-0.1.0.tar.bz2` and
`package_autonomylogic_sam_index.json`, with URLs pointing at the GitHub
release `v0.1.0`. Downloads are cached in `build/`.

To install the result before publishing it, serve `dist/` and repoint a copy
of the index:

```
(cd dist && python3 -m http.server 8765 --bind 127.0.0.1) &
cp dist/package_autonomylogic_sam_index.json /tmp/index-local.json
tools/ci/localize-index.py /tmp/index-local.json http://127.0.0.1:8765
arduino-cli core update-index --additional-urls file:///tmp/index-local.json
arduino-cli core install autonomylogic:sam@0.1.0 --additional-urls file:///tmp/index-local.json
arduino-cli compile -b autonomylogic:sam:arduino_due_x tools/ci/sketches/due_smoke
```

## Branches

Work lands on `development` through pull requests; releases are merged to
`main` and tagged `v<version>`.
