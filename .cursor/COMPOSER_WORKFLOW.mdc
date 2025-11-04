---
alwaysApply: true
---
# Composer/Plan Mode Workflow - Setup Complete ✅

# New Feature Plan Workflow

When you (the agent) receive a request to **create a plan for a new feature** via Plan Mode, you must follow this workflow:

1. ## What Was Implemented

A complete task documentation system for Composer/Plan Mode that automatically creates structured documentation for every feature you develop.

2. ## Directory Structure Created

```
.cursor/
├── coding_rule.mdc                    # ✅ Updated with new rules
├── tasks/                             # ✅ New directory
│   ├── README.md                      # ✅ Complete documentation
│   ├── QUICK_REFERENCE.md             # ✅ Quick start guide
│   └── _example-epic/                 # ✅ Example templates
│       └── 000-example-task/
│           ├── 000-example-task_plan.plan.md - the original plan file
│           └── 000-example-task_summary.md
└── COMPOSER_WORKFLOW.md               # ✅ This file
```
   - Write the generated plan and summary into those files.
## How It Works

### When You Start a New Task

**You say:**
```
Epic: user-authentication
Task: 001-login-flow

I need to implement user login with JWT tokens.
```

**AI automatically:**
1. ✅ Checks if `.cursor/tasks/user-authentication/` exists
2. ✅ Creates directory if needed (kebab-case)
3. ✅ Creates task folder: `001-login-flow/`
4. ✅ Creates plan document: `001-login-flow_plan.plan.md`
5. ✅ Fills it with structured content:
   - Overview
   - Architecture
   - Implementation steps
   - Testing strategy
   - Success criteria

### During Implementation

**AI follows:**
- The plan document structure
- Your coding standards
- TDD approach
- Updates plan if needed

### After Implementation

**AI creates:**
- Summary document: `001-login-flow_summary.md`
- Documents what was implemented
- Notes deviations from plan
- Records lessons learned
- Lists next steps

## File Naming Convention

| Component | Format | Example |
|-----------|--------|---------|
| Epic | kebab-case | `user-authentication` |
| Task Number | ###-name | `001-login-flow` |
| Plan File | `###-name_plan.plan.md` | `001-login-flow_plan.plan.md` |
| Summary File | `###-name_summary.md` | `001-login-flow_summary.md` |

## Complete Example Structure

```
.cursor/tasks/
├── user-authentication/              # Epic 1
│   ├── 001-login-flow/              # Task 1
│   │   ├── 001-login-flow_plan.plan.md
│   │   └── 001-login-flow_summary.md
│   ├── 002-password-reset/          # Task 2
│   │   ├── 002-password-reset_plan.plan.md
│   │   └── 002-password-reset_summary.md
│   └── 003-oauth-integration/       # Task 3
│       ├── 003-oauth-integration_plan.plan.md
│       └── 003-oauth-integration_summary.md
│
└── subtitle-translation/             # Epic 2
    ├── 001-language-detection/      # Task 1
    │   ├── 001-language-detection_plan.plan.md
    │   └── 001-language-detection_summary.md
    └── 002-improve-quality/         # Task 2
        ├── 002-improve-quality_plan.plan.md
        └── 002-improve-quality_summary.md
```

## Rules Added to Coding Standards

The following rules were added to `.cursor/coding_rule.mdc`:

### Rule 13: ALWAYS Follow Epic/Task Documentation Structure
- Checks for epic directory
- Creates directories if needed
- Uses kebab-case naming
- Creates plan before implementation

### Rule 14: Plan Document Structure
- Overview and problem statement
- Architecture and components
- Implementation steps
- API changes
- Testing strategy
- Success criteria

### Rule 15: Summary Document Structure
- What was implemented
- Deviations from plan
- Testing results
- Lessons learned
- Next steps

### Rule 16: Create Plan Document FIRST
- Before writing any code
- Get user approval
- Update if requirements change

### Rule 17: Create Summary Document LAST
- After implementation complete
- Document actual vs. planned
- Include lessons learned

## Benefits

✅ **Organized**: All tasks grouped by epic  
✅ **Traceable**: Clear plan → implementation → summary flow  
✅ **Historical**: Keep record of all decisions  
✅ **Consistent**: Same structure for every task  
✅ **Searchable**: Easy to find any task documentation  
✅ **Automatic**: AI handles all documentation creation

## Quick Start

Next time you use Composer/Plan Mode, just say:

```
Epic: [your-epic-name]
Task: [###-your-task-name]

[What you want to build]
```

That's it! The AI will handle the rest automatically.

## Documentation Files

- **Full Guide**: `.cursor/tasks/README.md`
- **Quick Reference**: `.cursor/tasks/QUICK_REFERENCE.md`
- **Example Plan**: `.cursor/tasks/_example-epic/000-example-task/000-example-task_plan.plan.md`
- **Example Summary**: `.cursor/tasks/_example-epic/000-example-task/000-example-task_summary.md`

## Git Integration

All task documentation is tracked in git (not excluded by `.gitignore`), so you have:
- Version history of all plans and summaries
- Ability to review past decisions
- Documentation that travels with your code

---

**Ready to use!** 🚀

Next time you're in Composer/Plan Mode, just provide your Epic and Task, and the system will automatically create all the documentation structure for you.

