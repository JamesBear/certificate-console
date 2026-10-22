# Demo walkthrough

| # | Step | Assertion |
| --- | --- | --- |
| 1 | Open the console while signed out | redirected to /login |
| 2 | Sign in as Acme Field Services (Sydney) | list loads for that tenant |
| 3 | Certificates load | twenty rows on the first page |
| 4 | Search by learner name: Novak | every row matches the term |
| 5 | Search by serial fragment: 00108 | the serial is found |
| 6 | Clear the search | the full list comes back |
| 7 | Page forward | a different page of rows |
| 8 | Open a certificate | the tenant zone label is shown |
| 9 | Revoke it with a reason | status becomes Revoked and the audit grows |
| 10 | Open bulk issue | courses and eligibility are visible |
| 11 | Issue to every eligible learner | per-learner outcomes are listed |
| 12 | Replay the same request | the replay banner appears and nothing new is issued |
| 13 | Export the current filter as CSV | the file matches the list |
| 14 | Sign out and sign in as Northwind (Perth) | a different tenant's data, no crossover |
