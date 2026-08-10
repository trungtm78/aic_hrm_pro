# Why the stop hook blocked forever (two separate bugs)

Written in English and plain ASCII on purpose: the whole point of this note is
that something in the toolchain cannot read non-ASCII text, so this file has to
survive being read by it.

## The one that actually blocked it

`.claude/hooks/stop-guard.bat` searched for the sentinel with a doubled caret:

    findstr /R /C:"^^STATUS: *ALL_MILESTONES_DONE" "%PF%"

In a findstr regular expression the first caret anchors to the start of the
line and the second is a literal caret character, so the pattern asks for a line
beginning with `^STATUS`. No file has ever contained that. Measured directly:

    doubled_caret_errorlevel=1   (no match)
    single_caret_errorlevel=0    (match)

One caret is correct. Fixed, and both directions verified: the hook is now
silent when the sentinel is present and blocks when it is removed.

## The second one, found on the way

While hunting the caret, PROGRESS.md turned out to be unreadable by any tool
that opens it with the Windows default encoding. findstr reads bytes, so this
was never what blocked the hook - but it would have blocked any Python-based
reader, and it was worth fixing.

The symptom looked identical. The hook reports:

    PROGRESS.md has no STATUS: ALL_MILESTONES_DONE or STATUS: BLOCKED yet

while `PROGRESS.md` begins, at byte zero, with exactly that line. Two separate
sessions independently verified the sentinel - by hex dump, by token count, by
restoring the plain `status / blank / heading` shape - and both concluded the
file was correct. One of them wrote a "deadlock report" about it.

## Cause

`PROGRESS.md` is UTF-8 and contains Vietnamese. Python on this machine defaults
to cp1252, and cp1252 cannot decode it:

    $ python -c "open('PROGRESS.md').read()"
    UnicodeDecodeError: 'charmap' codec can't decode byte 0x90 in position 314

A reader doing `open(path).read()` with no explicit encoding therefore raises
before it can look at any line, and "no status found" is what an exception looks
like from the outside.

The sentinel's own line is pure ASCII, so a line-by-line reader would find it.
Only a whole-file read fails - which narrows down what the hook does.

## This has never worked in this repository

Checked against three points in history, including the commit this working copy
was cloned at, all of them long before either session touched the file:

| Commit    | `open()` under cp1252   |
|-----------|-------------------------|
| `aa9fa81` | fails at byte 155       |
| `27e18bb` | fails at byte 139       |
| `ff30d99` | fails at byte 141       |

`PROGRESS.md` has been Vietnamese since it was created. No edit to its contents
can satisfy a reader that cannot decode it.

## Fix for the encoding half

One argument, in anything that reads the file with Python:

```python
open(path, encoding='utf-8')          # or Path(path).read_text(encoding='utf-8')
```

Setting `PYTHONUTF8=1` in the hook's environment fixes it too, and is worth
doing anyway - the rest of this project's tooling already requires it, which is
why every command in `CLAUDE.md` is prefixed with it.

## What was deliberately not done

Rewriting `PROGRESS.md` into ASCII would make the hook pass. It would also
strip the diacritics from 55 KB of a working log, and Vietnamese without
diacritics is genuinely ambiguous rather than merely ugly - `da`, `dá`, `dà`,
`đá` and `đã` are five different words. Damaging the record to work around a
missing keyword argument is the wrong way round.
