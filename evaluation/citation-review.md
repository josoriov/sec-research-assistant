# Citation-support review

Adjudicate whether each answer's claims are supported by its cited evidence,
then pass pass/fail per question id via `--support-judgements`.

## Q01 (AAPL)

Question: `{"company": "AAPL", "metric": "revenue", "fiscal_years": [2024, 2025]}`

Answer: 'AAPL revenue: FY2024 (2023-10-01 to 2024-09-28) = 391,035,000,000.0 USD; FY2025 (2024-09-29 to 2025-09-27) = 416,161,000,000.0 USD. Year-over-year change: +25,126,000,000.0 USD (+6.43%).'

Abstained: False | Limitations: Figures as reported in the evidence for the stated fiscal periods; the change and percentage are derived from the reported values.

Cited evidence:
- `metric:320193:revenue:2023-10-01:2024-09-28` revenue (2023-10-01 to 2024-09-28) (full cited text):

391035000000.0

- `metric:320193:revenue:2024-09-29:2025-09-27` revenue (2024-09-29 to 2025-09-27) (full cited text):

416161000000.0


## Q02 (AAPL)

Question: `{"company": "AAPL", "metric": "net_income", "fiscal_years": [2023, 2024]}`

Answer: 'AAPL net income: FY2023 (2022-09-25 to 2023-09-30) = 96,995,000,000.0 USD; FY2024 (2023-10-01 to 2024-09-28) = 93,736,000,000.0 USD. Year-over-year change: -3,259,000,000.0 USD (-3.36%).'

Abstained: False | Limitations: None

Cited evidence:
- `metric:320193:net_income:2022-09-25:2023-09-30` net_income (2022-09-25 to 2023-09-30) (full cited text):

96995000000.0

- `metric:320193:net_income:2023-10-01:2024-09-28` net_income (2023-10-01 to 2024-09-28) (full cited text):

93736000000.0


## Q03 (AAPL)

Question: `{"company": "AAPL", "metric": "operating_cash_flow", "fiscal_years": [2024, 2025]}`

Answer: 'AAPL operating_cash_flow: FY2024 (2023-10-01 to 2024-09-28) = 118,254,000,000.0 USD; FY2025 (2024-09-29 to 2025-09-27) = 111,482,000,000.0 USD. Year-over-year change: -6,772,000,000.0 USD (-5.73%).'

Abstained: False | Limitations: Both figures are as reported in the same 10-K (accession 0000320193-25-000079, filed 2025-10-31); no conflicting evidence.

Cited evidence:
- `metric:320193:operating_cash_flow:2023-10-01:2024-09-28` operating_cash_flow (2023-10-01 to 2024-09-28) (full cited text):

118254000000.0

- `metric:320193:operating_cash_flow:2024-09-29:2025-09-27` operating_cash_flow (2024-09-29 to 2025-09-27) (full cited text):

111482000000.0


## Q04 (MSFT)

Question: `{"company": "MSFT", "metric": "revenue", "fiscal_years": [2024, 2025]}`

Answer: 'Microsoft (MSFT) revenue: FY2024 (2023-07-01 to 2024-06-30) = 245,122,000,000 USD; FY2025 (2024-07-01 to 2025-06-30) = 281,724,000,000 USD. Year-over-year change = +36,602,000,000 USD (+14.93%).'

Abstained: False | Limitations: Both figures come from a single 10-K (accession 0001193125-26-323660, filed 2026-07-29) as reported in the evidence; the percentage change is derived from the provided calculation.

Cited evidence:
- `metric:789019:revenue:2023-07-01:2024-06-30` revenue (2023-07-01 to 2024-06-30) (full cited text):

245122000000.0

- `metric:789019:revenue:2024-07-01:2025-06-30` revenue (2024-07-01 to 2025-06-30) (full cited text):

281724000000.0


## Q05 (MSFT)

Question: `{"company": "MSFT", "metric": "net_income", "fiscal_years": [2025, 2026]}`

Answer: 'MSFT net income: FY2025 (2024-07-01 to 2025-06-30) = 101,832,000,000.0 USD; FY2026 (2025-07-01 to 2026-06-30) = 133,749,000,000.0 USD. Year-over-year change: +31,917,000,000.0 USD (+31.3%). Both figures are company-reported values from Form 10-K (accession 0001193125-26-323660, filed 2026-07-29).'

Abstained: False | Limitations: None

Cited evidence:
- `metric:789019:net_income:2024-07-01:2025-06-30` net_income (2024-07-01 to 2025-06-30) (full cited text):

101832000000.0

- `metric:789019:net_income:2025-07-01:2026-06-30` net_income (2025-07-01 to 2026-06-30) (full cited text):

133749000000.0


## Q06 (MSFT)

Question: `{"company": "MSFT", "metric": "operating_cash_flow", "fiscal_years": [2024, 2025]}`

Answer: "MSFT operating_cash_flow: FY2024 (2023-07-01 to 2024-06-30) = 118,548,000,000.0 USD; FY2025 (2024-07-01 to 2025-06-30) = 136,162,000,000.0 USD. Year-over-year change: +17,614,000,000.0 USD (+14.86%) as computed in the provided SQL calculations. Both figures are reported in the company's 10-K (accession 0001193125-26-323660, filed 2026-07-29)."

Abstained: False | Limitations: Figures are as reported in the cited evidence; the change/percentage is derived from the supplied calculations rather than directly from the evidence passages.

Cited evidence:
- `metric:789019:operating_cash_flow:2023-07-01:2024-06-30` operating_cash_flow (2023-07-01 to 2024-06-30) (full cited text):

118548000000.0

- `metric:789019:operating_cash_flow:2024-07-01:2025-06-30` operating_cash_flow (2024-07-01 to 2025-06-30) (full cited text):

136162000000.0


## Q07 (AMZN)

