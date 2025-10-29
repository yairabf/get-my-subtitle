# CI/CD Flow Diagram

## Complete CI/CD Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Developer Workflow                          │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
        ┌────────────────────┐        ┌────────────────────┐
        │   Local Changes    │        │  Run make check    │
        │   - Edit code      │───────▶│  - format          │
        │   - Add tests      │        │  - lint            │
        └────────────────────┘        │  - test-unit       │
                                      │  - test-cov        │
                                      └────────────────────┘
                                               │
                                               │ All pass? ✅
                                               ▼
                                      ┌────────────────────┐
                                      │  Git commit & push │
                                      │  to feature branch │
                                      └────────────────────┘
                                               │
                                               │
┌──────────────────────────────────────────────┴───────────────────────────────┐
│                           GitHub Actions Triggered                           │
└──────────────────────────────────────────────────────────────────────────────┘
                                               │
                           ┌───────────────────┴───────────────────┐
                           │                                       │
                           ▼                                       ▼
                  ┌─────────────────┐                   ┌─────────────────┐
                  │   CI Workflow   │                   │  Lint Workflow  │
                  │    (ci.yml)     │                   │   (lint.yml)    │
                  └─────────────────┘                   └─────────────────┘
                           │                                       │
        ┌──────────────────┼──────────────────┐                  │
        │                  │                  │         ┌─────────┼─────────┐
        ▼                  ▼                  ▼         ▼                   ▼
   ┌────────┐         ┌────────┐        ┌────────┐  ┌────────┐       ┌────────┐
   │  Lint  │         │  Test  │        │Coverage│  │ Black  │       │ isort  │
   │ Job    │         │  Job   │        │  Job   │  │  Job   │       │  Job   │
   │        │         │(Matrix)│        │        │  │        │       │        │
   │ ~30s   │         │ ~2-3m  │        │ ~2-3m  │  │ ~15s   │       │ ~15s   │
   └────────┘         └────────┘        └────────┘  └────────┘       └────────┘
        │                  │                  │         │                   │
        │                  │                  │         │                   │
        ▼                  ▼                  ▼         ▼                   ▼
   ┌────────┐         ┌────────┐        ┌────────┐  ┌────────┐       ┌────────┐
   │ ✅ or ❌│         │ ✅ or ❌│        │ ✅ or ❌│  │ ✅ or ❌│       │ ✅ or ❌│
   └────────┘         └────────┘        └────────┘  └────────┘       └────────┘
        │                  │                  │
        │                  │                  └──────────┐
        │                  ▼                             │
        │         ┌────────────────┐                     │
        │         │  Integration   │                     │
        │         │   Test Job     │                     │
        │         │  with Redis &  │                     │
        │         │   RabbitMQ     │                     │
        │         │    ~4-5m       │                     │
        │         └────────────────┘                     │
        │                  │                             │
        │                  ▼                             │
        │         ┌────────────────┐                     │
        │         │  Build Check   │                     │
        │         │   Job (All     │                     │
        │         │   Services)    │                     │
        │         │    ~3-4m       │                     │
        │         └────────────────┘                     │
        │                  │                             │
        └──────────────────┴─────────────────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Status Check   │
                  │      Job        │
                  │   (Aggregate)   │
                  └─────────────────┘
                           │
                ┌──────────┴──────────┐
                │                     │
                ▼                     ▼
        ┌──────────────┐      ┌──────────────┐
        │   All Pass   │      │  Any Failed  │
        │      ✅      │      │      ❌      │
        └──────────────┘      └──────────────┘
                │                     │
                │                     └─────────────────┐
                │                                       │
                ▼                                       ▼
        ┌──────────────────────┐           ┌──────────────────────┐
        │   Create/Update PR   │           │    CI Failed         │
        │                      │           │  - Check logs        │
        │  • Coverage comment  │           │  - Fix issues        │
        │  • Status checks ✅  │           │  - Push fixes        │
        │  • Ready for review  │           │  - Re-run CI         │
        └──────────────────────┘           └──────────────────────┘
                │                                       │
                │                                       │
                ▼                                       │
        ┌──────────────────────┐                      │
        │   Code Review        │◄─────────────────────┘
        │                      │
        │  • Review changes    │
        │  • Check coverage    │
        │  • Approve/Request   │
        │    changes           │
        └──────────────────────┘
                │
                │ Approved ✅
                ▼
        ┌──────────────────────┐
        │  Branch Protection   │
        │  Checks:             │
        │  ✅ CI passed        │
        │  ✅ Review approved  │
        │  ✅ Up to date      │
        │  ✅ Conversations   │
        │     resolved         │
        └──────────────────────┘
                │
                │ All satisfied ✅
                ▼
        ┌──────────────────────┐
        │   Merge to main/     │
        │     develop          │
        │                      │
        │  🎉 Success!         │
        └──────────────────────┘
