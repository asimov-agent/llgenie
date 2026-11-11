# Repairing a partial clone that fails to fetch (pack-objects BUG)

## Recognize
A checkout created with `--filter=tree:0` (or `blob:none`) is a partial/promisor clone:

    git config --get-regexp 'remote\..*(promisor|partialclonefilter)'
    # remote.origin.promisor true
    # remote.origin.partialclonefilter tree:0

`git fetch origin` (or an app self-update that fetches internally) dies with:

    BUG: builtin/pack-objects.c:XXXX: should_include_obj should only be called on existing objects
    error: pack-objects died of signal 6
    fatal: could not finish pack-objects to repack local links

## Why
Partial clones omit trees/blobs until needed (promisor packs). During fetch git's
connectivity repack ("repack local links") calls `should_include_obj` on a tree/blob the
local repo does not yet hold, hitting the assertion. Plain `git status`/`log` still works
(branch tips are fine); only the fetch's repack path breaks.

## Cheap unblock (try first)

    git -c fetch.writeCommitGraph=false fetch origin

Writing the commit graph is what drives the connectivity repack; disabling it lets the
fetch advance (typically through the tag stage) when the BUG would otherwise abort it.

## Robust fix — convert to a full clone so every object is present

    git config --unset remote.origin.promisor
    git config --unset remote.origin.partialclonefilter
    git fetch origin          # now pulls every missing tree/blob
    git config --get-regexp 'remote\..*(promisor|partialclonefilter)'  # -> empty
    ls .git/objects/pack/*.promisor                                    # -> none

This roughly doubles on-disk size (previously-omitted trees/blobs land on disk) but makes
every git operation reliable again. If the checkout is disposable, a fresh full clone is
the other option.