Question: `{"company": "AMZN", "metric": "revenue", "fiscal_years": [2023, 2024]}`

Answer: "AMZN revenue: FY2023 (2023-01-01 to 2023-12-31) = 574,785,000,000 USD; FY2024 (2024-01-01 to 2024-12-31) = 637,959,000,000 USD. Year-over-year change = +63,174,000,000 USD, an increase of approximately 11.0% (10.99%). Both figures are as reported in the company's Form 10-K (accession 0001018724-26-000004, filed 2026-02-06)."

Abstained: False | Limitations: The absolute and percentage change figures come from the provided SQL calculations, which agree with the reported metric values in the evidence; no conflicting data was present.

Cited evidence:
- `metric:1018724:revenue:2023-01-01:2023-12-31` revenue (2023-01-01 to 2023-12-31) (full cited text):

574785000000.0

- `metric:1018724:revenue:2024-01-01:2024-12-31` revenue (2024-01-01 to 2024-12-31) (full cited text):

637959000000.0


## Q08 (AMZN)

Question: `{"company": "AMZN", "metric": "net_income", "fiscal_years": [2024, 2025]}`

Answer: 'AMZN net income: FY2024 = 59,248,000,000 USD; FY2025 = 77,670,000,000 USD; change = +18,422,000,000 USD (+31.09%).'

Abstained: False | Limitations: None

Cited evidence:
- `metric:1018724:net_income:2024-01-01:2024-12-31` net_income (2024-01-01 to 2024-12-31) (full cited text):

59248000000.0

- `metric:1018724:net_income:2025-01-01:2025-12-31` net_income (2025-01-01 to 2025-12-31) (full cited text):

77670000000.0


## Q09 (AMZN)

Question: `{"company": "AMZN", "metric": "operating_cash_flow", "fiscal_years": [2023, 2024]}`

Answer: 'AMZN operating cash flow: FY2023 = 84,946,000,000 USD; FY2024 = 115,877,000,000 USD; change = +30,931,000,000 USD (+36.4%)'

Abstained: False | Limitations: Figures as reported in the provided evidence (10-K, accession 0001018724-26-000004); year-over-year change and percentage are computed from those values.

Cited evidence:
- `metric:1018724:operating_cash_flow:2023-01-01:2023-12-31` operating_cash_flow (2023-01-01 to 2023-12-31) (full cited text):

84946000000.0

- `metric:1018724:operating_cash_flow:2024-01-01:2024-12-31` operating_cash_flow (2024-01-01 to 2024-12-31) (full cited text):

115877000000.0


## Q10 (META)

Question: `{"company": "META", "metric": "revenue", "fiscal_years": [2024, 2025]}`

Answer: 'Meta revenue: FY2024 = 164,501,000,000 USD; FY2025 = 200,966,000,000 USD. Change = +36,465,000,000 USD (+22.17%).'

Abstained: False | Limitations: Figures are as reported in the FY2025 10-K (accession 0001628280-26-003942, filed 2026-01-29); the change and percentage change are computed from these reported values.

Cited evidence:
- `metric:1326801:revenue:2024-01-01:2024-12-31` revenue (2024-01-01 to 2024-12-31) (full cited text):

164501000000.0

- `metric:1326801:revenue:2025-01-01:2025-12-31` revenue (2025-01-01 to 2025-12-31) (full cited text):

200966000000.0


## Q11 (META)

Question: `{"company": "META", "metric": "operating_cash_flow", "fiscal_years": [2023, 2024]}`

Answer: 'META operating_cash_flow: FY2023 = 71,113,000,000 USD; FY2024 = 91,328,000,000 USD; change = +20,215,000,000 USD (+28.4%)'

Abstained: False | Limitations: Figures are as reported in the 10-K (accession 0001628280-26-003942, filed 2026-01-29); the change and percentage are derived from the reported values.

Cited evidence:
- `metric:1326801:operating_cash_flow:2023-01-01:2023-12-31` operating_cash_flow (2023-01-01 to 2023-12-31) (full cited text):

71113000000.0

- `metric:1326801:operating_cash_flow:2024-01-01:2024-12-31` operating_cash_flow (2024-01-01 to 2024-12-31) (full cited text):

91328000000.0


## Q12 (GOOGL)

Question: `{"company": "GOOGL", "metric": "revenue", "fiscal_years": [2024, 2025]}`

Answer: "Alphabet (GOOGL) revenue: FY2024 = 350,018,000,000 USD (350.018 billion); FY2025 = 402,836,000,000 USD (402.836 billion). Year-over-year change = +52,818,000,000 USD, an increase of approximately 15.09%. Both figures are as reported in the company's Form 10-K (accession 0001652044-26-000018, filed 2026-02-05)."

Abstained: False | Limitations: Figures are company-reported values from the 10-K; the percentage change and absolute change are computed from those reported values rather than directly reported.

Cited evidence:
- `metric:1652044:revenue:2024-01-01:2024-12-31` revenue (2024-01-01 to 2024-12-31) (full cited text):

350018000000.0

- `metric:1652044:revenue:2025-01-01:2025-12-31` revenue (2025-01-01 to 2025-12-31) (full cited text):

402836000000.0


## Q13 (GOOGL)

Question: `{"company": "GOOGL", "metric": "net_income", "fiscal_years": [2023, 2024]}`

Answer: 'GOOGL net income: FY2023 = 73,795,000,000.0 USD; FY2024 = 100,118,000,000.0 USD. Year-over-year change = +26,323,000,000.0 USD (+35.67%).'

Abstained: False | Limitations: None

Cited evidence:
- `metric:1652044:net_income:2023-01-01:2023-12-31` net_income (2023-01-01 to 2023-12-31) (full cited text):

73795000000.0

- `metric:1652044:net_income:2024-01-01:2024-12-31` net_income (2024-01-01 to 2024-12-31) (full cited text):

100118000000.0


## Q14 (AAPL)

