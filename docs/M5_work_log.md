# M5 work log

- Base: 87496f67f0e8415c9d0ca7cff525cfcf761fc985; separate clone in user-requested course directory, branch feat/m5-time-change.
- Read proposal, lecture requirements and existing M4. User approved M5 scope and asked to execute to completion.
- Ruling: keep original modules untouched; use explicit local context import instead of introducing shell-wide coupling.
- Official CEPII ZIP download failed TLS/HTTP connections; retrieving same-vintage public Parquet distribution and requiring full reconciliation before use. Source limitations will remain visible.

- Data: three pinned release assets (132,977,388 bytes) downloaded into data/sources/m5. All566,165 product keys and870,755 bilateral keys reconciled; maxrelativeerror2.44e-14. No official-CSV audit claimed.
- Ruling: exact duplicate metadata region rows collapse, conflicting region assignments fail. Original country_meta is not rewritten.
- TDD: watched analytics/UI tests fail before implementation. Added regression for an event-year above baseline followed by a later loss; recovery requires a subsequent return after that loss.
- Whole-branch reviewer independently ran29 tests and independently checked bilateral-key reconciliation; one color-collision issue fixed with unique comparison colours and redundant line patterns.30 tests pass after the fix.
- Browser: original shared CSS overrode the M5 flex layout; fixed using scoped specificity. Actual plot resize completion is awaited in verification; desktop/820px screenshots and operations pass, no browser errors or page overflow.
- Implementation finished locally; no remote publication, merge, message or Feishu edit performed.
