# Candidate canonical serialisation for AI-XF concepts (E13)

Draft for experiment E13. Not normative until E13 passes. The goal: one exact
byte sequence for a concept, from its data alone, so that any two systems
holding the same concept write the same file and compute the same hash.

## 1. The data model

A concept is a **frontmatter mapping** and a **body string**.

The frontmatter is read with the **YAML 1.2 core schema**, with one exception:
**timestamps are strings**. So `yes`, `on` and `y` are strings; `010` is the
integer 10; `1:20` is a string; `2026-09-21T08:00:00Z` is a string. Numbers
compare as JSON numbers (`1.0` equals `1`). Comments, anchors, aliases, tags and
document markers inside the frontmatter are not data, and a canonical file has
none.

## 2. File layout

```
---\n
<frontmatter>
---\n
\n                      (only when the body is not empty)
<body>\n                (only when the body is not empty)
```

- Line endings are `\n`. The file is UTF-8 without a byte-order mark.
- **Body:** the text after the closing `---` line, with `\r\n` and `\r`
  turned into `\n`, leading and trailing blank lines removed, then written after
  one blank line and ended with exactly one `\n`. Nothing inside it changes,
  including trailing spaces (a markdown line break). An empty body writes
  nothing after the closing `---\n`.
- An empty frontmatter mapping writes `---\n---\n`.

## 3. Key order

Mappings are written in a fixed order: the **listed keys first, in the order
listed**, then **every other key in ascending order of its UTF-8 bytes**.

| Mapping | Listed keys |
|---|---|
| Top level | `type`, `id`, `title`, `description`, `resource`, `tags`, `aliases`, `generated`, `verified`, `status`, `stale_after`, `sources`, `usage_window`, `provenance`, `links`, `media` |
| `generated`, each `verified[]` entry | `by`, `at` |
| each `sources[]` entry | `id`, `resource`, `title`, `author`, `last_modified`, `usage_count`, `usage_window`, `withheld` |
| `usage_window` (anywhere) | `from`, `to` |
| `provenance` | `confidence`, `source` |
| each `links[]` entry | `rel`, `to`, `note`, `by`, `at`, `state`, `resolved`, `verified` |
| `resolved` | `by`, `at`, `outcome` |
| each `media[]` entry | `uri`, `hash`, `type`, `describes` |
| any other mapping | none: all keys in byte order |

**Lists keep their order.** Order can carry meaning (`verified` events, a
writer's ordering of `sources`), so the canonical form never sorts a list.

## 4. Structure

- Two-space indentation. Block style only, with two exceptions: an empty list
  is written `[]` and an empty mapping `{}`.
- A mapping value is written `key: value` when it is a scalar, `[]` or `{}`;
  otherwise `key:` followed by its content on the next lines, indented two
  spaces more than the key.
- A list item is written `- ` at the parent key's indentation plus two
  (`tags:` then `  - a`). Never at column 0 under its key.
- A list item that is a mapping starts on the `- ` line with its first key;
  its other keys line up under the first.
- A list item that is itself a non-empty list is written `-` alone, with its
  items on the following lines, indented two spaces more.
- No line is ever wrapped.

## 5. Scalars

| Data | Written as |
|---|---|
| null | `null` |
| boolean | `true` / `false` |
| integer | decimal digits, with `-` when negative |
| other number | the shortest decimal that reads back as the same number, as ECMAScript's `Number.prototype.toString` writes it (so `0.5`, `1e+21`, `1e-7`); a number with no fractional part below 1e21 is written as an integer (`1.0` → `1`); infinity and not-a-number as `.inf`, `-.inf`, `.nan`; negative zero as `0` |
| string, **date or timestamp** | plain when it matches `YYYY-MM-DD`, or `YYYY-MM-DDTHH:MM:SS` with an optional fraction and `Z` or `±HH:MM`, under any key (adopted in E13b; the first run used a list of five keys) |
| string, **plain-safe** | plain, without quotes |
| any other string | double-quoted |

A string is **plain-safe** when all of these hold:

1. it is not empty, and has no leading or trailing space or tab;
2. its first character is a letter (`A–Z`, `a–z`), `_` or `/`, or it starts
   with `./` or `../` followed by a character that is not `.`;
3. it contains no character below U+0020, no character that double quoting
   escapes (below), and no `#`; does not contain `:` followed by a space; and
   does not end with `:`;
4. it is not one of (case-insensitive): `null`, `true`, `false`, `yes`, `no`,
   `y`, `n`, `on`, `off`.

Rule 2 is deliberately stricter than YAML needs: every YAML indicator, digit,
sign and dot is excluded as a first character, so no number, date, flow
collection, anchor, tag or block scalar can be read into a plain string.
Commas, brackets and quotes inside a string are safe, because the canonical form
never uses flow style. Over-quoting costs nothing; under-quoting changes what a
YAML 1.1 reader sees.

**Double quoting** writes `"`, then the string with these escapes, then `"`:
`\` → `\\`, `"` → `\"`, newline → `\n`, tab → `\t`, carriage return → `\r`;
and `\u` with four upper-case hex digits for every other character outside
YAML's printable set (U+0020–U+007E, U+00A0–U+D7FF, U+E000–U+FFFD, U+10000
and above), and for NEL (U+0085), U+2028, U+2029 and U+FEFF, which YAML 1.1
reads as line breaks or a byte-order mark (E13c). Every other character,
including all other non-ASCII, is written as itself. A string containing an
unpaired surrogate cannot be serialised.

**Readers must take dates and timestamps as strings.** The data model does not
record whether a value was quoted, so no canonical form can keep a YAML 1.1
reader's view of every date: E13b measured 409 values on 268 concepts that a
YAML 1.1 reader types differently before and after, almost all of them
timestamps a producer had quoted. A reader that resolves YAML 1.1 timestamps
must turn them back into strings, as OKF's reference Python implementation does
since its PR #6.

## 6. Content hash

`sha256:` followed by the lower-case hex SHA-256 of the canonical file's bytes.
It covers frontmatter and body. It is never stored inside the file it hashes.
