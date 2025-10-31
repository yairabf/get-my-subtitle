# Task Documentation - Quick Reference

## Starting a New Task in Composer/Plan Mode

### What to Say

```
Epic: [epic-name]
Task: [###-task-name]

[Describe what you want to build]
```

### Example

```
Epic: subtitle-translation
Task: 001-add-language-detection

I need to add automatic language detection for subtitles before translation.
```

---

## What Happens Automatically

1. ✅ AI checks if `.cursor/tasks/subtitle-translation/` exists
2. ✅ Creates epic directory if needed
3. ✅ Creates task directory: `.cursor/tasks/subtitle-translation/001-add-language-detection/`
4. ✅ Creates plan document: `001-add-language-detection_plan.mdc`
5. ✅ Fills plan with structured content
6. ✅ After implementation, creates: `001-add-language-detection_summary.mdc`

---

## Naming Rules

| Element | Format | Example |
|---------|--------|---------|
| Epic Name | kebab-case | `user-authentication` |
| Task Number | Zero-padded | `001`, `023`, `105` |
| Task Name | kebab-case | `login-flow`, `password-reset` |
| Plan File | `###-name_plan.mdc` | `001-login-flow_plan.mdc` |
| Summary File | `###-name_summary.mdc` | `001-login-flow_summary.mdc` |

---

## Directory Structure

```
.cursor/tasks/
└── [epic-name]/                    # Epic (kebab-case)
    └── [###-task-name]/            # Task (number + kebab-case)
        ├── ###-task-name_plan.mdc     # Created BEFORE
        └── ###-task-name_summary.mdc  # Created AFTER
```

---

## Real Example

```
.cursor/tasks/
└── subtitle-translation/
    ├── 001-add-language-detection/
    │   ├── 001-add-language-detection_plan.mdc
    │   └── 001-add-language-detection_summary.mdc
    ├── 002-improve-translation-quality/
    │   ├── 002-improve-translation-quality_plan.mdc
    │   └── 002-improve-translation-quality_summary.mdc
    └── 003-add-caching-layer/
        ├── 003-add-caching-layer_plan.mdc
        └── 003-add-caching-layer_summary.mdc
```

---

## Workflow

### 1. Planning Phase
- **You say**: Epic + Task + Description
- **AI creates**: Plan document with structure
- **You review**: Approve or modify plan

### 2. Implementation Phase
- **AI implements**: Following the plan
- **AI updates**: Plan if needed

### 3. Summary Phase
- **AI creates**: Summary document
- **AI documents**: What was done, lessons learned

---

## Tips

✅ **Use descriptive names**: `add-user-authentication` not `auth`  
✅ **One task = one feature**: Keep scope focused  
✅ **Sequential numbers**: 001, 002, 003 (not 1, 2, 3)  
✅ **Review plan first**: Before implementation starts  
✅ **Check summary**: After implementation completes

---

## Common Patterns

### New Feature
```
Epic: feature-name
Task: 001-initial-implementation
```

### Bug Fix
```
Epic: bug-fixes
Task: 042-fix-subtitle-timing
```

### Refactoring
```
Epic: code-quality
Task: 015-refactor-event-system
```

### Infrastructure
```
Epic: devops
Task: 008-add-monitoring
```

---

## Need Help?

See `.cursor/tasks/README.md` for detailed documentation.

