#!/usr/bin/env sh
# Entry points:  ./run.sh demo | test | attacks | eval | api | smoke      (set AEQUOUR_PY to pick a Python)
PY="${AEQUOUR_PY:-python3}"
cd "$(dirname "$0")" || exit 1
task="${1:-test}"
[ $# -gt 0 ] && shift
case "$task" in
  demo)    "$PY" -m autosettle_api --fresh-seen "$@" ;;
  test)    "$PY" -m unittest discover -s autosettle_engine/tests -t . && "$PY" -m unittest discover -s autosettle_api/tests -t . ;;
  attacks) "$PY" -m autosettle_engine.exploit_suite ;;
  eval)    "$PY" tools/eval_dev.py ;;
  api)     "$PY" -m autosettle_api "$@" ;;
  smoke)   "$PY" tools/smoke.py ;;
  *)       echo "usage: ./run.sh demo|test|attacks|eval|api|smoke"; exit 2 ;;
esac
