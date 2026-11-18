// Vercel function behind the site's "Update" button.
//
//   GET  /api/refresh   state of the latest "Update listings" run: idle | queued | running | done,
//                       plus `changed` (did that run publish new data?) and `canTrigger`.
//   POST /api/refresh   start a quick update (needs GH_DISPATCH_TOKEN), at most one every few minutes.
//
// The scraping itself runs on GitHub's free Actions runners (.github/workflows/update-listings.yml);
// this function only starts the workflow and reports on it, so it is instant and costs nothing.
//
// One-time setup for the trigger (without it the GET still works and the button just
// checks for the newest published data): add GH_DISPATCH_TOKEN in Vercel -> Settings ->
// Environment Variables, a fine-grained GitHub token limited to this repository with
// "Actions: Read and write" permission.

const REPO = process.env.GH_REPO || "Dielldev/banesa-pr";
const WORKFLOW = "update-listings.yml";
const BRANCH = process.env.GH_BRANCH || "main";
const TOKEN = process.env.GH_DISPATCH_TOKEN;
const COOLDOWN_MS = 5 * 60 * 1000;

const headers = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
};
const reply = (status, body) => new Response(JSON.stringify(body), { status, headers });

async function gh(path, init = {}) {
  return fetch(`https://api.github.com/repos/${REPO}${path}`, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "banesa-refresh",
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
      ...(init.headers || {}),
    },
    signal: AbortSignal.timeout(8000),
  });
}

/** The newest run, reduced to what the page needs. */
async function status() {
  const r = await gh(`/actions/workflows/${WORKFLOW}/runs?per_page=1`);
  if (!r.ok) throw new Error(`GitHub answered ${r.status}`);
  const run = (await r.json()).workflow_runs?.[0];
  const base = { canTrigger: Boolean(TOKEN), cooldownMs: COOLDOWN_MS };
  if (!run) return { ...base, state: "idle", changed: null, runId: null };

  const state = run.status === "completed" ? "done" : run.status === "queued" ? "queued" : "running";
  let changed = null;
  if (state === "done" && run.conclusion === "success") {
    // "Push update" only runs, and only succeeds, when the scrape found something to publish
    const jr = await gh(`/actions/runs/${run.id}/jobs`);
    if (jr.ok) {
      const step = (await jr.json()).jobs?.[0]?.steps?.find((s) => s.name === "Push update");
      changed = step ? step.conclusion === "success" : null;
    }
  }
  return {
    ...base,
    state,
    changed,
    runId: run.id,
    conclusion: run.conclusion,
    event: run.event,
    createdAt: run.created_at,
    finishedAt: state === "done" ? run.updated_at : null,
  };
}

export async function GET() {
  try {
    return reply(200, await status());
  } catch (e) {
    return reply(502, { error: String(e.message || e), canTrigger: Boolean(TOKEN) });
  }
}

export async function POST() {
  if (!TOKEN) return reply(501, { error: "Updates on demand are not set up yet.", canTrigger: false });
  try {
    const s = await status();
    if (s.state === "queued" || s.state === "running") return reply(200, { ...s, started: false });
    if (s.state === "done" && s.finishedAt && Date.now() - Date.parse(s.finishedAt) < COOLDOWN_MS) {
      return reply(200, { ...s, started: false, recent: true });
    }
    const r = await gh(`/actions/workflows/${WORKFLOW}/dispatches`, {
      method: "POST",
      body: JSON.stringify({ ref: BRANCH, inputs: { mode: "quick" } }),
    });
    if (r.status !== 204) {
      return reply(502, { error: `GitHub refused to start the update (${r.status})`, canTrigger: true });
    }
    return reply(202, { ...s, started: true, previousRunId: s.runId });
  } catch (e) {
    return reply(502, { error: String(e.message || e), canTrigger: true });
  }
}

// Vercel accepts either named method exports or a fetch handler; offer both.
export default {
  fetch(request) {
    if (request.method === "GET") return GET();
    if (request.method === "POST") return POST();
    return reply(405, { error: "Use GET or POST" });
  },
};
