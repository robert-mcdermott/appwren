#!/bin/sh
# Start AppWren in a container. Safe to run every time: `init` creates what is missing,
# brings the database up to date, and creates the first administrator, the organization's
# top unit, and the program only if there are none.
set -eu

set -- init
if [ -n "${APPWREN_ORGANIZATION:-}" ]; then
    set -- "$@" --organization "$APPWREN_ORGANIZATION"
fi
if [ -n "${APPWREN_PROGRAM:-}" ]; then
    set -- "$@" --program "$APPWREN_PROGRAM"
fi
if [ -n "${APPWREN_ADMIN_EMAIL:-}" ] && [ -n "${APPWREN_ADMIN_PASSWORD:-}" ]; then
    printf '%s' "$APPWREN_ADMIN_PASSWORD" | appwren "$@" \
        --admin-email "$APPWREN_ADMIN_EMAIL" \
        --admin-name "${APPWREN_ADMIN_NAME:-Administrator}" \
        --password-stdin
else
    appwren "$@" </dev/null
fi
unset APPWREN_ADMIN_PASSWORD
exec appwren serve