Question: `{"company": "AAPL", "question": "why did revenue change year over year?", "limit": 5}`

Answer: "The evidence explains the revenue change only partially, at the segment level. For fiscal 2024 vs 2023, total net sales rose 2% to $391,035 million; Americas net sales increased 3% 'due primarily to higher net sales of Services,' Europe rose 7%, Rest of Asia Pacific 4%, Japan 3%, while Greater China fell 8% to $66,952 million. The passage cuts off after beginning the Europe discussion, and no product-level (iPhone, Mac, etc.) explanation for the 2024 total revenue change is included in the provided evidence. For fiscal 2023 vs 2022, total net sales fell 3% to $383,285 million; the Americas declined 4% or $7.1 billion 'due to lower net sales of iPhone and Mac, partially offset by higher net sales of Services.' The company also notes that fiscal 2023 spanned 53 weeks versus 52 weeks in 2022 and 2024, and that macroeconomic conditions (inflation, interest rates, currency fluctuations) have impacted results. Additionally, management reports that R&D growth in 2024 and 2023 was driven primarily by headcount-related expenses, and SG&A rose $1.2 billion in 2024 — but these are expense drivers, not revenue drivers."

Abstained: False | Limitations: The evidence does not contain a consolidated, company-level explanation of the total year-over-year revenue change (e.g., drivers by product category for 2024). The 2024 segment commentary is truncated mid-sentence after 'Europe', and no explanation at all is provided for Europe, Greater China, Japan, or Rest of Asia Pacific in 2024, nor for the non-Americas segments in 2023. Answer relies on segment-level statements only; no calculations were available.

Cited evidence:
- `passage:315` Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (full cited text):

The Company’s fiscal year is the 52- or 53-week period that ends on the last Saturday of September. An additional week is included in the first fiscal quarter every five or six years to realign the Company’s fiscal quarters with calendar quarters, which occurred in the first quarter of 2023. The Company’s fiscal years 2024 and 2022 spanned 52 weeks each, whereas fiscal year 2023 spanned 53 weeks. Macroeconomic Conditions Macroeconomic conditions, including inflation, interest rates and currency fluctuations, have directly and indirectly impacted, and could in the future materially impact, the Company’s results of operations and financial condition. Apple Inc. | 2024 Form 10-K | 21 Segment Operating Performance The following table shows net sales by reportable segment for 2024, 2023 and 2022 (dollars in millions): | 2024 | | Change | | 2023 | | Change | | 2022 ; Americas | $ | 167,045 | | | 3 | % | | $ | 162,560 | | | (4) | % | | $ | 169,658 | ; Europe | 101,328 | | | 7 | % | | 94,294 | | | (1) | % | | 95,118 | ; Greater China | 66,952 | | | (8) | % | | 72,559 | | | (2) | % | | 74,200 | ; Japan | 25,052 | | | 3 | % | | 24,257 | | | (7) | % | | 25,977 | ; Rest of Asia Pacific | 30,658 | | | 4 | % | | 29,615 | | | 1 | % | | 29,375 | ; Total net sales | $ | 391,035 | | | 2 | % | | $ | 383,285 | | | (3) | % | | $ | 394,328 | Americas Americas net sales increased during 2024 compared to 2023 due primarily to higher net sales of Services. Europe

- `passage:319` Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (full cited text):

| 2024 | | Change | | 2023 | | Change | | 2022 ; Research and development | $ | 31,370 | | | 5 | % | | $ | 29,915 | | | 14 | % | | $ | 26,251 | ; Percentage of total net sales | 8 | % | | | | 8 | % | | | | 7 | % ; Selling, general and administrative | $ | 26,097 | | | 5 | % | | $ | 24,932 | | | (1) | % | | $ | 25,094 | ; Percentage of total net sales | 7 | % | | | | 7 | % | | | | 6 | % ; Total operating expenses | $ | 57,467 | | | 5 | % | | $ | 54,847 | | | 7 | % | | $ | 51,345 | ; Percentage of total net sales | 15 | % | | | | 14 | % | | | | 13 | % Research and Development The growth in R&D expense during 2024 compared to 2023 was driven primarily by increases in headcount-related expenses. Selling, General and Administrative Selling, general and administrative expense increased $1.2 billion during 2024 compared to 2023. Apple Inc. | 2024 Form 10-K | 24 Provision for Income Taxes Provision for income taxes, effective tax rate and statutory federal income tax rate for 2024, 2023 and 2022 were as follows (dollars in millions): | 2024 | | 2023 | | 2022 ; Provision for income taxes | $ | 29,749 | | | $ | 16,741 | | | $ | 19,300 | ; Effective tax rate | 24.1 | % | | 14.7 | % | | 16.2 | % ; Statutory federal income tax rate | 21 | % | | 21 | % | | 21 | %

- `passage:517` Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (full cited text):

Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations The following discussion should be read in conjunction with the consolidated financial statements and accompanying notes included in Part II, Item 8 of this Form 10-K. This Item generally discusses 2023 and 2022 items and year-to-year comparisons between 2023 and 2022. Discussions of 2021 items and year-to-year comparisons between 2022 and 2021 are not included, and can be found in “Management’s Discussion and Analysis of Financial Condition and Results of Operations” in Part II, Item 7 of the Company’s Annual Report on Form 10-K for the fiscal year ended September 24, 2022. Fiscal Period The Company’s fiscal year is the 52- or 53-week period that ends on the last Saturday of September. An additional week is included in the first fiscal quarter every five or six years to realign the Company’s fiscal quarters with calendar quarters, which occurred in the first quarter of 2023. The Company’s fiscal year 2023 spanned 53 weeks, whereas fiscal years 2022 and 2021 spanned 52 weeks each. Fiscal Year Highlights The Company’s total net sales were $383.3 billion and net income was $97.0 billion during 2023.

- `passage:519` Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (full cited text):

