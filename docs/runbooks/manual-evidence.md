# Manual Evidence Cadence

Phase 6 adds operator-entered evidence channels for comps, auction anchors, and cultural context. These records support review and internal scoring breadth; they do not override fixture/live marketplace ingestion.

## Weekly Workflow

1. Review each pilot bag once per week.
2. Enter manual comps from permitted operator sources such as Terapeak reads where allowed, Vestiaire, Fashionphile, or other clearly attributed marketplace observations.
3. Enter auction records with `source_type=auction_record` only when the record is a contextual anchor. Auction records render separately and must not enter daily aggregates or listing verdict math.
4. Every comp must include source, source type, observed date, condition band, confirmed-close flag, price type, shipping-included value, URL, and entered-by.
5. Add one cultural-context note per bag only when there is a concrete editorial observation worth preserving. Notes are a 0%-weight context layer and are excluded from score math.
6. After entering evidence, run the normal aggregate and score-shadow jobs. Source breadth should count API and manual evidence sources from the trailing 30 days, excluding auction records.

## Review Standard

- Prefer fewer, better-attributed rows over broad manual scraping.
- Keep notes factual and tied to observable context.
- Do not use auction records as replacement values for condition-banded asking ranges.
- If a source cannot be revisited or audited, do not enter it.
