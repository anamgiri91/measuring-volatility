#!/usr/bin/env bash
# usage: launch.sh script.py tag sample...
S=$(cd "$(dirname "$0")" && pwd)
cd "$S/../.."
script=$1; tag=$2; shift 2
for name in "$@"; do
  slug=$(echo "$name" | tr ' ' '_')
  nohup python "$S/$script" "$name" > "$S/../../output/dev_anam2/out_${tag}_${slug}.log" 2>&1 &
done
