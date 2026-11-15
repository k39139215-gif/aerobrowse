use std::time::Instant;
use crate::pruner::{PrunedResult, SemanticPruner};

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

    pub async fn fetch(&self, url: &str) -> Result<(PrunedResult, u128), String> {
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

        Ok((pruned, elapsed_ms))
    }
}
