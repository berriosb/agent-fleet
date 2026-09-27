// scripts/auto-fix-attempt.js
// Applies a surgical, validated mechanical fix to a single file using configured LLM.
// Guardrails:
// 1. Searches and replaces exact unique substring (never blind overwrite).
// 2. Syntax check before commit (reverts if syntax invalid).
// 3. Modifies at most ONE file under allowed paths (src, tests, app, packages, lib).
// 4. Exits gracefully (code 0) if no safe fix is possible.

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const { execSync } = require('child_process');

function resolveProvider() {
  const reqProvider = (process.env.LLM_PROVIDER || 'minimax').toLowerCase();

  if (reqProvider === 'minimax') {
    const key = process.env.MINIMAX_API_KEY;
    const base = (process.env.MINIMAX_BASE_URL || 'https://api.minimax.chat/v1').replace(/\/$/, '');
    const model = process.env.MINIMAX_MODEL || 'MiniMax-M3';
    return { name: 'minimax', key, base, model, format: 'openai' };
  }

  if (reqProvider === 'openai') {
    const key = process.env.OPENAI_API_KEY;
    const base = (process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1').replace(/\/$/, '');
    const model = process.env.OPENAI_MODEL || 'gpt-4o-mini';
    return { name: 'openai', key, base, model, format: 'openai' };
  }

  if (reqProvider === 'gemini') {
    const key = process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY;
    const base = (process.env.GEMINI_BASE_URL || 'https://generativelanguage.googleapis.com/v1beta/openai').replace(/\/$/, '');
    const model = process.env.GEMINI_MODEL || 'gemini-2.0-flash';
    return { name: 'gemini', key, base, model, format: 'openai' };
  }

  if (reqProvider === 'anthropic') {
    const key = process.env.ANTHROPIC_API_KEY;
    const base = (process.env.ANTHROPIC_BASE_URL || 'https://api.anthropic.com/v1').replace(/\/$/, '');
    const model = process.env.ANTHROPIC_MODEL || 'claude-3-5-sonnet-latest';
    const format = base.includes('anthropic.com') ? 'anthropic' : 'openai';
    return { name: 'anthropic', key, base, model, format };
  }

  // Fallback heuristic: check available keys
  if (process.env.MINIMAX_API_KEY) {
    return { name: 'minimax', key: process.env.MINIMAX_API_KEY, base: 'https://api.minimax.chat/v1', model: 'MiniMax-M3', format: 'openai' };
  }
  if (process.env.OPENAI_API_KEY) {
    return { name: 'openai', key: process.env.OPENAI_API_KEY, base: 'https://api.openai.com/v1', model: 'gpt-4o-mini', format: 'openai' };
  }
  if (process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY) {
    return { name: 'gemini', key: process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY, base: 'https://generativelanguage.googleapis.com/v1beta/openai', model: 'gemini-2.0-flash', format: 'openai' };
  }

  return { name: reqProvider, key: null, base: '', model: '', format: 'openai' };
}

function loadAutoFixPrompt() {
  const candidatePaths = [
    path.join(__dirname, '..', 'prompts', 'auto-fix.md'),
    path.join(__dirname, 'prompts', 'auto-fix.md'),
    '/tmp/gatling-prompts/auto-fix.md'
  ];
  for (const p of candidatePaths) {
    if (fs.existsSync(p)) {
      return fs.readFileSync(p, 'utf8');
    }
  }
  return `You are a surgical code repair agent. Provide JSON with:
{"file": "path", "search": "exact string", "replace": "replacement", "summary": "message"}
or {"skip": "reason"}`;
}

function postHttpRequest(targetUrl, headers, payload) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(targetUrl);
    const client = parsed.protocol === 'http:' ? http : https;
    const req = client.request(parsed, {
      method: 'POST',
      headers
    }, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ statusCode: res.statusCode, body: data }));
    });
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

