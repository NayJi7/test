# graphify reference: watch a folder

Load this when the user passed `--watch`. It is not part of the default build.

`/graphify add <url>` (fetching a web page, tweet, paper or video into the corpus) is **not available** in this build (graphify-local never fetches anything over the network). If the user wants a web page in the corpus, they can save it into the project folder themselves, then run `/graphify --update`.

## For --watch

Start a background watcher that monitors a folder and auto-updates the graph when files change.

```bash
$(cat graphify-out/.graphify_python) -m graphify.watch "$(cat graphify-out/.graphify_root)" --debounce 3
```

This watches the same folder graphify extracted, read from the trusted `graphify-out/.graphify_root` that Step 1 resolved - there is no path to substitute, so a scan root containing shell metacharacters can never be re-interpreted here. Behavior depends on what changed:

- **Code files only (.py, .ts, .go, etc.):** re-runs AST extraction + rebuild + cluster immediately, no LLM needed. `graph.json` and `GRAPH_REPORT.md` are updated automatically.
- **Docs, papers, or images:** writes a `graphify-out/needs_update` flag and prints a notification to run `/graphify --update` (LLM semantic re-extraction required).

Debounce (default 3s): waits until file activity stops before triggering, so a wave of parallel agent writes doesn't trigger a rebuild per file.

Press Ctrl+C to stop.

For agentic workflows: run `--watch` in a background terminal. Code changes from agent waves are picked up automatically between waves. If agents are also writing docs or notes, you'll need a manual `/graphify --update` after those waves.
