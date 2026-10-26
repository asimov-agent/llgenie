# registry-link-check-hub

## ADDED Requirements

### Requirement: a Hub model page is checked through the Hub's API, never its HTML page

`check_links` SHALL ask the Hub's API, not the model's web page, whether a Hub model page link exists:
a link of the shape `https://huggingface.co/<org>/<repo>` SHALL be checked as
`https://huggingface.co/api/models/<org>/<repo>`. The token SHALL be attached to that request, because
the endpoint authenticates it. A link on any other host, and a Hub URL that is not a `/<org>/<repo>`
model page, SHALL be checked as written.

WHEN a link is a Hub model page
THEN the existence check is a GET on `/api/models/<org>/<repo>` carrying the token, not a GET on the page.

#### Scenario: a Hub model page is asked at the API endpoint

Given a README link `https://huggingface.co/Qwen/Qwen3.8-27B`
When  the link check runs
Then  the request it makes is `https://huggingface.co/api/models/Qwen/Qwen3.8-27B`
And   that request carries `Authorization: Bearer <token>`.

- **Test:** `tests/test_trend_pick.py::test_check_links_asks_the_hub_api_not_the_model_page`

#### Scenario: a non-model link is checked exactly as written

Given the links `https://github.com/Niko1221/Strata` and `https://huggingface.co/collections/x/y`
When  the link check runs
Then  each is requested at its own URL and carries no Authorization header.

- **Test:** `tests/test_trend_pick.py::test_check_links_asks_the_hub_api_not_the_model_page`

### Requirement: a Hub throttle is waited out, never reported as a dead link

`check_links` SHALL route every link through `hf_auth.hub_open`, the repo's single Hub request policy: a
429 SHALL wait `rate_limit_wait` and retry within that policy's bounded budget instead of becoming a
finding, a 5xx or transport failure SHALL retry on that policy's ladder, and a 404 SHALL be definitive
on the first attempt. A link that still does not answer after the budget SHALL be reported dead, named
with the URL and the error.

WHEN the Hub answers a link check with 429
THEN the check waits and retries, and reports no dead link.

#### Scenario: a 429 is not a verdict

Given a transport that answers 429 once and then 200
When  the link check runs over one Hub model page
Then  it reports no dead link and the request was retried.

- **Test:** `tests/test_trend_pick.py::test_check_links_waits_out_a_hub_429`

#### Scenario: a genuinely missing repo is still dead on the first attempt

Given a transport that answers 404 for a link
When  the link check runs
Then  the dead list names that URL and the request was made once.

- **Test:** `tests/test_trend_pick.py::test_link_check_retries_a_gateway_timeout_but_not_a_404`

### Requirement: the token is attached to Hub endpoints only

`hf_auth.authorize` SHALL attach `Authorization` only when the URL is a Hub endpoint — a path under
`/api/` or containing `/resolve/` — and SHALL NOT attach it to a Hub web page (`/<org>/<repo>`), because
the Hub answers a token-bearing web-page GET with its API rate limit. `hub_open` SHALL keep applying the
same rule, so no caller can send the token to a page.

WHEN a request targets a Hub web page
THEN `authorize` leaves it without an Authorization header.

#### Scenario: the token never reaches a Hub web page

Given a request for `https://huggingface.co/Qwen/Qwen3.8-27B`, `https://huggingface.co/api/models/Qwen/Qwen3.8-27B`
  and `https://huggingface.co/Qwen/Qwen3.8-27B/resolve/main/x.gguf`
When  `hf_auth.authorize` is applied to each
Then  the page carries no Authorization header while the API and resolve URLs do.

- **Test:** `tests/test_trend_pick.py::test_authorize_never_sends_the_token_to_a_hub_web_page`