function parseJsonSafely(text) {
  if (!text || typeof text !== 'string') return null;
  const cleaned = text
    .replace(/^```json\s*/i, '')
    .replace(/^```\s*/i, '')
    .replace(/\s*```$/i, '')
    .trim();
  try {
    return JSON.parse(cleaned);
  } catch (_) {
    // Try to extract first JSON object {...}
    const match = cleaned.match(/\{[\s\S]*\}/);
    if (match) {
      try {
        return JSON.parse(match[0]);
      } catch (__) {}
    }
    return null;
  }
}

function validateFileSyntax(filePath) {
  try {
    const ext = path.extname(filePath);
    if (ext === '.py') {
      execSync(`python3 -m py_compile "${filePath}"`, { stdio: 'ignore' });
    } else if (ext === '.js' || ext === '.mjs' || ext === '.cjs') {
      execSync(`node --check "${filePath}"`, { stdio: 'ignore' });
    } else if (ext === '.json') {
      JSON.parse(fs.readFileSync(filePath, 'utf8'));
    }
    return true;
  } catch (err) {
    return false;
  }
}

(async () => {
  const branch = process.argv[2];
  if (!branch) {
    console.error('[auto-fix] Target branch argument required');
    process.exit(1);
  }

  const provider = resolveProvider();
  if (!provider.key) {
    console.log(`[auto-fix] No API key configured for provider "${provider.name}" — skipping auto-fix.`);
    process.exit(0);
  }

  // Load failed log
  let log = '';
  if (fs.existsSync('/tmp/failed.log')) {
    log = fs.readFileSync('/tmp/failed.log', 'utf8');
  } else if (fs.existsSync('/tmp/failed.log.head')) {
    log = fs.readFileSync('/tmp/failed.log.head', 'utf8');
  }

  if (!log.trim()) {
    console.log('[auto-fix] No failure log found — skipping.');
    process.exit(0);
  }

  // Scan for candidate files in allowed paths mentioned in the log
  const allowedPattern = /(?:src|tests|app|packages|lib)\/[a-zA-Z0-9_\-\.\/]+\.(?:py|js|ts|tsx|jsx|json|yaml|yml|tf)/g;
  const matches = log.match(allowedPattern) || [];
  let candidateFile = null;

  for (const m of matches) {
    const full = path.join(process.cwd(), m);
    if (fs.existsSync(full) && fs.statSync(full).isFile()) {
      candidateFile = m;
      break;
    }
  }

  if (!candidateFile) {
    console.log('[auto-fix] No existing file found within allowed directories in failure log.');
    process.exit(0);
  }

  const fullPath = path.join(process.cwd(), candidateFile);
  const originalContent = fs.readFileSync(fullPath, 'utf8');

  if (originalContent.length > 35000) {
    console.log(`[auto-fix] Candidate file ${candidateFile} too large (${originalContent.length} bytes) for safe auto-fix.`);
    process.exit(0);
  }

  const promptTemplate = loadAutoFixPrompt();
  const userContent = `${promptTemplate}\n\n` +
    `--- TARGET FILE: ${candidateFile} ---\n\`\`\`\n${originalContent}\n\`\`\`\n\n` +
    `--- CI FAILURE LOG (relevant snippet) ---\n\`\`\`\n${log.slice(0, 3000)}\n\`\`\`\n\n` +
    `Respond ONLY with a valid JSON object matching the requested schema.`;

  console.log(`[auto-fix] Requesting fix for ${candidateFile} using ${provider.name}...`);
  let responseText = '';

  try {
    if (provider.format === 'anthropic') {
      const payload = JSON.stringify({
        model: provider.model,
        max_tokens: 1200,
        temperature: 0.1,
        messages: [{ role: 'user', content: userContent }]
      });
      const res = await postHttpRequest(`${provider.base}/messages`, {
        'x-api-key': provider.key,
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }, payload);

      if (res.statusCode !== 200) {
        console.error(`[auto-fix] Anthropic error ${res.statusCode}: ${res.body.slice(0, 300)}`);
        process.exit(0);
      }
      const data = JSON.parse(res.body);
      responseText = data.content?.[0]?.text || '';
    } else {
      const payload = JSON.stringify({
        model: provider.model,
        max_tokens: 1200,
        temperature: 0.1,
        messages: [
          { role: 'system', content: 'You are an automated surgical code repair assistant. Output valid JSON only.' },
          { role: 'user', content: userContent }
        ]
      });
      const res = await postHttpRequest(`${provider.base}/chat/completions`, {
        'Authorization': `Bearer ${provider.key}`,
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }, payload);

      if (res.statusCode !== 200) {
        console.error(`[auto-fix] LLM API error ${res.statusCode}: ${res.body.slice(0, 300)}`);
        process.exit(0);
      }
      const data = JSON.parse(res.body);
      responseText = data.choices?.[0]?.message?.content || '';
    }

    const fix = parseJsonSafely(responseText);
    if (!fix) {
      console.log('[auto-fix] Could not parse valid JSON from model response.');
      process.exit(0);
    }

    if (fix.skip) {
      console.log(`[auto-fix] Model skipped fix: ${fix.skip}`);
      process.exit(0);
    }

    // Safety checks
    const targetFile = fix.file || candidateFile;
    const allowedPrefix = /^(src|tests|app|packages|lib)\//;
    if (!allowedPrefix.test(targetFile)) {
      console.log(`[auto-fix] Refused: file outside allowed scope (${targetFile})`);
      process.exit(0);
    }

    if (!fix.search || typeof fix.search !== 'string' || typeof fix.replace !== 'string') {
      console.log('[auto-fix] Invalid search/replace fields in proposal.');
      process.exit(0);
    }

    // Validate that search occurs EXACTLY ONCE
    const occurrences = originalContent.split(fix.search).length - 1;
    if (occurrences === 0) {
      console.log('[auto-fix] Proposed search string not found in original file. Aborting.');
      process.exit(0);
    }
    if (occurrences > 1) {
      console.log(`[auto-fix] Proposed search string occurs ${occurrences} times (ambiguous). Aborting.`);
      process.exit(0);
    }

    // Apply surgical replacement
    const newContent = originalContent.replace(fix.search, fix.replace);
    fs.writeFileSync(fullPath, newContent, 'utf8');

    // Syntax validation
    if (!validateFileSyntax(fullPath)) {
      console.log('[auto-fix] Syntax check failed on modified file. Reverting changes.');
      fs.writeFileSync(fullPath, originalContent, 'utf8');
      process.exit(0);
    }

    // Verify git diff modifies ONLY this file
    const changed = execSync('git diff --name-only', { encoding: 'utf8' }).trim().split('\n').filter(Boolean);
    if (changed.length !== 1 || changed[0] !== targetFile) {
      console.log(`[auto-fix] Unexpected git diff state: ${changed.join(', ')}. Reverting.`);
      execSync('git checkout -- .', { stdio: 'ignore' });
      process.exit(0);
    }

    // Commit and push side-branch
    console.log(`[auto-fix] Fix validated for ${targetFile}. Creating branch ${branch}...`);
    execSync(`git checkout -b "${branch}"`, { stdio: 'inherit' });
    execSync(`git add "${targetFile}"`, { stdio: 'inherit' });
    execSync(`git commit -m "auto-fix: ${fix.summary || 'mechanical fix'}"`, {
      stdio: 'inherit',
      env: {
        ...process.env,
        GIT_AUTHOR_NAME: 'gatling',
        GIT_AUTHOR_EMAIL: 'gatling@users.noreply.github.com',
        GIT_COMMITTER_NAME: 'gatling',
        GIT_COMMITTER_EMAIL: 'gatling@users.noreply.github.com'
      }
    });

    execSync(`git push -u origin "${branch}"`, { stdio: 'inherit' });
    console.log(`[auto-fix] Side-branch pushed: ${branch}`);

    // Create draft PR if gh is available
    const prNumber = process.env.PR_NUMBER;
    const headRef = process.env.HEAD_REF;
    const prTitle = process.env.PR_TITLE || 'PR';
    const repo = process.env.REPO || process.env.GITHUB_REPOSITORY;
    const repoArg = repo ? `--repo "${repo}"` : '';

    if (prNumber && headRef) {
      try {
        execSync(`gh pr create --base "${headRef}" --head "${branch}" --title "🤖 auto-fix attempt for ${prTitle}" --body "Automated surgical fix attempt. **Requires human review before merging.**\\n\\nSummary: ${fix.summary || 'mechanical fix'}" --draft ${repoArg}`, {
          stdio: 'inherit'
        });
        console.log('[auto-fix] Draft PR created successfully.');
      } catch (prErr) {
        console.warn(`[auto-fix] Could not create draft PR: ${prErr.message}. Posting comment instead.`);
        try {
          execSync(`gh pr comment "${prNumber}" ${repoArg} --body "🤖 **gatling auto-fix branch created**: \`${branch}\`. Review before merging."`, {
            stdio: 'inherit'
          });
        } catch (_) {}
      }
    }
  } catch (err) {
    console.error(`[auto-fix] Failed: ${err.message}`);
    // Ensure clean working tree on failure
    try { execSync('git checkout -- .', { stdio: 'ignore' }); } catch (_) {}
    process.exit(0);
  }
})();
