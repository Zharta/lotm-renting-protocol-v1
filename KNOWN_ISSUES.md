# Known issues

These issues were reported to Zharta and are closed. They are not eligible for
a bug bounty reward, and neither is any issue with the same root cause.
Findings in the audit reports in [`audits/`](audits/) are known as well.

| ID | Component | Issue | Resolution | Reported |
|---|---|---|---|---|
| KI-01 | `RentingV3.withdraw`, `RentingERC721V3.burn` | When a renting token has changed hands, withdrawing the NFT doesn't burn the renting token, which then remains valid for later deposits of the same token id. | Mitigated. All V3 markets are paused for new deposits, and they won't be re-enabled without a fixed deployment. | 8 Oct 2026 |