```

## CI Workflow Detailed Breakdown

```
┌───────────────────────────────────────────────────────────────┐
│                        CI Workflow                            │
│                        (ci.yml)                               │
└───────────────────────────────────────────────────────────────┘

Job 1: Lint                                     Duration: ~30s
┌────────────────────────────────────────────────────────────┐
│  1. Checkout code                                          │
│  2. Setup Python 3.11                                      │
│  3. Install: black, isort                                  │
│  4. Run: black --check --diff .                            │
│  5. Run: isort --check-only --diff .                       │
│  ────────────────────────────────────────────────────────  │
│  Output: ✅ Pass or ❌ Fail with diff                      │
└────────────────────────────────────────────────────────────┘

Job 2: Test (Matrix)                           Duration: ~2-3m
┌────────────────────────────────────────────────────────────┐
│  Matrix: [Python 3.11, Python 3.12]                       │
│  ────────────────────────────────────────────────────────  │
│  For each Python version:                                  │
│  1. Checkout code                                          │
│  2. Setup Python (with pip cache)                          │
│  3. Install: requirements.txt                              │
│  4. Run: pytest tests/ -m "unit" -v                        │
│  5. Upload: Test results artifact                          │
│  ────────────────────────────────────────────────────────  │
│  Output: ✅ Tests pass or ❌ Tests fail                    │
└────────────────────────────────────────────────────────────┘

Job 3: Coverage                                Duration: ~2-3m
┌────────────────────────────────────────────────────────────┐
│  1. Checkout code                                          │
│  2. Setup Python 3.11 (with pip cache)                     │
│  3. Install: requirements.txt                              │
│  4. Run: pytest with --cov flags                           │
│     • Coverage for: common, manager, downloader,           │
│       translator                                           │
│     • Reports: XML, HTML, terminal                         │
│     • Minimum: 70%                                         │
│  5. Upload to Codecov                                      │
│  6. Comment on PR with coverage info                       │
│  7. Upload: Coverage artifacts (14 days)                   │
│  ────────────────────────────────────────────────────────  │
│  Output: ✅ Coverage ≥70% or ❌ Coverage <70%              │
└────────────────────────────────────────────────────────────┘

Job 4: Integration Test                        Duration: ~4-5m
┌────────────────────────────────────────────────────────────┐
│  Services Started:                                         │
│  • Redis 7 (alpine)                                        │
│  • RabbitMQ 3 (management-alpine)                          │
│  ────────────────────────────────────────────────────────  │
│  1. Checkout code                                          │
│  2. Setup Python 3.11 (with pip cache)                     │
│  3. Install: requirements.txt                              │
│  4. Wait for services (health checks)                      │
│  5. Run: pytest tests/integration/ -v                      │
│  6. Upload: Integration test results (7 days)              │
│  ────────────────────────────────────────────────────────  │
│  Output: ✅ Integration tests pass or ❌ Fail              │
└────────────────────────────────────────────────────────────┘

Job 5: Build Check                             Duration: ~3-4m
┌────────────────────────────────────────────────────────────┐
│  1. Checkout code                                          │
│  2. Setup Docker Buildx                                    │
│  3. Build: Manager Docker image                            │
│     • Context: .                                           │
│     • Dockerfile: manager/Dockerfile                       │
│     • Cache: GitHub Actions cache                          │
│  4. Build: Downloader Docker image                         │
│     • Context: .                                           │
│     • Dockerfile: downloader/Dockerfile                    │
│     • Cache: GitHub Actions cache                          │
│  5. Build: Translator Docker image                         │
│     • Context: .                                           │
│     • Dockerfile: translator/Dockerfile                    │
│     • Cache: GitHub Actions cache                          │
│  ────────────────────────────────────────────────────────  │
│  Output: ✅ All builds succeed or ❌ Build fails           │
└────────────────────────────────────────────────────────────┘

Job 6: Status Check                            Duration: ~5s
┌────────────────────────────────────────────────────────────┐
│  Depends on: [lint, test, coverage, integration, build]   │
│  ────────────────────────────────────────────────────────  │
│  1. Check all previous job results                         │
│  2. If any failed: Exit 1 ❌                               │
│  3. If all passed: Exit 0 ✅                               │
│  ────────────────────────────────────────────────────────  │
│  Output: ✅ All CI passed or ❌ CI failed                  │
└────────────────────────────────────────────────────────────┘
```

## Lint Workflow Detailed Breakdown

```
┌───────────────────────────────────────────────────────────────┐
│                      Lint Workflow                            │
│                      (lint.yml)                               │
└───────────────────────────────────────────────────────────────┘

