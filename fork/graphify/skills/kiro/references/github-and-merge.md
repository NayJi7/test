# graphify reference: multi-folder merge

Load this when the user named several local subfolders (or several local repositories) to merge into one graph.

Cloning GitHub repositories (`/graphify https://github.com/...`, `graphify clone`) is **not available** in this build (graphify-local never fetches anything over the network). If the user gives a GitHub URL, ask them to clone the repository themselves, then run graphify on the local folder.

**Multiple local subfolders (monorepo or multi-service layout):**

The skill pipeline writes all intermediate and final outputs to `graphify-out/` in the current working directory. Running the skill on each subfolder separately will clobber the same output dir. Instead, use the CLI directly for each subfolder — it places `graphify-out/` *inside* the scanned path:

```bash
graphify extract ./core/     # → ./core/graphify-out/graph.json
graphify extract ./service/  # → ./service/graphify-out/graph.json
graphify extract ./platform/ # → ./platform/graphify-out/graph.json
# graphify-local: `graphify extract` indexes code only (no AI call); to include the
# documents of a subfolder, run /graphify from inside that subfolder instead.

# Then merge at the project root:
graphify merge-graphs \
  ./core/graphify-out/graph.json \
  ./service/graphify-out/graph.json \
  ./platform/graphify-out/graph.json \
  --out graphify-out/graph.json
```

Once `graphify-out/graph.json` exists, the fast path above takes over: any codebase question runs `graphify query` directly on the merged graph — no re-extraction, no size gate.
