# Readiness: Virtuals acp-python first contact (branch elm/nano-x402-settlement)

To open the PR the moment a token with external `pull-requests: write` (or a
classic `public_repo` PAT) exists:

```
export GITHUB_TOKEN="$(gh auth token)"        # only after the token is upgraded
cd /root/rai/work-acp/acp-python
gh pr create --repo Virtual-Protocol/acp-python \
  --head PANDeveloper001:elm/nano-x402-settlement \
  --base main \
  --title "docs: add fee-free Nano (XNO) settlement option for x402 jobs" \
  --body-file /root/rai/work-acp/acp-python/.pr-ready/pr_body.md
```

Branch on PANDeveloper001/acp-python: elm/nano-x402-settlement @ f32745e
contains docs/nano-x402-settlement.md + a README "Useful Resources" link,
already rai-publish push-checked (`clean: true`).

Blocker: the gh token is a fine-grained github_pat_ scoped to PANDeveloper001
repos; it cannot createPullRequest / createIssue on external orgs (403 "Resource
not accessible by personal access token"). Filed as swarm/rai network issue #19.
