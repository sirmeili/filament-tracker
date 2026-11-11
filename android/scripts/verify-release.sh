#!/usr/bin/env bash
# Checks a release APK before it is published (android/README.md, Releases): signed (v2 or
# later), RollCall's app ID, and the version and version code the tag asks for. Prints the
# signing certificate's SHA-256, which every release must share.
#
#   verify-release.sh <apk> <version, e.g. 1.2.3> [expected certificate SHA-256]
set -euo pipefail

apk=$1
version=$2
expected_cert=${3:-}

tools=$(ls -d "${ANDROID_HOME:?set ANDROID_HOME}"/build-tools/* | sort -V | tail -n 1)
aapt2=$tools/aapt2
apksigner=$tools/apksigner
# On Windows (Git Bash) the tools are aapt2.exe and apksigner.bat.
[[ -e $apksigner ]] || apksigner=$tools/apksigner.bat
IFS=. read -r major minor patch <<<"$version"
code=$((major * 10000 + minor * 100 + patch))

badging=$("$aapt2" dump badging "$apk" | head -n 1)
want="package: name='io.github.sirmeili.rollcall' versionCode='$code' versionName='$version'"
if [[ $badging != "$want"* ]]; then
  echo "unexpected package line: $badging" >&2
  echo "expected it to start with: $want" >&2
  exit 1
fi

signing=$("$apksigner" verify --verbose --print-certs "$apk" 2>&1 | tr -d '')
grep -q "Verified using v2 scheme (APK Signature Scheme v2): true" <<<"$signing" || {
  echo "not signed with APK Signature Scheme v2" >&2
  exit 1
}
# The signer's label differs between apksigner versions ("Signer #1", "Signer (minSdkVersion=…)").
cert=$(grep -m 1 -ioE 'certificate SHA-256 digest: [0-9a-f]{64}' <<<"$signing" | grep -oiE '[0-9a-f]{64}$' || true)
if [[ -z $cert ]]; then
  echo "no signing certificate found in apksigner's output (build-tools ${tools##*/}); its lines:" >&2
  sed -E 's/[0-9a-fA-F]{16,}/<hex>/g' <<<"$signing" >&2
  exit 1
fi
cert=${cert,,}
if [[ -n $expected_cert && $cert != "${expected_cert,,}" ]]; then
  echo "signed with an unexpected certificate: $cert" >&2
  exit 1
fi
echo "ok: io.github.sirmeili.rollcall $version ($code), certificate SHA-256 $cert"