In May 2023, the Company announced a new share repurchase program of up to $90 billion and raised its quarterly dividend from $0.23 to $0.24 per share beginning in May 2023. During 2023, the Company repurchased $76.6 billion of its common stock and paid dividends and dividend equivalents of $15.0 billion. Macroeconomic Conditions Macroeconomic conditions, including inflation, changes in interest rates, and currency fluctuations, have directly and indirectly impacted, and could in the future materially impact, the Company’s results of operations and financial condition. Apple Inc. | 2023 Form 10-K | 20 Segment Operating Performance The following table shows net sales by reportable segment for 2023, 2022 and 2021 (dollars in millions): | 2023 | | Change | | 2022 | | Change | | 2021 ; Net sales by reportable segment: | | | | | | | | | ; Americas | $ | 162,560 | | | (4) | % | | $ | 169,658 | | | 11 | % | | $ | 153,306 | ; Europe | 94,294 | | | (1) | % | | 95,118 | | | 7 | % | | 89,307 | ; Greater China | 72,559 | | | (2) | % | | 74,200 | | | 9 | % | | 68,366 | ; Japan | 24,257 | | | (7) | % | | 25,977 | | | (9) | % | | 28,482 | ; Rest of Asia Pacific | 29,615 | | | 1 | % | | 29,375 | | | 11 | % | | 26,356 | ; Total net sales | $ | 383,285 | | | (3) | % | | $ | 394,328 | | | 8 | % | | $ | 365,817 | Americas Americas net sales decreased 4% or $7.1 billion during 2023 compared to 2022 due to lower net sales of iPhone and Mac, partially offset by higher net sales of Services. Europe


## Q15 (MSFT)

Question: `{"company": "MSFT", "question": "what drove operating cash flow?", "limit": 5}`

Answer: 'For fiscal year 2025, cash from operations increased $17.6 billion to $136.2 billion, primarily driven by an increase in cash received from customers. This was offset in part by increases in cash paid to suppliers and employees and cash used to pay income taxes.'

Abstained: False | Limitations: The evidence explains the drivers of the year-over-year change in operating cash flow for fiscal 2025; it does not break down the composition of the $136.2 billion operating cash flow balance itself. Passages 5717, 5537, 5020, and 5037 do not address operating cash flow drivers.

Cited evidence:
- `passage:5041` Item 7 (full cited text):

Cash from operations increased $17.6 billion to $136.2 billion for fiscal year 2025, primarily due to an increase in cash received from customers, offset in part by an increase in cash paid to suppliers and employees and cash used to pay income taxes. Cash used in financing increased $13.9 billion to $51.7 billion for fiscal year 2025, primarily due to a $9.5 billion increase in cash used for repayments of debt, net of proceeds. Cash used in investing decreased $24.4 billion to $72.6 billion for fiscal year 2025, primarily due to a $63.2 billion decrease in cash used for acquisitions of companies, net of cash acquired and divestitures, and purchases of intangible and other assets, offset in part by a $22.3 billion increase in cash used in net investment purchases, sales, and maturities, and a $20.1 billion increase in additions to property and equipment. 43


## Q16 (AMZN)

Question: `{"company": "AMZN", "question": "what were the main drivers of revenue growth?", "limit": 5}`

Answer: 'The provided evidence does not contain information about revenue or its growth drivers. All passages cover operating expenses (cost of sales, fulfillment, technology and infrastructure, sales and marketing, G&A) and related percentages of net sales, plus general risk factor language about expansion and fluctuations in operating results. None of the passages state net sales figures or identify drivers of revenue growth, so the question cannot be answered from this evidence.'

Abstained: True | Limitations: Evidence is limited to operating expense tables for FY2022-2025 and generic risk-factor language; no revenue/net sales figures or management commentary on revenue growth drivers were provided.

Cited evidence:

## Q17 (META)

Question: `{"company": "META", "question": "how did operating cash flow change?", "limit": 5}`

Answer: 'Net cash provided by operating activities increased each year: from $50,475 million in 2022 to $71,113 million in 2023, to $91,328 million in 2024, and to $115,800 million in 2025. The company reported that the 2025 increase versus 2024 was primarily due to an increase in cash collections from customers driven by higher revenue and lower cash paid for income taxes, partially offset by higher operational spending. For 2024 versus 2023, it attributed the increase to higher cash collection from customers driven by increased revenue, partially offset by higher cash paid for income taxes and other operational spending. For 2023 versus 2022, the increase was mostly due to higher cash collection from customers driven by revenue growth and a decrease in payments to vendors.'

Abstained: False | Limitations: None

Cited evidence:
- `passage:12829` Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations (full cited text):

| Year Ended December 31, ; | 2025 | | 2024 | | 2023 ; Net cash provided by operating activities | $ | 115,800 | | | $ | 91,328 | | | $ | 71,113 | ; Net cash used in investing activities | $ | (102,003) | | | $ | (47,150) | | | $ | (24,495) | ; Net cash used in financing activities | $ | (20,370) | | | $ | (40,781) | | | $ | (19,500) | Cash Provided by Operating Activities Cash provided by operating activities during 2025 mostly consisted of $60.46 billion net income adjusted for certain non-cash items, such as $20.43 billion of share-based compensation expense, $18.74 billion of deferred income taxes, and $18.62 billion of depreciation and amortization expense. The increase in cash flows from operating activities during 2025 compared to 2024, was primarily due to an increase in cash collections from our customers driven by the increase in revenue and lower cash paid for income taxes, partially offset by higher operational spending. Cash Used in Investing Activities Cash used in investing activities during 2025 mostly consisted of $69.69 billion of purchases of property and equipment as we continued to invest in servers, data centers, and network infrastructure, and $18.33 billion of purchases of non-marketable equity investments, and $10.05 billion of net purchases of marketable securities. The increase in cash used in investing activities during 2025 compared to 2024 was mostly due to increases in purchases of property and equipment and non-marketable equity investments.

