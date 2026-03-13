---
name: github-code-reader
description: >
  Read, search, and analyze code files from GitHub repositories using the browser.
  Use this skill whenever you need to read source code from a GitHub repo, browse a
  repository's file tree, search for patterns across multiple files, or analyze a
  GitHub project's structure. Trigger on "read my GitHub repo", "look at the code on GitHub",
  "browse my repo", "find files in the repo", or any request involving reading code from GitHub.
---

# GitHub Code Reader

Specialized agent for reading and analyzing code from GitHub repositories via the browser.

## Strategy for Reading Files

### Step 1: Get the File Tree
Navigate to the GitHub API tree endpoint:
```
https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1
```

Use JavaScript to parse the response:
```javascript
const data = JSON.parse(document.body.innerText);
const files = data.tree.filter(t => t.type === 'blob').map(t => t.path);
```

### Step 2: Read Files via GitHub Blob View
Navigate to the GitHub blob view:
```
https://github.com/{owner}/{repo}/blob/{branch}/{filepath}
```

Extract raw code from embedded JSON:
```javascript
const allScripts = document.querySelectorAll('script[type="application/json"]');
const sorted = Array.from(allScripts).sort((a,b) => b.textContent.length - a.textContent.length);
const data = JSON.parse(sorted[0].textContent);
const lines = data.payload['codeViewBlobLayoutRoute.StyledBlob'].rawLines;
lines.join('\n');
```

### Step 3: For Smaller Files
Navigate directly to raw content:
```
https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filepath}
```
Then use get_page_text to extract the content.

### Step 4: Handle Content Blocking
If JavaScript tool blocks content:
1. Try extracting code in smaller chunks (50 lines at a time)
2. Use get_page_text on the raw URL instead
3. Store content to window.__fileContent and read in parts
4. As a last resort, take screenshots and read visually

### Tips
- Use two browser tabs in parallel for faster reading
- Group files by module/directory for organized analysis
- Filter out non-source files (images, lock files, node_modules)
- Prioritize: entry points > core logic > utilities > config > tests > docs
- Always note file path and line numbers when documenting issues

