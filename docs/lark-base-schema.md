# Lark Base Schema Draft

## AI_Call_Log

| Field | Type | Purpose |
| --- | --- | --- |
| Question | Text | Original staff or founder question |
| Scenario | Single select | Lead qualification, pricing, project execution, creator risk, finance, productization |
| Retrieved Sources | Text / linked records | RAGFlow source ids and titles |
| Draft Answer | Long text | Dify generated draft |
| Human Correction | Long text | Business owner correction |
| Review Status | Single select | pending_human_review, approved, revised, rejected |
| Rule Category | Single select | customer, pricing, execution, creator, finance, product |
| Reusable | Checkbox | Whether this case can enter formal knowledge |
| Created At | Created time | Audit |
| Reviewer | User | Owner of correction |

## Case_Library

| Field | Type | Purpose |
| --- | --- | --- |
| Case Title | Text | Human-readable case name |
| Customer Type | Single select | Brand, agency, middleman, platform, creator |
| Market | Single select | GCC, KSA, UAE, Qatar, other |
| Problem | Long text | Situation summary |
| Decision | Long text | Final business judgment |
| Result | Long text | Outcome after execution |
| Sensitive Level | Single select | public, internal, restricted |
| Source Files | Attachment / URL | Original docs or screenshots |

## P0 Rule

The P0 system should not automatically move AI drafts into formal knowledge. A human owner must approve or rewrite the draft first.

