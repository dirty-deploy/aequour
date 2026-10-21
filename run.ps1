# Entry points:  .\run.ps1 test | attacks | eval | api
param([string]$Task = "test")
$py = if ($env:AEQUOUR_PY) { $env:AEQUOUR_PY } else { "python" }
switch ($Task) {
  "test"    { & $py -I -m unittest discover -s autosettle_engine/tests -t .; & $py -I -m unittest discover -s autosettle_api/tests -t . }
  "attacks" { & $py -m autosettle_engine.exploit_suite }
  "eval"    { & $py tools/eval_dev.py }
  "api"     { & $py -m autosettle_api @args }
  default   { Write-Host "usage: run.ps1 test|attacks|eval|api" }
}