- `passage:13317` Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations (full cited text):

| Year Ended December 31, ; | 2024 | | 2023 | | 2022 ; Net cash provided by operating activities | $ | 91,328 | | | $ | 71,113 | | | $ | 50,475 | ; Net cash used in investing activities | $ | (47,150) | | | $ | (24,495) | | | $ | (28,970) | ; Net cash used in financing activities | $ | (40,781) | | | $ | (19,500) | | | $ | (22,136) | Cash Provided by Operating Activities Cash provided by operating activities during 2024 mostly consisted of $62.36 billion net income adjusted for certain non-cash items, such as $16.69 billion of share-based compensation expense and $15.50 billion of depreciation and amortization expense. The increase in cash flows from operating activities during 2024 compared to 2023, was due to an increase in cash collection from our customers driven by the increase in revenue, partially offset by higher cash paid for income taxes and other operational spending. Cash Used in Investing Activities Cash used in investing activities during 2024 mostly consisted of $37.26 billion of purchases of property and equipment as we continued to invest in servers, data centers, and network infrastructure, and $9.75 billion of net purchases of marketable securities. The increase in cash used in investing activities during 2024 compared to 2023 was mostly due to increases in net purchases of marketable debt securities and property and equipment.

- `passage:13782` Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations (full cited text):

| Year Ended December 31, ; | 2023 | | 2022 | | 2021 ; Net cash provided by operating activities | $ | 71,113 | | | $ | 50,475 | | | $ | 57,683 | ; Net cash used in investing activities | $ | (24,495) | | | $ | (28,970) | | | $ | (7,570) | ; Net cash used in financing activities | $ | (19,500) | | | $ | (22,136) | | | $ | (50,728) | Cash Provided by Operating Activities Cash provided by operating activities during 2023 mostly consisted of $39.10 billion net income adjusted for certain non-cash items, such as $14.03 billion of share-based compensation expense and $11.18 billion of depreciation and amortization expense, as well as $3.29 billion of favorable changes in working capital. The increase in cash flows from operating activities during 2023 compared to 2022 was mostly du e to an increase in cash collection from our customers driven by the increase in revenue, and a decrease in payments to our vendors. Cash Used in Investing Activities Cash used in investing activities during 2023 mostly consisted of $27.05 billion of net purchases of property and equipment as we continued to invest in data centers, servers, and network infrastructure, partially offset by $3.20 billion net proceeds from maturities and sales of marketable debt securities. The decrease in cash used in investing activities during 2023 compared to 2022 was mostly due to a decrease in purchases of property and equipment.


## Q18 (GOOGL)

Question: `{"company": "GOOGL", "question": "what factors affected revenue?", "limit": 5}`

Answer: 'The company identified several factors that could affect its revenue. In its risk factors, it stated that its revenue growth rate could decline due to: changes in customer usage and demand for existing products and increasing demand for competing technologies; changes in devices and modalities used to access its products and services; changes in geographic mix; deceleration or declines in advertiser spending; competition; decreases in pricing of products and services; ongoing product and policy changes; and shifts to lower-priced products and services. In MD&A, the company reported that fluctuations in revenues have been, and may continue to be, affected by a combination of general factors including changes in foreign currency exchange rates and changes in pricing (such as those resulting from changes in fee structures, discounts, and customer incentives). The company also generated revenues from online advertising, cloud-based solutions, sales of other products and services (apps, in-app purchases, devices), and consumer subscription fees, and noted hedging gains (losses) related to revenue at the Alphabet level. Note: the MD&A list of factors appears truncated in the provided evidence, so additional factors may exist that are not shown.'

Abstained: False | Limitations: Evidence for MD&A factors (passage:6589) is cut off mid-list, so the full enumeration of factors the company reported is not available; passages 6657 and 6611 describe revenue recognition and hedging rather than factors affecting revenue levels.

Cited evidence:
- `passage:5863` ITEM 1A. RISK FACTORS (full cited text):

Our revenue growth rate could decline over time as a result of a number of factors, including changes in customer usage and demand for our existing products and increasing demand for competing technologies; changes in the devices and modalities used to access our products and services; changes in geographic mix; deceleration or declines in advertiser spending; competition; decreases in the pricing of our products and services; ongoing product and policy changes; and shifts to lower priced products and services.

- `passage:6589` ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS (full cited text):

Our employees are among our best assets and are critical for our continued success. We expect to continue hiring talented employees around the globe and to provide competitive compensation programs. For additional information, see Culture and Workforce in Part I, Item 1 Business of this Annual Report on Form 10-K. Revenues and Monetization Metrics We generate revenues by delivering relevant, cost-effective online advertising; cloud-based solutions that provide enterprise customers of all sizes with infrastructure and platform services as well as communication and collaboration tools; sales of other products and services, such as apps and in-app purchases, and devices; and fees received for consumer subscription-based products. For additional information on how we recognize revenue, see Note 1 of the Notes to Consolidated Financial Statements included in Item 8 of this Annual Report on Form 10-K. In addition to the long-term trends and their financial effect on our business discussed above, fluctuations in our revenues have been, and may continue to be, affected by a combination of general factors, including: • changes in foreign currency exchange rates; 30. Table of Contents | Alphabet Inc. • changes in pricing, such as those resulting from changes in fee structures, discounts, and customer incentives;

- `passage:6657` ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA (full cited text):

