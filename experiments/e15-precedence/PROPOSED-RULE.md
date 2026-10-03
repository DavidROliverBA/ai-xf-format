# E15: the resolution rule under test

This is the complete text an implementer gets. It is the candidate wording for
SPEC §9.2, §9.5 and §11.1. It replaces the order in which a consumer resolves a
link's `to` value. The keywords MUST, SHOULD and MAY are as in RFC 2119.

## Terms

- A **bundle** is a directory with a `manifest.ai-xf.yaml`. Its **namespace** is
  the manifest's `namespace` value.
- A **concept** is a `.md` file in a bundle with YAML frontmatter holding `type`.
  Its `id` is the frontmatter `id`; its **aliases** are the strings in the
  frontmatter `aliases` list. `index.md` and `log.md` are not concepts.
- The **federation** is the set of bundles listed in a `federation.ai-xf.yaml`
  under `bundles`, each with `namespace` and a `path` relative to that file.
- The **containing bundle** is the bundle that holds the concept the link is in.

## 1. Nested bundles

A directory below a bundle's root that holds its own `manifest.ai-xf.yaml` is
the root of a separate bundle. That directory and everything under it are not
part of the enclosing bundle: its concepts' ids, aliases and paths belong to the
inner bundle only. This applies whether or not the inner bundle is in the
federation.

## 2. Classifying a `to` value

Classify by its text alone, never by which bundles are held. The first rule that
matches decides:

1. Starts with `ai-xf://`: **qualified**. Drop the prefix; the rest is
   `namespace/id`.
2. Ends with `.md`, or starts with `./` or `../`: **path**.
3. Matches `^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$`: **qualified**,
   `namespace/id`.
4. Anything else: **id**.

Producers SHOULD write a path with its `.md` extension: without it, `concepts/home`
is read as the qualified reference `home` in namespace `concepts`.

## 3. Federation order

The federation order is the order in which a consumer tries bundles other than
the containing one:

1. The namespaces listed in the federation manifest's optional `precedence` list,
   in the order listed, skipping any that the federation does not hold and the
   containing bundle's own namespace.
2. Then every other held namespace, in ascending order of the namespace's UTF-8
   bytes (not a locale's collation).

A `precedence` list MUST NOT name a namespace twice.

## 4. Resolving

**Qualified `namespace/id`.**

- If `namespace` is the containing bundle's own namespace: an error (producers
  MUST NOT qualify same-bundle references). It does not resolve.
- Otherwise, in that bundle only: a concept whose `id` equals `id` resolves
  silently. Failing that, a concept with `id` among its aliases resolves, with a
  warning to link to the concept's `id`. Failing that, or if the namespace is not
  held, it is a broken link, with a warning.

**Path.** Resolved inside the containing bundle only, never across bundles: first
relative to the directory of the concept that holds the link, then relative to
the bundle root. A concept file found there resolves silently. Otherwise it is a
broken link, with a warning.

**Id.** The first step that matches decides:

1. A concept in the containing bundle with that `id`: resolves silently.
2. A concept in the containing bundle with that alias: resolves, with a warning
   to link to its `id`.
3. A concept with that `id` in the other held bundles, tried in federation
   order: the first bundle that has one wins. A warning MUST name every
   namespace where a concept with that `id` was found, in federation order, and
   the one chosen.
4. A concept with that alias in the other held bundles, in federation order: as
   step 3, for aliases.
5. Otherwise a broken link, with a warning. A broken link is tolerable, never an
   error.

Steps 3 and 4 are never silent. Within one bundle, ids and aliases are unique,
so a step that reaches a bundle finds at most one concept there.
