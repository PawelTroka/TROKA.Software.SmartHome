#!/usr/bin/env bash
set -eu

printf '%s\n' \
  'ERROR: this legacy scratch script is retired and performs no storage changes.' \
  'Its hard-coded /dev/sdc and /dev/sda1 commands were inconsistent and unsafe.' \
  'Use the reviewed, identity-pinned procedure in ops/storage/README.md.' >&2
exit 64
