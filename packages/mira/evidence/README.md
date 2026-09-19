# Evidence

Canonical `Evidence` + `EvidenceReference`. Elastic adapter projects this layer; SQL remains the source of truth.

Index documents in `index_docs.py` always preserve `source_id` (the canonical UUID) as both `_id` and a keyword field.
