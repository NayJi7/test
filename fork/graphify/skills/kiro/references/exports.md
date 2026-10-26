# graphify reference: extra exports and benchmark

Load this when the user passed one of the export flags (`--wiki`, `--neo4j`, `--falkordb`, `--svg`, `--graphml`), or when the corpus is large enough for the token-reduction benchmark. Each step runs only for its own flag.

### Step 6b - Wiki (only if --wiki flag)

**Only run this step if `--wiki` was explicitly given in the original command.**

Run this before Step 9 (cleanup) so `.graphify_labels.json` is still available.

```bash
graphify export wiki
```

### Step 7 - Neo4j export (only if --neo4j flag)

**If `--neo4j`** - generate a Cypher file for manual import:

```bash
graphify export neo4j
```

Sending the graph to a Neo4j server (`--neo4j-push`) is **not available** in this build: graphify-local never sends data over the network. Import `graphify-out/cypher.txt` yourself (e.g. `cypher-shell < graphify-out/cypher.txt`).

### Step 7a - FalkorDB export (only if --falkordb flag)

**If `--falkordb`** - generate a Cypher file. The statements are OpenCypher, but FalkorDB's `GRAPH.QUERY` runs one statement at a time (no bulk script import like Neo4j's `cypher-shell`), so load the file statement by statement:

```bash
graphify export falkordb
```

Sending the graph to a FalkorDB server (`--falkordb-push`) is **not available** in this build: graphify-local never sends data over the network.

### Step 7b - SVG export (only if --svg flag)

```bash
graphify export svg
```

### Step 7c - GraphML export (only if --graphml flag)

```bash
graphify export graphml
```

### Step 7d - MCP server

The MCP server (`--mcp`, `python -m graphify.serve`) is **not available** in this build (graphify-local). Query the graph with `graphify query`, `graphify path` and `graphify explain` instead (see `references/query.md`).

### Step 8 - Token reduction benchmark (only if total_words > 5000)

If `total_words` from `graphify-out/.graphify_detect.json` is greater than 5,000, run:

```bash
graphify benchmark
```

Print the output directly in chat. If `total_words <= 5000`, skip silently - the graph value is structural clarity, not token compression, for small corpora.