In January 2023, we completed an assessment of the useful lives of our servers and network equipment and adjusted the estimated useful life of our servers from four years to six years and the estimated useful life of certain network equipment from five years to six years . This change in accounting estimate was effective beginning in fiscal year 2023. Based on the carrying value of servers and certain network equipment as of December 31, 2022, and those placed in service during the year ended December 31, 2023, the effect of this change in estimate was a reduction in depreciation expense of $ 3.9 billion and an increase in net income of $ 3.0 billion, or $ 0.24 per basic and $ 0.24 per diluted share, for the year ended December 31, 2023. Revenue Recognition Revenues are recognized when control of the promised goods or services is transferred to our customers, and the collectibility of an amount that we expect in exchange for those goods or services is probable. Sales and other similar taxes are excluded from revenues. Advertising Revenues We generate advertising revenues primarily by delivering advertising on: • Google Search and other properties, including revenues from traffic generated by search distribution partners who use Google.com as their default search in browsers, toolbars, etc. and other Google owned and operated properties like Gmail, Google Maps, and Google Play; • YouTube properties; and

- `passage:6611` ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS (full cited text):

| | | Year Ended December 31, ; | | | 2022 | | 2023 ; Operating income (loss): | | | | | ; Google Services | | | $ | 82,699 | | | $ | 95,858 | ; Google Cloud | | | (1,922) | | | 1,716 | ; Other Bets | | | (4,636) | | | (4,095) | ; Alphabet-level activities (1) | | | (1,299) | | | (9,186) | ; Total income from operations | | | $ | 74,842 | | | $ | 84,293 | (1) In addition to the costs included in Alphabet-level activities, hedging gains (losses) related to revenue were $2.0 billion and $236 million in 2022 and 2023, respectively. For the year ended December 31, 2023, Alphabet-level activities include charges related to the reduction in force and our office space optimization efforts totaling $3.9 billion. In addition, for the year ended December 31, 2023, we incurred $269 million in accelerated rent and accelerated depreciation. For additional information relating to our workforce reduction and other initiatives, see Note 8 of the Notes to Consolidated Financial Statements included in Item 8 of this Annual Report on Form 10-K. For additional information relating to our segments, see Note 15 of the Notes to Consolidated Financial Statements included in Item 8 of this Annual Report on Form 10-K. Google Services


## Q19 (AAPL)

Question: `{"company": "AAPL", "metric": "revenue", "fiscal_years": [2024, 2025], "question": "why did revenue change?", "limit": 5}`

Answer: "The evidence does not contain management's explanation of the drivers behind the revenue change. What can be supported is the arithmetic composition of the $25.126B (+6.4%) increase: per the FY2025 consolidated statements of operations, total net sales rose from $391,035M (FY2024) to $416,161M (FY2025), comprising Products net sales increasing from $294,866M to $307,003M (about +$12.1B) and Services net sales increasing from $96,169M to $109,158M (about +$13.0B) [metric:320193:revenue:2023-10-01:2024-09-28, metric:320193:revenue:2024-09-29:2025-09-27, passage:125]. Thus roughly half of the growth came from Services and half from Products. The provided passages include no FY2025 MD&A discussion of demand, pricing, product-cycle, or geographic factors behind these increases, so no causal 'why' can be established from this evidence. Any statement about specific drivers would be my inference, not company-reported."

Abstained: True | Limitations: Evidence contains the FY2025 income statement figures allowing a Products/Services decomposition of the change, but no FY2025 MD&A passage explaining drivers of the revenue change. The only MD&A passage provided (passage:319) covers operating expenses for 2024 vs 2023, not the FY2025 revenue discussion. Segment/geographic disaggregation for FY2025 (e.g., Greater China, iPhone) is also absent.

Cited evidence:
- `metric:320193:revenue:2023-10-01:2024-09-28` revenue (2023-10-01 to 2024-09-28) (full cited text):

391035000000.0

- `metric:320193:revenue:2024-09-29:2025-09-27` revenue (2024-09-29 to 2025-09-27) (full cited text):

416161000000.0

- `passage:125` Item 8. Financial Statements and Supplementary Data (full cited text):

| Years ended ; | September 27, 2025 | | September 28, 2024 | | September 30, 2023 ; Net sales: | | | | | ; Products | $ | 307,003 | | | $ | 294,866 | | | $ | 298,085 | ; Services | 109,158 | | | 96,169 | | | 85,200 | ; Total net sales | 416,161 | | | 391,035 | | | 383,285 | ; Cost of sales: | | | | | ; Products | 194,116 | | | 185,233 | | | 189,282 | ; Services | 26,844 | | | 25,119 | | | 24,855 | ; Total cost of sales | 220,960 | | | 210,352 | | | 214,137 | ; Gross margin | 195,201 | | | 180,683 | | | 169,148 | ; Operating expenses: | | | | | ; Research and development | 34,550 | | | 31,370 | | | 29,915 | ; Selling, general and administrative | 27,601 | | | 26,097 | | | 24,932 | ; Total operating expenses | 62,151 | | | 57,467 | | | 54,847 | ; Operating income | 133,050 | | | 123,216 | | | 114,301 | ; Other income/(expense), net | ( 321 ) | | | 269 | | | ( 565 ) | ; Income before provision for income taxes | 132,729 | | | 123,485 | | | 113,736 | ; Provision for income taxes | 20,719 | | | 29,749 | | | 16,741 | ; Net income | $ | 112,010 | | | $ | 93,736 | | | $ | 96,995 | ; Earnings per share: | | | | | ; Basic | $ | 7.49 | | | $ | 6.11 | | | $ | 6.16 | ; Diluted | $ | 7.46 | | | $ | 6.08 | | | $ | 6.13 | ; Shares used in computing earnings per share: | | | | | ; Basic | 14,948,500 | | | 15,343,783 | | | 15,744,231 | ; Diluted | 15,004,697 | | | 15,408,095 | | | 15,812,547 | See accompanying Notes to Consolidated Financial Statements. Apple Inc. | 2025 Form 10-K | 29


## Q20 (MSFT)

Question: `{"company": "MSFT", "metric": "revenue", "fiscal_years": [2025, 2026], "question": "why did revenue change?", "limit": 5}`

