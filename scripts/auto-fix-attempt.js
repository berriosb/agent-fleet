// scripts/auto-fix-attempt.js
// Tries a minimal fix for the FIRST failure in /tmp/failed.log.head using MiniMax M3.
// Strict guardrails: only one file changed, only an obvious mechanical fix, otherwise exit non-zero.
//
// Drop into consumer repo's scripts/. Invoked by the auto-fix job in qa.yml.

const fs   = require('fs');
const path = require('path');
const https = require('https');
const { execSync } = require('child_process');

const branch = process.argv[2];
if (!branch) { console.error('branch arg required'); process.exit(1); }

const base = (process.env.MINIMAX_BASE_URL || 'https://api.minimax.chat/v1').replace(/\/$/, '');
const key  = process.env.MINIMAX_API_KEY;
const log  = fs.existsSync('/tmp/failed.log.head')
  ? fs.readFileSync('/tmp/failed.log.head', 'utf8')
  : '(no log)';

const prompt = fs.readFileSync(
  path.join(__dirname, '..', 'prompts', 'auto-fix.md'), 'utf8');

// Step 1 — ask M3 what to do
const body = JSON.stringify({
  model: 'MiniMax-M3',
  max_tokens: 800,
  temperature: 0.1,
  messages: [{
    role: 'user',
    content: `${prompt}\n\n--- FAILED LOG ---\n${log.slice(0, 3000)}\n\n--- OUTPUT JSON ONLY ---`
  }]
});

https.request(new URL(base + '/chat/completions'), {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${key}`,
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(body)
  }
}, res => {
  let data = '';
  res.on('data', c => data += c);
  res.on('end', () => {
    if (res.statusCode !== 200) { console.error('M3 error', data.slice(0, 300)); process.exit(1); }
    try {
      const json = JSON.parse(data);
      const text = json.choices?.[0]?.message?.content || '';
      const fix  = JSON.parse(text);
      if (!fix.file || !fix.replacement) {
        console.log('no actionable fix');
        process.exit(1);
      }
      // Guardrails: only touch files under src/ or tests/
      const allowed = /^(src|tests|app|packages|lib)\//;
      if (!allowed.test(fix.file)) {
        console.log('refused: file outside allowed scope:', fix.file);
        process.exit(1);
      }
      // Single-file check
      const full = path.join(process.cwd(), fix.file);
      if (!fs.existsSync(full)) { console.log('file does not exist:', full); process.exit(1); }
      fs.writeFileSync(full, fix.replacement);

      execSync('git add ' + JSON.stringify(fix.file), { stdio: 'inherit' });
      execSync(`git commit -m "auto-fix: ${fix.summary || 'mechanical fix'}"`,
        { stdio: 'inherit', env: { ...process.env,
          GIT_AUTHOR_NAME: 'gatling', GIT_AUTHOR_EMAIL: 'gatling@users.noreply.github.com',
          GIT_COMMITTER_NAME: 'gatling', GIT_COMMITTER_EMAIL: 'gatling@users.noreply.github.com' }
        });
      execSync(`git push -u origin ${branch}`, { stdio: 'inherit' });
      console.log('auto-fix branch pushed:', branch);
    } catch (e) {
      console.error('parse/error', e.message);
      process.exit(1);
    }
  });
}).on('error', e => { console.error('http', e.message); process.exit(1); })
  .end(body);
