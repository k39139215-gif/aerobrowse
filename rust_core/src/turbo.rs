use std::time::Instant;
use crate::pruner::{PrunedResult, SemanticPruner};

pub struct TurboResponse {
    pub pruned: PrunedResult,
    pub elapsed_ms: u128,
    pub needs_fidelity: bool,
}

pub struct TurboEngine {
    client: reqwest::Client,
}

impl TurboEngine {
    pub fn new() -> Self {
        let client = reqwest::Client::builder()
            .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            .timeout(std::time::Duration::from_secs(12))
            .build()
            .unwrap_or_default();

        Self { client }
    }

    pub async fn fetch(&self, url: &str) -> Result<TurboResponse, String> {
        let start = Instant::now();
        let resp = self
            .client
            .get(url)
            .send()
            .await
            .map_err(|e| format!("Request failed: {}", e))?;

        let html = resp
            .text()
            .await
            .map_err(|e| format!("Failed to read body: {}", e))?;

        let elapsed_ms = start.elapsed().as_millis();
        let pruned = SemanticPruner::prune(&html, url);

        let needs_fidelity = Self::detect_spa_fallback(&html, &pruned.markdown);

        Ok(TurboResponse {
            pruned,
            elapsed_ms,
            needs_fidelity,
        })
    }

    fn detect_spa_fallback(html: &str, pruned_markdown: &str) -> bool {
        let lower = html.to_lowercase();
        if lower.contains("you need to enable javascript") || lower.contains("please enable js") {
            return true;
        }
        // If content is very sparse (< 250 chars) while page contains SPA app roots or JS render containers
        if pruned_markdown.trim().len() < 250
            && (lower.contains("id=\"root\"")
                || lower.contains("id=\"app\"")
                || lower.contains("__next")
                || (lower.contains("<script") && lower.contains("class=\"quote")))
        {
            return true;
        }
        false
    }
}
