# Add Additional Web Scrapers for Pakistani Business Intelligence

The goal is to enrich the Awaz pipeline with highly localized, scraped data from two major Pakistani business websites. This data will be fetched in parallel alongside the existing sources, giving the Analyst Agent more context to detect contradictions.

## Proposed Changes

We will add two new dedicated scraper modules that do not require API keys, using `BeautifulSoup` to scrape live data.

### [NEW] sources/business_recorder_scraper.py
Scrapes the top headlines from the Business Recorder website (brecorder.com) to get the latest localized financial and business news.
- Fetches the homepage or markets page.
- Extracts the top 5-10 article headlines and summaries.
- Includes a fallback mechanism if the site blocks the request.

### [NEW] sources/psx_scraper.py
Scrapes the Pakistan Stock Exchange Data Portal (dps.psx.com.pk) to get the live status of the KSE-100 index.
- Extracts the current index value, net change, and percentage change.
- Includes a fallback mechanism.

### [MODIFY] agents/ingestion_agent.py
- Update `_fetch_all_sources` to include the two new scrapers in the parallel `ThreadPoolExecutor`.
- Map the results to `business_recorder_data` and `psx_data` in the payload sent to the Analyst Agent.

### [MODIFY] agents/analyst_agent.py
- Update the contradiction detection to also analyze the `business_recorder` and `psx` data.
- Add them to the `SOURCE_WEIGHTS` (e.g., giving them a 0.15 weight each and adjusting the others).
- Include their summaries in the final plain-language explanation prompt.

## User Review Required
> [!IMPORTANT]
> Scraping websites directly can sometimes be fragile if their HTML structure changes. I will implement robust error handling and fallbacks so the pipeline never crashes if a scrape fails. Do you approve adding Business Recorder and PSX to the pipeline? Are there any other specific websites (like Dawn or Mettis Global) you want instead?
