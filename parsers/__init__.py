"""
parsers/
--------
One parser per bank. Each parser exposes a single function:

    def parse(html: str, source_url: str) -> list[CardRecord]:
        ...

The controller imports the right parser by bank_id and feeds it the
HTML it fetched. Parsers NEVER make HTTP calls, download images, or
write to the database. They only turn HTML into structured records.
"""

# Registry: bank_id -> parser module path.
# Populated as we add real parsers.
PARSER_REGISTRY: dict[str, str] = {
    # "hdfc":   "parsers.hdfc",
    # "icici":  "parsers.icici",
    # "sbi":    "parsers.sbi",
}
