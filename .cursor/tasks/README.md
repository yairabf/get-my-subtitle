# Task Documentation System

This directory contains all Epic and Task documentation created during feature development using Composer/Plan Mode.

## Directory Structure

```
.cursor/tasks/
└── [epic-name]/                           # Epic folder (kebab-case)
    └── [task-number]-[task-name]/         # Task folder (kebab-case)
        ├── [task-number]-[task-name]_plan.mdc      # Plan document (created BEFORE implementation)
        └── [task-number]-[task-name]_summary.mdc   # Summary document (created AFTER implementation)
```

## Naming Conventions

- **Epic Name**: Use kebab-case (e.g., `user-authentication`, `video-subtitle-sync`)
- **Task Number**: Use zero-padded numbers (e.g., `001`, `002`, `023`)
- **Task Name**: Use kebab-case (e.g., `login-flow`, `password-reset`, `api-integration`)

## Example Structure

```
.cursor/tasks/
├── user-authentication/
│   ├── 001-login-flow/
│   │   ├── 001-login-flow_plan.mdc
│   │   └── 001-login-flow_summary.mdc
│   ├── 002-password-reset/
│   │   ├── 002-password-reset_plan.mdc
│   │   └── 002-password-reset_summary.mdc
│   └── 003-oauth-integration/
│       ├── 003-oauth-integration_plan.mdc
│       └── 003-oauth-integration_summary.mdc
└── video-subtitle-sync/
    └── 001-timestamp-alignment/
        ├── 001-timestamp-alignment_plan.mdc
        └── 001-timestamp-alignment_summary.mdc
```

## Workflow

### 1. Starting a New Task (Plan Mode)

When starting a new feature in Composer/Plan Mode:

1. **Provide**: Epic name and Task number+name
   - Example: "Epic: User Authentication, Task: 001-login-flow"

2. **AI will**:
   - Check if `.cursor/tasks/[epic-name]/` exists
   - Create epic directory if needed
   - Create task directory: `.cursor/tasks/[epic-name]/[task-number]-[task-name]/`
   - Create plan document: `[task-number]-[task-name]_plan.mdc`

3. **Plan Document** contains:
   - Overview and problem statement
   - Architecture and component changes
   - Implementation steps
   - Testing strategy
   - Success criteria

### 2. During Implementation

- Follow the plan document
- Update plan if requirements change
- Document any deviations or discoveries

### 3. After Implementation (Summary)

1. **AI creates** summary document: `[task-number]-[task-name]_summary.mdc`

2. **Summary Document** contains:
   - What was actually implemented
   - Deviations from original plan
   - Testing results
   - Lessons learned
   - Next steps and follow-up tasks

## Benefits

✅ **Organized**: All task documentation in one place, grouped by epic  
✅ **Traceable**: Clear connection between planning and execution  
✅ **Historical**: Keep record of decisions and rationale  
✅ **Consistent**: Standardized structure across all features  
✅ **Searchable**: Easy to find documentation for any task

## Tips

- Use descriptive epic and task names
- Keep task scope focused (1 task = 1 feature/fix)
- Update plan if requirements change mid-implementation
- Always create summary after completion
- Reference task numbers in commit messages
- Link related tasks in summaries

## Quick Start

When starting a new task in Composer mode, simply say:

```
Epic: [epic-name]
Task: [number]-[task-name]

[Describe what you want to build]
```

The AI will automatically:
1. Check for epic directory
2. Create directories if needed
3. Create plan document with proper structure
4. Begin implementation planning

