# Local GitHub & Push Workflow

Reference for the commands used to initialize, reset, and push this
repository to `https://github.com/open-evidence-ar/btc-cycles.git`.

## 1. Credentials (.env)

Copied from `C:\Users\German\Desktop\state-vs-family-evidence\.env` (same
`PAT=ghp_...`). File is `.gitignore`-d at `D:\trading\.gitignore:10`.

```bash
# Copy
Copy-Item "C:\Users\German\Desktop\state-vs-family-evidence\.env" "D:\trading\.env"
# Confirm ignored
git check-ignore -v .env
```

## 2. Repo-local identity

Matches the other evidence project (`state-vs-family-evidence`).

```bash
git config user.name "open-evidence-ar"
git config user.email "dr.alf.martin@gmail.com"
```

## 3. Fresh orphan init commit (current working tree as single baseline)

Used when resetting history so only one init commit remains (previous
~19 I-n commits pruned):

```bash
# Create orphan branch from current tree
git checkout --orphan init-orphan
# Clear index and stage current tree
git rm -rf --cached .
git add -A
# Commit single root
git commit -m "init: Bitcoin Halving-Cycle Framework (single baseline)"
# Replace main with init commit
git branch -f main init-orphan
git branch -D init-orphan
# Prune dangling history
git reflog expire --expire=now --all
git gc --prune=now
```

## 4. Remote setup (clean URL — no embedded PAT)

```bash
git remote add origin https://github.com/open-evidence-ar/btc-cycles.git
git remote -v
```

## 5. Push with PAT (no interactive TTY, no history leakage)

Per `agents/daily-commands.md:84-101`. Uses `GIT_ASKPASS` so the PAT
never lands in PowerShell `Get-History` or the remote URL permanently.

```powershell
# Read PAT (gitignored .env)
$pat = (Get-Content .env | Select-String "PAT=(.+)" | % { $_.Matches.Groups[1].Value }).Trim()

# Create batch askpass (git executes this; echoes password)
$askpass = "C:\Users\German\AppData\Local\Temp\opencode\askpass.cmd"
Set-Content -Path $askpass -Value "@echo off`necho $pat"

# Configure environment
$env:GIT_ASKPASS = $askpass
$env:GIT_TERMINAL_PROMPT = "0"

# Temporarily set remote with inline PAT for HTTPS auth
git remote set-url origin "https://open-evidence-ar:${pat}@github.com/open-evidence-ar/btc-cycles.git"

# Push
git push -u origin main

# Restore clean URL (no embedded token in remote config)
git remote set-url origin "https://github.com/open-evidence-ar/btc-cycles.git"
```

Cleanup: delete `$askpass` file after push.

## 6. GitHub Pages enablement (repo-level setting)

Before the first deploy workflow run, the `actions/configure-pages@v5` step
fails with `Get Pages site failed` unless Pages is configured (see
`docs/blockers/I-20-predictive-gates-failed.md` analysis). Enabled via the
GitHub REST API (`POST /repos/open-evidence-ar/btc-cycles/pages` with
`{"build_type":"workflow"}`) using the `.env` PAT.

```powershell
# Enable via API (read .env PAT)
$pat = (Get-Content .env | Select-String "PAT=(.+)" | % { $_.Matches.Groups[1].Value }).Trim()
$h = @{ Authorization = "token $pat"; Accept = "application/vnd.github+json" }
Invoke-RestMethod -Method Post -Uri "https://api.github.com/repos/open-evidence-ar/btc-cycles/pages" -Headers $h -ContentType "application/json" -Body '{"build_type":"workflow"}'
```

## 7. Line-ending normalization (.gitattributes)

Without `*.csv text eol=lf` (missing from initial init), `core.autocrlf=true`
creates a mismatch between manifest hashes (computed from CRLF working
copies) and the LF blobs stored by git / checked out by CI Linux runners.
Fixed by adding `.gitattributes` (mirroring the working evidence project)
and normalizing.

```bash
# After writing .gitattributes (see .gitattributes in repo)
git add --renormalize .
# Commit normalized LF state; regenerate manifest hashes accordingly
```

## 8. Quick verification commands

```bash
git status
git log --oneline --all
git remote -v
git check-ignore -v .env
bundle exec jekyll build         # site build check
pytest -q tests/                 # full gate suite
```

---
*References: `AGENTS.md` (workflow rules); `DESIGN.md` §5-§9 (increment gates);
`docs/blockers/I-20-predictive-gates-failed.md` (Pages setup failure analysis);
`docs/open-questions.md` (future increments); `agents/daily-commands.md` (original
PAT push method).*
