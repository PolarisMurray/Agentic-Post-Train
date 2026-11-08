#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$ROOT/third_party"

while read -r name url sha; do
    [[ -z "${name:-}" || "$name" == \#* ]] && continue

    repo="$ROOT/third_party/$name"

    if [[ ! -d "$repo/.git" ]]; then
        git clone --depth 1 "$url" "$repo"
    fi

    if ! git -C "$repo" cat-file -e "$sha^{commit}" 2>/dev/null; then
        git -C "$repo" fetch --depth 1 origin "$sha"
    fi

    git -C "$repo" checkout --detach "$sha"

    echo "Pinned $name at $sha"

done < "$ROOT/third_party.lock"
