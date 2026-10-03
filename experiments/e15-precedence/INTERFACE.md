# E15: the resolver interface

Each resolver under test is a command:

```
resolve <federation.ai-xf.yaml> <from-namespace> <from-concept> <to>
```

- `<from-namespace>`: the containing bundle's namespace, which the federation holds.
- `<from-concept>`: the path of the concept holding the link, relative to its
  bundle's root, e.g. `concepts/glossary.md`.
- `<to>`: the link's `to` value, verbatim.

It prints one JSON object on stdout and exits 0:

```json
{"kind": "id", "target": "beta/glossary", "via": "id", "warning": true, "error": false, "candidates": ["beta", "gamma"]}
```

| Field | Value |
|---|---|
| `kind` | `"qualified"`, `"path"` or `"id"`: the classification (PROPOSED-RULE §2) |
| `target` | `"namespace/id"` of the concept it resolves to, or `null` |
| `via` | `"id"`, `"alias"` or `"path"`: how the target was found; `null` if no target |
| `warning` | `true` if the rule calls for a warning |
| `error` | `true` if the rule calls for an error |
| `candidates` | for id steps 3 and 4 only: every namespace where a match was found at the deciding step, in federation order; otherwise `[]` |

Ids in `target` are the concept's frontmatter `id`, never a file name.
