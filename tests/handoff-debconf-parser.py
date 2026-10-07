#!/usr/bin/env python3
"""Exercise unmodified cdebconf parser functions, not a permissive mock.

Usage: python3 tests/handoff-debconf-parser.py /path/to/cdebconf/src/strutl.c
Fixtures are public parser examples, never installation credentials.
The exit status is nonzero if the required round-trip contract is unmet.
"""
import pathlib
import subprocess
import sys
import tempfile


def extract(source, signature):
    start = source.rfind('\n', 0, source.index(signature)) + 1
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def main():
    source = pathlib.Path(sys.argv[1]).read_text()
    code = '#include <stdio.h>\n#include <string.h>\n#include <ctype.h>\n'
    code += '#define STRESCAPE_QUOTE 1\n#define STRESCAPE_CAPB 2\n'
    code += '\n'.join(extract(source, signature) for signature in (
        'char *strstrip(', 'int strcmdsplit(', 'void strunescape('))
    code += r'''
int main(void) {
    char line[16384];
    while (fgets(line, sizeof(line), stdin)) {
        char *p = strstrip(line), *a[2] = {"", ""}, *b[2] = {"", ""};
        strunescape(p, p, strlen(p) + 1, STRESCAPE_CAPB);
        strcmdsplit(p, a, 2);
        strcmdsplit(a[1], b, 2);
        for (unsigned char *v = (unsigned char *)b[1]; *v; v++)
            printf("%02x", *v);
        puts("");
    }
}
'''
    fixtures = [
        ('ascii', 'abc', 'abc'),
        ('internal-space', 'a b', 'a b'),
        ('single-quote', "a'b", "a'b"),
        ('double-quote', 'a"b', 'a"b'),
        ('dollar', 'a$b', 'a$b'),
        ('percent', 'a%b', 'a%b'),
        ('backslash', r'a\\b', 'a\\b'),
        ('unicode', '测试', '测试'),
        ('long', 'a' * 1024, 'a' * 1024),
        ('leading-space', ' abc', ' abc'),
        ('trailing-space', 'abc ', 'abc '),
        ('escaped-leading-space', '\\ abc', ' abc'),
        ('escaped-trailing-space', 'abc\\ ', 'abc '),
    ]
    failed = []
    # All source/binary artifacts are temporary and contain only public fixtures.
    with tempfile.TemporaryDirectory(prefix='cdebconf-parser-') as work:
        cfile = pathlib.Path(work) / 'parser.c'
        exe = pathlib.Path(work) / 'parser'
        cfile.write_text(code)
        subprocess.run(['cc', '-o', str(exe), str(cfile)], check=True)
        for name, encoded, expected in fixtures:
            result = subprocess.run([str(exe)], input=(
                'SET partman-crypto/passphrase ' + encoded + '\n'
            ), text=True, capture_output=True, check=True)
            actual = bytes.fromhex(result.stdout.strip()).decode()
            # Whitespace fixtures document why the helper rejects these inputs.
            passed = (actual != expected) if 'leading-space' in name or 'trailing-space' in name else (actual == expected)
            print(('PASS ' if passed else 'FAIL ') + name)
            if not passed:
                failed.append(name)
    print(f'{len(fixtures) - len(failed)}/{len(fixtures)} round trips passed')
    return bool(failed)


if __name__ == '__main__':
    sys.exit(main())
