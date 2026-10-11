# Canonical Gregorian DOB Adjudication v1

## Purpose

Record person-level DOB adjudications required to place all hierarchy-study dates on a single **proleptic Gregorian absolute-date coordinate** without mutating frozen source datasets.

This registry is an overlay. Frozen Nobel, NAS, Royal Society, and Leopoldina source snapshots remain unchanged for auditability.

## Trigger

The cross-study calendar-model audit found historical dates represented inconsistently across sources. The primary 1835-1985 hierarchy window reduced the relevant Julian-claim review set to a small number of cases. Manual source adjudication was then performed before any BaZi unblinding.

## Decision rules

- Primary/archival evidence with explicit Old Style/New Style semantics can establish the canonical Gregorian date.
- A source that merely prints a date without calendar semantics is not enough to override another high-quality source.
- Wikidata calendarmodel is a detection/locator signal, not by itself final evidence.
- Frozen source DOBs are never overwritten. Downstream analysis must join this registry by Wikidata QID and use `canonical_gregorian_dob` when `action=apply_overlay`.
- `pending_manual_calendar_semantics` rows remain excluded from automatic correction.
- No BaZi variables are computed here.

## Confirmed corrections

- Ivan Pavlov: 1849-09-14 Old Style -> **1849-09-26 Gregorian**.
- Nikolay Semenov: 1896-04-03 Old Style -> **1896-04-15 Gregorian**.
- Pyotr Kapitsa: 1894-06-26 Old Style -> **1894-07-08 Gregorian**. The common 1894-07-09 value is a documented +13-day error applied to a 19th-century date.
- George B. Kistiakowsky: 1900-11-18 Old Style parish-register date -> **1900-12-01 Gregorian**.
- Boris Uvarov: archival correction 1886-10-22 Old Style -> **1886-11-03 Gregorian**.

## Confirmed no-change

- Ilya Mechnikov: current 1845-05-15 is already the correct Gregorian date; the Nobel Foundation itself documents the Old Style 3 May / New Style 15 May issue.

## Pending

- Katherine Esau: sources consistently print 1898-04-03, but calendar semantics remain unresolved strongly enough to justify an automatic change.
- Gregory Breit: strong institutional sources print 1899-07-14 while Wikidata contains a conflicting Julian claim. Keep frozen date until a primary record is located.

## Scope

This v1 registry addresses manually adjudicated historical-calendar cases surfaced by the primary hierarchy audit. Automatically aligned Leopoldina cases remain governed by the calendar-normalization audit and do not require individual registry entries.

No BaZi variables were computed or inspected during adjudication.
