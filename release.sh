#!/usr/bin/env bash
# release.sh — froide-scheduler release-automaatio
#
# Käyttö:
#   ./release.sh 1.0.0
#   ./release.sh 1.0.0 --dry-run   (tulostaa mitä tapahtuisi, ei tee mitään)
#
# Edellytykset:
#   - gh CLI asennettu ja autentikoitu (gh auth login)
#   - git asennettu, working tree puhdas
#   - Ollaan repon juuressa
#   - main-branch on ajan tasalla (git pull)

set -euo pipefail

# ── Värit ──────────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${BLUE}▶${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET} $*"; }
error()   { echo -e "${RED}✗${RESET} $*" >&2; exit 1; }
step()    { echo -e "\n${BOLD}$*${RESET}"; }

# ── Argumentit ─────────────────────────────────────────────────────────────────
VERSION="${1:-}"
DRY_RUN=false
[[ "${2:-}" == "--dry-run" ]] && DRY_RUN=true

[[ -z "$VERSION" ]] && error "Anna versionumero: ./release.sh 1.0.0"

# Validoi semver-muoto
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
  || error "Versio '$VERSION' ei ole semver-muotoa (esim. 1.0.0)"

TAG="v${VERSION}"

$DRY_RUN && warn "DRY-RUN — ei oikeita muutoksia\n"

# ── Esitarkistukset ───────────────────────────────────────────────────────────────
step "1/7  Esitarkistukset"

command -v gh  &>/dev/null || error "gh CLI ei löydy. Asenna: https://cli.github.com"
command -v git &>/dev/null || error "git ei löydy"

# Autentikointi
gh auth status &>/dev/null || error "gh ei ole autentikoitu. Aja: gh auth login"

# Puhdas working tree
[[ -z "$(git status --porcelain)" ]] \
  || error "Working tree ei ole puhdas. Committaa tai stashaa muutokset ensin."

# Ollaan mainissa
CURRENT_BRANCH=$(git branch --show-current)
[[ "$CURRENT_BRANCH" == "main" ]] \
  || error "Täytyy olla main-branchissa (nyt: $CURRENT_BRANCH)"

# Tagi ei saa olla jo olemassa
git tag | grep -qx "$TAG" \
  && error "Tagi $TAG on jo olemassa"

# Haetaan uusin main
info "Haetaan origin/main..."
$DRY_RUN || git pull --ff-only origin main
success "main ajan tasalla"

# ── CI-tila ───────────────────────────────────────────────────────────────────────
step "2/7  Tarkistetaan CI-tila (main)"

CI_STATUS=$(gh api "repos/:owner/:repo/commits/main/status" --jq '.state' 2>/dev/null || echo "unknown")

if [[ "$CI_STATUS" == "failure" ]]; then
  error "CI epäonnistui main-branchissa. Korjaa testit ennen releasea."
elif [[ "$CI_STATUS" == "pending" ]]; then
  warn "CI on kesken. Odotetaan..."
  $DRY_RUN || gh run watch --exit-status \
    || error "CI epäonnistui odottamisen aikana"
elif [[ "$CI_STATUS" == "success" ]]; then
  success "CI vihreä"
else
  warn "CI-tilaa ei saatu ($CI_STATUS) — jatketaan"
fi

# ── Avoimet PR:t ───────────────────────────────────────────────────────────────
step "3/7  Tarkistetaan avoimet PR:t"