Answer: "The evidence does not contain any management discussion (MD&A) explaining the cause of the revenue change, so the 'why' cannot be supported. The reported segment data decompose the $50,115 million increase as follows: Intelligent Cloud revenue rose from $106,265M to $137,791M (+$31,526M), Productivity and Business Processes rose from $120,810M to $139,996M (+$19,186M), and More Personal Computing fell from $54,649M to $54,052M (-$597M), summing to the total change from $281,724M to $331,839M. These segment figures are reported; the attribution of the increase primarily to Intelligent Cloud is arithmetic inference from that reported data, not a stated causal explanation."

Abstained: True | Limitations: Evidence provides only segment revenue tables and unearned revenue data; no narrative explanation of drivers (e.g., product/service demand, pricing, or acquisitions) is included, and no MD&A section was supplied. The segment decomposition is computed from reported figures rather than stated by the company as the reason for the change.

Cited evidence:
- `metric:789019:revenue:2024-07-01:2025-06-30` revenue (2024-07-01 to 2025-06-30) (full cited text):

281724000000.0

- `metric:789019:revenue:2025-07-01:2026-06-30` revenue (2025-07-01 to 2026-06-30) (full cited text):

331839000000.0

- `passage:4734` Item 8 (full cited text):

Segment revenue, cost of revenue, operating expenses, and operating income were as follows during the periods presented: (In millions) | | | | | | | | | | | | ; Year Ended June 30, | | | 2026 | | | | 2025 | | | | 2024 | ; Productivity and Business Processes | | | | | | | | | | | | ; Revenue | | $ | 139,996 | | | $ | 120,810 | | | $ | 106,820 | ; Cost of revenue | | | 25,017 | | | | 22,422 | | | | 19,611 | ; Operating expenses | | | 31,100 | | | | 28,615 | | | | 27,548 | ; Operating income | | $ | 83,879 | | | $ | 69,773 | | | $ | 59,661 | ; Intelligent Cloud | | | | | | | | | | | | ; Revenue | | $ | 137,791 | | | $ | 106,265 | | | $ | 87,464 | ; Cost of revenue | | | 57,876 | | | | 40,171 | | | | 29,611 | ; Operating expenses | | | 22,943 | | | | 21,505 | | | | 20,040 | ; Operating income | | $ | 56,972 | | | $ | 44,589 | | | $ | 37,813 | ; More Personal Computing | | | | | | | | | | | | ; Revenue | | $ | 54,052 | | | $ | 54,649 | | | $ | 50,838 | ; Cost of revenue | | | 23,481 | | | | 25,238 | | | | 24,892 | ; Operating expenses | | | 16,185 | | | | 15,245 | | | | 13,987 | ; Operating income | | $ | 14,386 | | | $ | 14,166 | | | $ | 11,959 | ; Total | | | | | | | | | | | | ; Revenue | | $ | 331,839 | | | $ | 281,724 | | | $ | 245,122 | ; Cost of revenue | | | 106,374 | | | | 87,831 | | | | 74,114 | ; Operating expenses | | | 70,228 | | | | 65,365 | | | | 61,575 | ; Operating income | | $ | 155,237 | | | $ | 128,528 | | | $ | 109,433 |

- `passage:5205` Item 8 (full cited text):

Item 8 Segment revenue, cost of revenue, operating expenses, and operating income were as follows during the periods presented: (In millions) | | | | | | | | | | | | ; Year Ended June 30, | | | 2025 | | | | 2024 | | | | 2023 | ; Productivity and Business Processes | | | | | | | | | | | | ; Revenue | | $ | 120,810 | | | $ | 106,820 | | | $ | 94,151 | ; Cost of revenue | | | 22,422 | | | | 19,611 | | | | 17,202 | ; Operating expenses | | | 28,615 | | | | 27,548 | | | | 26,875 | ; Operating Income | | $ | 69,773 | | | $ | 59,661 | | | $ | 50,074 | ; Intelligent Cloud | | | | | | | | | | | | ; Revenue | | $ | 106,265 | | | $ | 87,464 | | | $ | 72,944 | ; Cost of revenue | | | 40,171 | | | | 29,611 | | | | 24,109 | ; Operating expenses | | | 21,505 | | | | 20,040 | | | | 20,424 | ; Operating Income | | $ | 44,589 | | | $ | 37,813 | | | $ | 28,411 | ; More Personal Computing | | | | | | | | | | | | ; Revenue | | $ | 54,649 | | | $ | 50,838 | | | $ | 44,820 | ; Cost of revenue | | | 25,238 | | | | 24,892 | | | | 24,552 | ; Operating expenses | | | 15,245 | | | | 13,987 | | | | 10,230 | ; Operating Income | | $ | 14,166 | | | $ | 11,959 | | | $ | 10,038 | ; Total | | | | | | | | | | | | ; Revenue | | $ | 281,724 | | | $ | 245,122 | | | $ | 211,915 | ; Cost of revenue | | | 87,831 | | | | 74,114 | | | | 65,863 | ; Operating expenses | | | 65,365 | | | | 61,575 | | | | 57,529 | ; Operating Income | | $ | 128,528 | | | $ | 109,433 | | | $ | 88,523 |


## Q21 (AMZN)

Question: `{"company": "AMZN", "metric": "revenue", "fiscal_years": [2024, 2025], "question": "why did revenue change?", "limit": 5}`

Answer: 'Revenue increased from $637,959 million (FY2024) to $716,924 million (FY2025), a rise of $78,965 million or approximately 12.4%. However, the provided evidence does not contain any management discussion or breakdown (e.g., by segment, product line, price/volume, or geography) explaining the drivers of this change. The accompanying passages only detail operating expenses (cost of sales, fulfillment, technology and infrastructure, sales and marketing, G&A), not revenue composition or causes. Therefore, the reason for the revenue change cannot be determined from the evidence supplied.'

Abstained: True | Limitations: No MD&A passage explaining revenue drivers was included; the passages provided (6896, 7183, 7018, 6883, 7169) cover operating expenses and tax contingencies only. The magnitude of the change is supported by the metric evidence, but its cause is not.

