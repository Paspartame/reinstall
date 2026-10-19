#!/bin/sh
# Emit only fixed allowlisted mirror answers from the live Installer's own
# confmodule context. Must run synchronously: confmodule speaks on inherited
# stdin/stdout and background/redirected execution breaks that protocol.
CONSOLE=${DI_CONSOLE:-/dev/console}
if [ -n "${DI_CONFMODULE:-}" ]; then
    . "$DI_CONFMODULE"
else
    . /usr/share/debconf/confmodule
fi

emit_value() {
    key=$1
    question=$2
    case "$key" in
        country) allowed='manual';;
        hostname) allowed='deb.debian.org';;
        directory) allowed='/debian';;
        suite) allowed='trixie';;
    esac
    if db_get "$question"; then
        case "$RET" in
            "$allowed") printf 'S72_MIRROR_%s_VALUE_%s\n' "$key" "$RET" >>"$CONSOLE";;
            *) printf 'S72_MIRROR_%s_VALUE_UNKNOWN\n' "$key" >>"$CONSOLE";;
        esac
    else
        printf 'S72_MIRROR_%s_VALUE_UNKNOWN\n' "$key" >>"$CONSOLE"
    fi
    if db_fget "$question" seen; then
        case "$RET" in true|false) printf 'S72_MIRROR_%s_SEEN_%s\n' "$key" "$RET" >>"$CONSOLE";; *) printf 'S72_MIRROR_%s_SEEN_UNKNOWN\n' "$key" >>"$CONSOLE";; esac
    else
        printf 'S72_MIRROR_%s_SEEN_UNKNOWN\n' "$key" >>"$CONSOLE"
    fi
}
printf '%s\n' S72_MIRROR_DIAGNOSTIC_BEGIN >>"$CONSOLE"
emit_value country mirror/country
emit_value hostname mirror/http/hostname
emit_value directory mirror/http/directory
emit_value suite mirror/suite
printf '%s\n' S72_MIRROR_DIAGNOSTIC_DONE >>"$CONSOLE"