Job 1: Black Formatter                         Duration: ~15s
┌────────────────────────────────────────────────────────────┐
│  1. Checkout code                                          │
│  2. Setup Python 3.11                                      │
│  3. Install: black==24.10.0                                │
│  4. Run: black --check --diff --color .                    │
│  5. If failed: Post PR comment with fix instructions       │
│  ────────────────────────────────────────────────────────  │
│  Output: ✅ Formatting OK or ❌ Needs formatting           │
└────────────────────────────────────────────────────────────┘

Job 2: isort Import Sorting                    Duration: ~15s
┌────────────────────────────────────────────────────────────┐
│  1. Checkout code                                          │
│  2. Setup Python 3.11                                      │
│  3. Install: isort==5.13.2                                 │
│  4. Run: isort --check-only --diff --color .               │
│  5. If failed: Post PR comment with fix instructions       │
│  ────────────────────────────────────────────────────────  │
│  Output: ✅ Imports sorted or ❌ Needs sorting             │
└────────────────────────────────────────────────────────────┘

Job 3: Pylint (Optional)                       Duration: ~1-2m
┌────────────────────────────────────────────────────────────┐
│  Continue-on-error: true (doesn't block CI)                │
│  ────────────────────────────────────────────────────────  │
│  1. Checkout code                                          │
│  2. Setup Python 3.11                                      │
│  3. Install: requirements.txt + pylint==3.0.3              │
│  4. Run: pylint --rcfile=.pylintrc (all services)          │
│  5. Upload: Pylint report artifact (7 days)                │
│  ────────────────────────────────────────────────────────  │
│  Output: ⚠️ Warnings only (never fails)                    │
└────────────────────────────────────────────────────────────┘
```

## Timing Breakdown

```
Total CI/CD Runtime: ~6-8 minutes (with parallel execution)

┌─────────────────────────────────────────────────────────────┐
│                    Parallel Execution                       │
└─────────────────────────────────────────────────────────────┘

Time    0s    1m    2m    3m    4m    5m    6m    7m    8m
        │     │     │     │     │     │     │     │     │
Lint    ████
        │
Test    █████████
        │
Coverage█████████
        │
Integ   ████████████████████
        │
Build   ████████████████
        │
Status                                              █
        │     │     │     │     │     │     │     │     │
        └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘
        
Legend: █ = Job running
```

## Branch Protection Flow

```
┌────────────────────────────────────────────────────────────┐
│              Branch Protection Requirements                │
└────────────────────────────────────────────────────────────┘

                    Pull Request Created
                            │
                            ▼
              ┌─────────────────────────┐
              │  Required Status Checks │
              └─────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
   ┌────────┐         ┌────────┐         ┌────────┐
   │   CI   │         │  Lint  │         │ Tests  │
   │ Status │         │  Pass  │         │  Pass  │
   │  ✅    │         │   ✅   │         │   ✅   │
   └────────┘         └────────┘         └────────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │   Review Required       │
              │   • 1 approval needed   │
              │   • ✅ Approved         │
              └─────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │   Branch Up-to-date     │
              │   • ✅ Current          │
              └─────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │ Conversations Resolved  │
              │   • ✅ All resolved     │
              └─────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │   🎉 Ready to Merge!    │
              │   Merge button enabled  │
              └─────────────────────────┘
```

## Dependabot Flow

```
┌────────────────────────────────────────────────────────────┐
│                  Dependabot Workflow                       │
└────────────────────────────────────────────────────────────┘

Every Monday @ 09:00
        │
        ▼
┌─────────────────────┐
│  Dependabot Checks  │
│  • Python deps      │
│  • GitHub Actions   │
│  • Docker images    │
└─────────────────────┘
        │
        ├── No updates needed ─────────────────┐
        │                                      │
        └── Updates available                 │
                 │                            │
                 ▼                            │
        ┌─────────────────────┐               │
        │  Create PRs         │               │
        │  • One per update   │               │
        │  • Auto-labeled     │               │
        │  • Auto-assigned    │               │
        └─────────────────────┘               │
                 │                            │
                 ▼                            │
        ┌─────────────────────┐               │
        │  CI Runs on PRs     │               │
        │  • All checks       │               │
        │  • Validates update │               │
        └─────────────────────┘               │
                 │                            │
        ┌────────┴────────┐                  │
        │                 │                  │
        ▼                 ▼                  │
   ┌────────┐        ┌────────┐              │
   │ CI ✅  │        │ CI ❌  │              │
   └────────┘        └────────┘              │
        │                 │                  │
        ▼                 ▼                  │
   ┌────────┐        ┌────────┐              │
   │ Review │        │ Needs  │              │
   │   &    │        │  Fix   │              │
   │ Merge  │        │   ⚠️   │              │
   └────────┘        └────────┘              │
        │                                    │
        └────────────────────────────────────┘
                       │
                       ▼
              Dependencies Updated! 🎉
```

---

**Note**: This diagram represents the complete CI/CD flow from developer changes to successful merge. All jobs run in parallel where possible to minimize total runtime.