Cited evidence:
- `metric:1018724:revenue:2024-01-01:2024-12-31` revenue (2024-01-01 to 2024-12-31) (full cited text):

637959000000.0

- `metric:1018724:revenue:2025-01-01:2025-12-31` revenue (2025-01-01 to 2025-12-31) (full cited text):

716924000000.0

- `passage:6896` Item 7. | Management’s Discussion and Analysis of Financial Condition and Results of Operations (full cited text):

| Year Ended December 31, ; | 2024 | | 2025 ; Operating Expenses: | | | ; Cost of sales | $ | 326,288 | | | $ | 356,414 | ; Fulfillment | 98,505 | | | 109,074 | ; Technology and infrastructure | 88,544 | | | 108,521 | ; Sales and marketing | 43,907 | | | 47,129 | ; General and administrative | 11,359 | | | 11,172 | ; Other operating expense (income), net | 763 | | | 4,639 | ; Total operating expenses | $ | 569,366 | | | $ | 636,949 | ; Year-over-year Percentage Growth (Decline): | | | ; Cost of sales | 7 | % | | 9 | % ; Fulfillment | 9 | | | 11 | ; Technology and infrastructure | 3 | | | 23 | ; Sales and marketing | (1) | | | 7 | ; General and administrative | (4) | | | (2) | ; Other operating expense (income), net | (1) | | | 508 | ; Percent of Net Sales: | | | ; Cost of sales | 51.1 | % | | 49.7 | % ; Fulfillment | 15.4 | | | 15.2 | ; Technology and infrastructure | 13.9 | | | 15.1 | ; Sales and marketing | 6.9 | | | 6.6 | ; General and administrative | 1.8 | | | 1.6 | ; Other operating expense (income), net | 0.1 | | | 0.6 | Cost of Sales Cost of sales primarily consists of the purchase price of consumer products, inbound and outbound shipping costs, including costs related to sortation and delivery centers and where we are the transportation service provider, and digital media content costs where we record revenue gross, including video and music.


## Q22 (GOOGL)

Question: `{"company": "GOOGL", "metric": "revenue", "fiscal_years": [2024, 2025], "question": "why did revenue change?", "limit": 5}`

Answer: 'The reported revenue figures show revenue increased from $350,018 million (FY2024) to $402,836 million (FY2025), a change of $52.8 billion (+15.1%). However, the provided evidence does not explain the drivers of this FY2024-to-FY2025 change. The only MD&A passages supplied are from the prior-year 10-K (accession 0001652044-25-000014) and describe 2023-to-2024 movements (e.g., revenue by type for 2023 vs. 2024, cost of revenues, segment operating income), not 2024-to-2025. Accordingly, I can confirm the magnitude of the change but must abstain on the reason for it.'

Abstained: True | Limitations: No MD&A or disaggregated revenue passage covering FY2025 versus FY2024 was included; all narrative evidence relates to the FY2024 10-K discussion of 2023-to-2024 results. Segment/category drivers, FX effects, or volume/price explanations for the 2024-2025 change cannot be assessed from the given evidence.

Cited evidence:
- `metric:1652044:revenue:2024-01-01:2024-12-31` revenue (2024-01-01 to 2024-12-31) (full cited text):

350018000000.0

- `metric:1652044:revenue:2025-01-01:2025-12-31` revenue (2025-01-01 to 2025-12-31) (full cited text):

402836000000.0

- `passage:6291` ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS (full cited text):

• Employee severance and related charges for the year ended December 31, 2024 were $1.0 billion, a decrease of $1.1 billion as compared to the year ended December 31, 2023. Office space charges, including accelerated rent and accelerated depreciation, for the year ended December 31, 2024 were $796 million, a decrease of $1.3 billion as compared to the year ended December 31, 2023. Substantially all of these charges were included in Alphabet-level activities. • Operating cash flow was $125.3 billion for the year ended December 31, 2024. • Capital expenditures, which primarily reflected investments in technical infrastructure, were $52.5 billion for the year ended December 31, 2024. • As of December 31, 2024, we had 183,323 employees. 35. Table of Contents | Alphabet Inc. Financial Results Revenues The following table presents revenues by type (in millions): | | | Year Ended December 31, ; | | | 2023 | | 2024 ; Google Search & other | | | $ | 175,033 | | | $ | 198,084 | ; YouTube ads | | | 31,510 | | | 36,147 | ; Google Network | | | 31,312 | | | 30,359 | ; Google advertising | | | 237,855 | | | 264,590 | ; Google subscriptions, platforms, and devices | | | 34,688 | | | 40,340 | ; Google Services total | | | 272,543 | | | 304,930 | ; Google Cloud | | | 33,088 | | | 43,229 | ; Other Bets | | | 1,527 | | | 1,648 | ; Hedging gains (losses) | | | 236 | | | 211 | ; Total revenues | | | $ | 307,394 | | | $ | 350,018 | Google Services Google advertising revenues Google Search & other


## Q25 (AAPL)

Question: `{"company": "AAPL", "metric": "revenue", "fiscal_years": [2010]}`

Answer: 'No supporting evidence was found in the published gold datasets.'

Abstained: True | Limitations: No calculations or passages matched the request.

Cited evidence:

## Judgements

```json
{
  "Q01": null,
  "Q02": null,
  "Q03": null,
  "Q04": null,
  "Q05": null,
  "Q06": null,
  "Q07": null,
  "Q08": null,
  "Q09": null,
  "Q10": null,
  "Q11": null,
  "Q12": null,
  "Q13": null,
  "Q14": null,
  "Q15": null,
  "Q16": null,
  "Q17": null,
  "Q18": null,
  "Q19": null,
  "Q20": null,
  "Q21": null,
  "Q22": null,
  "Q25": null
}
```