OPEN_PRS=$(gh pr list --base main --state open --json number,title 2>/dev/null || echo "[]")
PR_COUNT=$(echo "$OPEN_PRS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

if [[ "$PR_COUNT" -gt 0 ]]; then
  warn "$PR_COUNT avoin PR main-branchille:"
  echo "$OPEN_PRS" | python3 -c "
import sys, json
for pr in json.load(sys.stdin):
    print(f\"  #{pr['number']} {pr['title']}\")"
  echo ""
  read -r -p "Haluatko mergettää ne ennen releasea? [k/E] " MERGE_CONFIRM
  if [[ "$MERGE_CONFIRM" =~ ^[kK]$ ]]; then
    echo "$OPEN_PRS" | python3 -c "
import sys, json
for pr in json.load(sys.stdin):
    print(pr['number'])" | while read -r PR_NUM; do
      info "Mergetään PR #$PR_NUM..."
      $DRY_RUN || gh pr merge "$PR_NUM" --squash --auto \
        || warn "PR #$PR_NUM mergeäminen epäonnistui — ohitetaan"
    done
    $DRY_RUN || git pull --ff-only origin main
    success "PR:t mergetty"
  else
    info "Jatketaan ilman PR-mergejä"
  fi
else
  success "Ei avoimia PR:itä"
fi

# ── Versiopaivitys setup.py:ssä ────────────────────────────────────────────────────
step "4/7  Päivitetään versio setup.py → $VERSION"

SETUP_FILE="setup.py"
[[ -f "$SETUP_FILE" ]] || error "$SETUP_FILE ei löydy"

OLD_VERSION=$(grep -oP "version='\K[^']+" "$SETUP_FILE")
info "Vanha versio: $OLD_VERSION → uusi: $VERSION"

if $DRY_RUN; then
  warn "[dry-run] sed -i \"s/version='$OLD_VERSION'/version='$VERSION'/\" $SETUP_FILE"
else
  sed -i "s/version='$OLD_VERSION'/version='$VERSION'/" "$SETUP_FILE"
  grep "version=" "$SETUP_FILE" | grep -q "$VERSION" \
    || error "Versiopaivitys epäonnistui setup.py:ssä"
  success "setup.py päivitetty"
fi

# ── CHANGELOG.md ────────────────────────────────────────────────────────────────────────
step "5/7  Päivitetään CHANGELOG.md"

TODAY=$(date +%Y-%m-%d)
CHANGELOG_FILE="CHANGELOG.md"

# Kerätään commitit edellisestä tagista
PREV_TAG=$(git tag --sort=-version:refname | head -1 2>/dev/null || echo "")
if [[ -n "$PREV_TAG" ]]; then
  info "Muutokset $PREV_TAG → HEAD:"
  COMMITS=$(git log "${PREV_TAG}..HEAD" --oneline --no-merges 2>/dev/null || echo "")
else
  info "Ei aiempaa tagia — kerätään kaikki commitit:"
  COMMITS=$(git log --oneline --no-merges 2>/dev/null || echo "")
fi

NEW_ENTRY="## [$VERSION] - $TODAY\n"
if [[ -n "$COMMITS" ]]; then
  while IFS= read -r line; do
    NEW_ENTRY+="- $line\n"
  done <<< "$COMMITS"
else
  NEW_ENTRY+="- Ensimmäinen julkaistu versio\n"
fi

if $DRY_RUN; then
  warn "[dry-run] Lisättäisiin CHANGELOG.md:hen:\n$NEW_ENTRY"
else
  if [[ -f "$CHANGELOG_FILE" ]]; then
    HEADER=$(head -3 "$CHANGELOG_FILE")
    REST=$(tail -n +4 "$CHANGELOG_FILE")
    printf "%s\n\n%b\n%s\n" "$HEADER" "$NEW_ENTRY" "$REST" > "$CHANGELOG_FILE"
  else
    printf "# Changelog\n\nKaikki merkittävät muutokset dokumentoidaan tässä tiedostossa.\n\n%b\n" "$NEW_ENTRY" > "$CHANGELOG_FILE"
  fi
  success "CHANGELOG.md päivitetty"
fi

# ── Git commit + tagi ────────────────────────────────────────────────────────────────────
step "6/7  Commitataan ja tagataan $TAG"

if $DRY_RUN; then
  warn "[dry-run] git add setup.py $CHANGELOG_FILE"
  warn "[dry-run] git commit -m \"chore: release $TAG\""
  warn "[dry-run] git tag -a $TAG -m \"Release $TAG\""
  warn "[dry-run] git push origin main --tags"
else
  git add "$SETUP_FILE" "$CHANGELOG_FILE"
  git commit -m "chore: release $TAG"
  git tag -a "$TAG" -m "Release $TAG"
  git push origin main
  git push origin "$TAG"
  success "Commitattu ja tagattu $TAG"
fi

# ── GitHub Release ────────────────────────────────────────────────────────────────────
step "7/7  Luodaan GitHub Release $TAG"

RELEASE_NOTES=$(printf "%b" "$NEW_ENTRY")

if $DRY_RUN; then
  warn "[dry-run] gh release create $TAG --title \"$TAG\" --notes \"...\""
else
  gh release create "$TAG" \
    --title "$TAG" \
    --notes "$RELEASE_NOTES" \
    --latest
  success "GitHub Release luotu: $(gh release view \"$TAG\" --json url --jq '.url')"
fi

# ── Valmis ──────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}${BOLD}  Release $TAG valmis!${RESET}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
$DRY_RUN && echo -e "${YELLOW}  (dry-run — ei oikeita muutoksia tehty)${RESET}"
