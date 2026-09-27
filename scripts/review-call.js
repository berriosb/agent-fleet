// scripts/review-call.js
// MiniMax M3 PR review caller — OpenAI-compatible endpoint at $MINIMAX_BASE_URL.
// Drop into consumer repo's scripts/ alongside .github/workflows/gatling.yml.
//
// This file is loaded by the reusable workflow's ai-review job. Keep it tiny:
// the prompt template lives in prompts/review.md as plain text.

const fs   = require('fs');
const path = require('path');
const https = require('https');

(async () => {
  const base = (process.env.MINIMAX_BASE_URL || 'https://api.minimax.chat/v1').replace(/\/$/, '');
  const key  = process.env.MINIMAX_API_KEY;
  if (!key) { console.error('MINIMAX_API_KEY missing'); process.exit(0); }

  // Read PR diff (the workflow captures the changed files summary at PR open/sync).
  const event = process.env.GITHUB_EVENT_PATH
    ? JSON.parse(fs.readFileSync(process.env.GITHUB_EVENT_PATH, 'utf8'))
    : null;
  const pr    = event ? event.pull_request : null;
  if (!pr) { console.log('no PR context'); process.exit(0); }

  const promptTemplate = fs.readFileSync(
    path.join(__dirname, '..', 'prompts', 'review.md'), 'utf8');

  const body = JSON.stringify({
    model: 'MiniMax-M3',
    max_tokens: 1024,
    temperature: 0.2,
    messages: [{
      role: 'user',
      content: `${promptTemplate}\n\n---\n\n` +
               `PR title: ${pr.title}\n` +
               `PR body: ${(pr.body || '').slice(0, 1500)}\n` +
               `Base SHA: ${pr.base.sha}\n` +
               `Head SHA: ${pr.head.sha}\n` +
               `Changed files: ${pr.changed_files}, +${pr.additions}/-${pr.deletions}\n` +
               `\nNote: keep output as a single github-flavoured markdown comment. ` +
               `Format each finding as: file:line — severity (low|med|high|critical) — message.\n` +
               `Skip findings about whitespace/comments unless they're violations.\n`
    }]
  });

  const url = new URL(base + '/chat/completions');
  const req = https.request(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${key}`,
      'Content-Type':  'application/json',
      'Content-Length': Buffer.byteLength(body)
    }
  }, res => {
    let data = '';
    res.on('data', c => data += c);
    res.on('end', () => {
      if (res.statusCode !== 200) {
        console.error('MiniMax error', res.statusCode, data.slice(0, 300));
        process.exit(0);
      }
      try {
        const json  = JSON.parse(data);
        const reply = json.choices?.[0]?.message?.content || '';
        if (reply) {
          fs.writeFileSync('/tmp/review.md', reply);
          console.log('review.md written,', reply.length, 'chars');
        }
      } catch (e) { console.error('parse error', e.message); }
    });
  });
  req.on('error', e => console.error('http error', e.message));
  req.write(body); req.end();
})();
