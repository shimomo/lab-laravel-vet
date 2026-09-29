#!/bin/sh
# Re-run Vet's review with a real coding agent. Run it in your own terminal, where `claude` is logged in.
#   sh agent-demo.sh 1.0.1   # autoload.files injection (the laravel-lang pattern)
#   sh agent-demo.sh 1.1.0   # changes only config/ and dist/ (outside every autoload rule)
. "$(dirname "$0")/env.sh"
cd "$S" || exit 1
python3 serve.py 8443 "$S/repo" "$S/ca/server.pem" "$S/ca/server.key" "$S/logs/server.log" > /dev/null 2>&1 &
echo $! > "$S/logs/serve.pid"
sleep 1
python3 build_repo.py baseline
cd "$S/app" || exit 1
composer require "vetlab/widget:1.0.0" --no-update --no-interaction > /dev/null 2>&1
composer update vetlab/widget --no-interaction > /dev/null 2>&1
composer require "vetlab/widget:${1:-1.0.1}" --no-update --no-interaction > /dev/null 2>&1
composer update vetlab/widget --no-interaction > /dev/null 2>&1
echo
echo "Pending: vetlab/widget 1.0.0 -> ${1:-1.0.1}. Review it with your agent:"
echo "  cd $S/app && . $S/env.sh && ./vendor/bin/vet"
echo "Stop the server afterwards:"
echo "  kill \$(cat $S/logs/serve.pid)"
