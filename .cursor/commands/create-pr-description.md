---
alwaysApply: true
---

# Cursor Rules for PR Template Generation (with Automatic PR Description Push)

## Context
This project uses a standardized Pull Request template format to ensure consistency and thorough documentation of changes.

## PR Template Structure
When creating or reviewing pull requests, always use this exact template format:

## The Issue
Describe the issue that you're solving here. If there is a related issue, please link it here.

## Root Cause
Describe the root cause of the issue here. If needed, paste code and images here.

## The Solution
Describe how to solve this case, and how the PR will solve it.

## Testing
- [ ] I have tested this PR on my local machine.
- [ ] I have added unitests for the changes I made.

## Additional Changes
- [ ] Docs changed
- [ ] UI Changed
- [ ] Config Changed
- [ ] Other

---

## Guidelines for Each Section

### The Issue
- Clearly describe what problem is being solved
- Link to related GitHub/Jira issues using proper format (#123 or JIRA-456)
- Be specific about user impact or business value
- Include error messages or unexpected behaviors if applicable

### Root Cause
- Explain why the issue exists
- Include relevant code snippets showing the problem
- Add screenshots or diagrams if they help explain the issue
- Reference specific files, functions, or components involved

### The Solution
- Describe the approach taken to fix the issue
- Explain why this solution was chosen over alternatives
- Highlight key changes to the codebase
- Include code samples if helpful

### Testing
- Always check the first checkbox if tested locally
- Always check the second checkbox if unit tests were added
- Add bullet points for additional testing details
- Include covered test scenarios

### Additional Changes
- Check all applicable boxes
- If “Other” is checked, specify what changed
- Include impacts on docs, UI, config, dependencies, etc.

---

## Code Review Focus Areas
When reviewing PRs with this template:
1. Verify all template sections are properly filled out
2. Ensure the root cause explanation is correct and detailed
3. Check that the solution fully addresses the issue
4. Confirm the testing checkboxes and scenarios are accurate
5. Validate that additional changes are clearly documented

---

## Auto-completion Hints
- Use **"Fixes #123"** or **"Closes #123"** for automatic issue linking
- Include before/after code in Root Cause when helpful
- Reference specific commit SHAs when needed
- Use proper markdown code blocks and list formatting

---

## PR Automation Behavior

### 1. Detect the existing pull request automatically
- Identify the PR associated with the current branch.
- If multiple PRs exist, select the open one.

### 2. Generate the PR description using:
- The standardized PR template above  
- The actual code changes in the working branch (diff, uncommitted changes, recent commits)  
- Root cause analysis based on code inspection  
- Clear, complete, well-formatted markdown  

### 3. Push the generated PR description to the existing PR
- Fully replace the current PR description  
- Preserve markdown formatting  
- Do **not** modify the PR title unless explicitly asked  

### 4. If no PR exists
- Inform the user that the branch has no PR  
- Optionally offer to generate a PR title + description  

### 5. Safety and consistency requirements
- Never push partial templates  
- Never submit empty sections  
- Always ensure a complete and consistent PR description  
- Only push after validating the markdown structure

---
